#!/usr/bin/env python3
"""Benchmark harness for select_story_arcs.

Replays ONLY the arc-selection LLM call (app.pipeline.story_arcs.select_story_arcs)
on a frozen fixture, across one or more OpenRouter models. Nothing else in the
pipeline is recomputed: transcription, video_map (cheap vision), verify_arcs,
deep vision and rendering are all skipped. This isolates the editorial-judgment
step so different models can be compared on the exact same inputs.

Must be run from apps/worker with its venv, because it imports the worker's
own modules (app.models, app.pipeline.story_arcs, app.providers.openrouter)
and app.settings.get_settings() reads apps/worker/.env for OPENROUTER_API_KEY
(relative env_file path resolved against the current working directory):

    cd /Users/augustindemeaux/clipfactory-saas/apps/worker
    .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/bench_arcs.py \\
        --models "google/gemini-2.5-flash,deepseek/deepseek-chat-v3.2" \\
        --fixture /Users/augustindemeaux/clipfactory-data/bench/\\
fixture_2221f645-ed0e-47b2-8201-417d7c517a39.json \\
        --out /Users/augustindemeaux/clipfactory-data/bench/results

One JSON file per model is written to --out (filename = sanitized model id),
plus a one-line-per-model summary printed to the console. A model that fails
(HTTP error, timeout, unparsable JSON, no usable arcs) does NOT abort the run:
the failure is captured and recorded as a result in its own right, and the
script moves on to the next model.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Any

# --- make the worker package importable -------------------------------------
# This script lives outside apps/worker (in clipfactory-data/bench/), so
# `import app.*` only works if apps/worker (the venv's cwd, per the usage
# note above) is on sys.path. Running a script via `python /abs/path.py`
# does NOT put the cwd on sys.path (only the script's own directory is
# added), so we add it explicitly here.
_CWD = Path.cwd()
if str(_CWD) not in sys.path:
    sys.path.insert(0, str(_CWD))

try:
    from app.models import Transcript, TranscriptWord, VideoEvent, VideoMap
    from app.pipeline.story_arcs import select_story_arcs
    from app.providers.openrouter import OpenRouterProvider
except ImportError as exc:  # pragma: no cover - operator error, not a test path
    sys.exit(
        "bench_arcs.py failed to import the worker package (app.*).\n"
        "It must be launched from apps/worker with its venv, e.g.:\n\n"
        "  cd /Users/augustindemeaux/clipfactory-saas/apps/worker\n"
        "  .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/bench_arcs.py "
        "--models ...\n\n"
        f"(underlying ImportError: {exc})"
    )


# =============================================================
# Fixture -> worker dataclasses
# =============================================================


def _build_transcript(raw: dict[str, Any]) -> Transcript:
    """Reconstruct Transcript/TranscriptWord from the fixture dict.

    Not actually fed into select_story_arcs() (it takes the pre-formatted
    `transcript_lines` string directly, produced upstream by
    transcript_to_timestamped_lines() — the fixture already carries that
    string under the "transcript_lines" key). Built here anyway: (a) the
    mission asks for it, (b) it doubles as a structural sanity check on the
    fixture, (c) word count is echoed in `raw_video_read` below.
    """
    words: list[TranscriptWord] = []
    for w in raw.get("words") or []:
        if not isinstance(w, dict):
            continue
        try:
            words.append(
                TranscriptWord(
                    word=str(w.get("word", "")),
                    start=float(w.get("start", 0.0)),
                    end=float(w.get("end", 0.0)),
                )
            )
        except (TypeError, ValueError):
            continue
    return Transcript(
        text=str(raw.get("text", "")),
        words=words,
        language=raw.get("language"),
    )


def _build_video_map(raw: dict[str, Any]) -> VideoMap:
    """Reconstruct VideoMap/VideoEvent from the fixture dict, tolerating
    missing/malformed fields (a benchmark run must not crash on one bad event).
    """
    events: list[VideoEvent] = []
    for e in raw.get("events") or []:
        if not isinstance(e, dict):
            continue
        try:
            events.append(
                VideoEvent(
                    id=str(e.get("id", "")),
                    start=float(e.get("start", 0.0)),
                    end=float(e.get("end", 0.0)),
                    decor=str(e.get("decor", "")),
                    people=str(e.get("people", "")),
                    objects=list(e.get("objects") or []),
                    action=str(e.get("action", "")),
                    transcript_summary=str(e.get("transcript_summary", "")),
                    visual_importance=int(float(e.get("visual_importance", 0) or 0)),
                    narrative_role=str(e.get("narrative_role", "neutral")),
                )
            )
        except (TypeError, ValueError):
            continue
    return VideoMap(summary=str(raw.get("summary", "")), events=events)


def _sanitize_model_filename(model: str) -> str:
    return model.replace("/", "__").replace(":", "_")


# =============================================================
# Per-model run
# =============================================================


async def bench_one_model(
    *,
    model: str,
    timeout_seconds: float,
    transcript_lines: str,
    video_map: VideoMap,
    campaign: dict[str, Any],
    target_clip_count: int,
    raw_video_read: dict[str, Any],
) -> dict[str, Any]:
    provider = OpenRouterProvider(timeout_seconds=timeout_seconds)
    t0 = time.perf_counter()
    try:
        arcs, tokens = await select_story_arcs(
            provider=provider,
            model=model,
            transcript_lines=transcript_lines,
            video_map=video_map,
            campaign=campaign,
            target_clip_count=target_clip_count,
        )
        latency = time.perf_counter() - t0
        return {
            "model": model,
            "ok": True,
            "error": None,
            "latency_seconds": round(latency, 3),
            "tokens": tokens,
            "arcs": [dataclasses.asdict(a) for a in arcs],
            "raw_video_read": raw_video_read,
        }
    except Exception as exc:  # a failing model must not kill the whole benchmark run
        latency = time.perf_counter() - t0
        return {
            "model": model,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "latency_seconds": round(latency, 3),
            "tokens": 0,
            "arcs": [],
            "raw_video_read": raw_video_read,
        }


def _print_summary_line(result: dict[str, Any]) -> None:
    model = result["model"]
    if result["ok"]:
        arcs = result["arcs"]
        n_arcs = len(arcs)
        n_multi = sum(1 for a in arcs if len(a.get("segments") or []) > 1)
        print(
            f"  OK  {model:<38} arcs={n_arcs:<3} multi_seg={n_multi:<3} "
            f"latency={result['latency_seconds']:>7.2f}s tokens={result['tokens']}"
        )
    else:
        print(
            f"  KO  {model:<38} latency={result['latency_seconds']:>7.2f}s "
            f"error={result['error']}"
        )


# =============================================================
# CLI
# =============================================================

DEFAULT_FIXTURE = (
    "/Users/augustindemeaux/clipfactory-data/bench/"
    "fixture_2221f645-ed0e-47b2-8201-417d7c517a39.json"
)
DEFAULT_OUT = "/Users/augustindemeaux/clipfactory-data/bench/results"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--models",
        required=True,
        help=(
            'Comma-separated OpenRouter model ids, e.g. '
            '"google/gemini-2.5-flash,deepseek/deepseek-chat-v3.2"'
        ),
    )
    p.add_argument(
        "--fixture", default=DEFAULT_FIXTURE, help="Path to the frozen fixture JSON."
    )
    p.add_argument(
        "--out", default=DEFAULT_OUT, help="Directory to write one result JSON per model into."
    )
    p.add_argument(
        "--target-clip-count",
        type=int,
        default=None,
        help="Override fixture's target_clip_count (default: use the fixture's own value).",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Per-request HTTP timeout in seconds passed to OpenRouterProvider (default 120s).",
    )
    return p.parse_args()


async def _main_async(args: argparse.Namespace) -> int:
    fixture_path = Path(args.fixture)
    if not fixture_path.is_file():
        print(f"fixture not found: {fixture_path}", file=sys.stderr)
        return 2
    with fixture_path.open("r", encoding="utf-8") as f:
        fixture = json.load(f)

    transcript_raw = fixture.get("transcript") or {}
    video_map_raw = fixture.get("video_map") or {}
    campaign = fixture.get("campaign") or {}
    transcript_lines = fixture.get("transcript_lines") or ""
    target_clip_count = args.target_clip_count or int(fixture.get("target_clip_count") or 3)

    transcript = _build_transcript(transcript_raw)  # built for validation, see docstring
    video_map = _build_video_map(video_map_raw)

    raw_video_read = {
        "n_events": len(video_map.events),
        "n_events_in_fixture": len(video_map_raw.get("events") or []),
        "video_map_summary_chars": len(video_map.summary),
        "n_transcript_words": len(transcript.words),
        "n_transcript_words_in_fixture": len(transcript_raw.get("words") or []),
        "transcript_lines_chars": len(transcript_lines),
    }

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        print("--models produced no model ids", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"fixture:            {fixture_path}")
    print(f"job_id:             {fixture.get('job_id')}")
    print(f"duration_seconds:   {fixture.get('duration_seconds')}")
    print(f"target_clip_count:  {target_clip_count}")
    print(f"video_map events:   {raw_video_read['n_events']}")
    print(f"transcript words:   {raw_video_read['n_transcript_words']}")
    print(f"models:             {models}")
    print(f"out dir:            {out_dir}")
    print()

    results: list[dict[str, Any]] = []
    for model in models:
        print(f"running {model} ...")
        result = await bench_one_model(
            model=model,
            timeout_seconds=args.timeout,
            transcript_lines=transcript_lines,
            video_map=video_map,
            campaign=campaign,
            target_clip_count=target_clip_count,
            raw_video_read=raw_video_read,
        )
        results.append(result)

        out_file = out_dir / f"{_sanitize_model_filename(model)}.json"
        with out_file.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    print()
    print("=== summary ===")
    for result in results:
        _print_summary_line(result)

    n_ok = sum(1 for r in results if r["ok"])
    print()
    print(f"{n_ok}/{len(results)} models succeeded. Results written to {out_dir}")
    return 0


def main() -> None:
    args = _parse_args()
    sys.exit(asyncio.run(_main_async(args)))


if __name__ == "__main__":
    main()
