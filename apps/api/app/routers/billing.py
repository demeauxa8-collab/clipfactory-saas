from __future__ import annotations

import stripe
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth import CurrentUser, current_user
from ..db import get_pool
from ..schemas import CheckoutCreate, CheckoutResponse
from ..services import billing as billing_svc

log = structlog.get_logger()

router = APIRouter(tags=["billing"])


@router.post("/billing/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutCreate,
    user: CurrentUser = Depends(current_user),
) -> CheckoutResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        url = await billing_svc.create_checkout_url(
            conn,
            user_id=user.user_id,
            email=user.email,
            plan_code=payload.plan_code,
        )
    return CheckoutResponse(checkout_url=url)


@router.post("/stripe/webhook", include_in_schema=False)
async def stripe_webhook(request: Request) -> dict[str, bool]:
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="missing_stripe_signature"
        )
    payload = await request.body()

    try:
        event = billing_svc.construct_event(payload, signature)
    except (stripe.SignatureVerificationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_signature"
        ) from exc

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            is_new = await billing_svc.record_event(conn, event)
            if not is_new:
                return {"received": True}
            try:
                await billing_svc.handle_event(conn, event)
            except Exception as exc:
                log.error("stripe.webhook.handler_failed", event=event["type"], err=str(exc))
                # Mark error but don't re-raise (we already recorded the event) to
                # avoid Stripe retry storms. Visible via stripe_events.error column.
                await conn.execute(
                    "update stripe_events set error = $1 where event_id = $2",
                    str(exc),
                    event["id"],
                )
                return {"received": True}
            await conn.execute(
                "update stripe_events set processed_at = now() where event_id = $1",
                event["id"],
            )

    return {"received": True}
