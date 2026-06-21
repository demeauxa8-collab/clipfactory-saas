"""First-party analytics sink (+ optional PostHog mirror).

Design rules:
- Analytics must NEVER break a request. Every path swallows its own errors.
- Analytics must NOT add latency. Domain events are scheduled fire-and-forget on
  their own connection, never inside a domain transaction.
- PostHog is an optional mirror: a no-op unless POSTHOG_API_KEY is set.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import httpx
import structlog

from ..settings import get_settings

log = structlog.get_logger()

# Keep a strong ref to in-flight background tasks so they are not GC'd mid-flight.
_background: set[asyncio.Task[Any]] = set()


def fire_and_forget(coro: Any) -> None:
    """Schedule a coroutine without awaiting it; errors are swallowed by the coro."""
    try:
        task = asyncio.create_task(coro)
    except RuntimeError:
        # No running loop (shouldn't happen inside the app) — drop silently.
        return
    _background.add(task)
    task.add_done_callback(_background.discard)


async def record_event(
    conn: asyncpg.Connection,
    *,
    event_name: str,
    source: str = "api",
    user_id: str | None = None,
    anon_id: str | None = None,
    session_id: str | None = None,
    properties: dict[str, Any] | None = None,
    path: str | None = None,
    referrer: str | None = None,
) -> None:
    """Insert one event using an existing connection, then mirror to PostHog."""
    props = properties or {}
    try:
        await conn.execute(
            """
            insert into analytics_events
              (user_id, anon_id, session_id, event_name, source, properties, path, referrer)
            values ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
            """,
            user_id,
            anon_id,
            session_id,
            event_name,
            source,
            json.dumps(props),
            path,
            referrer,
        )
    except Exception as exc:
        log.warning("analytics.insert_failed", event=event_name, err=str(exc))

    distinct_id = user_id or anon_id
    if distinct_id:
        fire_and_forget(
            _forward_posthog(
                event_name=event_name,
                distinct_id=distinct_id,
                properties={**props, "source": source, "$current_url": path},
            )
        )


async def track_with_pool(
    pool: asyncpg.Pool,
    *,
    event_name: str,
    **kwargs: Any,
) -> None:
    """Acquire a short-lived connection and record one event. Best-effort."""
    try:
        async with pool.acquire() as conn:
            await record_event(conn, event_name=event_name, **kwargs)
    except Exception as exc:
        log.warning("analytics.track_failed", event=event_name, err=str(exc))


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
