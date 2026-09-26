"""Create and read a sequential series of existing single-source jobs."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import asyncpg

from ..schemas import SeriesCreate, SeriesOut
from . import campaigns as campaigns_svc
from . import credits as credits_svc
from . import jobs as jobs_svc

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def _canonical_video_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname not in YOUTUBE_HOSTS or parsed.username or parsed.password:
        raise jobs_svc.JobError("unsupported_source", "Use YouTube video URLs for every source.")
    path = parsed.path.strip("/").split("/")
    video_id = ""
    if parsed.hostname == "youtu.be" and len(path) == 1:
        video_id = path[0]
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    elif len(path) == 2 and path[0] in {"shorts", "live", "embed"}:
        video_id = path[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise jobs_svc.JobError(
            "unsupported_source",
            "Use links to individual YouTube videos, not channels or playlists.",
        )
    return f"https://www.youtube.com/watch?v={video_id}"


async def create_series(
    conn: asyncpg.Connection, *, user_id: str, payload: SeriesCreate
) -> SeriesOut:
    urls = [_canonical_video_url(str(url)) for url in payload.source_urls]
    if len(set(urls)) != len(urls):
        raise jobs_svc.JobError("duplicate_source", "Each source video must be different.")

    async with conn.transaction():
        # Serialise simultaneous submissions for this account.
        await conn.execute("select pg_advisory_xact_lock(hashtext($1))", user_id)
        sub = await jobs_svc._active_subscription(conn, user_id)
        if sub is None:
            raise jobs_svc.JobError("no_active_subscription", "An active subscription is required.")
        max_sources = int(sub["max_series_sources"])
        if len(urls) > max_sources:
            raise jobs_svc.JobError(
                "series_not_in_plan",
                "Multi-video series are not included in your plan."
                if max_sources == 1
                else f"Your plan allows up to {max_sources} videos per series.",
            )
        if payload.target_clip_count > int(sub["max_clips_per_video"]):
            raise jobs_svc.JobError(
                "clip_count_exceeded",
                f"Your plan allows up to {sub['max_clips_per_video']} clips per video.",
            )
        campaign = await campaigns_svc.get_campaign(
            conn, user_id=user_id, campaign_id=payload.campaign_id
        )
        if campaign is None:
            raise jobs_svc.JobError("campaign_not_found", "Campaign not found or not owned by you.")
        if await jobs_svc._concurrent_jobs(conn, user_id):
            raise jobs_svc.JobError(
                "concurrent_jobs_exceeded",
                "Finish the current job or series before starting another.",
            )
        if await credits_svc.get_balance(conn, user_id) < len(urls):
            raise jobs_svc.JobError(
                "insufficient_credits", "At least one credit per source is required to start."
            )

        series = await conn.fetchrow(
            """
            insert into clip_series (user_id, campaign_id)
            values ($1, $2)
            returning id, campaign_id, created_at
            """,
            user_id,
            payload.campaign_id,
        )
        jobs = []
        for position, url in enumerate(urls):
            row = await conn.fetchrow(
                f"""
                insert into jobs
                  (user_id, campaign_id, series_id, series_position, source_url,
                   target_clip_count, status, current_step, credits_estimated)
                values ($1, $2, $3, $4, $5, $6, 'queued', 'queued', 1)
                returning {jobs_svc._JOB_COLUMNS}
                """,
                user_id,
                payload.campaign_id,
                series["id"],
                position,
                url,
                payload.target_clip_count,
            )
            jobs.append(jobs_svc._row_to_job_out(row))

    return SeriesOut(
        id=str(series["id"]),
        campaign_id=str(series["campaign_id"]),
        created_at=series["created_at"],
        jobs=jobs,
    )


async def get_series(
    conn: asyncpg.Connection, *, user_id: str, series_id: str
) -> SeriesOut | None:
    series = await conn.fetchrow(
        "select id, campaign_id, created_at from clip_series where id = $1 and user_id = $2",
        series_id,
        user_id,
    )
    if series is None:
        return None
    rows = await conn.fetch(
        f"""
        select {jobs_svc._JOB_COLUMNS}
          from jobs
         where series_id = $1 and user_id = $2
         order by series_position
        """,
        series_id,
        user_id,
    )
    return SeriesOut(
        id=str(series["id"]),
        campaign_id=str(series["campaign_id"]),
        created_at=series["created_at"],
        jobs=[jobs_svc._row_to_job_out(row) for row in rows],
    )
