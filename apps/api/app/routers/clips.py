from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import CurrentUser, current_user
from ..db import get_pool
from ..schemas import ClipDownloadUrl
from ..services import analytics, entitlements
from ..services.storage import presigned_get_url

router = APIRouter(prefix="/clips", tags=["clips"])

DOWNLOAD_TTL_SECONDS = 600


@router.get("/{clip_id}/download", response_model=ClipDownloadUrl)
async def download_clip(clip_id: str, user: CurrentUser = Depends(current_user)) -> ClipDownloadUrl:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select r2_key, idx from clips where id = $1 and user_id = $2",
            clip_id,
            user.user_id,
        )
        ent = await entitlements.load(conn, user.user_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="clip_not_found")

    # The paywall lands here: on a trial the clips exist and are rendered, but
    # the files need a plan. Enforced server-side — the UI lock is only a hint.
    if ent is not None and ent.clip_is_locked(int(row["idx"])):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="upgrade_required")

    url = presigned_get_url(row["r2_key"], expires_in=DOWNLOAD_TTL_SECONDS)
    analytics.fire_and_forget(
        analytics.track_with_pool(
            get_pool(),
            event_name="clip_download",
            source="api",
            user_id=user.user_id,
            properties={"clip_id": clip_id},
        )
    )
    return ClipDownloadUrl(url=url, expires_in_seconds=DOWNLOAD_TTL_SECONDS)
