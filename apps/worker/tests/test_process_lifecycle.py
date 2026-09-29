import asyncio
import os
import sys

import pytest

from app.pipeline.ffmpeg import FFmpegError, _run


async def test_process_timeout_reaps_the_child(tmp_path):
    pid_path = tmp_path / "pid"
    script = "import os,sys,time;open(sys.argv[1],'w').write(str(os.getpid()));time.sleep(30)"
    with pytest.raises(FFmpegError, match="timed out"):
        await _run([sys.executable, "-c", script, str(pid_path)], timeout_seconds=0.5)
    pid = int(pid_path.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


async def test_cancelling_render_reaps_the_child_and_propagates_cancellation(tmp_path):
    pid_path = tmp_path / "pid"
    script = "import os,sys,time;open(sys.argv[1],'w').write(str(os.getpid()));time.sleep(30)"
    task = asyncio.create_task(_run([sys.executable, "-c", script, str(pid_path)]))
    for _ in range(100):
        if pid_path.exists() and pid_path.read_text():
            break
        await asyncio.sleep(0.01)
    pid = int(pid_path.read_text())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


async def test_short_process_preserves_output_and_exit_status():
    code, out, err = await _run([sys.executable, "-c", "import sys;print('ok');sys.exit(3)"])
    assert (code, out.strip(), err) == (3, "ok", "")
