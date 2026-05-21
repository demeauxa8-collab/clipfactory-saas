from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import CurrentUser, current_user
from ..db import get_pool
from ..schemas import ClipDownloadUrl
from ..services.storage import presigned_get_url

router = APIRouter(prefix="/clips", tags=["clips"])

DOWNLOAD_TTL_SECONDS = 600


@router.get("/{clip_id}/download", response_model=ClipDownloadUrl)
async def download_clip(
    clip_id: str, user: CurrentUser = Depends(current_user)
) -> ClipDownloadUrl:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select r2_key from clips where id = $1 and user_id = $2",
            clip_id,
            user.user_id,
        )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="clip_not_found")

    url = presigned_get_url(row["r2_key"], expires_in=DOWNLOAD_TTL_SECONDS)
    return ClipDownloadUrl(url=url, expires_in_seconds=DOWNLOAD_TTL_SECONDS)
