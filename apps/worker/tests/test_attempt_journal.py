from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app import attempt_journal, main
from app.attempt_journal import AttemptJournal


class Pool:
    def __init__(self, row=None, error=None):
        self.connection = SimpleNamespace(fetchrow=AsyncMock(return_value=row, side_effect=error))

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


def test_state_has_only_one_owner(tmp_path):
    with AttemptJournal(str(tmp_path), str(tmp_path)):
        with pytest.raises(RuntimeError, match="Another worker"):
            with AttemptJournal(str(tmp_path), str(tmp_path)):
                pass


@pytest.mark.parametrize("owns_attempt", [True, False])
async def test_crash_recovery_is_fenced_and_runs_once(tmp_path, monkeypatch, owns_attempt):
    job, token, user = map(str, (uuid4(), uuid4(), uuid4()))
    work = tmp_path / "work"
    attempt = work / job / token
    attempt.mkdir(parents=True)
    (attempt / "source.mp4").write_bytes(b"partial")
    other = work / job / str(uuid4())
    other.mkdir()
    fail = AsyncMock()
    monkeypatch.setattr(attempt_journal, "fail_job", fail)
    with AttemptJournal(str(tmp_path / "state"), str(work)) as journal:
        journal.start(job, token)
    # A fresh process sees the old durable attempt.
    with AttemptJournal(str(tmp_path / "state"), str(work)) as journal:
        pool = Pool({"user_id": user} if owns_attempt else None)
        assert await journal.recover(pool)
        assert not await journal.recover(pool)
        assert not attempt.exists()
        assert other.exists()
        if owns_attempt:
            fail.assert_awaited_once()
            assert fail.call_args.kwargs["token"] == token
            assert fail.call_args.kwargs["code"] == "worker_interrupted"
        else:
            fail.assert_not_awaited()


async def test_database_outage_preserves_attempt_and_prevents_overwrite(tmp_path):
    with AttemptJournal(str(tmp_path), str(tmp_path / "work")) as journal:
        job, token = str(uuid4()), str(uuid4())
        journal.start(job, token)
        with pytest.raises(ConnectionError):
            await journal.recover(Pool(error=ConnectionError()))
        assert journal.pending() == {"job_id": job, "token": token}
        with pytest.raises(RuntimeError, match="unresolved"):
            journal.start(str(uuid4()), str(uuid4()))


async def test_corrupt_attempt_cannot_escape_work_directory(tmp_path):
    with AttemptJournal(str(tmp_path / "state"), str(tmp_path / "work")) as journal:
        journal.path.write_text('{"job_id":"../../important","token":"invalid"}')
        pool = Pool()
        with pytest.raises(ValueError):
            await journal.recover(pool)
        pool.connection.fetchrow.assert_not_awaited()
        assert journal.path.exists()


async def test_queued_database_job_runs_without_redis_delivery(monkeypatch):
    import asyncio

    stop = asyncio.Event()
    job_id = uuid4()
    pool = Pool()
    pool.connection.fetchval = AsyncMock(return_value=job_id)
    journal = SimpleNamespace(recover=AsyncMock(return_value=False))
    client = SimpleNamespace(blpop=AsyncMock(), aclose=AsyncMock())
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(redis_url="redis://local"))
    monkeypatch.setattr(main, "get_pool", lambda: pool)
    monkeypatch.setattr(main.redis_async, "from_url", lambda *a, **k: client)
    monkeypatch.setattr(main, "claim_next_series_job", AsyncMock(return_value=None))

    async def run(pool_arg, received, stop_arg, journal_arg):
        assert (pool_arg, received, stop_arg, journal_arg) == (pool, str(job_id), stop, journal)
        stop.set()

    monkeypatch.setattr(main, "_run_until_stop", run)
    await main._worker_loop(stop, journal)
    client.blpop.assert_not_awaited()
    client.aclose.assert_awaited_once()
