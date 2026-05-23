from fastapi import APIRouter, Depends, Request, status

from ..auth import CurrentUser, current_user
from ..db import get_pool
from ..rate_limit import LIMIT_CAMPAIGNS_CREATE, limiter
from ..schemas import Campaign, CampaignCreate
from ..services import campaigns as campaigns_svc

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[Campaign])
async def list_campaigns(user: CurrentUser = Depends(current_user)) -> list[Campaign]:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await campaigns_svc.list_campaigns(conn, user.user_id)


@router.post("", response_model=Campaign, status_code=status.HTTP_201_CREATED)
@limiter.limit(LIMIT_CAMPAIGNS_CREATE)
async def create_campaign(
    request: Request,
    payload: CampaignCreate,
    user: CurrentUser = Depends(current_user),
) -> Campaign:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await campaigns_svc.create_campaign(conn, user_id=user.user_id, payload=payload)
