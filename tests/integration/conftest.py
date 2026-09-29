"""Real PostgreSQL fixtures: one disposable database per test, no production DSN."""

import os
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from apply_schema import apply_schema


@pytest_asyncio.fixture
async def db_pool():
    dsn = os.environ.get("CLIPFACTORY_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip(
            "Set CLIPFACTORY_TEST_DATABASE_URL to a disposable local PostgreSQL database"
        )
    parsed = urlparse(dsn)
    if (
        parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.path != "/clipfactory_test"
    ):
        pytest.fail(
            "Integration tests require localhost and database name clipfactory_test"
        )
    admin = await asyncpg.connect(dsn)
    name = "clipfactory_test_" + uuid4().hex
    pool = None
    try:
        for role in ("anon", "authenticated", "service_role"):
            if not await admin.fetchval(
                "select 1 from pg_roles where rolname = $1", role
            ):
                await admin.execute(f'create role "{role}"')
        await admin.execute(f'create database "{name}"')
        test_dsn = urlunparse(parsed._replace(path="/" + name))
        pool = await asyncpg.create_pool(
            test_dsn, min_size=1, max_size=5, command_timeout=15
        )
        async with pool.acquire() as conn:
            await apply_schema(conn)
        yield pool
    finally:
        if pool is not None:
            await pool.close()
        await admin.execute(f'drop database if exists "{name}" with (force)')
        await admin.close()


@pytest_asyncio.fixture
async def account(db_pool):
    user_id = uuid4()
    async with db_pool.acquire() as conn:
        await conn.execute(
            "insert into auth.users (id, email) values ($1, 'test@example.com')",
            user_id,
        )
        await conn.execute(
            """insert into subscriptions (user_id, plan_code, status)
                              values ($1, 'starter', 'active')""",
            user_id,
        )
        await conn.execute(
            """insert into credit_ledger (user_id, delta, reason)
                              values ($1, 10, 'subscription_grant')""",
            user_id,
        )
        campaign_id = await conn.fetchval(
            "insert into campaigns (user_id, name) values ($1, 'Test campaign') returning id",
            user_id,
        )
    return user_id, campaign_id
