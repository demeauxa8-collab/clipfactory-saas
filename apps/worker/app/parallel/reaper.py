"""Stale-job reaper. Fixes audit #2 (orphaned jobs).

A job whose worker died (OOM, SIGKILL, crash) stops heartbeating. After
JOB_LEASE_SECONDS the reaper either:
  - requeues it (attempts < MAX_ATTEMPTS) so another worker re-runs it, or
  - fails it + refunds credits (attempts exhausted).

Without this, a killed worker leaves the job stuck in a running status forever:
credits never refunded, and (with max_concurrent_jobs=1) the user is blocked for
good. See docs/architecture/parallel-workers.md §5.
"""

from __future__ import annotations

import asyncio

import asyncpg
import structlog

log = structlog.get_logger()

# Refund mirrors runner._mark_failed: give back the credits debited up front.
_REQUEUE_SQL = """
update jobs
   set status       = 'queued',
       worker_id    = null,
       current_step = 'requeued_after_stall',
       heartbeat_at = null,
       claimed_at   = null,
       updated_at   = now()
 where status in ('downloading', 'transcribing', 'analyzing', 'rendering')
   and heartbeat_at < now() - make_interval(secs => $1)
   and attempts < $2
returning id;
"""

_FAIL_SELECT_SQL = """
select id, user_id, credits_estimated
  from jobs
 where status in ('downloading', 'transcribing', 'analyzing', 'rendering')
   and heartbeat_at < now() - make_interval(secs => $1)
   and attempts >= $2
 for update skip locked
"""


async def sweep_once(
    pool: asyncpg.Pool, *, lease_seconds: int, max_attempts: int
) -> tuple[int, int]:
    """One reaper pass. Returns (requeued, failed)."""
    async with pool.acquire() as conn:
        # 1) Requeue jobs that still have attempts left.
        requeued_rows = await conn.fetch(_REQUEUE_SQL, lease_seconds, max_attempts)
        requeued = len(requeued_rows)

        # 2) Fail + refund the ones that exhausted their attempts.
        failed = 0
        async with conn.transaction():
            stale = await conn.fetch(_FAIL_SELECT_SQL, lease_seconds, max_attempts)
            for job in stale:
                await conn.execute(
                    """
                    update jobs
                       set status = 'failed', error_code = 'worker_stalled',
                           error_message = 'No heartbeat; reaped after max attempts.',
                           failed_step = 'reaper', finished_at = now(), updated_at = now()
                     where id = $1
                    """,
                    job["id"],
                )
                refund = int(job["credits_estimated"] or 0)
                if refund > 0:
                    await conn.execute(
                        """
                        insert into credit_ledger (user_id, delta, reason, job_id, note)
                        values ($1, $2, 'job_refund', $3, 'reaper refund (worker stalled)')
                        """,
                        job["user_id"], refund, job["id"],
                    )
                failed += 1

    if requeued or failed:
        log.info("reaper.sweep", requeued=requeued, failed=failed)
    return requeued, failed


async def run_reaper(
    pool: asyncpg.Pool,
    stop: asyncio.Event,
    *,
    interval_seconds: int,
    lease_seconds: int,
    max_attempts: int,
) -> None:
    """Loop until `stop` is set. Safe to run in every worker (idempotent)."""
    log.info("reaper.start", interval=interval_seconds, lease=lease_seconds)
    while not stop.is_set():
        try:
            await sweep_once(pool, lease_seconds=lease_seconds, max_attempts=max_attempts)
        except Exception as exc:  # noqa: BLE001 — reaper must never die
            log.warning("reaper.error", err=str(exc))
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
