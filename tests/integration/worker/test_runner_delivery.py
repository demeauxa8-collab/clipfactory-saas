import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.models import ArcSegmentSpec, StoryArc, Transcript, TranscriptWord
from app.pipeline import runner
from app.pipeline.clip_render import ClipRejected

pytestmark = pytest.mark.asyncio


@pytest.fixture
def offline_pipeline(monkeypatch, tmp_path):
    settings = runner.get_settings().model_copy(
        update={"worker_tmp_dir": str(tmp_path)}
    )
    monkeypatch.setattr(runner, "get_settings", lambda: settings)
    monkeypatch.setattr(
        runner.analytics, "fire_and_forget", lambda coroutine: coroutine.close()
    )
    monkeypatch.setattr(
        runner, "_provider_pair", lambda: (SimpleNamespace(name="offline"), None)
    )
    monkeypatch.setattr(runner, "_validate_url", AsyncMock())

    async def download(url, workdir):
        path = Path(workdir) / "source.mp4"
        path.write_bytes(
            b"source fixture; media stages are mocked in this database test"
        )
        return str(path)

    monkeypatch.setattr(runner, "yt_dlp_download", download)
    monkeypatch.setattr(runner, "fetch_audience_heatmap", AsyncMock(return_value=None))
    monkeypatch.setattr(
        runner, "probe_duration_seconds", AsyncMock(return_value=120.01)
    )
    words = [TranscriptWord(f"word{i}", i * 0.5, i * 0.5 + 0.45) for i in range(180)]
    transcript = Transcript(" ".join(word.word for word in words), words)
    monkeypatch.setattr(runner, "transcribe", AsyncMock(return_value=transcript))
    arcs = [
        StoryArc(
            f"Candidate {i}",
            "single",
            [
                ArcSegmentSpec(
                    "single",
                    start,
                    start + 14.45,
                    " ".join(
                        word.word
                        for word in words
                        if start <= word.start < start + 14.5
                    ),
                )
            ],
            "Complete source passage",
            90 - i,
            "low",
        )
        for i, start in enumerate([1, 31, 61])
    ]
    monkeypatch.setattr(runner, "_run_simple_path", AsyncMock(return_value=arcs))
    monkeypatch.setattr(
        runner, "deep_vision_for_arc", AsyncMock(return_value=([], 0, 0))
    )
    monkeypatch.setattr(runner, "_guard_black_open", AsyncMock(return_value=True))
    calls = []

    async def render(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise ClipRejected("test: rejected first candidate")
        output = Path(kwargs["out_path"])
        output.write_bytes(b"mock rendered bytes")
        manifest = output.with_suffix(".manifest.json")
        manifest.write_text("{}")
        return SimpleNamespace(
            rendered_duration_seconds=14.45, manifest_path=str(manifest)
        )

    monkeypatch.setattr(runner, "render_prepared_candidate", render)
    monkeypatch.setattr(
        runner, "upload_file", lambda path, *args: Path(path).stat().st_size
    )
    from app.pipeline import job_artifacts

    monkeypatch.setattr(
        job_artifacts, "upload_file", lambda path, *args: Path(path).stat().st_size
    )
    return calls


async def new_job(pool, account):
    async with pool.acquire() as conn:
        return str(
            await conn.fetchval(
                """insert into jobs (user_id, campaign_id, source_url,
            target_clip_count, credits_estimated) values ($1, $2, 'https://youtu.be/test', 2, 1)
            returning id""",
                *account,
            )
        )


async def test_runner_backfills_rejection_saves_final_windows_and_charges_once(
    db_pool,
    account,
    offline_pipeline,
):
    job_id = await new_job(db_pool, account)
    await runner.run_job(db_pool, job_id)
    async with db_pool.acquire() as conn:
        job = await conn.fetchrow("select * from jobs where id = $1", job_id)
        assert job["status"] == "completed", job["error_message"]
        assert job["credits_charged"] == 3
        assert job["duration_seconds"] == 121
        clips = await conn.fetch(
            "select * from clips where job_id = $1 order by idx", job_id
        )
        assert len(clips) == 2
        assert [row["idx"] for row in clips] == [0, 1]
        assert all(job["worker_id"] in row["r2_key"] for row in clips)
        for clip, call in zip(clips, offline_pipeline[1:], strict=True):
            assert (
                float(clip["start_seconds"])
                == call["prepared"].edl.shots[0].source_in_ms / 1000
            )
        assert await conn.fetchval("select sum(delta) from credit_ledger") == 7
    await runner.run_job(db_pool, job_id)
    assert len(offline_pipeline) == 3


async def test_all_rejected_renders_refund_full_reservation(
    db_pool, account, offline_pipeline, monkeypatch
):
    monkeypatch.setattr(
        runner, "render_prepared_candidate", AsyncMock(side_effect=ClipRejected("QC"))
    )
    job_id = await new_job(db_pool, account)
    await runner.run_job(db_pool, job_id)
    async with db_pool.acquire() as conn:
        job = await conn.fetchrow("select * from jobs where id = $1", job_id)
        assert job["status"] == "failed"
        assert job["error_code"] == "render_qc_failed"
        assert await conn.fetchval("select sum(delta) from credit_ledger") == 10
        assert await conn.fetchval("select count(*) from clips") == 0


async def test_canceled_attempt_refunds_and_propagates(
    db_pool, account, offline_pipeline, monkeypatch
):
    started = asyncio.Event()

    async def stalled_transcription(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(runner, "transcribe", stalled_transcription)
    job_id = await new_job(db_pool, account)
    task = asyncio.create_task(runner.run_job(db_pool, job_id))
    await asyncio.wait_for(started.wait(), 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with db_pool.acquire() as conn:
        assert (
            await conn.fetchval("select error_code from jobs where id = $1", job_id)
            == "worker_interrupted"
        )
        assert await conn.fetchval("select sum(delta) from credit_ledger") == 10
