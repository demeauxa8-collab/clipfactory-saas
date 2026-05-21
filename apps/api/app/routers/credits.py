from fastapi import APIRouter, Depends

from ..auth import CurrentUser, current_user
from ..db import get_pool
from ..schemas import CreditBalance
from ..services import credits as credits_svc

router = APIRouter(tags=["credits"])


@router.get("/credits", response_model=CreditBalance)
async def credits_balance(user: CurrentUser = Depends(current_user)) -> CreditBalance:
    pool = get_pool()
    async with pool.acquire() as conn:
        balance = await credits_svc.get_balance(conn, user.user_id)
    return CreditBalance(balance=balance)
