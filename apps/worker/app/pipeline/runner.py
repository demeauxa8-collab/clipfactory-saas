from __future__ import annotations

import math
import os
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import structlog

from ..models import JobContext, ScoredClip
from ..settings import get_settings
from ..storage import upload_file
from .analyze import select_text_candidates
from .captions import write_ass_for_window
from .ffmpeg import (
    FFmpegError,
    probe_duration_seconds,
    render_vertical_clip,
    yt_dlp_download,
)
from .score import rank_and_pick, score_candidate
from .transcribe import transcribe, transcript_to_timestamped_lines
from .vision import analyze_candidate

log = structlog.get_logger()

ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com", "vimeo.com"}


class PipelineFailure(RuntimeError):
    def __init__(self, code: str, step: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.step = step
        self.message = message


# ---------- helpers ----------


def _validate_url(url: str) -> None:
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise PipelineFailure("invalid_url", "validate_url", "URL parse failed") from exc
    if parsed.scheme not in {"http", "https"}:
        raise PipelineFailure("invalid_url", "validate_url", "URL must be http or https")
    if not parsed.hostname or parsed.hostname.lower() not in ALLOWED_HOSTS:
        raise PipelineFailure("invalid_url", "validate_url", "URL host not allowed in V1")


async def _set_status(
    conn: asyncpg.Connection, job_id: str, status: str, *, current_step: str | None = None
) -> None:
    await conn.execute(
        """
        update jobs
           set status = $1,
               current_step = coalesce($3, current_step),
               started_at = case when started_at is null then now() else started_at end,
               updated_at = now()
         where id = $2
        """,
        status,
        job_id,
        current_step,
    )


async def _mark_failed(
    pool: asyncpg.Pool,
    *,
    job_id: str,
    user_id: str,
    code: str,
    step: str,
    message: str,
    refund_credits: int,
) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                update jobs
                   set status = 'failed',
                       error_code = $1,
                       error_message = $2,
                       failed_step = $3,
                       finished_at = now(),
                       updated_at = now()
                 where id = $4
                """,
                code,
                message,
                step,
                job_id,
            )
            if refund_credits > 0:
                await conn.execute(
                    """
                    insert into credit_ledger (user_id, delta, reason, job_id, note)
                    values ($1, $2, 'job_refund', $3, $4)
                    """,
                    user_id,
                    int(refund_credits),
                    job_id,
                    f"refund {step}: {message[:200]}",
                )


async def _debit_credits(
    conn: asyncpg.Connection,
    *,
    job_id: str,
    user_id: str,
    minutes: int,
    estimated: int,
) -> int:
    """Debit the difference between the actual cost (1 credit/min) and the upfront
    estimated debit. Returns the amount finally debited for the job."""
    target_debit = max(1, minutes)
    delta = target_debit - estimated
    if delta > 0:
        await conn.execute(
            """
            insert into credit_ledger (user_id, delta, reason, job_id, note)
            values ($1, $2, 'job_debit', $3, $4)
            """,
            user_id,
            -delta,
            job_id,
            f"debit {delta} extra credits after probe",
        )
    elif delta < 0:
        await conn.execute(
            """
            insert into credit_ledger (user_id, delta, reason, job_id, note)
            values ($1, $2, 'job_refund', $3, $4)
            """,
            user_id,
            -delta,  # negative delta -> positive refund
            job_id,
            "refund overestimated credits",
        )
    return target_debit


async def _get_credit_balance(conn: asyncpg.Connection, user_id: str) -> int:
    row = await conn.fetchrow(
        "select coalesce(sum(delta), 0)::int as balance from credit_ledger where user_id = $1",
        user_id,
    )
    return int(row["balance"]) if row else 0


async def _initial_debit(
    conn: asyncpg.Connection,
    *,
    job_id: str,
    user_id: str,
    estimated: int,
) -> None:
    """Debit the upfront estimate when the job leaves queue.

    The estimated credits were charged conceptually at submit, but we move the
    actual ledger entry here so the worker is the single writer.
    """
    if estimated <= 0:
        return
    await conn.execute(
        """
        insert into credit_ledger (user_id, delta, reason, job_id, note)
        values ($1, $2, 'job_debit', $3, $4)
        """,
        user_id,
        -int(estimated),
        job_id,
        "initial debit on dequeue",
    )


# ---------- main entry ----------


async def run_job(pool: asyncpg.Pool, job_id: str) -> None:
    settings = get_settings()
    log_ctx = log.bind(job_id=job_id)
    log_ctx.info("pipeline.start")

    # --- Load job + campaign + plan
    async with pool.acquire() as conn:
        job_row = await conn.fetchrow(
            """
            select j.id, j.user_id, j.campaign_id, j.source_url, j.target_clip_count,
                   j.credits_estimated, p.max_video_minutes
              from jobs j
              join subscriptions s on s.user_id = j.user_id
                and s.status in ('trialing', 'active')
              join plan_definitions p on p.code = s.plan_code
             where j.id = $1
             limit 1
            """,
            job_id,
        )
        if job_row is None:
            log_ctx.error("pipeline.no_job_or_subscription")
            return

        campaign_row = None
        if job_row["campaign_id"]:
            campaign_row = await conn.fetchrow(
                """
                select name, audience, niche, tone, goal, avoid_topics, example_hooks
                  from campaigns where id = $1
                """,
                job_row["campaign_id"],
            )

    user_id = str(job_row["user_id"])
    estimated_credits = int(job_row["credits_estimated"])
    max_minutes = int(job_row["max_video_minutes"])
    workdir = os.path.join(settings.worker_tmp_dir, job_id)
    Path(workdir).mkdir(parents=True, exist_ok=True)

    ctx = JobContext(
        job_id=job_id,
        user_id=user_id,
        campaign=dict(campaign_row) if campaign_row else {},
        source_url=job_row["source_url"],
        target_clip_count=int(job_row["target_clip_count"]),
        workdir=workdir,
    )
    debited_credits = 0

    try:
        # Step 1 — validate URL
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "downloading", current_step="validate_url")
        _validate_url(ctx.source_url)

        # Step 2 — download
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "downloading", current_step="download")
        try:
            ctx.source_path = await yt_dlp_download(ctx.source_url, workdir)
        except FFmpegError as exc:
            raise PipelineFailure("download_failed", "download", str(exc)) from exc

        # Step 3 — probe duration
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "downloading", current_step="probe")
        try:
            dur = await probe_duration_seconds(ctx.source_path)
            ctx.duration_seconds = round(dur)
        except FFmpegError as exc:
            raise PipelineFailure("probe_failed", "probe", str(exc)) from exc

        # Step 4 — check plan max
        if ctx.duration_seconds and ctx.duration_seconds > max_minutes * 60:
            raise PipelineFailure(
                "video_too_long",
                "check_plan_max",
                f"Video is {ctx.duration_seconds}s, plan max is {max_minutes * 60}s.",
            )

        minutes = max(1, math.ceil((ctx.duration_seconds or 0) / 60))

        # Step 4b — check actual credit balance after probing duration. The API
        # only knows the URL at submit time, so the worker is the first process
        # that can safely enforce "no job if credits are insufficient".
        async with pool.acquire() as conn:
            balance = await _get_credit_balance(conn, user_id)
        if balance < minutes:
            raise PipelineFailure(
                "insufficient_credits",
                "check_credits",
                f"Video needs {minutes} credits, current balance is {balance}.",
            )

        # Step 5 — initial debit (was estimated at submit; move to ledger now)
        async with pool.acquire() as conn:
            async with conn.transaction():
                await _initial_debit(
                    conn, job_id=job_id, user_id=user_id, estimated=estimated_credits
                )
                debited_credits = estimated_credits

        # Step 6 — upload source to R2 (best-effort)
        try:
            ctx.source_r2_key = f"sources/{user_id}/{job_id}.mp4"
            ctx.storage_bytes += upload_file(ctx.source_path, ctx.source_r2_key)
        except Exception as exc:
            log_ctx.warning("pipeline.source_upload_failed", err=str(exc))
            ctx.source_r2_key = None  # not fatal in V1

        async with pool.acquire() as conn:
            await conn.execute(
                "update jobs set source_r2_key = $1, duration_seconds = $2 where id = $3",
                ctx.source_r2_key,
                ctx.duration_seconds,
                job_id,
            )

        # Step 7 — transcribe
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "transcribing", current_step="transcribe")
        ctx.transcript = await transcribe(ctx.source_path)
        ctx.transcription_cost_cents = round(minutes * settings.cost_transcribe_cents_per_min)

        # Step 8 — text candidates
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "analyzing", current_step="text_candidates")
        lines = transcript_to_timestamped_lines(ctx.transcript)
        candidates, tokens = await select_text_candidates(
            transcript_lines=lines,
            campaign=ctx.campaign,
            target_clip_count=ctx.target_clip_count,
        )
        ctx.candidates = candidates
        ctx.analysis_tokens += tokens
        if not candidates:
            raise PipelineFailure(
                "analysis_failed", "text_candidates", "No candidate clips returned."
            )

        # Step 9-11 — vision per candidate + score
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "analyzing", current_step="vision_score")
        scored_list: list[ScoredClip] = []
        for i, cand in enumerate(candidates):
            vision, frames_used, vtokens = await analyze_candidate(
                candidate=cand,
                source_path=ctx.source_path,
                workdir=workdir,
                idx=i,
            )
            ctx.vision_frames_count += frames_used
            ctx.analysis_tokens += vtokens
            scored_list.append(
                score_candidate(candidate=cand, vision=vision, campaign=ctx.campaign)
            )

        # Step 12 — pick top N
        ctx.scored = rank_and_pick(scored_list, ctx.target_clip_count)

        # Step 13-16 — render + captions + upload + save
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "rendering", current_step="render")
        render_start = time.monotonic()
        for idx, sc in enumerate(ctx.scored):
            out_clip = os.path.join(workdir, f"clip_{idx}.mp4")
            ass_path = os.path.join(workdir, f"clip_{idx}.ass")
            has_captions = write_ass_for_window(
                transcript=ctx.transcript,
                window_start=sc.candidate.start,
                window_end=sc.candidate.end,
                out_path=ass_path,
            )
            try:
                await render_vertical_clip(
                    source=ctx.source_path,
                    start=sc.candidate.start,
                    end=sc.candidate.end,
                    out_path=out_clip,
                    subtitles_path=ass_path if has_captions else None,
                )
            except FFmpegError:
                # Retry once without subtitles
                await render_vertical_clip(
                    source=ctx.source_path,
                    start=sc.candidate.start,
                    end=sc.candidate.end,
                    out_path=out_clip,
                    subtitles_path=None,
                )

            clip_key = f"clips/{user_id}/{job_id}/{idx}.mp4"
            bytes_uploaded = upload_file(out_clip, clip_key)
            ctx.storage_bytes += bytes_uploaded

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    insert into clips
                      (job_id, user_id, idx, title, hook_text, rationale,
                       visual_summary, transcript_excerpt,
                       start_seconds, end_seconds, score_total, score_breakdown,
                       r2_key, bytes, width, height)
                    values
                      ($1, $2, $3, $4, $5, $6,
                       $7, $8,
                       $9, $10, $11, $12::jsonb,
                       $13, $14, 1080, 1920)
                    """,
                    job_id,
                    user_id,
                    idx,
                    sc.candidate.suggested_title,
                    sc.candidate.suggested_hook,
                    sc.candidate.why,
                    _vision_summary(sc),
                    sc.candidate.transcript_excerpt,
                    sc.candidate.start,
                    sc.candidate.end,
                    sc.score_total,
                    _json_dumps(sc.score_breakdown),
                    clip_key,
                    bytes_uploaded,
                )

        ctx.render_seconds = int(time.monotonic() - render_start)

        # Step 17 — finalize
        async with pool.acquire() as conn:
            async with conn.transaction():
                final_debit = await _debit_credits(
                    conn,
                    job_id=job_id,
                    user_id=user_id,
                    minutes=minutes,
                    estimated=estimated_credits,
                )
                total_cost_cents = _estimate_total_cost_cents(ctx)
                await conn.execute(
                    """
                    update jobs
                       set status = 'completed',
                           current_step = 'completed',
                           credits_charged = $1,
                           transcription_cost_cents = $2,
                           analysis_tokens = $3,
                           vision_frames_count = $4,
                           render_seconds = $5,
                           storage_bytes = $6,
                           total_cost_estimate_cents = $7,
                           finished_at = now(),
                           updated_at = now()
                     where id = $8
                    """,
                    int(final_debit),
                    int(ctx.transcription_cost_cents or 0),
                    int(ctx.analysis_tokens or 0),
                    int(ctx.vision_frames_count or 0),
                    int(ctx.render_seconds or 0),
                    int(ctx.storage_bytes or 0),
                    int(total_cost_cents),
                    job_id,
                )
        log_ctx.info("pipeline.completed", clips=len(ctx.scored))

    except PipelineFailure as exc:
        log_ctx.error("pipeline.failed", step=exc.step, code=exc.code, err=exc.message)
        # On hard failures: refund the initial debit and the upfront estimate
        await _mark_failed(
            pool,
            job_id=job_id,
            user_id=user_id,
            code=exc.code,
            step=exc.step,
            message=exc.message,
            refund_credits=debited_credits,
        )
    except Exception as exc:
        log_ctx.exception("pipeline.crashed", err=str(exc))
        await _mark_failed(
            pool,
            job_id=job_id,
            user_id=user_id,
            code="internal_error",
            step="unknown",
            message=str(exc)[:500],
            refund_credits=debited_credits,
        )
    finally:
        # Best-effort cleanup of the workdir
        shutil.rmtree(workdir, ignore_errors=True)


# ---------- helpers continued ----------


def _vision_summary(sc: ScoredClip) -> str | None:
    v = sc.vision
    if v is None:
        return "vision unavailable"
    parts = [
        f"decor={v.decor}",
        f"action={v.action}",
        f"energy={v.energy}",
        f"face={'yes' if v.person_visible else 'no'}",
    ]
    if v.proof_objects:
        parts.append("proof=" + ",".join(v.proof_objects[:3]))
    if v.problems:
        parts.append("problems=" + ",".join(v.problems[:3]))
    return "; ".join(parts)


def _estimate_total_cost_cents(ctx: JobContext) -> int:
    s = get_settings()
    vision_cents = round(ctx.vision_frames_count * s.cost_vision_cents_per_frame)
    text_cents = round((ctx.analysis_tokens / 1000.0) * s.cost_text_cents_per_1k_tokens)
    return int(ctx.transcription_cost_cents or 0) + vision_cents + text_cents


def _json_dumps(obj: object) -> str:
    import json

    return json.dumps(obj, default=str)
