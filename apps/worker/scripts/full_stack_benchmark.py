"""Bounded local integration benchmark with retained provider evidence."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path("/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12")
SOURCE = Path(
    "/Users/augustindemeaux/clipfactory-data/bench/source/2221f645-ed0e-47b2-8201-417d7c517a39/source.mp4"
)
FIXTURE = Path(
    "/Users/augustindemeaux/clipfactory-data/bench/fixture_2221f645-ed0e-47b2-8201-417d7c517a39.json"
)
TRANSCRIPT = Path(
    "/Users/augustindemeaux/clipfactory-data/bench/craft-refs/transcript_with_sentences.json"
)


def save(name, data):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")


def read(name):
    return json.loads((ROOT / name).read_text())


def configure():
    values = dotenv_values("/Users/augustindemeaux/clipfactory-saas/apps/worker/.env")
    for key in (
        "OPENROUTER_API_KEY",
        "PRIMARY_TEXT_MODEL",
        "VISION_CHEAP_MODEL",
        "PRIMARY_VISION_DEEP_MODEL",
    ):
        if values.get(key):
            os.environ[key] = values[key]
    os.environ.update(
        DATABASE_URL="postgresql://local:local@127.0.0.1:5432/local",
        STORAGE_BACKEND="local",
        R2_ACCOUNT_ID="local",
        R2_ACCESS_KEY_ID="local",
        R2_SECRET_ACCESS_KEY="local",
        R2_ENDPOINT_URL="https://example.com",
        OPENAI_API_KEY="local",
        ENABLE_FALLBACK="false",
    )


configure()

from app.models import (  # noqa: E402
    Transcript,
    TranscriptSentence,
    TranscriptWord,
    VideoEvent,
    VideoMap,
)
from app.pipeline.ffmpeg import analyze_audio_map  # noqa: E402
from app.pipeline.story_arcs import select_story_arcs  # noqa: E402
from app.pipeline.video_map import build_video_map  # noqa: E402
from app.providers.openrouter import OpenRouterProvider  # noqa: E402
from app.settings import get_settings  # noqa: E402


class AuditedProvider(OpenRouterProvider):
    """Cap all HTTP attempts, including internal retries, before dispatch."""

    async def _post_chat(self, body):
        ledger = read("calls.json") if (ROOT / "calls.json").exists() else []
        if len(ledger) >= 40:
            raise RuntimeError("benchmark request limit reached")
        prices = {r["model"]: r["pricing"] for r in read("provider-models.json")}
        pricing = prices[body["model"]]
        serialized = json.dumps(body, ensure_ascii=False)
        # UTF-8 bytes bound textual tokens conservatively; base64 also bounds
        # image tokens for this small-frame benchmark. Retain the reservation
        # even after errors, so unknown provider charges cannot be retried free.
        upper_cost = len(serialized.encode()) * float(pricing["prompt"]) + int(
            body.get("max_tokens", 4096)
        ) * float(pricing["completion"])
        if sum(c["reserved_usd"] for c in ledger) + upper_cost > 1.0:
            raise RuntimeError("benchmark conservative USD 1 reservation cap reached")
        index = len(ledger)
        entry = {
            "index": index,
            "model": body["model"],
            "reserved_usd": upper_cost,
            "status": "started",
            "request_sha256": hashlib.sha256(serialized.encode()).hexdigest(),
        }
        ledger.append(entry)
        save("calls.json", ledger)
        started = time.monotonic()
        try:
            result = await super()._post_chat(body)
            save(f"calls/{index:03d}.response.json", result)
            entry.update(
                status="completed", usage=result.get("usage"), seconds=time.monotonic() - started
            )
            return result
        except Exception as exc:
            entry.update(
                status="failed",
                error_type=type(exc).__name__,
                error=str(exc)[:400],
                seconds=time.monotonic() - started,
            )
            raise
        finally:
            ledger[index] = entry
            save("calls.json", ledger)


def inputs():
    fixture = json.loads(FIXTURE.read_text())
    raw = json.loads(TRANSCRIPT.read_text())
    transcript = Transcript(
        text=raw["text"],
        language=raw.get("language"),
        words=[TranscriptWord(**w) for w in raw["words"]],
        sentences=[TranscriptSentence(**s) for s in raw.get("sentences", [])],
    )
    return fixture, transcript


async def analyze():
    fixture, transcript = inputs()
    provider, settings = AuditedProvider(timeout_seconds=120), get_settings()
    save(
        "inputs.json",
        {
            "source": str(SOURCE),
            "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "transcript": str(TRANSCRIPT),
            "transcript_file_sha256": hashlib.sha256(TRANSCRIPT.read_bytes()).hexdigest(),
            "campaign": fixture["campaign"],
            "transcription": "retained_shared_input_not_regenerated",
            "max_reserved_provider_usd": 1.0,
            "max_http_attempts": 40,
        },
    )
    if not (ROOT / "audio_map.json").exists():
        save("audio_map.json", asdict(await analyze_audio_map(str(SOURCE))))
    if not (ROOT / "video_map.json").exists():
        directory = ROOT / "global_frames"
        directory.mkdir(exist_ok=True)
        vm, frames, tokens = await build_video_map(
            provider=provider,
            model=settings.vision_cheap_model,
            source_path=str(SOURCE),
            duration_seconds=596,
            transcript=transcript,
            workdir=str(directory),
        )
        save("video_map.json", asdict(vm))
        save("global_vision_stats.json", {"frames": frames, "tokens": tokens})
    raw = read("video_map.json")
    vm = VideoMap(summary=raw["summary"], events=[VideoEvent(**e) for e in raw["events"]])
    if not (ROOT / "fresh_arcs.json").exists():
        arcs, tokens = await select_story_arcs(
            provider=provider,
            model=settings.primary_text_model,
            transcript_lines=fixture["transcript_lines"],
            video_map=vm,
            campaign=fixture["campaign"],
            target_clip_count=3,
            duration_seconds=596,
            language=transcript.language,
            transcript=transcript,
        )
        save("fresh_arcs.json", {"arcs": [asdict(a) for a in arcs], "tokens": tokens})
    print(
        json.dumps(
            {
                "stage": "analyze",
                "arcs": len(read("fresh_arcs.json")["arcs"]),
                "video_events": len(vm.events),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["analyze"], default="analyze")
    args = parser.parse_args()
    asyncio.run(analyze())
