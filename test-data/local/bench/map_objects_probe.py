#!/usr/bin/env python3
"""Video-map object naming, on six frames whose content is known.

The full video_map pass shows qwen3-vl-32b naming far more objects than
gemini-2.5-flash, which is only good news if the extra names are real. This
probe runs the worker's own VIDEO_MAP prompt on six frames that were inspected
by hand, so every returned object can be marked present or invented.

    cd /Users/augustindemeaux/clipfactory-saas/apps/worker
    .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/map_objects_probe.py
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

from app.prompts import VIDEO_MAP_SYSTEM_PROMPT, video_map_user_prompt  # noqa: E402
from app.providers.base import ImageInput  # noqa: E402
from app.providers.openrouter import OpenRouterProvider  # noqa: E402

DIR = Path("/Users/augustindemeaux/clipfactory-data/bench/face-probe")
FRAMES = [
    (30.0, "f_30.jpg"),    # balcony, towers, palms, coin in hand
    (95.0, "f_95.jpg"),    # underground car park, cars, red pipes
    (210.0, "f_210.jpg"),  # Google home page + webcam inset (apartment)
    (355.0, "f_355.jpg"),  # bright apartment, TV, glass partitions
    (505.0, "f_505.jpg"),  # Shopify analytics dashboard + webcam inset
    (560.0, "f_560.jpg"),  # bedroom, office chair, curtains
]
TRANSCRIPT_SUMMARY = (
    "Gaspar tente de lancer une boutique dropshipping rentable avec un seul euro "
    "en 24 heures : il gagne son budget pub, choisit un produit, lance Google Ads "
    "et fait une premiere vente."
)


async def run(model: str) -> dict[str, Any]:
    provider = OpenRouterProvider(timeout_seconds=180.0)
    images = [ImageInput(bytes_jpeg=(DIR / n).read_bytes(), label=f"{ts:.1f}s")
              for ts, n in FRAMES]
    res = await provider.vision_json(
        model=model,
        system=VIDEO_MAP_SYSTEM_PROMPT,
        user_text=video_map_user_prompt(
            duration_seconds=595,
            transcript_summary=TRANSCRIPT_SUMMARY,
            frame_timestamps=[ts for ts, _ in FRAMES],
        ),
        images=images,
        max_tokens=4096,
        temperature=0.2,
    )
    return {"model": model, "payload": res.payload,
            "tokens_in": res.tokens_in, "tokens_out": res.tokens_out}


async def main_async(models: list[str], out: Path) -> int:
    results = []
    for m in models:
        try:
            r = await run(m)
        except Exception as exc:
            print(f"{m}: KO {type(exc).__name__}: {exc}")
            continue
        results.append(r)
        events = (r["payload"] or {}).get("events") or []
        print(f"\n{m}   events={len(events)}  tokens_in={r['tokens_in']} tokens_out={r['tokens_out']}")
        for e in events:
            print(f"  [{e.get('start')}-{e.get('end')}] decor={e.get('decor')!r} "
                  f"people={e.get('people')!r}")
            print(f"      objects: {e.get('objects')}")
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwritten: {out}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models", default="qwen/qwen3-vl-32b-instruct,google/gemini-2.5-flash")
    p.add_argument("--out", default="/Users/augustindemeaux/clipfactory-data/bench/results/"
                                    "map-objects-probe-2026-08-08.json")
    args = p.parse_args()
    sys.exit(asyncio.run(main_async([m.strip() for m in args.models.split(",")], Path(args.out))))


if __name__ == "__main__":
    main()
