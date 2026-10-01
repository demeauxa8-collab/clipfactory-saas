import asyncio
from unittest.mock import AsyncMock

import pytest
from app.schemas import JobCreate
from app.services import jobs

pytestmark = pytest.mark.asyncio


def payload(account):
    return JobCreate(
        campaign_id=str(account[1]),
        source_url="https://youtu.be/test",
        target_clip_count=3,
    )


async def create(pool, account):
    async with pool.acquire() as conn:
        return await jobs.create_job(
            conn, user_id=str(account[0]), payload=payload(account)
        )


async def test_simultaneous_admissions_respect_concurrency_limit(
    db_pool, account, monkeypatch
):
    enqueue = AsyncMock()
    monkeypatch.setattr(jobs.queue_svc, "enqueue_job", enqueue)
    results = await asyncio.gather(
        *(create(db_pool, account) for _ in range(3)), return_exceptions=True
    )
    assert sum(isinstance(result, jobs.JobError) for result in results) == 2
    assert all(
        result.code == "concurrent_jobs_exceeded"
        for result in results
        if isinstance(result, jobs.JobError)
    )
    enqueue.assert_awaited_once()


async def test_enqueue_failure_does_not_leave_queued_job_or_debit(
    db_pool, account, monkeypatch
):
    monkeypatch.setattr(
        jobs.queue_svc, "enqueue_job", AsyncMock(side_effect=OSError("offline"))
    )
    with pytest.raises(jobs.JobError, match="could not be queued"):
        await create(db_pool, account)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "select status, error_code, credits_charged from jobs"
        )
        assert dict(row) == {
            "status": "failed",
            "error_code": "queue_unavailable",
            "credits_charged": 0,
        }
        assert await conn.fetchval("select sum(delta) from credit_ledger") == 10


async def test_lost_queue_response_does_not_fail_already_claimed_job(
    db_pool, account, monkeypatch
):
    async def enqueue_then_timeout(job_id):
        async with db_pool.acquire() as conn:
            await conn.execute(
                "update jobs set status = 'downloading' where id = $1", job_id
            )
        raise TimeoutError("response lost after push")

    monkeypatch.setattr(jobs.queue_svc, "enqueue_job", enqueue_then_timeout)
    job = await create(db_pool, account)
    assert job.status == "downloading"
