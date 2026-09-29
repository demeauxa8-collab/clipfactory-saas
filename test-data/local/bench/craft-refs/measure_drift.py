#!/usr/bin/env python3
"""BEFORE/AFTER measurement of the transcript-anchoring fix, on real data.

Replays one real selection call (google/gemini-2.5-flash) on the bench fixture,
keeps the RAW payload, and runs the exact audit the diagnosis ran:

  * where do the words the model quoted actually start, versus the start it
    declared (drift), before and after anchoring;
  * how many phrase boundaries the transcript yields (legacy gap threshold vs
    ASR sentences vs the new ranked-gap fallback);
  * how many segments the snapper could align;
  * how many arcs died on the 12s floor and how many are repaired;
  * how many payoff lines fall outside the clip.

The drift measurement is deliberately INDEPENDENT of the production code: it
searches the whole transcript, with its own matcher, so a wrong anchor shows up
as residual drift instead of being hidden.

    cd /Users/augustindemeaux/clipfactory-saas/apps/worker
    .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/craft-refs/\
measure_drift.py [--reuse]
"""

from __future__ import annotations

import asyncio
import json
import math
import statistics
import sys
from dataclasses import asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # bench_arcs.py

from app.models import (  # noqa: E402
    StoryArc,
    Transcript,
    TranscriptSentence,
    TranscriptWord,
)
from app.pipeline.boundaries import (  # noqa: E402
    _phrases_from_gaps,
    _phrases_from_sentences,
    anchor_arcs_to_transcript,
    build_phrase_index,
    snap_arc_segments,
)
from app.pipeline.story_arcs import _parse_arcs, _video_map_to_json  # noqa: E402
from app.pipeline.transcribe import transcript_to_timestamped_lines  # noqa: E402
from app.pipeline.verify import verify_arcs  # noqa: E402
from app.prompts import STORY_ARC_SYSTEM_PROMPT, story_arc_user_prompt  # noqa: E402
from app.providers.openrouter import OpenRouterProvider  # noqa: E402
from bench_arcs import _build_video_map  # noqa: E402

HERE = Path(__file__).parent
FIXTURE = Path(
    "/Users/augustindemeaux/clipfactory-data/bench/"
    "fixture_2221f645-ed0e-47b2-8201-417d7c517a39.json"
)
TRANSCRIPT = HERE / "transcript_with_sentences.json"
PAYLOAD = HERE / "raw_payload_gemini.json"
MODEL = "google/gemini-2.5-flash"


# =============================================================
# Legacy boundary detection (the code as it was before the fix)
# =============================================================


def legacy_percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo, hi = math.floor(rank), math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


def legacy_phrases(words: list[TranscriptWord]) -> list[tuple[int, int]]:
    gaps = [max(0.0, words[i + 1].start - words[i].end) for i in range(len(words) - 1)]
    threshold = max(0.28, legacy_percentile(gaps, 85.0))
    out: list[tuple[int, int]] = []
    start = 0
    for i in range(len(words) - 1):
        if words[i + 1].start - words[i].end >= threshold:
            out.append((start, i))
            start = i + 1
    out.append((start, len(words) - 1))
    return out


def legacy_snap(
    words: list[TranscriptWord], start: float, end: float
) -> tuple[float, float, bool]:
    """The pre-fix snap: phrase-start recede + 8s minimum duration."""
    phrases = legacy_phrases(words)
    idx = 0
    for pi, (first, _last) in enumerate(phrases):
        if words[first].start <= start:
            idx = pi
        else:
            break
    first, last = phrases[idx]
    p_start, p_end = words[first].start, words[last].end
    if start <= p_start + (p_end - p_start) / 3.0:
        start_word = first
    elif idx + 1 < len(phrases):
        start_word = phrases[idx + 1][0]
    else:
        start_word = first
    start_time = words[start_word].start

    max_end = min(end + 8.0, start_time + 45.0)
    end_word = None
    for _f, last_i in phrases:
        if words[last_i].end <= start_time:
            continue
        if end - 0.5 <= words[last_i].end <= max_end:
            end_word = last_i
            break
    if end_word is None:
        for _f, last_i in phrases:
            if start_time < words[last_i].end <= max_end:
                end_word = last_i
    if end_word is None or end_word < start_word:
        return start, end, True
    snapped_start = max(0.0, start_time - 0.12)
    snapped_end = words[end_word].end + 0.22
    if not (8.0 <= snapped_end - snapped_start <= 50.0):
        return start, end, True
    return snapped_start, snapped_end, False


# =============================================================
# Independent drift measurement
# =============================================================


def norm(text: str) -> str:
    return " ".join("".join(c if c.isalnum() else " " for c in text.lower()).split())


def locate_globally(
    words: list[TranscriptWord], query: str, *, n_words: int = 8
) -> tuple[float, float, float] | None:
    """Best match for the first n_words of `query` over the WHOLE transcript.

    Returns (start_time, end_time, ratio). No tolerance window, no reuse of the
    production matcher's bounds: this is the referee, not the player.
    """
    q = " ".join(norm(query).split()[:n_words])
    if len(q) < 8:
        return None
    normalized = [norm(w.word) for w in words]
    best: tuple[float, int, int] | None = None
    for i in range(len(words)):
        parts, total, j = [], 0, i
        while j < len(words) and total < len(q):
            if normalized[j]:
                parts.append(normalized[j])
                total += len(normalized[j]) + 1
            j += 1
        if not parts:
            continue
        ratio = SequenceMatcher(None, q, " ".join(parts)).ratio()
        if best is None or ratio > best[0]:
            best = (ratio, i, max(i, j - 1))
    if best is None or best[0] < 0.7:
        return None
    return words[best[1]].start, words[best[2]].end, best[0]


def drift_rows(arcs: list[StoryArc], words: list[TranscriptWord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arc in arcs:
        for i, seg in enumerate(arc.segments):
            quote = seg.transcript_excerpt or (arc.opening_words if i == 0 else "")
            found = locate_globally(words, quote or "")
            rows.append(
                {
                    "title": arc.title[:44],
                    "segment": i,
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "quote_at": round(found[0], 2) if found else None,
                    "drift": round(found[0] - seg.start, 2) if found else None,
                    "ratio": round(found[2], 2) if found else None,
                }
            )
    return rows


def payoff_rows(arcs: list[StoryArc], words: list[TranscriptWord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arc in arcs:
        if not arc.payoff_line or not arc.segments:
            continue
        found = locate_globally(words, arc.payoff_line, n_words=12)
        last = arc.segments[-1]
        rows.append(
            {
                "title": arc.title[:44],
                "payoff_end": round(found[1], 2) if found else None,
                "clip_end": round(last.end, 2),
                "inside": bool(found and found[1] <= last.end + 1e-6),
                "found": bool(found),
            }
        )
    return rows


# =============================================================
# Run
# =============================================================


async def get_payload(transcript: Transcript, fixture: dict[str, Any]) -> Any:
    if PAYLOAD.is_file():
        return json.loads(PAYLOAD.read_text())
    video_map = _build_video_map(fixture["video_map"])
    user = story_arc_user_prompt(
        transcript_lines=transcript_to_timestamped_lines(transcript),
        video_map_json=_video_map_to_json(video_map),
        campaign=fixture["campaign"],
        target_clip_count=int(fixture.get("target_clip_count") or 3),
        duration_seconds=int(fixture.get("duration_seconds") or 0),
        video_summary=video_map.summary,
        language=transcript.language,
    )
    provider = OpenRouterProvider(timeout_seconds=180.0)
    result = await provider.chat_json(
        model=MODEL,
        system=STORY_ARC_SYSTEM_PROMPT,
        user=user,
        max_tokens=8192,
        temperature=0.3,
    )
    PAYLOAD.write_text(json.dumps(result.payload, ensure_ascii=False, indent=2))
    return result.payload


def summarize(label: str, rows: list[dict[str, Any]]) -> str:
    drifts = [abs(r["drift"]) for r in rows if r["drift"] is not None]
    if not drifts:
        return f"{label}: no measurable segment"
    over = sum(1 for d in drifts if d > 1.0)
    return (
        f"{label}: n={len(drifts)} median={statistics.median(drifts):.2f}s "
        f"mean={statistics.mean(drifts):.2f}s max={max(drifts):.2f}s "
        f"segments_off_by_more_than_1s={over}/{len(drifts)}"
    )


async def main() -> int:
    fixture = json.loads(FIXTURE.read_text())
    raw = json.loads(TRANSCRIPT.read_text())
    transcript = Transcript(
        text=raw["text"],
        words=[TranscriptWord(**w) for w in raw["words"]],
        language=raw.get("language"),
        sentences=[TranscriptSentence(**s) for s in raw.get("sentences") or []],
    )
    words = transcript.words

    print("=" * 78)
    print("1. PHRASE BOUNDARIES")
    print("=" * 78)
    legacy = legacy_phrases(words)
    gaps_new = _phrases_from_gaps(words)
    sent = _phrases_from_sentences(words, transcript.sentences)

    def stats(name: str, phrases: list[tuple[int, int]]) -> None:
        durs = sorted(words[b].end - words[a].start for a, b in phrases)
        print(
            f"  {name:<34} phrases={len(phrases):<5} "
            f"median={statistics.median(durs):.2f}s "
            f"p90={durs[int(0.9 * (len(durs) - 1))]:.2f}s max={max(durs):.2f}s"
        )

    print(f"  words={len(words)}  asr_sentences={len(transcript.sentences)}")
    stats("BEFORE gap threshold max(.28,p85)", legacy)
    stats("AFTER  ASR sentences", sent)
    stats("AFTER  ranked-gap fallback", gaps_new)

    payload = await get_payload(transcript, fixture)

    print()
    print("=" * 78)
    print("2. ARCS: FLOOR REJECTIONS")
    print("=" * 78)
    raw_arcs = payload.get("arcs") if isinstance(payload, dict) else payload
    before_arcs = _parse_arcs(payload)
    after_arcs = _parse_arcs(payload, transcript=transcript)
    print(f"  arcs proposed by the model : {len(raw_arcs or [])}")
    print(f"  BEFORE (reject under 12s)  : {len(before_arcs)} kept")
    print(f"  AFTER  (repair under 12s)  : {len(after_arcs)} kept")

    print()
    print("=" * 78)
    print("3. DRIFT: WHERE THE QUOTED WORDS REALLY ARE")
    print("=" * 78)
    before_rows = drift_rows(after_arcs, words)
    anchored, anchor_report = anchor_arcs_to_transcript(after_arcs, transcript)
    after_rows = drift_rows(anchored, words)

    print(f"  {'arc':<46}{'seg':>4}{'start':>9}{'quote@':>9}{'drift':>8}")
    for b, a in zip(before_rows, after_rows, strict=True):
        print(
            f"  {b['title']:<46}{b['segment']:>4}{b['start']:>9}"
            f"{str(b['quote_at']):>9}{str(b['drift']):>8}"
            f"   ->  start={a['start']:<9} drift={a['drift']}"
        )
    print()
    print("  " + summarize("BEFORE", before_rows))
    print("  " + summarize("AFTER ", after_rows))
    print(f"  anchor report: {asdict(anchor_report)}")

    print()
    print("=" * 78)
    print("4. PAYOFF INSIDE THE CLIP")
    print("=" * 78)
    p_before = payoff_rows(after_arcs, words)
    p_after = payoff_rows(anchored, words)
    for b, a in zip(p_before, p_after, strict=True):
        print(
            f"  {b['title']:<46} payoff_end={str(b['payoff_end']):>8} "
            f"clip_end={b['clip_end']:>8} inside={b['inside']!s:<6} -> "
            f"clip_end={a['clip_end']:>8} inside={a['inside']}"
        )
    print(
        f"  BEFORE inside: {sum(1 for r in p_before if r['inside'])}/{len(p_before)}"
        f"   AFTER inside: {sum(1 for r in p_after if r['inside'])}/{len(p_after)}"
    )

    print()
    print("=" * 78)
    print("5. VERIFY + SNAP")
    print("=" * 78)
    kept_before, dropped_before = verify_arcs(transcript, after_arcs)
    kept_after, dropped_after = verify_arcs(transcript, anchored)
    print(f"  verify BEFORE anchoring: kept={len(kept_before)} dropped={dropped_before}")
    print(f"  verify AFTER  anchoring: kept={len(kept_after)} dropped={dropped_after}")

    legacy_failed = legacy_changed = legacy_seen = 0
    legacy_backward = 0.0
    for arc in kept_before:
        for seg in arc.segments:
            legacy_seen += 1
            s, e, failed = legacy_snap(words, seg.start, seg.end)
            legacy_failed += int(failed)
            legacy_changed += int(not failed)
            if not failed:
                legacy_backward = min(legacy_backward, s - seg.start)
    print(
        f"  BEFORE snap: {legacy_seen - legacy_failed}/{legacy_seen} aligned, "
        f"worst backward pull={legacy_backward:.2f}s"
    )

    snapped, snap_report = snap_arc_segments(
        kept_after, words, sentences=transcript.sentences
    )
    backward = 0.0
    for arc_in, arc_out in zip(kept_after, snapped, strict=True):
        for si, so in zip(arc_in.segments, arc_out.segments, strict=True):
            backward = min(backward, so.start - si.start)
    print(
        f"  AFTER  snap: {snap_report.segments_seen - snap_report.segments_failed}"
        f"/{snap_report.segments_seen} aligned, worst backward pull={backward:.2f}s"
    )

    final_rows = drift_rows(snapped, words)
    print("  " + summarize("FINAL (after anchor+verify+snap)", final_rows))
    p_final = payoff_rows(snapped, words)
    print(
        f"  FINAL payoff inside: {sum(1 for r in p_final if r['inside'])}/{len(p_final)}"
    )

    index = build_phrase_index(words, transcript.sentences)
    print(f"  phrase index source used by the snapper: {index.source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
