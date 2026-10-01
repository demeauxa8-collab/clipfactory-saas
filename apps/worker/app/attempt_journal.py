"""Persist one worker attempt so a process crash cannot strand its credits."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from .pipeline.job_state import fail_job


class AttemptJournal:
    def __init__(self, directory: str, work_directory: str):
        self.directory = Path(directory)
        self.work_directory = Path(work_directory)
        self.path = self.directory / "attempt.json"
        self._lock = None

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock = os.fdopen(
            os.open(self.directory / "worker.lock", os.O_CREAT | os.O_RDWR, 0o600), "a+",
        )
        try:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock.close()
            self._lock = None
            raise RuntimeError("Another worker owns this state directory") from None
        return self

    def __exit__(self, *_args):
        if self._lock is not None:
            self._lock.close()
            self._lock = None

    def pending(self) -> dict[str, str] | None:
        if not self.path.exists():
            return None
        raw = json.loads(self.path.read_text())
        return {"job_id": str(UUID(raw["job_id"])), "token": str(UUID(raw["token"]))}

    def start(self, job_id: str, token: str) -> None:
        if self.pending() is not None:
            raise RuntimeError("An unresolved attempt must be recovered first")
        payload = {"job_id": str(UUID(job_id)), "token": str(UUID(token))}
        with tempfile.NamedTemporaryFile(mode="w", dir=self.directory, delete=False) as handle:
            temporary = Path(handle.name)
            try:
                json.dump(payload, handle)
                handle.flush()
                os.fsync(handle.fileno())
                os.replace(temporary, self.path)
                self._sync_directory()
            finally:
                temporary.unlink(missing_ok=True)

    def _sync_directory(self) -> None:
        descriptor = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    async def recover(self, pool) -> bool:
        attempt = self.pending()
        if attempt is None:
            return False
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "select user_id from jobs where id = $1 and worker_id = $2",
                UUID(attempt["job_id"]), attempt["token"],
            )
            if row is not None:
                await fail_job(
                    conn, job_id=attempt["job_id"], user_id=str(row["user_id"]),
                    token=attempt["token"], code="worker_interrupted", step="interrupted",
                    message="Worker restarted before completion. Reserved credits were refunded.",
                )
        # UUID validation above keeps cleanup inside this attempt's temp folder.
        shutil.rmtree(
            self.work_directory / attempt["job_id"] / attempt["token"], ignore_errors=True,
        )
        self.path.unlink()
        self._sync_directory()
        return True
