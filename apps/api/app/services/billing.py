from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import asyncpg
import stripe
import structlog

from ..settings import get_settings
from . import credits as credits_svc

log = structlog.get_logger()


def _ensure_stripe_configured() -> None:
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key
    stripe.api_version = "2025-04-30.basil"


async def _get_or_create_customer(
    conn: asyncpg.Connection, *, user_id: str, email: str | None
) -> str:
    """Ensures the user has a Stripe customer id; returns it."""
    _ensure_stripe_configured()
    row = await conn.fetchrow(
        "select stripe_customer_id from profiles where user_id = $1",
        user_id,
    )
    if row and row["stripe_customer_id"]:
        return str(row["stripe_customer_id"])

    customer = stripe.Customer.create(
        email=email,
        metadata={"user_id": user_id},
    )
    await conn.execute(
        "update profiles set stripe_customer_id = $1 where user_id = $2",
        customer.id,
        user_id,
    )
    return str(customer.id)


async def create_checkout_url(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    email: str | None,
    plan_code: str,
) -> str:
    settings = get_settings()
    _ensure_stripe_configured()
    plan_row = await conn.fetchrow(
        "select stripe_price_id from plan_definitions where code = $1 and is_active",
        plan_code,
    )
    if plan_row is None or not plan_row["stripe_price_id"]:
        # In dev we fall back to the env-configured starter price id.
        price_id = settings.stripe_starter_price_id
    else:
        price_id = plan_row["stripe_price_id"]

    customer_id = await _get_or_create_customer(conn, user_id=user_id, email=email)

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.web_base_url}/app/billing?status=success",
        cancel_url=f"{settings.web_base_url}/app/billing?status=cancel",
        allow_promotion_codes=True,
        client_reference_id=user_id,
        subscription_data={"metadata": {"user_id": user_id, "plan_code": plan_code}},
    )
    return str(session.url)


def construct_event(payload: bytes, signature: str) -> stripe.Event:
    settings = get_settings()
    _ensure_stripe_configured()
    return stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)


# ---------------- Webhook handlers ----------------


async def record_event(conn: asyncpg.Connection, event: stripe.Event) -> bool:
    """Returns True if we should process the event (new), False if duplicate."""
    payload_json = json.dumps(event.to_dict(), default=str)
    inserted = await conn.fetchrow(
        """
        insert into stripe_events (event_id, event_type, payload)
        values ($1, $2, $3::jsonb)
        on conflict (event_id) do nothing
        returning event_id
        """,
        event["id"],
        event["type"],
        payload_json,
    )
    return inserted is not None


async def _resolve_user_id(
    conn: asyncpg.Connection, *, customer_id: str | None, metadata_user_id: str | None
) -> str | None:
    if metadata_user_id:
        return metadata_user_id
    if customer_id:
        row = await conn.fetchrow(
            "select user_id from profiles where stripe_customer_id = $1",
            customer_id,
        )
        if row:
            return str(row["user_id"])
    return None


async def _upsert_subscription(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    plan_code: str,
    sub: dict[str, Any],
) -> str:
    period_start = (
        datetime.fromtimestamp(sub["current_period_start"], tz=UTC)
        if sub.get("current_period_start")
        else None
    )
    period_end = (
        datetime.fromtimestamp(sub["current_period_end"], tz=UTC)
        if sub.get("current_period_end")
        else None
    )
    canceled_at = (
        datetime.fromtimestamp(sub["canceled_at"], tz=UTC) if sub.get("canceled_at") else None
    )
    row = await conn.fetchrow(
        """
        insert into subscriptions
          (user_id, plan_code, stripe_subscription_id, stripe_customer_id, status,
           current_period_start, current_period_end, cancel_at_period_end, canceled_at)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        on conflict (stripe_subscription_id) do update
          set status = excluded.status,
              current_period_start = excluded.current_period_start,
              current_period_end = excluded.current_period_end,
              cancel_at_period_end = excluded.cancel_at_period_end,
              canceled_at = excluded.canceled_at,
              plan_code = excluded.plan_code,
              updated_at = now()
        returning id
        """,
        user_id,
        plan_code,
        sub["id"],
        sub.get("customer"),
        sub["status"],
        period_start,
        period_end,
        bool(sub.get("cancel_at_period_end", False)),
        canceled_at,
    )
    return str(row["id"])


async def _grant_credits_once(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    subscription_id: str,
    credits: int,
    reason: str,
    note: str,
) -> None:
    # Idempotency on credit grants: we rely on stripe_events being recorded before
    # this handler runs. If the event was already processed (record_event returned
    # False), the caller will skip this function entirely.
    await credits_svc.insert_ledger(
        conn,
        user_id=user_id,
        delta=credits,
        reason=reason,
        subscription_id=subscription_id,
        note=note,
    )


async def handle_event(conn: asyncpg.Connection, event: stripe.Event) -> None:
    etype = event["type"]
    obj = event["data"]["object"]

    if etype == "checkout.session.completed":
        await _handle_checkout_completed(conn, obj)
    elif etype == "invoice.paid":
        await _handle_invoice_paid(conn, obj)
    elif etype in {"customer.subscription.updated", "customer.subscription.created"}:
        await _handle_subscription_updated(conn, obj)
    elif etype == "customer.subscription.deleted":
        await _handle_subscription_deleted(conn, obj)


async def _handle_checkout_completed(conn: asyncpg.Connection, session: dict[str, Any]) -> None:
    user_id = session.get("client_reference_id") or await _resolve_user_id(
        conn,
        customer_id=session.get("customer"),
        metadata_user_id=(session.get("metadata") or {}).get("user_id"),
    )
    sub_id = session.get("subscription")
    if not user_id or not sub_id:
        log.warning("billing.checkout.skip", reason="missing_user_or_subscription")
        return

    _ensure_stripe_configured()
    sub = stripe.Subscription.retrieve(sub_id)
    plan_code = (sub.get("metadata") or {}).get("plan_code", "starter")
    plan_row = await conn.fetchrow(
        "select credits_per_period from plan_definitions where code = $1",
        plan_code,
    )
    credits = int(plan_row["credits_per_period"]) if plan_row else 300

    db_sub_id = await _upsert_subscription(
        conn, user_id=user_id, plan_code=plan_code, sub=sub.to_dict()
    )
    await _grant_credits_once(
        conn,
        user_id=user_id,
        subscription_id=db_sub_id,
        credits=credits,
        reason="subscription_grant",
        note=f"Stripe checkout {session.get('id', '')}",
    )


async def _handle_invoice_paid(conn: asyncpg.Connection, invoice: dict[str, Any]) -> None:
    if invoice.get("billing_reason") != "subscription_cycle":
        return  # initial invoice is handled by checkout.completed
    sub_id = invoice.get("subscription")
    if not sub_id:
        return

    sub_row = await conn.fetchrow(
        "select id, user_id, plan_code from subscriptions where stripe_subscription_id = $1",
        sub_id,
    )
    if sub_row is None:
        return

    plan_row = await conn.fetchrow(
        "select credits_per_period from plan_definitions where code = $1",
        sub_row["plan_code"],
    )
    credits = int(plan_row["credits_per_period"]) if plan_row else 300
    await _grant_credits_once(
        conn,
        user_id=str(sub_row["user_id"]),
        subscription_id=str(sub_row["id"]),
        credits=credits,
        reason="subscription_renewal",
        note=f"Stripe invoice {invoice.get('id', '')}",
    )


async def _handle_subscription_updated(conn: asyncpg.Connection, sub: dict[str, Any]) -> None:
    user_id = await _resolve_user_id(
        conn,
        customer_id=sub.get("customer"),
        metadata_user_id=(sub.get("metadata") or {}).get("user_id"),
    )
    if not user_id:
        return
    plan_code = (sub.get("metadata") or {}).get("plan_code", "starter")
    await _upsert_subscription(conn, user_id=user_id, plan_code=plan_code, sub=sub)


async def _handle_subscription_deleted(conn: asyncpg.Connection, sub: dict[str, Any]) -> None:
    await conn.execute(
        """
        update subscriptions
           set status = 'canceled', canceled_at = now(), updated_at = now()
         where stripe_subscription_id = $1
        """,
        sub.get("id"),
    )
