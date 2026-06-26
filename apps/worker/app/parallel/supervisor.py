"""Asyncio task-pool supervisor — the worker's main loop (see main.py).

Keeps up to WORKER_SLOTS pipelines in flight. Each job runs its pipeline as a
coroutine; the CPU-heavy render stage is gated by a per-machine
Semaphore(RENDER_SLOTS) so we don't OOM the box. Each in-flight job is
heartbeated; if the reaper steals it (heartbeat returns False) the job is
cancelled to avoid double processing. On SIGTERM the supervisor stops claiming
and drains in-flight jobs up to a deadline.

See docs/architecture/parallel-workers.md §3.
"""

from __future__ import annotations

import asyncio
import contextlib

import asyncpg
import structlog

from . import claim
from .reaper import run_reaper

log = structlog.get_logger()


class Supervisor:
    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        worker_id: str,
        worker_slots: int = 6,
        render_slots: int = 2,
        poll_interval_seconds: float = 2.0,
        heartbeat_interval_seconds: float = 20.0,
        reaper_interval_seconds: int = 60,
        job_lease_seconds: int = 180,
        max_attempts: int = 3,
        drain_deadline_seconds: float = 120.0,
    ) -> None:
        self._pool = pool
        self._worker_id = worker_id
        self._slots = worker_slots
        self._render_sem = asyncio.Semaphore(render_slots)
        self._poll = poll_interval_seconds
        self._hb_interval = heartbeat_interval_seconds
        self._reaper_interval = reaper_interval_seconds
        self._lease = job_lease_seconds
        self._max_attempts = max_attempts
        self._drain_deadline = drain_deadline_seconds

        self._stop = asyncio.Event()
        self._in_flight: dict[str, asyncio.Task[None]] = {}

    def request_stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        log.info("supervisor.start", worker_id=self._worker_id, slots=self._slots)
        reaper_task = asyncio.create_task(
            run_reaper(
                self._pool, self._stop,
                interval_seconds=self._reaper_interval,
                lease_seconds=self._lease,
                max_attempts=self._max_attempts,
            )
        )
        try:
            await self._claim_loop()
        finally:
            await self._drain()
            self._stop.set()
            with contextlib.suppress(Exception):
                await reaper_task

    # ----- claim loop -----

    async def _claim_loop(self) -> None:
        while not self._stop.is_set():
            claimed_any = False
            while len(self._in_flight) < self._slots and not self._stop.is_set():
                job_id = await claim.claim_next_job(self._pool, worker_id=self._worker_id)
                if job_id is None:
                    break  # queue empty — stop filling, go wait
                task = asyncio.create_task(self._process(job_id))
                self._in_flight[job_id] = task
                task.add_done_callback(lambda t, jid=job_id: self._in_flight.pop(jid, None))
                claimed_any = True

            # Wait until a slot frees, the poll interval elapses, or we're told to stop.
            await self._wait_for_capacity(idle=not claimed_any)

    async def _wait_for_capacity(self, *, idle: bool) -> None:
        waiters: list[asyncio.Future[object]] = [asyncio.ensure_future(self._stop.wait())]
        if self._in_flight:
            waiters.append(asyncio.ensure_future(asyncio.wait(
                list(self._in_flight.values()), return_when=asyncio.FIRST_COMPLETED
            )))
        timeout = self._poll if idle else None
        try:
            await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for w in waiters:
                w.cancel()

    # ----- per-job execution -----

    async def _process(self, job_id: str) -> None:
        hb_stop = asyncio.Event()
        hb_task = asyncio.create_task(self._heartbeat_loop(job_id, hb_stop))
        try:
            await self._process_job(job_id)
        except asyncio.CancelledError:
            log.warning("supervisor.job_cancelled", job_id=job_id)
            raise
        except Exception as exc:  # noqa: BLE001 — run_job already handles its own failures
            log.exception("supervisor.job_crash", job_id=job_id, err=str(exc))
        finally:
            hb_stop.set()
            with contextlib.suppress(Exception):
                await hb_task

    async def _process_job(self, job_id: str) -> None:
        # run_job binds render_sem to its task context (render_gate); every
        # ffmpeg render inside this job then shares the machine-wide brake.
        # Liveness is driven externally by _heartbeat_loop, not by the runner.
        from ..pipeline.runner import run_job
        await run_job(self._pool, job_id, render_sem=self._render_sem)

    async def _heartbeat_loop(self, job_id: str, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._hb_interval)
                return  # stop was set → job finished
            except TimeoutError:
                pass
            alive = await claim.heartbeat(self._pool, job_id)
            if not alive:
                # The reaper requeued this job — cancel our in-flight task to avoid
                # double processing.
                log.warning("supervisor.job_reaped_midflight", job_id=job_id)
                task = self._in_flight.get(job_id)
                if task is not None:
                    task.cancel()
                return

    # ----- shutdown -----

    async def _drain(self) -> None:
        if not self._in_flight:
            return
        log.info("supervisor.drain", in_flight=len(self._in_flight), deadline=self._drain_deadline)
        pending = list(self._in_flight.values())
        _done, still = await asyncio.wait(pending, timeout=self._drain_deadline)
        if still:
            # These will be reclaimed by the reaper after the lease expires.
            log.warning("supervisor.drain_timeout", abandoned=len(still))
