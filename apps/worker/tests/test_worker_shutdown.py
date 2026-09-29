import asyncio

import pytest

from app import main


@pytest.mark.parametrize("external_cancel", [False, True])
async def test_shutdown_waits_for_pipeline_cleanup(monkeypatch, external_cancel):
    running, cleaned = asyncio.Event(), asyncio.Event()
    stop = asyncio.Event()

    async def job(*args):
        try:
            running.set()
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            cleaned.set()

    monkeypatch.setattr(main, "run_job", job)
    task = asyncio.create_task(main._run_until_stop(None, "job", stop))
    await running.wait()
    if external_cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        stop.set()
        await asyncio.wait_for(task, 1)
    assert cleaned.is_set()
