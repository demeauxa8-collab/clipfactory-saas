#!/usr/bin/env python3
"""Provider-reported cost of one arc-selection run, per model.

bench_arcs.py records tokens_in+tokens_out as a single number, which cannot be
turned into dollars (input and output are priced 5-20x apart). This probe
replays the exact same prompt once per model with `usage: {include: true}`, so
OpenRouter returns its own billed cost for that generation - the real price of
one run, not an estimate.

It also answers a second question for models our client cannot call at all:
`--no-reasoning-retry` repeats a failed call without the
`"reasoning": {"max_tokens": 0}` field that OpenRouterProvider always sends, to
tell "this model is bad" apart from "our client asks for something it refuses".

    cd /Users/augustindemeaux/clipfactory-saas/apps/worker
    .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/cost_probe_text.py \
        --models "google/gemini-2.5-flash,..."
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx

_CWD = Path.cwd()
if str(_CWD) not in sys.path:
    sys.path.insert(0, str(_CWD))

from app.models import VideoEvent, VideoMap  # noqa: E402
from app.pipeline.story_arcs import _video_map_to_json  # noqa: E402
from app.prompts import STORY_ARC_SYSTEM_PROMPT, story_arc_user_prompt  # noqa: E402
from app.providers._jsonparse import extract_json  # noqa: E402
from app.settings import get_settings  # noqa: E402

FIXTURE = (
    "/Users/augustindemeaux/clipfactory-data/bench/"
    "fixture_2221f645-ed0e-47b2-8201-417d7c517a39.json"
)


def build_prompt() -> tuple[str, str]:
    fx = json.loads(Path(FIXTURE).read_text(encoding="utf-8"))
    events = []
    for e in fx["video_map"]["events"]:
        events.append(VideoEvent(
            id=str(e.get("id", "")), start=float(e.get("start", 0.0)),
            end=float(e.get("end", 0.0)), decor=str(e.get("decor", "")),
            people=str(e.get("people", "")), objects=list(e.get("objects") or []),
            action=str(e.get("action", "")),
            transcript_summary=str(e.get("transcript_summary", "")),
            visual_importance=int(float(e.get("visual_importance", 0) or 0)),
            narrative_role=str(e.get("narrative_role", "neutral")),
        ))
    vm = VideoMap(summary=str(fx["video_map"].get("summary", "")), events=events)
    user = story_arc_user_prompt(
        transcript_lines=fx["transcript_lines"],
        video_map_json=_video_map_to_json(vm),
        campaign=fx["campaign"],
        target_clip_count=int(fx.get("target_clip_count") or 3),
        duration_seconds=int(fx["duration_seconds"]),
        video_summary=vm.summary,
        language=None,
    )
    return STORY_ARC_SYSTEM_PROMPT, user


async def one_call(model: str, system: str, user: str, *, reasoning: bool) -> dict[str, Any]:
    s = get_settings()
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": 8192,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "usage": {"include": True},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    if reasoning:
        body["reasoning"] = {"max_tokens": 0}
    headers = {"Authorization": f"Bearer {s.openrouter_api_key}",
               "HTTP-Referer": s.openrouter_http_referer,
               "X-Title": s.openrouter_app_name,
               "Content-Type": "application/json"}
    async with httpx.AsyncClient(base_url=s.openrouter_base_url, timeout=300.0,
                                 headers=headers) as client:
        r = await client.post("/chat/completions", json=body)
    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "error": r.text[:300]}
    data = r.json()
    usage = data.get("usage") or {}
    text = ""
    choices = data.get("choices") or []
    if choices:
        content = (choices[0].get("message") or {}).get("content")
        text = "".join(c.get("text", "") for c in content if isinstance(c, dict)) \
            if isinstance(content, list) else str(content or "")
    try:
        payload = extract_json(text)
        n_arcs = len(payload.get("arcs") or []) if isinstance(payload, dict) else 0
        parsed = True
    except Exception:
        n_arcs, parsed = 0, False
    return {"ok": True, "provider": data.get("provider"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "cost": usage.get("cost"),
            "parsed_first_try": parsed, "n_arcs_raw": n_arcs}


async def main_async(models: list[str], retry_no_reasoning: bool, out: Path) -> int:
    system, user = build_prompt()
    print(f"prompt: system={len(system)} chars, user={len(user)} chars\n")
    print(f"{'model':<32}{'cost$':>10}{'in_tok':>9}{'out_tok':>9}{'arcs':>6}  provider")
    rows = []
    for m in models:
        r = await one_call(m, system, user, reasoning=True)
        if not r["ok"] and retry_no_reasoning:
            r2 = await one_call(m, system, user, reasoning=False)
            r["retry_without_reasoning"] = r2
        rows.append({"model": m, **r})
        if r["ok"]:
            print(f"{m:<32}{(r['cost'] or 0):>10.5f}{r['prompt_tokens']:>9}"
                  f"{r['completion_tokens']:>9}{r['n_arcs_raw']:>6}  {r['provider']}")
        else:
            note = ""
            r2 = r.get("retry_without_reasoning")
            if r2 and r2.get("ok"):
                note = (f"  -> WORKS without reasoning:{{max_tokens:0}}: "
                        f"cost={r2['cost']:.5f}$ arcs={r2['n_arcs_raw']}")
            print(f"{m:<32}   HTTP {r['status']}  {r['error'][:90]}{note}")
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwritten: {out}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models", required=True)
    p.add_argument("--no-reasoning-retry", action="store_true", default=True)
    p.add_argument("--out", default="/Users/augustindemeaux/clipfactory-data/bench/results/"
                                    "text-cost-2026-08-08.json")
    a = p.parse_args()
    sys.exit(asyncio.run(main_async([m.strip() for m in a.models.split(",") if m.strip()],
                                    a.no_reasoning_retry, Path(a.out))))


if __name__ == "__main__":
    main()
