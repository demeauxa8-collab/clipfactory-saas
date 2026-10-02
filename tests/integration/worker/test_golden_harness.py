"""A synthetic source, actual runner + PostgreSQL + FFmpeg, all paid APIs mocked."""

import asyncio
import json
import subprocess

import pytest
from app.golden.harness import PreloadJournal, export_source, seed_source
from app.golden.sources import sha256
from app.models import Transcript, TranscriptSentence, TranscriptWord
from app.pipeline import runner
from app.providers.base import LLMCallResult
from app.settings import get_settings


@pytest.mark.asyncio
async def test_synthetic_source_uses_real_runner_render_and_exports(
    db_pool, monkeypatch, tmp_path
):
    source_dir = tmp_path / "frozen"
    source_dir.mkdir()
    media = source_dir / "source.mp4"
    await asyncio.to_thread(
        subprocess.run,
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=25:duration=34",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=600:sample_rate=44100:duration=34",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-shortest",
            str(media),
        ],
        check=True,
        capture_output=True,
    )
    metadata = {
        "id": "fake_source",
        "sha256": sha256(media),
        "duration": 34,
        "heatmap_available": False,
    }
    (source_dir / "meta.json").write_text(json.dumps(metadata))
    (source_dir / "heatmap.json").write_text("null")
    directory, work = tmp_path / "delivered", tmp_path / "work"
    directory.mkdir()
    for name, value in {
        "DATABASE_URL": "postgresql://local",
        "STORAGE_BACKEND": "local",
        "STORAGE_LOCAL_DIR": str(directory),
        "WORKER_TMP_DIR": str(work),
        "OPENAI_API_KEY": "offline",
        "OPENROUTER_API_KEY": "offline",
        "CLIP_JUDGE_ENABLED": "false",
        "ENABLE_FALLBACK": "false",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    words = [TranscriptWord(f"w{i}", i * 0.5, i * 0.5 + 0.3) for i in range(68)]
    transcript = Transcript(
        " ".join(w.word for w in words),
        words,
        sentences=[TranscriptSentence("Complete sentence.", 1, 25.8)],
    )
    excerpt = " ".join(w.word for w in words[2:52])

    class OfflineProvider:
        name = "offline"

        async def chat_json(self, **kwargs):
            return LLMCallResult(
                payload={
                    "segments": [
                        {
                            "start": 1,
                            "end": 25.8,
                            "title": "Synthetic complete passage",
                            "transcript_excerpt": excerpt,
                            "start_anchor": "w2 w3 w4 w5",
                            "end_anchor": "w48 w49 w50 w51",
                            "hook_score_text": 90,
                            "emotion_score": 80,
                            "why": "Complete source sentence",
                        }
                    ]
                },
                tokens_in=10,
                tokens_out=10,
                model=kwargs["model"],
            )

        async def vision_json(self, **kwargs):
            return LLMCallResult(
                payload={
                    "decor": "screen",
                    "person_visible": False,
                    "energy": 70,
                    "action": "other",
                    "visual_score": 80,
                    "problems": [],
                    "proof_objects": [],
                },
                tokens_in=10,
                tokens_out=10,
                model=kwargs["model"],
            )

    async def asr(*args, **kwargs):
        return transcript

    monkeypatch.setattr(runner, "_provider_pair", lambda: (OfflineProvider(), None))
    monkeypatch.setattr(runner, "transcribe", asr)

    # No network should occur: cache preloading bypasses both yt-dlp calls.
    async def no_http(*args, **kwargs):
        raise AssertionError("offline harness attempted network access")

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "send", no_http)

    # External URL reachability is mocked; real cached downloader and media remain.
    async def reachable(*args, **kwargs):
        return None

    monkeypatch.setattr(runner, "_validate_url", reachable)
    source = {
        "id": "fake_source",
        "campaign": {
            "audience": "Test audience",
            "niche": "Education",
            "tone": "Clear",
            "goal": "Teach",
            "example_hooks": ["One", "Two", "Three"],
        },
    }
    try:
        jid = await seed_source(db_pool, source, target=1)
        await runner.run_job(
            db_pool, jid, attempt_journal=PreloadJournal(source_dir, work)
        )
        async with db_pool.acquire() as conn:
            job = dict(await conn.fetchrow("select * from jobs where id=$1", jid))
            rows = await conn.fetch(
                "select * from clips where job_id=$1 order by idx", jid
            )
        assert job["status"] == "completed", job["error_message"]
        result = export_source(directory, metadata, job, rows)
        assert len(result["clips"]) == 1
        clip = result["clips"][0]
        assert not clip["metrics"]["cut_inside_word"]
        assert clip["segments"][0]["quote"].startswith("w2 ")
        assert (directory / clip["media"]).stat().st_size > 10000
        assert not list(work.rglob("source.mp4"))
        assert sha256(media) == metadata["sha256"]
    finally:
        get_settings.cache_clear()
