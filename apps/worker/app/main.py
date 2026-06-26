from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import uuid

import structlog

from .db import close_pool, get_pool, init_pool
from .log_sanitize import scrub_email_values
from .parallel.supervisor import Supervisor
from .settings import get_settings

log = structlog.get_logger()


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


def _worker_id() -> str:
    """Stable-ish per-process id for claim ownership and reaper logs."""
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


async def main() -> None:
    settings = get_settings()
    _configure_logging(settings.log_level)
    await init_pool()
    pool = get_pool()

    supervisor = Supervisor(
        pool,
        worker_id=_worker_id(),
        worker_slots=settings.worker_slots,
        render_slots=settings.render_slots,
        poll_interval_seconds=settings.worker_poll_interval,
        heartbeat_interval_seconds=settings.heartbeat_interval_seconds,
        reaper_interval_seconds=settings.reaper_interval_seconds,
        job_lease_seconds=settings.job_lease_seconds,
        max_attempts=settings.max_attempts,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, supervisor.request_stop)
        except NotImplementedError:
            pass

    log.info("worker.ready", slots=settings.worker_slots, render_slots=settings.render_slots)
    try:
        await supervisor.run()
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
