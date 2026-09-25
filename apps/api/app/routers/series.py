from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth import CurrentUser, current_user
from ..db import get_pool
from ..rate_limit import LIMIT_JOBS_CREATE, limiter
from ..schemas import SeriesCreate, SeriesOut
from ..services import analytics
from ..services import jobs as jobs_svc
from ..services import series as series_svc

router = APIRouter(prefix="/series", tags=["series"])


@router.post("", response_model=SeriesOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(LIMIT_JOBS_CREATE)
async def create_series(
    request: Request, payload: SeriesCreate, user: CurrentUser = Depends(current_user)
) -> SeriesOut:
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            series = await series_svc.create_series(conn, user_id=user.user_id, payload=payload)
        except jobs_svc.JobError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
    analytics.fire_and_forget(
        analytics.track_with_pool(
            pool,
            event_name="series_created",
            source="api",
            user_id=user.user_id,
            properties={"series_id": series.id, "source_count": len(series.jobs)},
        )
    )
    return series


@router.get("/{series_id}", response_model=SeriesOut)
async def get_series(series_id: str, user: CurrentUser = Depends(current_user)) -> SeriesOut:
    pool = get_pool()
    async with pool.acquire() as conn:
        series = await series_svc.get_series(conn, user_id=user.user_id, series_id=series_id)
    if series is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="series_not_found")
    return series
