"""Atomic job claiming on Postgres (queue = jobs table).

Replaces the Redis BLPOP dispatch. A claim is one transaction that:
  1. takes a global advisory lock so the per-user concurrency count is exact
     (claims take ms, jobs take minutes — serialising claims is free);
  2. picks the oldest `queued` job whose owner is under their plan's
     max_concurrent_jobs;
  3. locks it (FOR UPDATE SKIP LOCKED) and flips it to running, stamping
     worker_id / claimed_at / heartbeat_at / attempts.

See docs/architecture/parallel-workers.md §4.
"""

from __future__ import annotations

import asyncpg
import structlog

log = structlog.get_logger()

# Arbitrary fixed key for the fleet-wide claim lock. If claim throughput ever
# becomes hot (it won't at this scale), shard by hashtext(user_id) instead.
_CLAIM_LOCK_KEY = 816072

# Statuses that count as "a job is actively occupying a slot".
RUNNING_STATUSES = ("downloading", "transcribing", "analyzing", "rendering")

_CLAIM_SQL = """
with claimable as (
  select j.id
    from jobs j
    join subscriptions s on s.user_id = j.user_id and s.status in ('trialing', 'active')
    join plan_definitions p on p.code = s.plan_code
   where j.status = 'queued'
     and (
           select count(*) from jobs r
            where r.user_id = j.user_id
              and r.status in ('downloading', 'transcribing', 'analyzing', 'rendering')
         ) < p.max_concurrent_jobs
   order by j.queued_at
   for update of j skip locked
   limit 1
)
update jobs
   set status       = 'downloading',
       current_step = 'claimed',
       worker_id    = $1,
       claimed_at   = now(),
       heartbeat_at = now(),
       started_at   = coalesce(started_at, now()),
       attempts     = attempts + 1,
       updated_at   = now()
 where id in (select id from claimable)
returning id;
"""


async def claim_next_job(pool: asyncpg.Pool, *, worker_id: str) -> str | None:
    """Atomically claim one queued job. Returns its id, or None if none is claimable."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("select pg_advisory_xact_lock($1)", _CLAIM_LOCK_KEY)
            row = await conn.fetchrow(_CLAIM_SQL, worker_id)
    if row is None:
        return None
    job_id = str(row["id"])
    log.info("claim.acquired", job_id=job_id, worker_id=worker_id)
    return job_id


async def heartbeat(pool: asyncpg.Pool, job_id: str) -> bool:
    """Mark the job alive. Returns False if the job is no longer ours/running
    (e.g. the reaper requeued it) so the caller can abort early."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            update jobs set heartbeat_at = now(), updated_at = now()
             where id = $1
               and status in ('downloading', 'transcribing', 'analyzing', 'rendering')
            returning id
            """,
            job_id,
        )
    return row is not None
