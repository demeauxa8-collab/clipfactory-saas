#!/usr/bin/env python3
"""Replay the AUDITED run (bench/results/google__gemini-2.5-flash.json) offline.

Same arcs the diagnosis looked at, same transcript (the fixture's — which has NO
ASR sentences, so this also exercises the ranked-gap fallback on real data).
No LLM call, no cost.

    cd /Users/augustindemeaux/clipfactory-saas/apps/worker
    .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/craft-refs/\
measure_audit_run.py [path/to/result.json]
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models import (  # noqa: E402
    ArcSegmentSpec,
    StoryArc,
    Transcript,
    TranscriptWord,
)
from app.pipeline.boundaries import (  # noqa: E402
    _phrases_from_gaps,
    anchor_arcs_to_transcript,
    snap_arc_segments,
)
from measure_drift import drift_rows, legacy_phrases, legacy_snap, summarize  # noqa: E402

FIXTURE = Path(
    "/Users/augustindemeaux/clipfactory-data/bench/"
    "fixture_2221f645-ed0e-47b2-8201-417d7c517a39.json"
)
DEFAULT_RESULT = Path(
    "/Users/augustindemeaux/clipfactory-data/bench/results/google__gemini-2.5-flash.json"
)


def main() -> int:
    result_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RESULT
    fixture = json.loads(FIXTURE.read_text())
    words = [TranscriptWord(**w) for w in fixture["transcript"]["words"]]
    transcript = Transcript(
        text=fixture["transcript"]["text"],
        words=words,
        language=fixture["transcript"].get("language"),
    )  # no sentences: this is the pre-fix cached transcript

    result = json.loads(result_path.read_text())
    arcs = [
        StoryArc(
            title=a["title"],
            arc_type=a["arc_type"],
            segments=[ArcSegmentSpec(**s) for s in a["segments"]],
            viral_reason=a.get("viral_reason", ""),
            estimated_retention=a.get("estimated_retention", 0),
            continuity_risk=a.get("continuity_risk", "medium"),
            suggested_hook=a.get("suggested_hook"),
            link_reason=a.get("link_reason"),
            campaign_fit_llm=a.get("campaign_fit_llm"),
            campaign_fit_reason=a.get("campaign_fit_reason"),
            opening_words=a.get("opening_words"),
            self_contained=a.get("self_contained", True),
            payoff_line=a.get("payoff_line"),
        )
        for a in result["arcs"]
    ]
    print(f"run: {result_path.name}   arcs={len(arcs)}  words={len(words)}")

    legacy = legacy_phrases(words)
    ranked = _phrases_from_gaps(words)

    def stats(name: str, phrases: list[tuple[int, int]]) -> None:
        durs = sorted(words[b].end - words[a].start for a, b in phrases)
        print(
            f"  {name:<34} phrases={len(phrases):<5} "
            f"median={statistics.median(durs):.2f}s "
            f"p90={durs[int(0.9 * (len(durs) - 1))]:.2f}s max={max(durs):.2f}s"
        )

    print()
    print("PHRASES (no ASR sentences in this cached transcript)")
    stats("BEFORE gap threshold max(.28,p85)", legacy)
    stats("AFTER  ranked-gap fallback", ranked)

    print()
    print("DRIFT")
    before = drift_rows(arcs, words)
    anchored, report = anchor_arcs_to_transcript(arcs, transcript)
    after = drift_rows(anchored, words)
    for b, a in zip(before, after, strict=True):
        print(
            f"  {b['title']:<46}{b['segment']:>3}  start={b['start']:<8} "
            f"quote@={str(b['quote_at']):<8} drift={str(b['drift']):<7}"
            f"->  start={a['start']:<8} drift={a['drift']}"
        )
    print("  " + summarize("BEFORE", before))
    print("  " + summarize("AFTER ", after))
    print(f"  anchored={report.segments_anchored}/{report.segments_seen} "
          f"unmatched={report.segments_unmatched} max_drift={report.max_drift_seconds}")

    print()
    print("SNAP")
    seen = failed = 0
    worst_back = 0.0
    for arc in arcs:
        for seg in arc.segments:
            seen += 1
            s, _e, f = legacy_snap(words, seg.start, seg.end)
            failed += int(f)
            if not f:
                worst_back = min(worst_back, s - seg.start)
    print(f"  BEFORE: {seen - failed}/{seen} aligned, worst backward pull={worst_back:.2f}s")

    snapped, rep = snap_arc_segments(anchored, words)
    back = 0.0
    for a_in, a_out in zip(anchored, snapped, strict=True):
        for si, so in zip(a_in.segments, a_out.segments, strict=True):
            back = min(back, so.start - si.start)
    print(
        f"  AFTER : {rep.segments_seen - rep.segments_failed}/{rep.segments_seen} "
        f"aligned, worst backward pull={back:.2f}s"
    )
    print("  " + summarize("FINAL ", drift_rows(snapped, words)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
