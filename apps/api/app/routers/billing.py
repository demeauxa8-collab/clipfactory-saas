from __future__ import annotations

import stripe
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth import CurrentUser, current_user
from ..db import get_pool
from ..rate_limit import LIMIT_BILLING_CHECKOUT, LIMIT_STRIPE_WEBHOOK, limiter
from ..schemas import CheckoutCreate, CheckoutResponse, PortalResponse
from ..services import analytics
from ..services import billing as billing_svc

log = structlog.get_logger()

router = APIRouter(tags=["billing"])


@router.post("/billing/checkout", response_model=CheckoutResponse)
@limiter.limit(LIMIT_BILLING_CHECKOUT)
async def create_checkout(
    request: Request,
    payload: CheckoutCreate,
    user: CurrentUser = Depends(current_user),
) -> CheckoutResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            url = await billing_svc.create_checkout_url(
                conn,
                user_id=user.user_id,
                email=user.email,
                plan_code=payload.plan_code,
            )
        except billing_svc.BillingError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except stripe.StripeError as exc:
            log.error("billing.checkout.provider_failed", err=str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "billing_provider_unavailable",
                    "message": "Billing is unavailable.",
                },
            ) from exc
    analytics.fire_and_forget(
        analytics.track_with_pool(
            pool,
            event_name="checkout_started",
            source="api",
            user_id=user.user_id,
            properties={"plan_code": payload.plan_code},
        )
    )
    return CheckoutResponse(checkout_url=url)


@router.post("/billing/portal", response_model=PortalResponse)
@limiter.limit(LIMIT_BILLING_CHECKOUT)
async def create_portal(
    request: Request, user: CurrentUser = Depends(current_user)
) -> PortalResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            url = await billing_svc.create_portal_url(conn, user_id=user.user_id)
        except billing_svc.BillingError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except stripe.StripeError as exc:
            log.error("billing.portal.provider_failed", err=str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "billing_provider_unavailable",
                    "message": "Billing is unavailable.",
                },
            ) from exc
    return PortalResponse(portal_url=url)


@router.post("/stripe/webhook", include_in_schema=False)
@limiter.limit(LIMIT_STRIPE_WEBHOOK)
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
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                is_new = await billing_svc.record_event(conn, event)
                if not is_new:
                    return {"received": True}
                await billing_svc.handle_event(conn, event)
                await conn.execute(
                    "update stripe_events set processed_at = now() where event_id = $1",
                    event["id"],
                )
    except Exception as exc:
        # Roll back both the event marker and any partial grant. Stripe can retry.
        log.error("stripe.webhook.handler_failed", event=event["type"], err=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "billing_webhook_retry", "message": "Webhook processing will retry."},
        ) from exc

    analytics.fire_and_forget(
        analytics.track_with_pool(
            get_pool(),
            event_name="billing_webhook",
            source="api",
            properties={"type": event["type"]},
        )
    )
    return {"received": True}
