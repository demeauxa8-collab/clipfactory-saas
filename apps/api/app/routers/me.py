from fastapi import APIRouter, Depends

from ..auth import CurrentUser, current_user
from ..db import get_pool
from ..schemas import CreditBalance, MeResponse, Profile, SubscriptionInfo
from ..services import credits as credits_svc

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser = Depends(current_user)) -> MeResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        profile_row = await conn.fetchrow(
            "select user_id, email, full_name from profiles where user_id = $1",
            user.user_id,
        )
        if profile_row is None:
            # Trigger should have created it. If we are here, create defensively.
            profile_row = await conn.fetchrow(
                """
                insert into profiles (user_id, email)
                values ($1, $2)
                on conflict (user_id) do update set email = excluded.email
                returning user_id, email, full_name
                """,
                user.user_id,
                user.email or "",
            )

        sub_row = await conn.fetchrow(
            """
            select plan_code, status, current_period_end, cancel_at_period_end
              from subscriptions
             where user_id = $1 and status in ('trialing', 'active', 'past_due')
             order by current_period_end desc nulls last
             limit 1
            """,
            user.user_id,
        )

        balance = await credits_svc.get_balance(conn, user.user_id)

    return MeResponse(
        profile=Profile(
            user_id=str(profile_row["user_id"]),
            email=profile_row["email"],
            full_name=profile_row["full_name"],
        ),
        subscription=(
            SubscriptionInfo(
                plan_code=sub_row["plan_code"],
                status=sub_row["status"],
                current_period_end=sub_row["current_period_end"],
                cancel_at_period_end=sub_row["cancel_at_period_end"],
            )
            if sub_row
            else None
        ),
        credits=CreditBalance(balance=balance),
    )
