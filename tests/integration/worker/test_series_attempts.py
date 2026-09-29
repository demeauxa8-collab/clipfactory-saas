"""Series claims (Postgres, SKIP LOCKED) feed the same fenced attempt model."""

import asyncio

import pytest

from app.pipeline.job_state import claim_job, fail_job, reserve_credits
from app.series_queue import claim_next_series_job

pytestmark = pytest.mark.asyncio


async def new_series(pool, account, count):
    user_id, campaign_id = account
    async with pool.acquire() as conn:
        series_id = await conn.fetchval(
            "insert into clip_series (user_id, campaign_id) values ($1, $2) returning id",
            user_id,
            campaign_id,
        )
        ids = []
        for position in range(count):
            ids.append(
                str(
                    await conn.fetchval(
                        """insert into jobs (user_id, campaign_id, source_url,
                           target_clip_count, credits_estimated, series_id, series_position)
                           values ($1, $2, $3, 3, 1, $4, $5) returning id""",
                        user_id,
                        campaign_id,
                        f"https://youtu.be/source{position:05}",
                        series_id,
                        position,
                    )
                )
            )
    return ids


async def balance(pool, user_id):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "select sum(delta) from credit_ledger where user_id = $1", user_id
        )


async def test_series_preclaim_becomes_one_fenced_attempt_in_order(db_pool, account):
    user_id = account[0]
    first, second = await new_series(db_pool, account, 2)

    assert await claim_next_series_job(db_pool) == first
    # The next source waits for the first one to reach a terminal state.
    assert await claim_next_series_job(db_pool) is None

    async def claim():
        async with db_pool.acquire() as conn:
            return await claim_job(conn, first)

    rows = await asyncio.gather(*(claim() for _ in range(4)))
    owners = [row for row in rows if row is not None]
    assert len(owners) == 1
    token = owners[0]["worker_id"]

    async with db_pool.acquire() as conn:
        await reserve_credits(conn, job_id=first, user_id=str(user_id), token=token, minutes=2)
    assert await balance(db_pool, user_id) == 8

    async with db_pool.acquire() as conn:
        assert await fail_job(
            conn,
            job_id=first,
            user_id=str(user_id),
            token=token,
            code="render_qc_failed",
            step="render_qc",
            message="Injected failure",
        )
        # A second failure report for the same attempt is a no-op.
        assert not await fail_job(
            conn,
            job_id=first,
            user_id=str(user_id),
            token=token,
            code="render_qc_failed",
            step="render_qc",
            message="Injected failure",
        )
    assert await balance(db_pool, user_id) == 10

    # A failed source does not block the rest of the series.
    assert await claim_next_series_job(db_pool) == second
