"""Regression checks for the Supabase transaction pooler."""

from types import SimpleNamespace

import pytest

from app import db
from app.services import analytics


@pytest.mark.asyncio
async def test_api_pool_disables_prepared_statement_cache(monkeypatch: pytest.MonkeyPatch):
    pool = object()

    async def create_pool(**kwargs):
        assert kwargs["statement_cache_size"] == 0
        return pool

    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setattr(
        db,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgres://example", database_pool_min=1, database_pool_max=2
        ),
    )
    monkeypatch.setattr(db.asyncpg, "create_pool", create_pool)
    assert await db.init_pool() is pool


@pytest.mark.asyncio
async def test_analytics_insert_failure_does_not_escape():
    class BrokenConnection:
        async def execute(self, *_args):
            raise RuntimeError("database unavailable")

    await analytics.record_event(BrokenConnection(), event_name="test_event")
