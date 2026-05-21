from __future__ import annotations

from pathlib import Path

from ..models import Transcript


def _format_ass_time(seconds: float) -> str:
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


def write_ass_for_window(
    *,
    transcript: Transcript,
    window_start: float,
    window_end: float,
    out_path: str,
    chunk_words: int = 5,
) -> bool:
    """Generate an ASS file for the given time window using the transcript words.

    Returns True if any captions were written, False otherwise.
    """
    words = [w for w in transcript.words if w.end >= window_start and w.start <= window_end]
    if not words:
        return False

    lines: list[str] = []
    for i in range(0, len(words), chunk_words):
        group = words[i : i + chunk_words]
        if not group:
            continue
        start_rel = max(0.0, group[0].start - window_start)
        end_rel = min(window_end - window_start, group[-1].end - window_start)
        if end_rel <= start_rel:
            continue
        text = " ".join(g.word.strip() for g in group).strip()
        if not text:
            continue
        # Escape commas and braces for ASS syntax
        text = text.replace("{", "(").replace("}", ")")
        start_ass = _format_ass_time(start_rel)
        end_ass = _format_ass_time(end_rel)
        lines.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}")

    if not lines:
        return False

    Path(out_path).write_text(ASS_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
    return True
