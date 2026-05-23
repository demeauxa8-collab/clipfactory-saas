from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import HTTPException, Request, status

from .settings import get_settings


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    email: str | None
    role: str


def _extract_bearer(request: Request) -> str:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_authorization",
        )
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_authorization",
        )
    return parts[1]


def verify_supabase_jwt(token: str) -> CurrentUser:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token_expired"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token"
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token_subject",
        )

    return CurrentUser(
        user_id=user_id,
        email=payload.get("email"),
        role=payload.get("role", "authenticated"),
    )


async def current_user(request: Request) -> CurrentUser:
    token = _extract_bearer(request)
    user = verify_supabase_jwt(token)
    # Stash for rate limiter key_func (per-user limits instead of per-IP).
    request.state.user_id = user.user_id
    return user


async def admin_required(request: Request) -> CurrentUser:
    """Same as current_user but also requires profiles.is_admin = true."""
    from .db import get_pool

    user = await current_user(request)
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select is_admin from profiles where user_id = $1",
            user.user_id,
        )
    if row is None or not row["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_required")
    return user
