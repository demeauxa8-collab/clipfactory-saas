from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import CurrentUser, current_user
from ..db import get_pool
from ..schemas import Feedback, FeedbackCreate

router = APIRouter(tags=["feedback"])


@router.post(
    "/clips/{clip_id}/feedback",
    response_model=Feedback,
    status_code=status.HTTP_201_CREATED,
)
async def post_clip_feedback(
    clip_id: str,
    payload: FeedbackCreate,
    user: CurrentUser = Depends(current_user),
) -> Feedback:
    pool = get_pool()
    async with pool.acquire() as conn:
        clip_row = await conn.fetchrow(
            """
            select c.id, c.user_id, j.campaign_id
              from clips c
              join jobs j on j.id = c.job_id
             where c.id = $1
            """,
            clip_id,
        )
        if clip_row is None or str(clip_row["user_id"]) != user.user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="clip_not_found")

        row = await conn.fetchrow(
            """
            insert into campaign_feedback (clip_id, user_id, campaign_id, kind, note)
            values ($1, $2, $3, $4, $5)
            on conflict (clip_id, user_id)
              do update set kind = excluded.kind, note = excluded.note, created_at = now()
            returning id, clip_id, kind, note, created_at
            """,
            clip_id,
            user.user_id,
            clip_row["campaign_id"],
            payload.kind,
            payload.note,
        )

    return Feedback(
        id=str(row["id"]),
        clip_id=str(row["clip_id"]),
        kind=row["kind"],
        note=row["note"],
        created_at=row["created_at"],
    )
