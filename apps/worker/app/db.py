from __future__ import annotations

import asyncpg
import structlog

from .settings import get_settings

log = structlog.get_logger()

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=4,
        command_timeout=30,
    )
    log.info("worker.db.pool.ready")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool is not initialised.")
    return _pool
