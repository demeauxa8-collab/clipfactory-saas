"""Endpoints publics non authentifiés (stats agrégées pour la landing)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..db import get_pool

router = APIRouter(prefix="/public", tags=["public"])


class PublicStats(BaseModel):
    clips_generated: int
    hours_processed: int
    creators_active: int


@router.get("/stats", response_model=PublicStats)
async def public_stats() -> PublicStats:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select clips_generated, hours_processed, creators_active from public_stats"
        )
    return PublicStats(
        clips_generated=int(row["clips_generated"] or 0) if row else 0,
        hours_processed=int(row["hours_processed"] or 0) if row else 0,
        creators_active=int(row["creators_active"] or 0) if row else 0,
    )
