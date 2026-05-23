from __future__ import annotations

import asyncio
import json
import logging
import signal

import redis.asyncio as redis_async
import structlog

from .db import close_pool, get_pool, init_pool
from .log_sanitize import scrub_email_values
from .pipeline.runner import run_job
from .settings import get_settings

log = structlog.get_logger()

JOBS_QUEUE_KEY = "clipfactory:jobs:queue"


def _configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper())
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            scrub_email_values,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper())),
    )


async def _worker_loop(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    pool = get_pool()
    client = redis_async.from_url(settings.redis_url, decode_responses=True)
    log.info("worker.ready", concurrency=settings.worker_concurrency)

    while not stop_event.is_set():
        try:
            result = await client.blpop(JOBS_QUEUE_KEY, timeout=settings.worker_poll_interval)
        except Exception as exc:
            log.warning("worker.queue.error", err=str(exc))
            await asyncio.sleep(2)
            continue
        if result is None:
            continue
        _, raw = result
        try:
            payload = json.loads(raw)
            job_id = payload["job_id"]
        except (ValueError, KeyError) as exc:
            log.warning("worker.bad_payload", raw=raw, err=str(exc))
            continue

        try:
            await run_job(pool, job_id)
        except Exception as exc:
            log.exception("worker.run_job.crash", job_id=job_id, err=str(exc))


async def main() -> None:
    settings = get_settings()
    _configure_logging(settings.log_level)
    await init_pool()

    stop_event = asyncio.Event()

    def _handle_signal(*_args: object) -> None:
        log.info("worker.signal", action="stopping")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass

    try:
        await _worker_loop(stop_event)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
