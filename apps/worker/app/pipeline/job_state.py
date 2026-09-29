"""Atomic job ownership and ledger-backed credit reservation.

Row locks work with transaction-mode connection poolers. A queue delivery can
claim only a queued job; every mutation carries the attempt's fencing token.
There is deliberately no automatic reclaim of an active attempt without a lease.
"""

from __future__ import annotations

import math
from uuid import UUID, uuid4

import asyncpg


class JobStateError(RuntimeError):
    def __init__(self, code: str, message: str, *, step: str = "job_state") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.step = step


def billable_minutes(duration: float, max_minutes: int) -> int:
    if not math.isfinite(duration) or duration <= 0:
        raise JobStateError("probe_failed", "Source duration must be finite and positive.",
                            step="probe")
    if duration > max_minutes * 60:
        raise JobStateError("video_too_long", f"Video exceeds the {max_minutes} minute plan limit.",
                            step="check_plan_max")
    return max(1, math.ceil(duration / 60))


async def claim_job(conn: asyncpg.Connection, job_id: str) -> asyncpg.Record | None:
    """Skip duplicate, terminal and active deliveries before touching any files."""
    parsed_id = UUID(job_id)
    return await conn.fetchrow(
        """
        update jobs set status = 'downloading', current_step = 'validate_url',
               worker_id = $2, started_at = now(), finished_at = null,
               error_code = null, error_message = null, failed_step = null,
               updated_at = now()
         where id = $1 and status = 'queued'
        returning *
        """,
        parsed_id, str(uuid4()),
    )


async def _lock_attempt(conn: asyncpg.Connection, job_id: str, user_id: str, token: str) -> None:
    # All credit writers in the worker and API admissions lock user -> job.
    await conn.fetchrow("select user_id from profiles where user_id = $1 for update", user_id)
    row = await conn.fetchrow(
        """select id from jobs where id = $1 and user_id = $2 and worker_id = $3
           and status in ('downloading', 'transcribing', 'analyzing', 'rendering') for update""",
        job_id, user_id, token,
    )
    if row is None:
        raise JobStateError("job_ownership_lost", "This attempt no longer owns the active job.")


async def _reserved(conn: asyncpg.Connection, job_id: str, user_id: str) -> int:
    return -int(await conn.fetchval(
        """select coalesce(sum(delta), 0) from credit_ledger
           where job_id = $1 and user_id = $2 and reason in ('job_debit', 'job_refund')""",
        job_id, user_id,
    ))


async def reserve_credits(
    conn: asyncpg.Connection, *, job_id: str, user_id: str, token: str, minutes: int,
) -> int:
    """Reserve the measured duration before paid analysis, exactly once."""
    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1:
        raise ValueError("minutes must be a positive integer")
    async with conn.transaction():
        await _lock_attempt(conn, job_id, user_id, token)
        reserved = await _reserved(conn, job_id, user_id)
        if reserved < 0 or reserved > minutes:
            raise JobStateError("credit_ledger_mismatch", "Unexpected reservation for this job.")
        remaining = minutes - reserved
        if not remaining:
            return minutes
        balance = int(await conn.fetchval(
            "select coalesce(sum(delta), 0) from credit_ledger where user_id = $1", user_id,
        ))
        if balance < remaining:
            raise JobStateError(
                "insufficient_credits", f"Video needs {remaining} more credits; balance is {balance}.",
                step="check_credits",
            )
        await conn.execute(
            """insert into credit_ledger (user_id, delta, reason, job_id, note)
               values ($1, $2, 'job_debit', $3, 'reserve measured source duration')""",
            user_id, -remaining, job_id,
        )
    return minutes


async def confirm_reservation(
    conn: asyncpg.Connection, *, job_id: str, user_id: str, token: str, minutes: int,
) -> int:
    """Called inside the same transaction that publishes job completion."""
    if not conn.is_in_transaction():
        raise RuntimeError("finalization requires a transaction")
    await _lock_attempt(conn, job_id, user_id, token)
    if await _reserved(conn, job_id, user_id) != minutes:
        raise JobStateError("credit_ledger_mismatch", "Reserved credits changed before completion.")
    return minutes


async def fail_job(
    conn: asyncpg.Connection, *, job_id: str, user_id: str, token: str,
    code: str, step: str, message: str,
) -> bool:
    """Refund the actual net debit once; never create credits from an estimate."""
    async with conn.transaction():
        try:
            await _lock_attempt(conn, job_id, user_id, token)
        except JobStateError:
            return False
        refund = max(0, await _reserved(conn, job_id, user_id))
        if refund:
            await conn.execute(
                """insert into credit_ledger (user_id, delta, reason, job_id, note)
                   values ($1, $2, 'job_refund', $3, $4)""",
                user_id, refund, job_id, f"refund after {step}: {message[:200]}",
            )
        await conn.execute("delete from clips where job_id = $1 and user_id = $2", job_id, user_id)
        await conn.execute(
            """update jobs set status = 'failed', error_code = $1, error_message = $2,
                   failed_step = $3, credits_charged = 0, finished_at = now(), updated_at = now()
               where id = $4 and worker_id = $5""",
            code, message[:500], step, job_id, token,
        )
    return True
