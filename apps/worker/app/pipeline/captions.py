"""ASS captions with multi-segment retiming.

For a single-segment clip, captions are simply word-timed against the source.
For a multi-segment montage, each word's source timestamp is recomputed on the
final timeline (offset by the cumulative duration of previous segments, minus
the crossfade overlaps).
"""

from __future__ import annotations

from pathlib import Path

from ..models import MontageSegment, Transcript


def _format_ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - (h * 3600 + m * 60)
    return f"{h:01d}:{m:02d}:{s:05.2f}"


ASS_STYLE_FORMAT = (
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
    "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
    "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
    "MarginL, MarginR, MarginV, Encoding"
)
ASS_DEFAULT_STYLE = (
    "Style: Default,Inter,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
    "1,0,0,0,100,100,0,0,1,4,2,2,80,80,200,1"
)
ASS_HEADER = "\n".join(
    [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        ASS_STYLE_FORMAT,
        ASS_DEFAULT_STYLE,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        "",
    ]
)


def _retimed_words_for_montage(
    *,
    transcript: Transcript,
    segments: list[MontageSegment],
    audio_crossfade_seconds: float,
) -> list[tuple[float, float, str]]:
    """For each word in the transcript that falls inside one of the segments,
    map its (start, end) onto the final clip timeline. Returns a list of
    (start_in_clip, end_in_clip, word).
    """
    out: list[tuple[float, float, str]] = []
    offset = 0.0
    for i, seg in enumerate(segments):
        seg_dur = max(0.0, seg.end - seg.start)
        if seg_dur <= 0:
            continue
        for w in transcript.words:
            if w.end < seg.start or w.start > seg.end:
                continue
            local_start = max(0.0, w.start - seg.start)
            local_end = min(seg_dur, w.end - seg.start)
            if local_end <= local_start:
                continue
            out.append((offset + local_start, offset + local_end, w.word))
        # Move offset forward, accounting for the crossfade overlap with NEXT segment
        offset += seg_dur
        if i < len(segments) - 1:
            offset -= audio_crossfade_seconds
    return out


def write_ass_for_montage(
    *,
    transcript: Transcript,
    segments: list[MontageSegment],
    out_path: str,
    audio_crossfade_seconds: float = 0.15,
    chunk_words: int = 5,
) -> bool:
    """Generate an ASS file for a multi-segment montage.

    For a single-segment list this behaves exactly like the old single-window
    writer (same chunking, no offset).
    """
    timed = _retimed_words_for_montage(
        transcript=transcript,
        segments=segments,
        audio_crossfade_seconds=audio_crossfade_seconds,
    )
    if not timed:
        return False

    lines: list[str] = []
    for i in range(0, len(timed), chunk_words):
        group = timed[i : i + chunk_words]
        if not group:
            continue
        start_rel = group[0][0]
        end_rel = group[-1][1]
        if end_rel <= start_rel:
            continue
        text = " ".join(g[2].strip() for g in group).strip()
        if not text:
            continue
        text = text.replace("{", "(").replace("}", ")")
        lines.append(
            f"Dialogue: 0,{_format_ass_time(start_rel)},{_format_ass_time(end_rel)},Default,,0,0,0,,{text}"
        )

    if not lines:
        return False

    Path(out_path).write_text(ASS_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
    return True


# Legacy alias kept for callers that still target a single window.
def write_ass_for_window(
    *,
    transcript: Transcript,
    window_start: float,
    window_end: float,
    out_path: str,
    chunk_words: int = 5,
) -> bool:
    segments = [MontageSegment(role="single", start=window_start, end=window_end)]
    return write_ass_for_montage(
        transcript=transcript,
        segments=segments,
        out_path=out_path,
        audio_crossfade_seconds=0.0,  # no crossfade with a single segment
        chunk_words=chunk_words,
    )
