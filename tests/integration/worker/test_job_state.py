import asyncio
from uuid import uuid4

import pytest
from app.pipeline.job_state import (
    JobStateError,
    claim_job,
    confirm_reservation,
    fail_job,
    reserve_credits,
)
from app.pipeline.runner import _set_status, run_job

pytestmark = pytest.mark.asyncio


async def new_job(pool, account):
    async with pool.acquire() as conn:
        return str(
            await conn.fetchval(
                """insert into jobs (user_id, campaign_id, source_url, target_clip_count,
                   credits_estimated) values ($1, $2, 'https://youtu.be/test', 3, 1) returning id""",
                *account,
            )
        )


async def claim(pool, job_id):
    async with pool.acquire() as conn:
        return await claim_job(conn, job_id)


async def reserve(pool, job_id, user_id, token, minutes):
    async with pool.acquire() as conn:
        return await reserve_credits(
            conn, job_id=job_id, user_id=str(user_id), token=token, minutes=minutes
        )


async def fail(pool, job_id, user_id, token):
    async with pool.acquire() as conn:
        return await fail_job(
            conn,
            job_id=job_id,
            user_id=str(user_id),
            token=token,
            code="test_failure",
            step="render",
            message="Injected failure",
        )


async def balance(pool, user_id):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "select sum(delta) from credit_ledger where user_id = $1", user_id
        )


async def test_simultaneous_deliveries_have_one_owner(db_pool, account):
    job_id = await new_job(db_pool, account)
    rows = await asyncio.gather(*(claim(db_pool, job_id) for _ in range(5)))
    assert sum(row is not None for row in rows) == 1
    assert await balance(db_pool, account[0]) == 10


async def test_refund_before_debit_and_duplicate_failure_never_mint_credits(
    db_pool, account
):
    job_id = await new_job(db_pool, account)
    row = await claim(db_pool, job_id)
    results = await asyncio.gather(
        *(fail(db_pool, job_id, account[0], row["worker_id"]) for _ in range(3))
    )
    assert results.count(True) == 1
    assert await balance(db_pool, account[0]) == 10
    async with db_pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "select count(*) from credit_ledger where job_id = $1", job_id
            )
            == 0
        )


async def test_full_duration_is_reserved_once_and_refunded_once(db_pool, account):
    job_id = await new_job(db_pool, account)
    token = (await claim(db_pool, job_id))["worker_id"]
    await asyncio.gather(
        *(reserve(db_pool, job_id, account[0], token, 7) for _ in range(3))
    )
    assert await balance(db_pool, account[0]) == 3
    await asyncio.gather(*(fail(db_pool, job_id, account[0], token) for _ in range(3)))
    assert await balance(db_pool, account[0]) == 10
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "select delta from credit_ledger where job_id = $1 order by id", job_id
        )
        assert [r["delta"] for r in rows] == [-7, 7]


async def test_concurrent_jobs_cannot_overdraw_one_balance(db_pool, account):
    jobs = [await new_job(db_pool, account) for _ in range(2)]
    rows = [await claim(db_pool, job_id) for job_id in jobs]
    results = await asyncio.gather(
        *(
            reserve(db_pool, job_id, account[0], row["worker_id"], 7)
            for job_id, row in zip(jobs, rows, strict=True)
        ),
        return_exceptions=True,
    )
    assert sum(value == 7 for value in results) == 1
    assert sum(isinstance(value, JobStateError) for value in results) == 1
    assert await balance(db_pool, account[0]) == 3


async def test_stale_attempt_cannot_write_or_refund(db_pool, account):
    job_id = await new_job(db_pool, account)
    token = (await claim(db_pool, job_id))["worker_id"]
    await reserve(db_pool, job_id, account[0], token, 4)
    assert not await fail(db_pool, job_id, account[0], str(uuid4()))
    async with db_pool.acquire() as conn:
        with pytest.raises(JobStateError):
            await _set_status(conn, job_id, "rendering", token="old_attempt")
    assert await balance(db_pool, account[0]) == 6


async def test_terminal_job_is_not_rerun_or_refunded(db_pool, account):
    job_id = await new_job(db_pool, account)
    token = (await claim(db_pool, job_id))["worker_id"]
    await reserve(db_pool, job_id, account[0], token, 4)
    async with db_pool.acquire() as conn, conn.transaction():
        assert (
            await confirm_reservation(
                conn, job_id=job_id, user_id=str(account[0]), token=token, minutes=4
            )
            == 4
        )
        await conn.execute(
            "update jobs set status = 'completed' where id = $1", job_id
        )
    await run_job(db_pool, job_id)
    assert not await fail(db_pool, job_id, account[0], token)
    assert await balance(db_pool, account[0]) == 6
