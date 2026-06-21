"""Worker-side analytics sink (+ optional PostHog mirror).

Same contract as the API sink: never raise, never block job processing. Events
are written to the shared analytics_events table with source='worker'.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import httpx
import structlog

from .settings import get_settings

log = structlog.get_logger()

_background: set[asyncio.Task[Any]] = set()


def fire_and_forget(coro: Any) -> None:
    """Schedule a coroutine without awaiting it; errors are swallowed by the coro."""
    try:
        task = asyncio.create_task(coro)
    except RuntimeError:
        return
    _background.add(task)
    task.add_done_callback(_background.discard)


async def track(
    pool: asyncpg.Pool,
    *,
    event_name: str,
    user_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> None:
    props = properties or {}
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                insert into analytics_events (user_id, event_name, source, properties)
                values ($1, $2, 'worker', $3::jsonb)
                """,
                user_id,
                event_name,
                json.dumps(props),
            )
    except Exception as exc:
        log.warning("analytics.insert_failed", event=event_name, err=str(exc))

    if user_id:
        await _forward_posthog(
            event_name=event_name,
            distinct_id=user_id,
            properties={**props, "source": "worker"},
        )


async def _forward_posthog(
    *, event_name: str, distinct_id: str, properties: dict[str, Any]
) -> None:
    settings = get_settings()
    if not settings.posthog_api_key:
        return
    payload = {
        "api_key": settings.posthog_api_key,
        "event": event_name,
        "distinct_id": str(distinct_id),
        "properties": properties,
    }
    url = f"{settings.posthog_host.rstrip('/')}/capture/"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(url, json=payload)
    except Exception as exc:
        log.debug("analytics.posthog_failed", event=event_name, err=str(exc))
