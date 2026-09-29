#!/usr/bin/env python3
"""Real-frame A/B check for the vision model switch (gemini-2.5-flash -> qwen3-vl-32b).

Runs the worker's OWN vision code paths (app.pipeline.video_map.build_video_map and
app.pipeline.vision.deep_vision_for_arc) on the real source video of the frozen
fixture, once per model, and prints what a regression would break:

  1. frame geometry  - proves ffmpeg.extract_frame downscales (Qwen bills by
     resolution, so the whole cost argument rests on this)
  2. deep vision     - per-segment JSON parse + face_center_x, the value that
     drives the vertical crop; the two models are compared frame-for-frame
  3. video map       - event count and how many distinct objects get named

Must be run from apps/worker with its venv:

    cd /Users/augustindemeaux/clipfactory-saas/apps/worker
    .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/verify_vision_switch.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_CWD = Path.cwd()
if str(_CWD) not in sys.path:
    sys.path.insert(0, str(_CWD))

from app.models import ArcSegmentSpec, StoryArc, Transcript, VideoEvent, VideoMap  # noqa: E402
from app.pipeline.ffmpeg import extract_frame  # noqa: E402
from app.pipeline.video_map import build_video_map  # noqa: E402
from app.pipeline.vision import deep_vision_for_arc  # noqa: E402
from app.providers.openrouter import OpenRouterProvider  # noqa: E402
from app.settings import get_settings  # noqa: E402

FIXTURE = (
    "/Users/augustindemeaux/clipfactory-data/bench/"
    "fixture_2221f645-ed0e-47b2-8201-417d7c517a39.json"
)
SOURCE = (
    "/Users/augustindemeaux/clipfactory-data/bench/source/"
    "2221f645-ed0e-47b2-8201-417d7c517a39/source.mp4"
)
# Live OpenRouter prices, $/token (in, out), fetched 2026-08-08.
PRICES = {
    "qwen/qwen3-vl-32b-instruct": (0.104e-6, 0.416e-6),
    "google/gemini-2.5-flash": (0.30e-6, 2.50e-6),
}


def _probe_dims(path: str) -> tuple[int, int]:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", path,
        ],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    w, h = out.split("x")[:2]
    return int(w), int(h)


def _cost(model: str, tokens_in: int, tokens_out: int) -> float:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    return tokens_in * pin + tokens_out * pout


# =============================================================
# 1. frame geometry
# =============================================================


async def check_frames(workdir: str) -> list[dict[str, Any]]:
    rows = []
    for ts in (12.0, 180.0, 470.0):
        out = str(Path(workdir) / f"geo_{int(ts)}.jpg")
        await extract_frame(SOURCE, ts, out)
        w, h = _probe_dims(out)
        rows.append({"ts": ts, "path": out, "w": w, "h": h,
                     "kb": round(Path(out).stat().st_size / 1024, 1)})
    src_w, src_h = _probe_dims(SOURCE)
    print(f"source geometry          : {src_w}x{src_h}")
    for r in rows:
        print(f"  extracted frame @{r['ts']:>6.1f}s : {r['w']}x{r['h']}  {r['kb']} kB  -> {r['path']}")
    return rows


# =============================================================
# 2. deep vision, same segments, both models
# =============================================================


def _arc_from_fixture(fixture: dict[str, Any]) -> StoryArc:
    """Build a 2-segment arc out of two real video_map events (a talking-head
    stretch and a screen-capture stretch), so deep vision sees genuinely
    different visual material in one call sequence."""
    events = [VideoEvent(**{k: e[k] for k in
                            ("id", "start", "end", "decor", "people", "objects",
                             "action", "transcript_summary", "visual_importance",
                             "narrative_role") if k in e})
              for e in fixture["video_map"]["events"]]
    picked = [e for e in events if (e.end - e.start) >= 6][:40]
    head = picked[1]
    tail = picked[-2]
    return StoryArc(
        title="vision regression probe",
        arc_type="proof",
        segments=[
            ArcSegmentSpec(role="setup", start=head.start, end=min(head.start + 12, head.end),
                           transcript_excerpt=head.transcript_summary[:200]),
            ArcSegmentSpec(role="payoff", start=tail.start, end=min(tail.start + 12, tail.end),
                           transcript_excerpt=tail.transcript_summary[:200]),
        ],
        viral_reason="n/a - regression probe",
        estimated_retention=50,
        continuity_risk="low",
    )


async def run_deep_vision(model: str, arc: StoryArc, workdir: str) -> dict[str, Any]:
    provider = OpenRouterProvider(timeout_seconds=180.0)
    wd = Path(workdir) / model.replace("/", "__")
    wd.mkdir(parents=True, exist_ok=True)
    segs, frames, tokens = await deep_vision_for_arc(
        provider=provider, model=model, source_path=SOURCE, arc=arc,
        workdir=str(wd), arc_idx=0,
    )
    rows = []
    for sv in segs:
        v = sv.vision
        rows.append({
            "segment_idx": sv.segment_idx,
            "frames_used": sv.frames_used,
            "parsed": v is not None,
            "decor": v.decor if v else None,
            "person_visible": v.person_visible if v else None,
            "face_center_x": v.face_center_x if v else None,
            "energy": v.energy if v else None,
            "visual_score": v.visual_score if v else None,
            "proof_objects": v.proof_objects if v else [],
            "burned_captions": v.burned_captions if v else None,
            "tokens_used": sv.tokens_used,
        })
    return {"model": model, "segments": rows, "frames": frames, "tokens": tokens}


# =============================================================
# 3. video map
# =============================================================


async def run_video_map(model: str, fixture: dict[str, Any], workdir: str) -> dict[str, Any]:
    provider = OpenRouterProvider(timeout_seconds=180.0)
    wd = Path(workdir) / ("map_" + model.replace("/", "__"))
    wd.mkdir(parents=True, exist_ok=True)
    transcript = Transcript(text=fixture["transcript"]["text"], words=[],
                            language=fixture["transcript"].get("language"))
    vm, frames, tokens = await build_video_map(
        provider=provider, model=model, source_path=SOURCE,
        duration_seconds=int(fixture["duration_seconds"]),
        transcript=transcript, workdir=str(wd),
    )
    objects = sorted({o.strip().lower() for e in vm.events for o in e.objects if o.strip()})
    decors = sorted({e.decor.strip().lower() for e in vm.events if e.decor.strip()})
    return {
        "model": model, "n_events": len(vm.events), "frames": frames, "tokens": tokens,
        "n_distinct_objects": len(objects), "objects": objects,
        "n_distinct_decors": len(decors), "decors": decors,
        "summary": vm.summary[:400],
        "n_events_out_of_range": sum(
            1 for e in vm.events if e.start < 0 or e.end > fixture["duration_seconds"] + 1
        ),
    }


async def main_async(args: argparse.Namespace) -> int:
    fixture = json.loads(Path(FIXTURE).read_text(encoding="utf-8"))
    s = get_settings()
    print(f"configured vision_cheap_model       : {s.vision_cheap_model}")
    print(f"configured primary_vision_deep_model: {s.primary_vision_deep_model}")
    print()

    workdir = args.workdir or tempfile.mkdtemp(prefix="visioncheck_")
    Path(workdir).mkdir(parents=True, exist_ok=True)
    print(f"workdir: {workdir}\n")

    print("=== 1. frame geometry (Qwen bills by resolution) ===")
    await check_frames(workdir)
    print()

    models = [m.strip() for m in args.models.split(",") if m.strip()]

    print("=== 2. deep vision, identical segments ===")
    arc = _arc_from_fixture(fixture)
    for sg in arc.segments:
        print(f"  segment {sg.role}: [{sg.start:.1f} -> {sg.end:.1f}]")
    deep: list[dict[str, Any]] = []
    for m in models:
        try:
            r = await run_deep_vision(m, arc, workdir)
        except Exception as exc:  # a failing model is a result, not an incident
            r = {"model": m, "error": f"{type(exc).__name__}: {exc}", "segments": [],
                 "frames": 0, "tokens": 0}
        deep.append(r)
        if r.get("error"):
            print(f"  KO {m}: {r['error']}")
            continue
        n_seg = max(1, len(r["segments"]))
        c = _cost(m, r["tokens"], 0)  # tokens_total; in-heavy, see note in the doc
        print(f"  {m}  tokens={r['tokens']}  frames={r['frames']}  "
              f"cost~{c:.6f}$  per_segment~{c / n_seg:.6f}$")
        for row in r["segments"]:
            print(f"      seg{row['segment_idx']} parsed={row['parsed']} "
                  f"person={row['person_visible']} face_x={row['face_center_x']} "
                  f"decor={row['decor']!r} score={row['visual_score']} "
                  f"objects={row['proof_objects']}")
    print()

    if len(deep) == 2 and all(not d.get("error") for d in deep):
        print("  face_center_x delta between the two models:")
        for a, b in zip(deep[0]["segments"], deep[1]["segments"]):
            fa, fb = a["face_center_x"], b["face_center_x"]
            d = None if (fa is None or fb is None) else round(abs(fa - fb), 3)
            print(f"      seg{a['segment_idx']}: {deep[0]['model']}={fa}  "
                  f"{deep[1]['model']}={fb}  |delta|={d}")
        print()

    maps: list[dict[str, Any]] = []
    if args.video_map:
        print("=== 3. video map (full 595 s pass) ===")
        for m in models:
            try:
                r = await run_video_map(m, fixture, workdir)
            except Exception as exc:
                r = {"model": m, "error": f"{type(exc).__name__}: {exc}"}
            maps.append(r)
            if r.get("error"):
                print(f"  KO {m}: {r['error']}")
                continue
            print(f"  {m}  events={r['n_events']}  frames={r['frames']}  "
                  f"tokens={r['tokens']}  cost~{_cost(m, r['tokens'], 0):.5f}$  "
                  f"distinct_objects={r['n_distinct_objects']}  "
                  f"distinct_decors={r['n_distinct_decors']}  "
                  f"out_of_range_events={r['n_events_out_of_range']}")
            print(f"      objects: {r['objects']}")
        print()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"deep_vision": deep, "video_map": maps,
                               "workdir": workdir}, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"written: {out}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models", default="qwen/qwen3-vl-32b-instruct,google/gemini-2.5-flash")
    p.add_argument("--video-map", action="store_true", help="also run the full video_map pass")
    p.add_argument("--workdir", default=None)
    p.add_argument("--out", default="/Users/augustindemeaux/clipfactory-data/bench/results/"
                                    "vision-switch-2026-08-08.json")
    sys.exit(asyncio.run(main_async(p.parse_args())))


if __name__ == "__main__":
    main()
