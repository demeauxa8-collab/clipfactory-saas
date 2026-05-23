import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth import CurrentUser, current_user
from ..db import get_pool
from ..rate_limit import LIMIT_JOBS_CREATE, limiter
from ..schemas import ClipOut, ClipSegment, JobCreate, JobOut, JobWithClips
from ..services import jobs as jobs_svc

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _parse_segments(value: Any) -> list[ClipSegment]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    out: list[ClipSegment] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        try:
            out.append(
                ClipSegment(
                    role=str(raw.get("role", "single")),  # type: ignore[arg-type]
                    start=float(raw.get("start", 0.0)),
                    end=float(raw.get("end", 0.0)),
                    transcript_excerpt=str(raw.get("transcript_excerpt", "")),
                )
            )
        except (TypeError, ValueError):
            continue
    return out


def _json_object(value: Any) -> dict[str, int] | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if not isinstance(value, dict):
        return None
    out: dict[str, int] = {}
    for key, raw in value.items():
        try:
            out[str(key)] = int(raw)
        except (TypeError, ValueError):
            continue
    return out


@router.get("", response_model=list[JobOut])
async def list_jobs(user: CurrentUser = Depends(current_user)) -> list[JobOut]:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await jobs_svc.list_jobs(conn, user.user_id)


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(LIMIT_JOBS_CREATE)
async def create_job(
    request: Request, payload: JobCreate, user: CurrentUser = Depends(current_user)
) -> JobOut:
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            return await jobs_svc.create_job(conn, user_id=user.user_id, payload=payload)
        except jobs_svc.JobError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": exc.code, "message": exc.message},
            ) from exc


@router.get("/{job_id}", response_model=JobWithClips)
async def get_job(job_id: str, user: CurrentUser = Depends(current_user)) -> JobWithClips:
    pool = get_pool()
    async with pool.acquire() as conn:
        job = await jobs_svc.get_job(conn, user.user_id, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")

        clip_rows = await conn.fetch(
            """
            select id, job_id, idx, title, hook_text, rationale,
                   visual_summary, transcript_excerpt,
                   start_seconds, end_seconds, duration_seconds,
                   rendered_duration_seconds, segments,
                   score_total, score_breakdown, width, height
              from clips
             where job_id = $1 and user_id = $2
             order by idx asc
            """,
            job_id,
            user.user_id,
        )

    clips = [
        ClipOut(
            id=str(r["id"]),
            job_id=str(r["job_id"]),
            idx=int(r["idx"]),
            title=r["title"],
            hook_text=r["hook_text"],
            rationale=r["rationale"],
            visual_summary=r["visual_summary"],
            transcript_excerpt=r["transcript_excerpt"],
            start_seconds=float(r["start_seconds"]),
            end_seconds=float(r["end_seconds"]),
            duration_seconds=float(r["duration_seconds"]),
            rendered_duration_seconds=(
                float(r["rendered_duration_seconds"])
                if r["rendered_duration_seconds"] is not None
                else None
            ),
            segments=_parse_segments(r["segments"]),
            score_total=r["score_total"],
            score_breakdown=_json_object(r["score_breakdown"]),
            width=int(r["width"]),
            height=int(r["height"]),
        )
        for r in clip_rows
    ]
    return JobWithClips(job=job, clips=clips)
