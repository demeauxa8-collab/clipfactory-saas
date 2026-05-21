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
        min_size=settings.database_pool_min,
        max_size=settings.database_pool_max,
        command_timeout=30,
    )
    log.info("db.pool.ready", min=settings.database_pool_min, max=settings.database_pool_max)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("db.pool.closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool is not initialised. Call init_pool() at startup.")
    return _pool
