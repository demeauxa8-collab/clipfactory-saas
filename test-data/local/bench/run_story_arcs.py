"""Throwaway bench: run select_story_arcs on the frozen fixture with a real provider.

Usage (from the worker dir so .env resolves):
    cd /Users/augustindemeaux/clipfactory-saas/apps/worker
    .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/run_story_arcs.py [model]
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

WORKER = "/Users/augustindemeaux/clipfactory-saas/apps/worker"
os.chdir(WORKER)
sys.path.insert(0, WORKER)

FIXTURE = (
    "/Users/augustindemeaux/clipfactory-data/bench/"
    "fixture_2221f645-ed0e-47b2-8201-417d7c517a39.json"
)

from app.models import Transcript, TranscriptWord, VideoEvent, VideoMap  # noqa: E402
from app.pipeline.story_arcs import select_story_arcs  # noqa: E402
from app.pipeline.verify import verify_arc  # noqa: E402
from app.providers import OpenRouterProvider  # noqa: E402

BANNED = (
    "et", "mais", "donc", "alors", "puis", "car", "parce", "vu", "du coup",
    "en fait", "en vrai", "en plus", "par contre", "d'ailleurs", "d’ailleurs",
    "voilà", "bref", "bon", "ben", "genre", "enfin", "après", "ensuite", "ça",
    "cette", "ce ",
)


def opener_flag(words: str | None) -> str:
    if not words:
        return "NO-OPENING"
    low = words.strip().lower()
    for b in BANNED:
        if low.startswith(b):
            return f"BAD-OPENER({b})"
    return "ok"

MODEL = sys.argv[1] if len(sys.argv) > 1 else "google/gemini-2.5-flash"


class Capturing(OpenRouterProvider):
    """Same provider, but keeps the raw parsed payload for inspection."""

    def __init__(self) -> None:
        super().__init__(timeout_seconds=300.0)
        self.last_payload = None

    async def chat_json(self, **kw):  # type: ignore[override]
        res = await super().chat_json(**kw)
        self.last_payload = res.payload
        return res


def load_fixture() -> dict:
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def build_video_map(d: dict) -> VideoMap:
    vm = d["video_map"]
    return VideoMap(
        summary=vm.get("summary", ""),
        events=[
            VideoEvent(
                id=e.get("id", f"evt_{i:03d}"),
                start=float(e.get("start", 0)),
                end=float(e.get("end", 0)),
                decor=e.get("decor", ""),
                people=e.get("people", ""),
                objects=list(e.get("objects") or []),
                action=e.get("action", ""),
                transcript_summary=e.get("transcript_summary", ""),
                visual_importance=int(e.get("visual_importance", 0)),
                narrative_role=e.get("narrative_role", "neutral"),
            )
            for i, e in enumerate(vm.get("events") or [])
        ],
    )


def ts(v: float) -> str:
    return f"{int(v) // 60}:{int(v) % 60:02d}"


async def main() -> None:
    d = load_fixture()
    video_map = build_video_map(d)
    provider = Capturing()

    kwargs = dict(
        provider=provider,
        model=MODEL,
        transcript_lines=d["transcript_lines"],
        video_map=video_map,
        campaign=d["campaign"],
        target_clip_count=d.get("target_clip_count", 3),
    )
    # New optional context args — ignored by the old signature.
    import inspect

    params = inspect.signature(select_story_arcs).parameters
    if "duration_seconds" in params:
        kwargs["duration_seconds"] = d.get("duration_seconds")
    if "language" in params:
        kwargs["language"] = (d.get("transcript") or {}).get("language")

    try:
        arcs, tokens = await select_story_arcs(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001 - bench script
        print(f"!! select_story_arcs failed: {exc}")
        arcs, tokens = [], 0

    payload = provider.last_payload if isinstance(provider.last_payload, dict) else {}
    print("=" * 78)
    print(f"MODEL {MODEL}  tokens={tokens}  arcs_kept={len(arcs)} "
          f"raw_arcs={len(payload.get('arcs') or [])}")
    print("=" * 78)
    vr = payload.get("video_read")
    if vr:
        print("\nVIDEO_READ:\n" + str(vr) + "\n")

    tr = Transcript(
        text=(d.get("transcript") or {}).get("text", ""),
        words=[
            TranscriptWord(word=w["word"], start=float(w["start"]), end=float(w["end"]))
            for w in (d.get("transcript") or {}).get("words", [])
        ],
        language=(d.get("transcript") or {}).get("language"),
    )

    n_verified = 0
    n_bad_open = 0
    for i, a in enumerate(arcs, 1):
        total = sum(s.end - s.start for s in a.segments)
        ok, ratios = verify_arc(tr, a)
        n_verified += int(ok)
        flag = opener_flag(getattr(a, "opening_words", None))
        n_bad_open += int(flag != "ok")
        print("-" * 78)
        print(f"[{i}] {a.title}")
        print(f"    type={a.arc_type} segs={len(a.segments)} total={total:.1f}s "
              f"fit={a.campaign_fit_llm} retention={a.estimated_retention} "
              f"risk={a.continuity_risk}")
        print(f"    VERIFY        : {'PASS' if ok else 'FAIL'} ratios={ratios}")
        print(f"    OPENER        : {flag}")
        print(f"    opening_words : {getattr(a, 'opening_words', None)!r}")
        print(f"    self_contained: {getattr(a, 'self_contained', None)!r}")
        print(f"    payoff_line   : {getattr(a, 'payoff_line', None)!r}")
        print(f"    hook          : {a.suggested_hook!r}")
        print(f"    viral_reason  : {a.viral_reason}")
        print(f"    link_reason   : {a.link_reason}")
        print(f"    campaign_fit  : {a.campaign_fit_reason}")
        for s in a.segments:
            print(f"      - {s.role:9s} {ts(s.start)}->{ts(s.end)} "
                  f"({s.end - s.start:.1f}s) why={s.why}")
            print(f"        « {s.transcript_excerpt[:170]} »")

    print("\n" + "=" * 78)
    print(f"SCORECARD  raw={len(payload.get('arcs') or [])} kept={len(arcs)} "
          f"verify_pass={n_verified}/{len(arcs)} bad_openers={n_bad_open}/{len(arcs)} "
          f"multi={sum(1 for a in arcs if len(a.segments) > 1)}")
    print("=" * 78)

    out = f"/tmp/bench_story_arcs_{MODEL.replace('/', '_')}.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"\nraw payload -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
