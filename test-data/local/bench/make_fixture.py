"""Freeze one real job into a benchmark fixture.

Downloads the source, transcribes it once, and pulls the cached video map and
campaign from Postgres, so model benchmarks can replay the exact same inputs
without paying for transcription or vision again.

Run from apps/worker with its venv:
    .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/make_fixture.py <job_id>
"""

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

import asyncpg

from app.pipeline.ffmpeg import yt_dlp_download
from app.pipeline.transcribe import transcribe, transcript_to_timestamped_lines
from app.settings import get_settings

OUT_DIR = Path("/Users/augustindemeaux/clipfactory-data/bench")


async def main(job_id: str) -> int:
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url, statement_cache_size=0)
    try:
        job = await conn.fetchrow(
            """
            select j.source_url, j.duration_seconds, j.video_map, j.target_clip_count,
                   c.name, c.audience, c.niche, c.tone, c.goal,
                   c.avoid_topics, c.example_hooks
              from jobs j
              left join campaigns c on c.id = j.campaign_id
             where j.id = $1
            """,
            job_id,
        )
    finally:
        await conn.close()

    if job is None:
        print(f"job {job_id} not found")
        return 1
    if not job["video_map"]:
        print("job has no cached video_map — run it once before freezing a fixture")
        return 1

    workdir = OUT_DIR / "source" / job_id
    workdir.mkdir(parents=True, exist_ok=True)
    print(f"source → {workdir}")
    source_path = await yt_dlp_download(job["source_url"], str(workdir))
    print(f"got {source_path}")

    print("transcribing (whisper-1)…")
    transcript = await transcribe(source_path)
    print(f"{len(transcript.words)} words, lang={transcript.language}")

    fixture = {
        "job_id": job_id,
        "source_url": job["source_url"],
        "source_path": source_path,
        "duration_seconds": job["duration_seconds"],
        "target_clip_count": job["target_clip_count"],
        "campaign": {
            "name": job["name"],
            "audience": job["audience"],
            "niche": job["niche"],
            "tone": job["tone"],
            "goal": job["goal"],
            "avoid_topics": list(job["avoid_topics"] or []),
            "example_hooks": list(job["example_hooks"] or []),
        },
        "video_map": json.loads(job["video_map"]),
        "transcript": asdict(transcript),
        "transcript_lines": transcript_to_timestamped_lines(transcript),
    }

    out = OUT_DIR / f"fixture_{job_id}.json"
    out.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
    size_kb = out.stat().st_size // 1024
    print(f"wrote {out} ({size_kb} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1])))
