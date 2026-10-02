"""Deterministic heuristics. These are flags, not human publishability labels."""

from __future__ import annotations

import random
import unicodedata

ENDING = frozenset(
    (
        "et mais donc si que parce alors car lorsque puisque avec pour de du des un une le la "
        "les au aux and but so if that because when with for of the a an to or"
    ).split()
)
OPENING = ENDING | frozenset(
    (
        "ca ceci cela il elle ils elles ce cette ces lui eux on it they he she this "
        "those these them"
    ).split()
)
SENTENCE_TOLERANCE = 0.5


def normalize(word):
    text = unicodedata.normalize("NFKD", word.lower().strip())
    return "".join(c for c in text if c.isalpha() and not unicodedata.combining(c))


def union(intervals):
    result = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return result


def overlap(intervals, selected):
    return sum(
        max(0, min(b, d) - max(a, c)) for a, b in union(intervals) for c, d in union(selected)
    )


def audience_overlap(segments, heatmap, source_duration, seed=0):
    if not heatmap:
        return None
    top = sorted(heatmap, key=lambda p: (-p["value"], p["start_time"]))[
        : max(1, len(heatmap) // 10)
    ]
    selected = [(p["start_time"], p["end_time"]) for p in top]
    intervals = union(segments)
    duration = sum(b - a for a, b in intervals)
    if duration <= 0 or source_duration < duration:
        return None
    rng = random.Random(seed)
    baseline = []
    for _ in range(1000):
        start = rng.uniform(0, source_duration - duration)
        baseline.append(overlap([(start, start + duration)], selected) / duration)
    return {
        "selected_fraction": overlap(intervals, selected) / duration,
        "random_same_duration_fraction": sum(baseline) / len(baseline),
        "samples": 1000,
    }


def clip_metrics(manifest, transcript, heatmap=None, source_duration=0):
    words, sentences = transcript["words"], transcript.get("sentences", [])
    flags = []
    intervals = []
    for shot in manifest["edl"]["shots"]:
        start, end = shot["source_in_ms"] / 1000, shot["source_out_ms"] / 1000
        intervals.append((start, end))
        first, last = words[shot["from_word_id"]], words[shot["to_word_id"]]
        connector = normalize(last["word"]) in ENDING
        boundary = any(abs(end - s["end"]) <= SENTENCE_TOLERANCE for s in sentences)
        cut_word = any(
            w["start"] + 0.001 < edge < w["end"] - 0.001 for edge in (start, end) for w in words
        )
        flags.append(
            {
                "suspended_ending": connector or not boundary,
                "ending_connector": connector,
                "sentence_end_match": boundary,
                "dependent_opening": normalize(first["word"]) in OPENING,
                "cut_inside_word": cut_word,
            }
        )
    qc = manifest["technical_qc"]
    duration = qc["duration_seconds"]
    return {
        "segments": flags,
        "suspended_ending": flags[-1]["suspended_ending"] if flags else None,
        "any_segment_suspended": any(s["suspended_ending"] for s in flags),
        "dependent_opening": flags[0]["dependent_opening"] if flags else None,
        "cut_inside_word": any(s["cut_inside_word"] for s in flags),
        "black_seconds": sum(b - a for a, b in union(qc.get("black_intervals", []))),
        "silence_seconds": sum(b - a for a, b in union(qc.get("silence_intervals", []))),
        "duration_seconds": duration,
        "duration_in_target_15_60": 15 <= duration <= 60,
        "audience_overlap": audience_overlap(intervals, heatmap, source_duration),
    }
