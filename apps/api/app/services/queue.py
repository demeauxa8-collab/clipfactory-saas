from __future__ import annotations

import json

import redis.asyncio as redis_async
import structlog

from ..settings import get_settings

log = structlog.get_logger()

JOBS_QUEUE_KEY = "clipfactory:jobs:queue"

_redis: redis_async.Redis | None = None


def get_redis() -> redis_async.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def enqueue_job(job_id: str) -> None:
    client = get_redis()
    payload = json.dumps({"job_id": job_id})
    await client.rpush(JOBS_QUEUE_KEY, payload)
    log.info("queue.enqueued", job_id=job_id)


async def queue_length() -> int:
    client = get_redis()
    return int(await client.llen(JOBS_QUEUE_KEY))
