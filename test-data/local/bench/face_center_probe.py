#!/usr/bin/env python3
"""Per-frame face_center_x accuracy, against a hand-read ground truth.

deep_vision_for_arc() sends 5 frames at once and gets a single averaged
face_center_x back, so a disagreement between two models is impossible to
attribute. This probe sends ONE real frame per call, with the worker's own deep
vision prompt, and compares the answer to a position read off the picture by
hand (tolerance +/-0.06 of frame width). face_center_x drives the 9:16 re-crop:
an error of 0.2 puts the speaker's head against the edge of the clip.

Ground truth was read on the 512x288 frames extracted by ffmpeg.extract_frame
from the fixture's source video.

    cd /Users/augustindemeaux/clipfactory-saas/apps/worker
    .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/face_center_probe.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

_CWD = Path.cwd()
if str(_CWD) not in sys.path:
    sys.path.insert(0, str(_CWD))

from app.prompts import DEEP_VISION_SYSTEM_PROMPT, deep_vision_user_prompt  # noqa: E402
from app.providers.base import ImageInput  # noqa: E402
from app.providers.openrouter import OpenRouterProvider  # noqa: E402

DIR = Path("/Users/augustindemeaux/clipfactory-data/bench/face-probe")

# frame -> (hand-read face_center_x, what the frame shows)
GROUND_TRUTH: dict[str, tuple[float, str]] = {
    "f_30.jpg":  (0.48, "talking head, balcony, holding a coin"),
    "f_95.jpg":  (0.41, "talking head, parking garage, slightly left"),
    "f_210.jpg": (0.13, "Google page + small webcam inset bottom-left"),
    "f_355.jpg": (0.54, "talking head, apartment, slightly right"),
    "f_505.jpg": (0.08, "Shopify dashboard + small webcam inset bottom-left"),
    "f_560.jpg": (0.43, "talking head, bedroom, left of centre"),
}
TOLERANCE = 0.06


async def probe(model: str, name: str) -> dict[str, Any]:
    provider = OpenRouterProvider(timeout_seconds=120.0)
    img = ImageInput(bytes_jpeg=(DIR / name).read_bytes())
    try:
        res = await provider.vision_json(
            model=model,
            system=DEEP_VISION_SYSTEM_PROMPT,
            user_text=deep_vision_user_prompt(
                segment_context=f"role=single, source_seconds=[0.0, 1.0], excerpt: (single frame probe)"
            ),
            images=[img],
            max_tokens=512,
            temperature=0.2,
        )
    except Exception as exc:
        return {"frame": name, "error": f"{type(exc).__name__}: {exc}"}
    p = res.payload if isinstance(res.payload, dict) else {}
    return {
        "frame": name,
        "face_center_x": p.get("face_center_x"),
        "person_visible": p.get("person_visible"),
        "decor": p.get("decor"),
        "tokens": res.tokens_total,
        "tokens_in": res.tokens_in,
        "tokens_out": res.tokens_out,
    }


async def main_async(models: list[str], out: Path) -> int:
    all_rows: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        rows = [await probe(model, name) for name in GROUND_TRUTH]
        all_rows[model] = rows
        errs, hits, tok_in, tok_out = [], 0, 0, 0
        print(f"\n{model}")
        print(f"  {'frame':<12}{'truth':>7}{'model':>8}{'err':>7}  decor")
        for r in rows:
            truth = GROUND_TRUTH[r["frame"]][0]
            v = r.get("face_center_x")
            tok_in += r.get("tokens_in") or 0
            tok_out += r.get("tokens_out") or 0
            if v is None:
                print(f"  {r['frame']:<12}{truth:>7.2f}{'null':>8}{'-':>7}  "
                      f"{r.get('decor')}  {r.get('error','')}")
                continue
            err = abs(float(v) - truth)
            errs.append(err)
            hits += err <= TOLERANCE
            print(f"  {r['frame']:<12}{truth:>7.2f}{float(v):>8.2f}{err:>7.2f}  {r.get('decor')}")
        if errs:
            print(f"  -> within +/-{TOLERANCE}: {hits}/{len(GROUND_TRUTH)}   "
                  f"mean_abs_err={sum(errs)/len(errs):.3f}   max={max(errs):.2f}   "
                  f"tokens_in={tok_in} tokens_out={tok_out}")
    out.write_text(json.dumps({"ground_truth": GROUND_TRUTH, "results": all_rows},
                              indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwritten: {out}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models", default="qwen/qwen3-vl-32b-instruct,google/gemini-2.5-flash")
    p.add_argument("--out", default="/Users/augustindemeaux/clipfactory-data/bench/results/"
                                    "face-center-probe-2026-08-08.json")
    args = p.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    sys.exit(asyncio.run(main_async(models, Path(args.out))))


if __name__ == "__main__":
    main()
