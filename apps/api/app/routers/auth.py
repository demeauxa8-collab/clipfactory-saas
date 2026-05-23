from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from ..rate_limit import LIMIT_TURNSTILE_VERIFY, limiter
from ..schemas import TurnstileVerifyRequest, TurnstileVerifyResponse
from ..settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _remote_ip(request: Request) -> str | None:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else None


@router.post("/turnstile/verify", response_model=TurnstileVerifyResponse)
@limiter.limit(LIMIT_TURNSTILE_VERIFY)
async def verify_turnstile(
    request: Request,
    payload: TurnstileVerifyRequest,
) -> TurnstileVerifyResponse:
    settings = get_settings()
    if not settings.turnstile_secret_key or settings.turnstile_secret_key == "TODO":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "turnstile_not_configured",
                "message": "Turnstile secret key is not configured.",
            },
        )

    form = {
        "secret": settings.turnstile_secret_key,
        "response": payload.token,
    }
    remote_ip = _remote_ip(request)
    if remote_ip:
        form["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(TURNSTILE_VERIFY_URL, data=form)
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "turnstile_unavailable", "message": str(exc)},
        ) from exc

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "turnstile_failed",
                "message": "Turnstile verification failed.",
                "errors": result.get("error-codes", []),
            },
        )

    return TurnstileVerifyResponse(ok=True)
