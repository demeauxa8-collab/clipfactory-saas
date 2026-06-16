"""ASS captions with multi-segment retiming and karaoke word highlighting.

For a single-segment clip, captions are simply word-timed against the source.
For a multi-segment montage, each word's source timestamp is recomputed on the
final timeline (offset by the cumulative duration of previous segments, minus
the crossfade overlaps).

Captions are rendered "karaoke" style: a chunk of ~5 words stays on screen and
the word currently being spoken is highlighted in an accent colour with a slight
size punch. We emit one Dialogue event per word (each holding until the next word
starts) instead of the classic ASS ``\\k`` fill, because per-word colour overrides
let us highlight a single active word rather than progressively colouring every
already-spoken word. Word timings are already computed, so this adds no cost.
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


# Active-word highlight colour as ASS BBGGRR (inline \c overrides take 6 hex
# digits + a trailing '&'). This is a vivid yellow (RGB 255,229,0) which reads
# well over the white outline on most footage.
HIGHLIGHT_BGR = "00E5FF"
# Size punch applied to the active word (percent of the style font size).
HIGHLIGHT_SCALE_PERCENT = 112


def _sanitize_word(word: str) -> str:
    """Strip the braces ASS uses for override blocks so transcript text can't
    break the tag stream."""
    return word.strip().replace("{", "(").replace("}", ")")


def _render_karaoke_chunk(words: list[str], active_idx: int) -> str:
    """Render a chunk with the word at ``active_idx`` highlighted.

    The active word gets an accent colour and a small scale punch; ``\\r`` resets
    back to the Default style for the rest of the line.
    """
    parts: list[str] = []
    for idx, raw in enumerate(words):
        word = _sanitize_word(raw)
        if not word:
            continue
        if idx == active_idx:
            parts.append(
                f"{{\\c&H{HIGHLIGHT_BGR}&\\fscx{HIGHLIGHT_SCALE_PERCENT}"
                f"\\fscy{HIGHLIGHT_SCALE_PERCENT}}}{word}{{\\r}}"
            )
        else:
            parts.append(word)
    return " ".join(parts)


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
    karaoke: bool = True,
) -> bool:
    """Generate an ASS file for a multi-segment montage.

    For a single-segment list this behaves exactly like the old single-window
    writer (same chunking, no offset). With ``karaoke=True`` (default) the chunk
    stays on screen while the active word is highlighted word-by-word; with
    ``karaoke=False`` each chunk is a single static line.
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
        chunk_start = group[0][0]
        chunk_end = group[-1][1]
        if chunk_end <= chunk_start:
            continue
        chunk_words_text = [g[2] for g in group]

        if not karaoke:
            text = _render_karaoke_chunk(chunk_words_text, active_idx=-1)
            if not text:
                continue
            lines.append(
                f"Dialogue: 0,{_format_ass_time(chunk_start)},"
                f"{_format_ass_time(chunk_end)},Default,,0,0,0,,{text}"
            )
            continue

        # One event per word: each highlights its word and holds until the next
        # word starts (the last holds to the chunk end). The union covers the
        # whole chunk with no gap or flicker.
        for j, (word_start, word_end, _word) in enumerate(group):
            ev_start = word_start
            ev_end = group[j + 1][0] if j + 1 < len(group) else chunk_end
            if ev_end <= ev_start:
                ev_end = word_end
            if ev_end <= ev_start:
                continue
            text = _render_karaoke_chunk(chunk_words_text, active_idx=j)
            if not text:
                continue
            lines.append(
                f"Dialogue: 0,{_format_ass_time(ev_start)},"
                f"{_format_ass_time(ev_end)},Default,,0,0,0,,{text}"
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
