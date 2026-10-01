"""Compare the fixed MLX model with whisper-1 without changing production settings."""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "apps/worker"))
os.chdir(REPO / "apps/worker")

from app.pipeline.asr_mlx import _decode
from app.pipeline.transcribe import build_transcript
from app.settings import get_settings
from openai import AsyncOpenAI


def normalized(word: str) -> str:
    return word.lower().replace("’", "'").strip(".,!?;:…\" ")


def zero_rate(words: list[dict]) -> float:
    return sum(int(w["end"] - w["start"] < 0.001) for w in words) / max(1, len(words))


async def benchmark(source: Path, output: Path) -> None:
    settings = get_settings()
    with tempfile.TemporaryDirectory(prefix="cf-asr-benchmark-") as temporary:
        audio = Path(temporary) / "first180.mp3"
        await asyncio.to_thread(subprocess.run,
            [settings.ffmpeg_bin, "-v", "error", "-y", "-i", str(source), "-t", "180",
             "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(audio)], check=True,
        )
        duration = float((await asyncio.to_thread(subprocess.check_output,
            [settings.ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio)], text=True,
        )).strip())
        started = time.monotonic()
        async with AsyncOpenAI(api_key=settings.openai_api_key, timeout=180) as client:
            with audio.open("rb") as handle:
                response = await client.audio.transcriptions.create(
                    file=handle, model="whisper-1", response_format="verbose_json",
                    timestamp_granularities=["word", "segment"],
                )
        openai_seconds = time.monotonic() - started
        reference = response.model_dump()
        print("OpenAI reference complete", flush=True)
        started = time.monotonic()
        local = await asyncio.to_thread(_decode, str(audio), settings.mlx_whisper_model)
        cold_seconds = time.monotonic() - started
        print("MLX first decode complete", flush=True)
        started = time.monotonic()
        await asyncio.to_thread(_decode, str(audio), settings.mlx_whisper_model)
        warm_seconds = time.monotonic() - started
        local_words = [w for segment in local.get("segments", []) for w in segment.get("words", [])]
        baseline = build_transcript(
            text=reference["text"], raw_words=reference["words"],
            raw_segments=reference["segments"], language=reference.get("language"), backend="openai",
        )
        candidate = build_transcript(
            text=local["text"], raw_words=local_words, raw_segments=local["segments"],
            language=local.get("language"), backend="mlx_whisper",
        )
        a, b = [normalized(w.word) for w in baseline.words], [normalized(w.word) for w in candidate.words]
        matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
        changed = 0
        deltas = []
        for tag, i, j, k, l in matcher.get_opcodes():
            if tag == "equal":
                deltas.extend(abs(baseline.words[x].start - candidate.words[y].start)
                              for x, y in zip(range(i, j), range(k, l), strict=True))
            else:
                changed += (j - i) + (l - k)
        median = float(statistics.median(deltas)) if deltas else None
        mismatch = changed / max(1, len(a))
        gates = {
            "zero_duration": zero_rate(local_words) <= zero_rate(reference["words"]),
            "timestamp_drift": median is not None and median < 0.15,
            "word_difference": mismatch < 0.03,
            "speed": duration / warm_seconds >= 10,
        }
        report = {
            "source_duration_seconds": duration, "mlx_model": settings.mlx_whisper_model,
            "openai_model": "whisper-1", "openai_seconds": openai_seconds,
            "mlx_cold_seconds_including_model_load": cold_seconds, "mlx_warm_seconds": warm_seconds,
            "mlx_realtime_multiple": duration / warm_seconds,
            "openai_raw_zero_duration_rate": zero_rate(reference["words"]),
            "mlx_raw_zero_duration_rate": zero_rate(local_words),
            "median_aligned_start_drift_seconds": median, "missing_extra_words_rate": mismatch,
            "openai_clean_words": len(a), "mlx_clean_words": len(b),
            "matched_words": len(deltas), "gates": gates, "activate_mlx": all(gates.values()),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    asyncio.run(benchmark(args.source.resolve(), args.output.resolve()))
