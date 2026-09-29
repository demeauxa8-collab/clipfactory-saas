"""Deterministic audio evidence for editorial pacing decisions.

This module only parses local FFmpeg analysis output and proposes *candidate*
timeline cuts.  It never invokes ``silenceremove`` and never mutates media:
the EDL compiler remains responsible for accepting a candidate and rebuilding
video, audio and captions together.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal


class AudioMapError(ValueError):
    """Raised when audio evidence or word-boundary inputs are inconsistent."""


SilenceKind = Literal["dead_air", "kept_pause", "protected_pause", "too_short"]


@dataclass(frozen=True)
class SilenceInterval:
    """One detected silent interval in source-timeline seconds."""

    start: float
    end: float

    @property
    def duration_seconds(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class LoudnessPoint:
    """Momentary loudness reported by FFmpeg's ebur128 filter."""

    timestamp_seconds: float
    momentary_lufs: float | None = None
    short_term_lufs: float | None = None
    integrated_lufs: float | None = None


@dataclass(frozen=True)
class AudioMap:
    """Parsed local audio-analysis evidence; no judgement or media side effects."""

    duration_seconds: float | None
    silences: tuple[SilenceInterval, ...]
    loudness_points: tuple[LoudnessPoint, ...] = ()
    integrated_lufs: float | None = None
    peak_db: float | None = None
    rms_db: float | None = None


@dataclass(frozen=True)
class TimedWord:
    """A stable transcript word identity on the same source timeline as audio."""

    id: str
    start: float
    end: float


@dataclass(frozen=True)
class ProtectedWordSpan:
    """Inclusive span of words whose internal pause must not be cut.

    To preserve a dramatic pause between two spoken words, include both words in
    the span.  This makes pause preservation explicit and reviewable instead of
    inferring dramatic intent from silence duration.
    """

    start_word_id: str
    end_word_id: str
    reason: str = "editorial"


@dataclass(frozen=True)
class ClassifiedSilence:
    interval: SilenceInterval
    kind: SilenceKind
    reason: str
    left_word_id: str | None
    right_word_id: str | None


@dataclass(frozen=True)
class MicroCut:
    """A bounded EDL candidate entirely inside an observed silence.

    ``left_word_id`` and ``right_word_id`` identify the two transcript edges.
    The renderer must keep both before applying the cut, so a candidate cannot
    silently cross into spoken content when a transcript changes.
    """

    start: float
    end: float
    source_silence: SilenceInterval
    left_word_id: str
    right_word_id: str

    @property
    def duration_seconds(self) -> float:
        return self.end - self.start


_SILENCE_START_RE = re.compile(r"silence_start:\s*(-?(?:\d+(?:\.\d*)?|\.\d+))")
_SILENCE_END_RE = re.compile(r"silence_end:\s*(-?(?:\d+(?:\.\d*)?|\.\d+))")
_EBUR_TIME_RE = re.compile(r"\bt:\s*(-?(?:\d+(?:\.\d*)?|\.\d+))")
_EBUR_FIELD_RE = {
    "momentary_lufs": re.compile(r"\bM:\s*(-?(?:\d+(?:\.\d*)?|\.\d+)|-inf)"),
    "short_term_lufs": re.compile(r"\bS:\s*(-?(?:\d+(?:\.\d*)?|\.\d+)|-inf)"),
    "integrated_lufs": re.compile(r"\bI:\s*(-?(?:\d+(?:\.\d*)?|\.\d+)|-inf)"),
}
_EBUR_SUMMARY_RE = re.compile(
    r"\bI:\s*(-?(?:\d+(?:\.\d*)?|\.\d+)|-inf)\s*LUFS", re.IGNORECASE
)
_ASTATS_RMS_RE = re.compile(
    r"(?:RMS level dB|RMS peak dB):\s*(-?(?:\d+(?:\.\d*)?|\.\d+)|-inf)", re.IGNORECASE
)
_ASTATS_PEAK_RE = re.compile(
    r"(?:Peak level dB|Peak dB):\s*(-?(?:\d+(?:\.\d*)?|\.\d+)|-inf)", re.IGNORECASE
)


def _finite(value: float, *, field: str) -> float:
    if not math.isfinite(value):
        raise AudioMapError(f"{field} must be finite")
    return value


def _parse_ffmpeg_number(value: str) -> float | None:
    return None if value.lower() == "-inf" else float(value)


def _normalize_silences(
    intervals: Iterable[SilenceInterval], *, duration_seconds: float | None
) -> tuple[SilenceInterval, ...]:
    duration = (
        None
        if duration_seconds is None
        else _finite(duration_seconds, field="duration_seconds")
    )
    if duration is not None and duration < 0:
        raise AudioMapError("duration_seconds must be non-negative")

    normalized: list[SilenceInterval] = []
    for interval in sorted(intervals, key=lambda item: (item.start, item.end)):
        start = max(0.0, _finite(interval.start, field="silence.start"))
        end = _finite(interval.end, field="silence.end")
        if duration is not None:
            end = min(end, duration)
        if end <= start:
            continue
        # FFmpeg can log adjacent overlapping fragments around a threshold.
        # Merge them into a single physical quiet interval before classifying it.
        if normalized and start <= normalized[-1].end:
            previous = normalized[-1]
            normalized[-1] = SilenceInterval(previous.start, max(previous.end, end))
        else:
            normalized.append(SilenceInterval(start, end))
    return tuple(normalized)


def parse_silencedetect(
    output: str,
    *,
    duration_seconds: float | None = None,
) -> tuple[SilenceInterval, ...]:
    """Parse FFmpeg ``silencedetect`` stderr defensively.

    A dangling ``silence_start`` has no measured end and is ignored.  An end
    without a start is likewise ignored; accepting it would manufacture a cut
    boundary not measured by FFmpeg.
    """
    if not isinstance(output, str):
        raise AudioMapError("silencedetect output must be text")
    pending_start: float | None = None
    intervals: list[SilenceInterval] = []
    for line in output.splitlines():
        start_match = _SILENCE_START_RE.search(line)
        if start_match:
            pending_start = float(start_match.group(1))
        end_match = _SILENCE_END_RE.search(line)
        if end_match and pending_start is not None:
            end = float(end_match.group(1))
            intervals.append(SilenceInterval(pending_start, end))
            pending_start = None
    return _normalize_silences(intervals, duration_seconds=duration_seconds)


def parse_ebur128(output: str) -> tuple[tuple[LoudnessPoint, ...], float | None]:
    """Parse timestamped ebur128 samples and its final integrated loudness.

    FFmpeg writes periodic records like ``t: 3.1 M: -18.3 S: -20.1 I: -21.0``
    plus a summary.  Unknown/noisy lines are ignored rather than treated as a
    signal.  ``-inf`` stays ``None`` because it is not useful as a gain value.
    """
    if not isinstance(output, str):
        raise AudioMapError("ebur128 output must be text")
    points: list[LoudnessPoint] = []
    summary: float | None = None
    for line in output.splitlines():
        time_match = _EBUR_TIME_RE.search(line)
        if time_match:
            values: dict[str, float | None] = {}
            for field, pattern in _EBUR_FIELD_RE.items():
                match = pattern.search(line)
                values[field] = _parse_ffmpeg_number(match.group(1)) if match else None
            points.append(
                LoudnessPoint(
                    timestamp_seconds=float(time_match.group(1)),
                    momentary_lufs=values["momentary_lufs"],
                    short_term_lufs=values["short_term_lufs"],
                    integrated_lufs=values["integrated_lufs"],
                )
            )
        for match in _EBUR_SUMMARY_RE.finditer(line):
            parsed = _parse_ffmpeg_number(match.group(1))
            if parsed is not None:
                summary = parsed
    if summary is None:
        for point in reversed(points):
            if point.integrated_lufs is not None:
                summary = point.integrated_lufs
                break
    return tuple(points), summary


def parse_astats(output: str) -> tuple[float | None, float | None]:
    """Return the final RMS and peak dB values reported by FFmpeg ``astats``."""
    if not isinstance(output, str):
        raise AudioMapError("astats output must be text")
    rms_values = [
        parsed
        for match in _ASTATS_RMS_RE.finditer(output)
        if (parsed := _parse_ffmpeg_number(match.group(1))) is not None
    ]
    peak_values = [
        parsed
        for match in _ASTATS_PEAK_RE.finditer(output)
        if (parsed := _parse_ffmpeg_number(match.group(1))) is not None
    ]
    return (rms_values[-1] if rms_values else None, peak_values[-1] if peak_values else None)


def build_audio_map(
    *,
    silencedetect_output: str,
    duration_seconds: float | None = None,
    ebur128_output: str = "",
    astats_output: str = "",
) -> AudioMap:
    """Build an immutable map from local FFmpeg output only."""
    silences = parse_silencedetect(silencedetect_output, duration_seconds=duration_seconds)
    loudness_points, integrated_lufs = parse_ebur128(ebur128_output)
    rms_db, peak_db = parse_astats(astats_output)
    return AudioMap(
        duration_seconds=duration_seconds,
        silences=silences,
        loudness_points=loudness_points,
        integrated_lufs=integrated_lufs,
        peak_db=peak_db,
        rms_db=rms_db,
    )


def _validate_words(words: Sequence[TimedWord]) -> dict[str, int]:
    if not words:
        raise AudioMapError("at least one timed word is required")
    index: dict[str, int] = {}
    previous_end = -1.0
    for position, word in enumerate(words):
        if not word.id or word.id in index:
            raise AudioMapError("word IDs must be unique non-empty strings")
        start = _finite(word.start, field="word.start")
        end = _finite(word.end, field="word.end")
        if start < previous_end or end < start:
            raise AudioMapError("words must be ordered and have non-negative duration")
        index[word.id] = position
        previous_end = end
    return index


def _protected_ranges(
    words: Sequence[TimedWord],
    protected_spans: Sequence[ProtectedWordSpan],
    word_index: dict[str, int],
) -> tuple[tuple[float, float], ...]:
    ranges: list[tuple[float, float]] = []
    for span in protected_spans:
        start_index = word_index.get(span.start_word_id)
        end_index = word_index.get(span.end_word_id)
        if start_index is None or end_index is None:
            raise AudioMapError("protected span references an unknown word ID")
        if start_index > end_index:
            raise AudioMapError("protected span start_word_id must not follow end_word_id")
        ranges.append((words[start_index].start, words[end_index].end))
    return tuple(ranges)


def _surrounding_words(
    interval: SilenceInterval, words: Sequence[TimedWord]
) -> tuple[TimedWord | None, TimedWord | None]:
    left: TimedWord | None = None
    right: TimedWord | None = None
    for word in words:
        if word.end <= interval.start:
            left = word
            continue
        if word.start >= interval.end:
            right = word
            break
    return left, right


def _intersects(interval: SilenceInterval, protected: tuple[float, float]) -> bool:
    start, end = protected
    return interval.start < end and start < interval.end


def classify_silences(
    audio_map: AudioMap,
    words: Sequence[TimedWord],
    *,
    protected_spans: Sequence[ProtectedWordSpan] = (),
    minimum_dead_air_seconds: float = 0.55,
) -> tuple[ClassifiedSilence, ...]:
    """Classify measured silence without guessing narrative intent.

    A silent interval becomes removable ``dead_air`` only if it is long enough,
    sits between two known word boundaries, and does not intersect an explicit
    protected span.  Short pauses and edge silence are retained by default.
    """
    minimum = _finite(minimum_dead_air_seconds, field="minimum_dead_air_seconds")
    if minimum <= 0:
        raise AudioMapError("minimum_dead_air_seconds must be positive")
    word_index = _validate_words(words)
    protected_ranges = _protected_ranges(words, protected_spans, word_index)
    classified: list[ClassifiedSilence] = []
    for interval in audio_map.silences:
        left, right = _surrounding_words(interval, words)
        left_id = left.id if left else None
        right_id = right.id if right else None
        if any(_intersects(interval, protected) for protected in protected_ranges):
            kind: SilenceKind = "protected_pause"
            reason = "intersects_protected_word_span"
        elif interval.duration_seconds < minimum:
            kind = "too_short"
            reason = "below_dead_air_threshold"
        elif left is None or right is None:
            kind = "kept_pause"
            reason = "clip_edge_has_no_bounded_word_pair"
        else:
            kind = "dead_air"
            reason = "bounded_silence_between_words"
        classified.append(
            ClassifiedSilence(
                interval=interval,
                kind=kind,
                reason=reason,
                left_word_id=left_id,
                right_word_id=right_id,
            )
        )
    return tuple(classified)


def propose_micro_cuts(
    audio_map: AudioMap,
    words: Sequence[TimedWord],
    *,
    protected_spans: Sequence[ProtectedWordSpan] = (),
    minimum_dead_air_seconds: float = 0.55,
    preserve_left_seconds: float = 0.10,
    preserve_right_seconds: float = 0.14,
    max_cut_seconds: float = 0.75,
    max_cuts: int = 3,
) -> tuple[MicroCut, ...]:
    """Propose bounded cuts inside dead air, never alter media directly.

    The retained lead/trail prevents an unnatural butt splice.  A candidate is
    skipped unless both transcript word IDs still bound it, and it is clamped to
    the silence measured by FFmpeg as well as those word edges.
    """
    left_keep = _finite(preserve_left_seconds, field="preserve_left_seconds")
    right_keep = _finite(preserve_right_seconds, field="preserve_right_seconds")
    maximum = _finite(max_cut_seconds, field="max_cut_seconds")
    if left_keep < 0 or right_keep < 0 or maximum <= 0 or max_cuts < 0:
        raise AudioMapError("micro-cut bounds must be non-negative and max_cut_seconds positive")
    if max_cuts == 0:
        return ()

    by_id = {word.id: word for word in words}
    cuts: list[MicroCut] = []
    for classified in classify_silences(
        audio_map,
        words,
        protected_spans=protected_spans,
        minimum_dead_air_seconds=minimum_dead_air_seconds,
    ):
        if classified.kind != "dead_air":
            continue
        assert classified.left_word_id is not None and classified.right_word_id is not None
        left_word = by_id[classified.left_word_id]
        right_word = by_id[classified.right_word_id]
        start = max(classified.interval.start + left_keep, left_word.end)
        end = min(classified.interval.end - right_keep, right_word.start)
        if end <= start:
            continue
        if end - start > maximum:
            # Keep the natural pause next to the following phrase.  Cutting from
            # the earlier side also makes the resulting caption boundary stable.
            end = start + maximum
        if end <= start:
            continue
        cuts.append(
            MicroCut(
                start=start,
                end=end,
                source_silence=classified.interval,
                left_word_id=left_word.id,
                right_word_id=right_word.id,
            )
        )
        if len(cuts) >= max_cuts:
            break
    return tuple(cuts)
