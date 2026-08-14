from __future__ import annotations

import asyncpg
import structlog

from ..schemas import JobCreate, JobOut
from . import campaigns as campaigns_svc
from . import credits as credits_svc
from . import entitlements
from . import queue as queue_svc

log = structlog.get_logger()


class JobError(Exception):
    """Domain error used to short-circuit job creation with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def _jobs_created(conn: asyncpg.Connection, user_id: str) -> int:
    """Lifetime job count, including failed ones.

    Failed jobs are refunded in credits but still count here: retrying a broken
    URL forever must not become a way to farm a free trial.
    """
    row = await conn.fetchrow(
        "select count(*)::int as n from jobs where user_id = $1",
        user_id,
    )
    return int(row["n"]) if row else 0


async def _concurrent_jobs(conn: asyncpg.Connection, user_id: str) -> int:
    row = await conn.fetchrow(
        """
        select count(*)::int as n
          from jobs
         where user_id = $1
           and status in ('queued', 'downloading', 'transcribing', 'analyzing', 'rendering')
        """,
        user_id,
    )
    return int(row["n"]) if row else 0


def _row_to_job_out(row: asyncpg.Record) -> JobOut:
    return JobOut(
        id=str(row["id"]),
        campaign_id=str(row["campaign_id"]) if row["campaign_id"] else None,
        source_url=row["source_url"],
        target_clip_count=row["target_clip_count"],
        status=row["status"],
        current_step=row["current_step"],
        duration_seconds=row["duration_seconds"],
        credits_estimated=row["credits_estimated"],
        credits_charged=row["credits_charged"],
        error_code=row["error_code"],
        error_message=row["error_message"],
        failed_step=row["failed_step"],
        retry_count=int(row["retry_count"] or 0),
        transcription_cost_cents=row["transcription_cost_cents"],
        analysis_tokens=row["analysis_tokens"],
        vision_frames_count=row["vision_frames_count"],
        render_seconds=row["render_seconds"],
        storage_bytes=int(row["storage_bytes"]) if row["storage_bytes"] is not None else None,
        total_cost_estimate_cents=row["total_cost_estimate_cents"],
        queued_at=row["queued_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


_JOB_COLUMNS = """
    id, user_id, campaign_id, source_url, target_clip_count, status, current_step,
    duration_seconds, credits_estimated, credits_charged,
    error_code, error_message, failed_step, retry_count,
    transcription_cost_cents, analysis_tokens, vision_frames_count,
    render_seconds, storage_bytes, total_cost_estimate_cents,
    queued_at, started_at, finished_at
"""


async def create_job(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    payload: JobCreate,
) -> JobOut:
    ent = await entitlements.load(conn, user_id)
    if ent is None:
        raise JobError("no_active_subscription", "You need an active subscription to create a job.")

    if payload.target_clip_count > ent.max_clips_per_video:
        raise JobError(
            "clip_count_exceeded",
            f"Your plan allows up to {ent.max_clips_per_video} clips per video.",
        )

    max_total = ent.max_jobs_total
    if max_total is not None and await _jobs_created(conn, user_id) >= max_total:
        raise JobError(
            "trial_used",
            "Your free video has already been used. Pick a plan to keep clipping.",
        )

    campaign = await campaigns_svc.get_campaign(
        conn, user_id=user_id, campaign_id=payload.campaign_id
    )
    if campaign is None:
        raise JobError("campaign_not_found", "Campaign not found or not owned by you.")

    if await _concurrent_jobs(conn, user_id) >= ent.max_concurrent_jobs:
        raise JobError(
            "concurrent_jobs_exceeded",
            "You already have a job running. Wait for it to finish before starting another.",
        )

    balance = await credits_svc.get_balance(conn, user_id)
    if balance <= 0:
        if ent.is_trial:
            raise JobError(
                "trial_used",
                "Your free trial credits are spent. Pick a plan to keep clipping.",
            )
        raise JobError("insufficient_credits", "You have no credits left for this billing period.")

    # V1: we don't probe the URL before queueing. Charge the cheapest plausible
    # bucket (1 credit) up front; the worker debits the real duration after probe.
    estimated = 1

    async with conn.transaction():
        row = await conn.fetchrow(
            f"""
            insert into jobs
              (user_id, campaign_id, source_url, target_clip_count,
               status, current_step, credits_estimated)
            values ($1, $2, $3, $4, 'queued', 'queued', $5)
            returning {_JOB_COLUMNS}
            """,
            user_id,
            payload.campaign_id,
            str(payload.source_url),
            payload.target_clip_count,
            estimated,
        )

    await queue_svc.enqueue_job(str(row["id"]))
    return _row_to_job_out(row)


async def list_jobs(conn: asyncpg.Connection, user_id: str, limit: int = 50) -> list[JobOut]:
    rows = await conn.fetch(
        f"""
        select {_JOB_COLUMNS}
          from jobs
         where user_id = $1
         order by queued_at desc
         limit $2
        """,
        user_id,
        limit,
    )
    return [_row_to_job_out(r) for r in rows]


async def get_job(conn: asyncpg.Connection, user_id: str, job_id: str) -> JobOut | None:
    row = await conn.fetchrow(
        f"""
        select {_JOB_COLUMNS}
          from jobs
         where id = $1 and user_id = $2
        """,
        job_id,
        user_id,
    )
    if row is None:
        return None
    return _row_to_job_out(row)
