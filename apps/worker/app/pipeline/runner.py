"""Story-first pipeline runner.

Routing:
  duration < STORY_PIPELINE_THRESHOLD_SECONDS  →  simple pipeline
  duration ≥ STORY_PIPELINE_THRESHOLD_SECONDS  →  story-first pipeline

Both paths produce the same output shape: a list of MontageCandidate, each with
one or more segments. The render and persistence stages don't care which path
ran.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import structlog

from ..models import JobContext, MontageCandidate, StoryArc, Transcript, is_long_video
from ..providers import (
    AnthropicProvider,
    LLMProvider,
    OpenRouterProvider,
    ProviderError,
)
from ..settings import get_settings
from ..storage import upload_file
from .analyze import select_simple_segments
from .boundaries import snap_arc_segments
from .captions import write_ass_for_montage
from .ffmpeg import (
    FFmpegError,
    probe_duration_seconds,
    render_montage_clip,
    validate_rendered_clip,
    yt_dlp_download,
)
from .score import rank_and_pick, score_arc
from .story_arcs import select_story_arcs
from .transcribe import transcribe, transcript_to_timestamped_lines
from .verify import verify_arcs
from .video_map import build_video_map
from .vision import deep_vision_for_arc

log = structlog.get_logger()

ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "m.youtube.com",
    "vimeo.com",
}

# Deep vision happens on this many top arcs only (cost control).
TOP_ARCS_FOR_DEEP_VISION = 5


# =============================================================
# Domain failure
# =============================================================


class PipelineFailure(RuntimeError):
    def __init__(self, code: str, step: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.step = step
        self.message = message


# =============================================================
# Helpers
# =============================================================


import ipaddress
import socket

import httpx

_REDIRECT_MAX_HOPS = 4
_REDIRECT_TIMEOUT = 5.0


def _host_in_whitelist(hostname: str | None) -> bool:
    return bool(hostname) and hostname.lower() in ALLOWED_HOSTS


def _host_resolves_to_private_ip(hostname: str) -> bool:
    """Defence against DNS rebinding / private IP injection. Resolves every A/AAAA
    record and rejects RFC1918, link-local, loopback, and cloud metadata ranges."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        # If resolution fails, let yt-dlp surface the real network error later.
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr.split("%", 1)[0])  # strip scope id (IPv6)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            return True
        # AWS metadata 169.254.169.254, GCP metadata 169.254.169.254, OCI 169.254.169.254
        if str(ip) == "169.254.169.254":
            return True
    return False


async def _validate_url(url: str) -> None:
    try:
        parsed = urlparse(url)
    except Exception as exc:  # noqa: BLE001
        raise PipelineFailure("invalid_url", "validate_url", "URL parse failed") from exc
    if parsed.scheme not in {"http", "https"}:
        raise PipelineFailure("invalid_url", "validate_url", "URL must be http or https")
    if not _host_in_whitelist(parsed.hostname):
        raise PipelineFailure("invalid_url", "validate_url", "URL host not allowed in V1")
    if _host_resolves_to_private_ip(parsed.hostname or ""):
        raise PipelineFailure(
            "invalid_url", "validate_url", "URL host resolves to a non-public IP"
        )

    # Follow redirects manually, verifying each hop's host stays in the whitelist.
    # This blocks open-redirect-based SSRF (attacker submits youtu.be/X that 302s
    # to http://169.254.169.254/...).
    current_url = url
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=_REDIRECT_TIMEOUT,
            headers={"User-Agent": "ClipFactoryURLCheck/1.0"},
        ) as client:
            for _ in range(_REDIRECT_MAX_HOPS):
                try:
                    resp = await client.head(current_url)
                except httpx.HTTPError:
                    # Some hosts (YouTube notably) reject HEAD — fall back to GET
                    # with a 1-byte range so we don't pull the body.
                    resp = await client.get(
                        current_url, headers={"Range": "bytes=0-0"}
                    )
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        break
                    next_url = httpx.URL(current_url).join(location)
                    if next_url.scheme not in ("http", "https"):
                        raise PipelineFailure(
                            "invalid_url",
                            "validate_url",
                            "Redirect target uses a non-HTTP scheme",
                        )
                    if not _host_in_whitelist(next_url.host):
                        raise PipelineFailure(
                            "invalid_url",
                            "validate_url",
                            f"Redirect target host '{next_url.host}' is not in the whitelist",
                        )
                    if _host_resolves_to_private_ip(next_url.host):
                        raise PipelineFailure(
                            "invalid_url",
                            "validate_url",
                            "Redirect target resolves to a non-public IP",
                        )
                    current_url = str(next_url)
                    continue
                break
            else:
                raise PipelineFailure(
                    "invalid_url",
                    "validate_url",
                    f"Too many redirects (>{_REDIRECT_MAX_HOPS})",
                )
    except PipelineFailure:
        raise
    except httpx.HTTPError as exc:
        log.warning("validate_url.precheck_failed", url=url, err=str(exc))
        # Let yt-dlp handle the actual download error — we don't fail just because
        # the HEAD probe is flaky.


async def _set_status(
    conn: asyncpg.Connection,
    job_id: str,
    status: str,
    *,
    current_step: str | None = None,
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


async def _settle_credits(
    conn: asyncpg.Connection,
    *,
    job_id: str,
    user_id: str,
    minutes: int,
    estimated: int,
) -> int:
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
            -delta,
            job_id,
            "refund overestimated credits",
        )
    return target_debit


def _provider_pair() -> tuple[LLMProvider, LLMProvider | None]:
    settings = get_settings()
    primary: LLMProvider = OpenRouterProvider() if settings.openrouter_api_key else AnthropicProvider()
    fallback: LLMProvider | None = None
    if settings.enable_fallback and settings.anthropic_api_key and primary.name != "anthropic":
        fallback = AnthropicProvider()
    return primary, fallback


async def _call_with_fallback(
    primary: LLMProvider,
    fallback: LLMProvider | None,
    primary_model: str,
    fallback_model: str,
    coroutine_factory,
    *,
    label: str,
) -> tuple[LLMProvider, object]:
    """Run `coroutine_factory(provider, model)`, fall back on ProviderError.

    Returns (provider_used, result). `coroutine_factory` is called with the
    provider and the model name so the caller can produce the right awaitable.
    """
    try:
        result = await coroutine_factory(primary, primary_model)
        return primary, result
    except ProviderError as exc:
        log.warning("provider.primary_failed", step=label, kind=exc.kind, err=str(exc))
        if fallback is None:
            raise
    try:
        result = await coroutine_factory(fallback, fallback_model)
        log.info("provider.fallback_used", step=label)
        return fallback, result
    except ProviderError as exc:
        log.error("provider.fallback_failed", step=label, kind=exc.kind, err=str(exc))
        raise


def _segments_to_jsonb(candidate: MontageCandidate) -> str:
    return json.dumps(
        [
            {
                "role": s.role,
                "start": round(s.start, 3),
                "end": round(s.end, 3),
                "transcript_excerpt": s.transcript_excerpt,
                "why": s.why,
            }
            for s in candidate.segments
        ]
    )


# =============================================================
# Main entry
# =============================================================


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

    primary, fallback = _provider_pair()
    ctx.primary_provider = primary.name

    try:
        # Step 1 — validate
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "downloading", current_step="validate_url")
        await _validate_url(ctx.source_url)

        # Step 2 — download
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "downloading", current_step="download")
        try:
            ctx.source_path = await yt_dlp_download(ctx.source_url, workdir)
        except FFmpegError as exc:
            raise PipelineFailure("download_failed", "download", str(exc)) from exc

        # Step 3 — probe
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "downloading", current_step="probe")
        try:
            dur = await probe_duration_seconds(ctx.source_path)
            ctx.duration_seconds = round(dur)
        except FFmpegError as exc:
            raise PipelineFailure("probe_failed", "probe", str(exc)) from exc

        # Step 4 — plan check + credit check
        if ctx.duration_seconds and ctx.duration_seconds > max_minutes * 60:
            raise PipelineFailure(
                "video_too_long",
                "check_plan_max",
                f"Video is {ctx.duration_seconds}s, plan max is {max_minutes * 60}s.",
            )
        minutes = max(1, math.ceil((ctx.duration_seconds or 0) / 60))
        async with pool.acquire() as conn:
            balance = await _get_credit_balance(conn, user_id)
        if balance < minutes:
            raise PipelineFailure(
                "insufficient_credits",
                "check_credits",
                f"Video needs {minutes} credits, current balance is {balance}.",
            )

        # Step 5 — initial debit
        async with pool.acquire() as conn:
            async with conn.transaction():
                await _initial_debit(conn, job_id=job_id, user_id=user_id, estimated=estimated_credits)

        # Step 6 — upload source (best-effort)
        try:
            ctx.source_r2_key = f"sources/{user_id}/{job_id}.mp4"
            ctx.storage_bytes += upload_file(ctx.source_path, ctx.source_r2_key)
        except Exception as exc:  # noqa: BLE001
            log_ctx.warning("pipeline.source_upload_failed", err=str(exc))
            ctx.source_r2_key = None

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

        # Step 8-12 — select arcs (story or simple)
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "analyzing", current_step="select_arcs")
        story_mode = is_long_video(ctx.duration_seconds, settings.story_pipeline_threshold_seconds)
        if story_mode:
            arcs = await _run_story_path(ctx=ctx, primary=primary, fallback=fallback, pool=pool)
        else:
            arcs = await _run_simple_path(ctx=ctx, primary=primary, fallback=fallback, pool=pool)

        if not arcs:
            raise PipelineFailure(
                "no_clips_selected", "select_arcs", "No usable arc passed verification."
            )

        # Step 13-14 — deep vision on top arcs (cap)
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "analyzing", current_step="deep_vision")
        top_for_vision = sorted(arcs, key=lambda a: a.estimated_retention, reverse=True)[
            :TOP_ARCS_FOR_DEEP_VISION
        ]
        candidates: list[MontageCandidate] = []
        for idx, arc in enumerate(top_for_vision):
            try:
                _, (per_seg, frames, tokens) = await _call_with_fallback(
                    primary, fallback,
                    settings.primary_vision_deep_model,
                    settings.fallback_vision_model,
                    lambda p, m: deep_vision_for_arc(
                        provider=p,
                        model=m,
                        source_path=ctx.source_path or "",
                        arc=arc,
                        workdir=workdir,
                        arc_idx=idx,
                    ),
                    label="deep_vision",
                )
            except ProviderError:
                per_seg, frames, tokens = [], 0, 0
            ctx.vision_frames_count += frames
            ctx.analysis_tokens += tokens
            ctx.deep_vision_cost_cents += int(
                round(frames * settings.cost_vision_deep_cents_per_frame)
            )
            candidate = score_arc(arc=arc, per_segment_vision=per_seg, campaign=ctx.campaign)
            candidate.vision_per_segment = per_seg
            candidates.append(candidate)

        # Pick top N
        ctx.montage_candidates = rank_and_pick(candidates, ctx.target_clip_count)

        # Step 15-16 — render + captions + upload + save
        async with pool.acquire() as conn:
            await _set_status(conn, job_id, "rendering", current_step="render")

        render_start = time.monotonic()
        clips_saved = 0
        for candidate_idx, cand in enumerate(ctx.montage_candidates):
            out_clip = os.path.join(workdir, f"clip_{candidate_idx}.mp4")
            ass_path = os.path.join(workdir, f"clip_{candidate_idx}.ass")
            has_captions = write_ass_for_montage(
                transcript=ctx.transcript,
                segments=cand.segments,
                out_path=ass_path,
                audio_crossfade_seconds=0.15 if len(cand.segments) > 1 else 0.0,
            )
            seg_tuples = [(s.start, s.end) for s in cand.segments]

            try:
                rendered_dur = await render_montage_clip(
                    source=ctx.source_path or "",
                    segments=seg_tuples,
                    out_path=out_clip,
                    workdir=os.path.join(workdir, f"render_{candidate_idx}"),
                    subtitles_path=ass_path if has_captions else None,
                )
            except FFmpegError:
                # Retry without subtitles
                rendered_dur = await render_montage_clip(
                    source=ctx.source_path or "",
                    segments=seg_tuples,
                    out_path=out_clip,
                    workdir=os.path.join(workdir, f"render_{candidate_idx}"),
                    subtitles_path=None,
                )

            qc = await validate_rendered_clip(
                path=out_clip,
                expected_duration_seconds=rendered_dur,
            )
            if not qc.ok:
                log_ctx.warning(
                    "pipeline.render_qc_failed",
                    candidate_idx=candidate_idx,
                    problems=qc.problems,
                    duration=qc.duration_seconds,
                    expected=qc.expected_duration_seconds,
                    mean_volume_db=qc.mean_volume_db,
                    mid_frame_luma=qc.mid_frame_luma,
                )
                continue

            clip_idx = clips_saved
            clip_key = f"clips/{user_id}/{job_id}/{clip_idx}.mp4"
            bytes_uploaded = upload_file(out_clip, clip_key)
            ctx.storage_bytes += bytes_uploaded

            first_seg = cand.segments[0]
            last_seg = cand.segments[-1]

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    insert into clips
                      (job_id, user_id, idx, title, hook_text, rationale,
                       visual_summary, transcript_excerpt,
                       start_seconds, end_seconds, score_total, score_breakdown,
                       segments, rendered_duration_seconds,
                       r2_key, bytes, width, height)
                    values
                      ($1, $2, $3, $4, $5, $6,
                       $7, $8,
                       $9, $10, $11, $12::jsonb,
                       $13::jsonb, $14,
                       $15, $16, 1080, 1920)
                    """,
                    job_id,
                    user_id,
                    clip_idx,
                    cand.title,
                    cand.hook,
                    cand.rationale,
                    cand.visual_summary,
                    cand.transcript_excerpt,
                    first_seg.start,
                    last_seg.end,
                    cand.score_total,
                    json.dumps(cand.score_breakdown),
                    _segments_to_jsonb(cand),
                    round(rendered_dur, 3),
                    clip_key,
                    bytes_uploaded,
                )
            clips_saved += 1

        ctx.render_seconds = int(time.monotonic() - render_start)
        if clips_saved == 0:
            raise PipelineFailure(
                "render_qc_failed",
                "render_qc",
                "No rendered clip passed quality control.",
            )

        # Step 17 — finalize
        async with pool.acquire() as conn:
            async with conn.transaction():
                final_debit = await _settle_credits(
                    conn,
                    job_id=job_id,
                    user_id=user_id,
                    minutes=minutes,
                    estimated=estimated_credits,
                )
                total_cost_cents = (
                    (ctx.transcription_cost_cents or 0)
                    + (ctx.video_map_cost_cents or 0)
                    + (ctx.deep_vision_cost_cents or 0)
                    + int(
                        round(
                            (ctx.analysis_tokens / 1000.0)
                            * settings.cost_text_cents_per_1k_tokens
                        )
                    )
                )
                await conn.execute(
                    """
                    update jobs
                       set status = 'completed',
                           current_step = 'completed',
                           credits_charged = $1,
                           transcription_cost_cents = $2,
                           video_map_cost_cents = $3,
                           deep_vision_cost_cents = $4,
                           analysis_tokens = $5,
                           vision_frames_count = $6,
                           render_seconds = $7,
                           storage_bytes = $8,
                           total_cost_estimate_cents = $9,
                           primary_provider = $10,
                           fallback_used = $11,
                           video_map = $12::jsonb,
                           finished_at = now(),
                           updated_at = now()
                     where id = $13
                    """,
                    int(final_debit),
                    int(ctx.transcription_cost_cents or 0),
                    int(ctx.video_map_cost_cents or 0),
                    int(ctx.deep_vision_cost_cents or 0),
                    int(ctx.analysis_tokens or 0),
                    int(ctx.vision_frames_count or 0),
                    int(ctx.render_seconds or 0),
                    int(ctx.storage_bytes or 0),
                    int(total_cost_cents),
                    ctx.primary_provider,
                    ctx.fallback_used,
                    _video_map_json(ctx),
                    job_id,
                )
        log_ctx.info(
            "pipeline.completed",
            clips=clips_saved,
            mode="story" if story_mode else "simple",
            cost_cents=int(total_cost_cents),
        )

    except PipelineFailure as exc:
        log_ctx.error("pipeline.failed", step=exc.step, code=exc.code, err=exc.message)
        await _mark_failed(
            pool,
            job_id=job_id,
            user_id=user_id,
            code=exc.code,
            step=exc.step,
            message=exc.message,
            refund_credits=estimated_credits,
        )
    except Exception as exc:  # noqa: BLE001
        log_ctx.exception("pipeline.crashed", err=str(exc))
        await _mark_failed(
            pool,
            job_id=job_id,
            user_id=user_id,
            code="internal_error",
            step="unknown",
            message=str(exc)[:500],
            refund_credits=estimated_credits,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# =============================================================
# Path implementations
# =============================================================


async def _run_story_path(
    *,
    ctx: JobContext,
    primary: LLMProvider,
    fallback: LLMProvider | None,
    pool: asyncpg.Pool,
) -> list[StoryArc]:
    settings = get_settings()
    assert ctx.transcript is not None and ctx.source_path is not None

    # 8. Video map
    async with pool.acquire() as conn:
        await _set_status(conn, ctx.job_id, "analyzing", current_step="video_map")
    used_provider, (video_map, frames_used, tokens) = await _call_with_fallback(
        primary, fallback,
        settings.vision_cheap_model,
        settings.fallback_vision_model,
        lambda p, m: build_video_map(
            provider=p,
            model=m,
            source_path=ctx.source_path or "",
            duration_seconds=ctx.duration_seconds or 0,
            transcript=ctx.transcript,
            workdir=os.path.join(ctx.workdir, "map_frames"),
        ),
        label="video_map",
    )
    ctx.video_map = video_map
    ctx.vision_frames_count += frames_used
    ctx.analysis_tokens += tokens
    ctx.video_map_cost_cents += int(round(frames_used * settings.cost_vision_cheap_cents_per_frame))
    if used_provider.name != primary.name:
        ctx.fallback_used = True

    # 9. Story arcs (text)
    async with pool.acquire() as conn:
        await _set_status(conn, ctx.job_id, "analyzing", current_step="story_arcs")
    lines = transcript_to_timestamped_lines(ctx.transcript)
    used_provider, (arcs, tokens2) = await _call_with_fallback(
        primary, fallback,
        settings.primary_text_model,
        settings.fallback_text_model,
        lambda p, m: select_story_arcs(
            provider=p,
            model=m,
            transcript_lines=lines,
            video_map=video_map,
            campaign=ctx.campaign,
            target_clip_count=ctx.target_clip_count,
        ),
        label="story_arcs",
    )
    ctx.analysis_tokens += tokens2
    if used_provider.name != primary.name:
        ctx.fallback_used = True

    # 10. Verify (anti-hallucination)
    async with pool.acquire() as conn:
        await _set_status(conn, ctx.job_id, "analyzing", current_step="verify_arcs")
    kept, dropped = verify_arcs(ctx.transcript, arcs)
    log.info("pipeline.verify", kept=len(kept), dropped=dropped)
    async with pool.acquire() as conn:
        await _set_status(conn, ctx.job_id, "analyzing", current_step="snap_segments")
    snapped, snap_report = snap_arc_segments(kept, ctx.transcript.words)
    log.info(
        "pipeline.snap_segments",
        arcs=snap_report.arcs_seen,
        segments=snap_report.segments_seen,
        changed=snap_report.segments_changed,
    )
    ctx.story_arcs = snapped
    return snapped


async def _run_simple_path(
    *,
    ctx: JobContext,
    primary: LLMProvider,
    fallback: LLMProvider | None,
    pool: asyncpg.Pool,
) -> list[StoryArc]:
    settings = get_settings()
    assert ctx.transcript is not None
    lines = transcript_to_timestamped_lines(ctx.transcript)
    used_provider, (arcs, tokens) = await _call_with_fallback(
        primary, fallback,
        settings.primary_text_model,
        settings.fallback_text_model,
        lambda p, m: select_simple_segments(
            provider=p,
            model=m,
            transcript_lines=lines,
            campaign=ctx.campaign,
            target_clip_count=ctx.target_clip_count,
        ),
        label="simple_segments",
    )
    ctx.analysis_tokens += tokens
    if used_provider.name != primary.name:
        ctx.fallback_used = True

    # Verify (same path as story)
    kept, dropped = verify_arcs(ctx.transcript, arcs)
    log.info("pipeline.verify_simple", kept=len(kept), dropped=dropped)
    async with pool.acquire() as conn:
        await _set_status(conn, ctx.job_id, "analyzing", current_step="snap_segments")
    snapped, snap_report = snap_arc_segments(kept, ctx.transcript.words)
    log.info(
        "pipeline.snap_segments_simple",
        arcs=snap_report.arcs_seen,
        segments=snap_report.segments_seen,
        changed=snap_report.segments_changed,
    )
    ctx.story_arcs = snapped
    return snapped


def _video_map_json(ctx: JobContext) -> str | None:
    if ctx.video_map is None:
        return None
    return json.dumps(
        {
            "summary": ctx.video_map.summary,
            "events": [
                {
                    "id": e.id,
                    "start": round(e.start, 2),
                    "end": round(e.end, 2),
                    "decor": e.decor,
                    "people": e.people,
                    "objects": e.objects,
                    "action": e.action,
                    "transcript_summary": e.transcript_summary,
                    "visual_importance": e.visual_importance,
                    "narrative_role": e.narrative_role,
                }
                for e in ctx.video_map.events
            ],
        }
    )
