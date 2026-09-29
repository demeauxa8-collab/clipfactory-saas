from __future__ import annotations

import asyncio
import json
import logging
import signal
from contextlib import suppress
from uuid import UUID

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


async def _run_until_stop(pool, job_id: str, stop_event: asyncio.Event) -> None:
    job = asyncio.create_task(run_job(pool, job_id))
    stopping = asyncio.create_task(stop_event.wait())
    try:
        done, _ = await asyncio.wait({job, stopping}, return_when=asyncio.FIRST_COMPLETED)
        if job in done:
            await job
        else:
            job.cancel()
            with suppress(asyncio.CancelledError):
                await job
    finally:
        # Cancellation must reach the pipeline's refund handler and its child
        # process cleanup before connections are closed.
        for task in (job, stopping):
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task


async def _worker_loop(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    pool = get_pool()
    client = redis_async.from_url(settings.redis_url, decode_responses=True)
    log.info("worker.ready", concurrency=1)
    try:
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
            if stop_event.is_set():
                await client.lpush(JOBS_QUEUE_KEY, raw)
                break
            try:
                payload = json.loads(raw)
                if not isinstance(payload, dict) or not isinstance(payload.get("job_id"), str):
                    raise ValueError("expected a job_id string")
                job_id = str(UUID(payload["job_id"]))
            except (ValueError, KeyError, TypeError) as exc:
                log.warning("worker.bad_payload", error_type=type(exc).__name__)
                continue
            try:
                await _run_until_stop(pool, job_id, stop_event)
            except Exception as exc:
                log.exception("worker.run_job.crash", job_id=job_id, err=str(exc))
    finally:
        await client.aclose()


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
