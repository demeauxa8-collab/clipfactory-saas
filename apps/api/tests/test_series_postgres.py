"""Opt-in integration checks using session-local tables and the deployed schema.

Set CLIPFACTORY_TEST_DATABASE_URL to a migrated PostgreSQL database. All fixture
rows live in temporary tables, inside a rolled-back transaction. No customer
rows are read or changed, and no public sequence is consumed.
"""

from __future__ import annotations

import importlib.util
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from app.schemas import SeriesCreate
from app.services.jobs import JobError
from app.services.series import create_series, get_series

pytestmark = pytest.mark.skipif(
    not os.environ.get("CLIPFACTORY_TEST_DATABASE_URL"),
    reason="CLIPFACTORY_TEST_DATABASE_URL is required for PostgreSQL integration checks",
)

worker_module = Path(__file__).resolve().parents[2] / "worker/app/series_queue.py"
spec = importlib.util.spec_from_file_location("series_queue_integration", worker_module)
assert spec and spec.loader
queue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(queue)


class SingleConnectionPool:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self.conn


@pytest_asyncio.fixture
async def database():
    conn = await asyncpg.connect(
        os.environ["CLIPFACTORY_TEST_DATABASE_URL"], statement_cache_size=0, timeout=10
    )
    transaction = conn.transaction()
    await transaction.start()
    try:
        await conn.execute("set local search_path = pg_temp, public, extensions")
        for table in ("plan_definitions", "campaigns", "subscriptions", "clip_series", "jobs"):
            await conn.execute(
                f"create temporary table {table} (like public.{table} including all) on commit drop"
            )
        await conn.execute("create temporary table credit_ledger (user_id uuid, delta integer)")
        await conn.execute(
            """
            insert into plan_definitions
              (code, name, price_eur_cents, credits_per_period, max_video_minutes,
               max_clips_per_video, max_concurrent_jobs, max_series_sources)
            values ('starter', 'Starter', 2900, 300, 30, 3, 1, 1),
                   ('pro', 'Pro', 7900, 1000, 60, 3, 1, 5)
            """
        )
        user_id, campaign_id = str(uuid4()), str(uuid4())
        await conn.execute(
            "insert into subscriptions (user_id, plan_code, status) values ($1, 'pro', 'active')",
            user_id,
        )
        await conn.execute(
            "insert into campaigns (id, user_id, name) values ($1, $2, 'Integration fixture')",
            campaign_id, user_id,
        )
        await conn.execute("insert into credit_ledger values ($1, 1000)", user_id)
        yield conn, user_id, campaign_id
    finally:
        await transaction.rollback()
        await conn.close()


def payload(campaign_id: str, count: int = 2) -> SeriesCreate:
    return SeriesCreate(
        campaign_id=campaign_id,
        source_urls=[f"https://youtu.be/source{i:05}" for i in range(count)],
    )


@pytest.mark.asyncio
async def test_ordered_claims_and_failed_source_continuation(database) -> None:
    conn, user_id, campaign_id = database
    series = await create_series(conn, user_id=user_id, payload=payload(campaign_id, 5))
    assert [job.series_position for job in series.jobs] == list(range(5))
    pool = SingleConnectionPool(conn)
    for index, job in enumerate(series.jobs):
        assert await queue.claim_next_series_job(pool) == job.id
        assert await queue.claim_next_series_job(pool) is None
        await conn.execute(
            "update jobs set status = $1 where id = $2",
            "failed" if index == 0 else "completed", job.id,
        )
    assert await queue.claim_next_series_job(pool) is None
    assert await get_series(conn, user_id=str(uuid4()), series_id=series.id) is None


@pytest.mark.asyncio
async def test_starter_and_foreign_campaign_rejected(database) -> None:
    conn, user_id, campaign_id = database
    await conn.execute("update subscriptions set plan_code = 'starter'")
    with pytest.raises(JobError, match="not included"):
        await create_series(conn, user_id=user_id, payload=payload(campaign_id))
    await conn.execute("update subscriptions set plan_code = 'pro'")
    await conn.execute("update campaigns set user_id = $1", str(uuid4()))
    with pytest.raises(JobError) as error:
        await create_series(conn, user_id=user_id, payload=payload(campaign_id))
    assert error.value.code == "campaign_not_found"
    assert await conn.fetchval("select count(*) from clip_series") == 0


@pytest.mark.asyncio
async def test_partial_creation_rolls_back_and_retry_is_complete(database) -> None:
    conn, user_id, campaign_id = database
    await conn.execute(
        "alter table jobs add constraint injected_failure check (series_position <> 1)"
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await create_series(conn, user_id=user_id, payload=payload(campaign_id))
    assert await conn.fetchval("select count(*) from clip_series") == 0
    assert await conn.fetchval("select count(*) from jobs") == 0
    await conn.execute("alter table jobs drop constraint injected_failure")
    series = await create_series(conn, user_id=user_id, payload=payload(campaign_id))
    assert len(series.jobs) == 2
    with pytest.raises(JobError) as error:
        await create_series(conn, user_id=user_id, payload=payload(campaign_id))
    assert error.value.code == "concurrent_jobs_exceeded"


@pytest.mark.asyncio
async def test_claim_recovers_only_before_processing_starts(database) -> None:
    conn, user_id, campaign_id = database
    series = await create_series(conn, user_id=user_id, payload=payload(campaign_id))
    pool = SingleConnectionPool(conn)
    assert await queue.claim_next_series_job(pool) == series.jobs[0].id
    await conn.execute("update jobs set started_at = now() - interval '3 minutes'")
    assert await queue.claim_next_series_job(pool) == series.jobs[0].id
    await conn.execute(
        "update jobs set current_step = 'download', started_at = now() - interval '3 minutes'"
        " where id = $1", series.jobs[0].id,
    )
    assert await queue.claim_next_series_job(pool) is None
