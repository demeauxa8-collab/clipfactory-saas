"""ASS captions with multi-segment retiming and karaoke word highlighting.

For a single-segment clip, captions are simply word-timed against the source.
For a multi-segment montage, each word's source timestamp is recomputed on the
final timeline (offset by the cumulative duration of previous segments, minus
the crossfade overlaps).

Captions are rendered "karaoke" style: a tight 2-3 word chunk stays on screen and
the word currently being spoken is highlighted in an accent colour with a slight
size punch. We emit one Dialogue event per word (each holding until the next word
starts) instead of the classic ASS ``\\k`` fill, because per-word colour overrides
let us highlight a single active word rather than progressively colouring every
already-spoken word. Word timings are already computed, so this adds no cost.

Text is shown all-caps and the highlight only lands on content words (French
stop-words and very short tokens are never accented), so the caption never fights
the creator's own burned-in subtitles.
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
# Full-screen framing means captions sit ON the video (not in a dead blur
# band): bigger font (110), thicker outline (6) and a bottom margin that keeps
# the baseline around ~80% of the 1920 px height. Fit-blur clips keep the 16:9
# band in the middle (sharp zone ends ~y=1264), so their captions use a larger
# margin to sit right under the video instead of floating in the blur.
FACE_CROP_MARGIN_V = 400
FIT_BLUR_MARGIN_V = 620


def _ass_header(margin_v: int) -> str:
    style = (
        "Style: Default,Inter,110,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        f"1,0,0,0,100,100,0,0,1,6,2,2,80,80,{margin_v},1"
    )
    return "\n".join(
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
            style,
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            "",
        ]
    )


# Kept for callers/tests that reference the default header.
ASS_HEADER = _ass_header(FACE_CROP_MARGIN_V)


# Active-word highlight colour as ASS BBGGRR (inline \c overrides take 6 hex
# digits + a trailing '&'). A punchy green (#00E676 -> BGR 76E600) that is
# clearly ours, so it never gets mistaken for a creator's own yellow subtitles.
HIGHLIGHT_BGR = "76E600"
# Size punch applied to the active word (percent of the style font size).
HIGHLIGHT_SCALE_PERCENT = 112

# Early caption cut when the silence between two words reaches this (seconds).
PAUSE_CUT_SECONDS = 0.3

# French function words we never highlight (articles, pronouns, short
# prepositions, auxiliaries). Elided forms use the typographic apostrophe.
_APOS = "’"  # noqa: RUF001 (typographic apostrophe is intentional data)
FRENCH_STOPWORDS = frozenset(
    {
        "le", "la", "les", "un", "une", "de", "des", "du", "et", "ou", "à",
        "au", "aux", "en", "y", "ce", "ça", "se", "ne", "que", "qui", "je",
        "tu", "il", "on", "me", "te", "mais", "donc", "or", "ni", "car", "si",
        "est", "es", "a", "ai", "as",
        "vous", "nous", "elle", "ils", "elles", "lui", "leur", "leurs",
        "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses",
        "nos", "vos", "cet", "cette", "ces", "dont", "quoi",
        "même", "alors", "aussi", "bien", "très", "plus", "moins", "comme",
        "tout", "tous", "toute", "toutes", "quand", "dans", "pour", "avec",
        "sans", "sous", "sur", "par", "pas",
        "l" + _APOS, "d" + _APOS, "c" + _APOS, "s" + _APOS, "n" + _APOS,
        "qu" + _APOS, "j" + _APOS, "m" + _APOS, "t" + _APOS,
    }
)


def _is_highlightable(word: str) -> bool:
    """Content words only: skip stop-words and tokens of 2 chars or fewer."""
    w = word.strip().lower()
    if _APOS in w:
        # Merged elisions (j'ai, l'objectif): judge the head word alone,
        # the elided prefix is always a function word.
        w = w.rsplit(_APOS, 1)[-1]
    return len(w) > 2 and w not in FRENCH_STOPWORDS


def _sanitize_word(word: str) -> str:
    """Strip the braces ASS uses for override blocks so transcript text can't
    break the tag stream."""
    return word.strip().replace("{", "(").replace("}", ")")


# Horizontal fit: at font 110, ~15 uppercase Inter chars fill the ~90% safe
# area of a 1080 px frame. Longer lines wrap on \N; a line that still exceeds
# the budget (single very long word) shrinks the whole event's font instead of
# bleeding off both edges.
MAX_LINE_CHARS = 15
BASE_FONT_SIZE = 110
MIN_FONT_SIZE = 64


def _layout_lines(displays: list[str]) -> list[list[int]]:
    """Greedy word-wrap by character count; returns lines of display indices."""
    lines: list[list[int]] = []
    current: list[int] = []
    length = 0
    for idx, word in enumerate(displays):
        candidate = len(word) if not current else length + 1 + len(word)
        if current and candidate > MAX_LINE_CHARS:
            lines.append(current)
            current = [idx]
            length = len(word)
        else:
            current.append(idx)
            length = candidate
    if current:
        lines.append(current)
    return lines


def _render_karaoke_chunk(words: list[str], active_idx: int) -> str:
    """Render an all-caps chunk with the word at ``active_idx`` highlighted.

    The active word gets an accent colour and a small scale punch. Stop-words
    and very short tokens are shown plain even when active. The highlight is
    closed with explicit overrides (not ``\\r``, which would also cancel the
    ``\\fs`` shrink applied to over-long lines).
    """
    entries: list[tuple[int, str, str]] = []
    for idx, raw in enumerate(words):
        word = _sanitize_word(raw)
        if not word:
            continue
        # .upper() keeps accents (é->É) and the U+2019 apostrophe intact.
        entries.append((idx, word, word.upper()))
    if not entries:
        return ""

    displays = [display for _, _, display in entries]
    lines = _layout_lines(displays)
    longest = max(
        sum(len(displays[i]) for i in line) + len(line) - 1 for line in lines
    )
    prefix = ""
    if longest > MAX_LINE_CHARS:
        shrunk = max(MIN_FONT_SIZE, BASE_FONT_SIZE * MAX_LINE_CHARS // longest)
        prefix = f"{{\\fs{shrunk}}}"

    line_texts: list[str] = []
    for line in lines:
        parts: list[str] = []
        for i in line:
            orig_idx, word, display = entries[i]
            if orig_idx == active_idx and _is_highlightable(word):
                parts.append(
                    f"{{\\c&H{HIGHLIGHT_BGR}&\\fscx{HIGHLIGHT_SCALE_PERCENT}"
                    f"\\fscy{HIGHLIGHT_SCALE_PERCENT}}}{display}"
                    "{\\c&HFFFFFF&\\fscx100\\fscy100}"
                )
            else:
                parts.append(display)
        line_texts.append(" ".join(parts))
    return prefix + "\\N".join(line_texts)


def _retimed_words_for_montage(
    *,
    transcript: Transcript,
    segments: list[MontageSegment],
    audio_crossfade_seconds: float,
) -> list[tuple[float, float, str, int]]:
    """For each word in the transcript that falls inside one of the segments,
    map its (start, end) onto the final clip timeline. Returns a list of
    (start_in_clip, end_in_clip, word, segment_idx).

    The trailing ``segment_idx`` is the index of the *originating* segment
    (position in ``segments``), so a caption group can later inherit its
    segment's vertical margin and never straddle a segment joint.
    """
    out: list[tuple[float, float, str, int]] = []
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
            out.append((offset + local_start, offset + local_end, w.word, i))
        # Move offset forward, accounting for the crossfade overlap with NEXT segment
        offset += seg_dur
        if i < len(segments) - 1:
            offset -= audio_crossfade_seconds
    return out


def _split_run(
    run: list[tuple[float, float, str, int]], max_size: int
) -> list[list[tuple[float, float, str, int]]]:
    """Split one pause-free run into balanced groups of ``max_size`` words max.

    Balancing avoids a stranded 1-word tail (e.g. 4 words -> [2, 2], not [3, 1]):
    a single-word group only ever comes out of a run that is itself one word,
    i.e. one already isolated by pauses on both sides.
    """
    max_size = max(1, max_size)
    if len(run) <= max_size:
        return [run]
    groups: list[list[tuple[float, float, str, int]]] = []
    i, total = 0, len(run)
    while i < total:
        remaining = total - i
        if remaining == max_size + 1:
            size = max(1, remaining - 2)  # leave a clean 2-word tail instead of 1
        elif remaining <= max_size:
            size = remaining
        else:
            size = max_size
        groups.append(run[i : i + size])
        i += size
    return groups


def _group_timed(
    timed: list[tuple[float, float, str, int]], chunk_words: int
) -> list[list[tuple[float, float, str, int]]]:
    """Group word-timed tokens into caption chunks of ``chunk_words`` max.

    Chunks break early on a >= ``PAUSE_CUT_SECONDS`` silence between words AND at
    every segment joint (a change of ``segment_idx``): a group must never straddle
    two segments, or the crossfade retiming would make the karaoke run through the
    joint out of sync. Within a pause-free, single-segment run words are packed and
    balanced to avoid orphan 1-word chunks.
    """
    runs: list[list[tuple[float, float, str, int]]] = []
    run: list[tuple[float, float, str, int]] = []
    for item in timed:
        if run and (
            (item[0] - run[-1][1]) >= PAUSE_CUT_SECONDS
            or item[3] != run[-1][3]
        ):
            runs.append(run)
            run = []
        run.append(item)
    if run:
        runs.append(run)

    groups: list[list[tuple[float, float, str, int]]] = []
    for r in runs:
        groups.extend(_split_run(r, chunk_words))
    return groups


def write_ass_for_montage(
    *,
    transcript: Transcript,
    segments: list[MontageSegment],
    out_path: str,
    audio_crossfade_seconds: float = 0.15,
    chunk_words: int = 3,
    karaoke: bool = True,
    margin_v: int = FACE_CROP_MARGIN_V,
    margins_per_segment: list[int] | None = None,
) -> bool:
    """Generate an ASS file for a multi-segment montage.

    For a single-segment list this behaves exactly like the old single-window
    writer (same chunking, no offset). With ``karaoke=True`` (default) the chunk
    stays on screen while the active word is highlighted word-by-word; with
    ``karaoke=False`` each chunk is a single static line.

    ``margin_v`` sets the style's default vertical margin (header) and is the
    fallback for every event. When ``margins_per_segment`` is given (one MarginV
    per segment, e.g. 400 for a face-crop segment and 620 for a fit-blur one) each
    Dialogue event instead carries the MarginV of the segment its words belong to,
    so caption height follows the per-segment framing. A group never straddles a
    joint, so every event maps to exactly one segment margin.
    """
    timed = _retimed_words_for_montage(
        transcript=transcript,
        segments=segments,
        audio_crossfade_seconds=audio_crossfade_seconds,
    )
    if not timed:
        return False

    lines: list[str] = []
    for group in _group_timed(timed, chunk_words):
        if not group:
            continue
        chunk_start = group[0][0]
        chunk_end = group[-1][1]
        if chunk_end <= chunk_start:
            continue
        chunk_words_text = [g[2] for g in group]
        # The whole group belongs to one segment (runs break at every joint), so
        # its MarginV is well defined. 0 => the event inherits the style default
        # (i.e. the global ``margin_v`` in the header), preserving the old output
        # when ``margins_per_segment`` is None.
        seg_idx = group[0][3]
        if margins_per_segment is not None and 0 <= seg_idx < len(margins_per_segment):
            ev_margin = margins_per_segment[seg_idx]
        else:
            ev_margin = 0

        if not karaoke:
            text = _render_karaoke_chunk(chunk_words_text, active_idx=-1)
            if not text:
                continue
            lines.append(
                f"Dialogue: 0,{_format_ass_time(chunk_start)},"
                f"{_format_ass_time(chunk_end)},Default,,0,0,{ev_margin},,{text}"
            )
            continue

        # One event per word: each highlights its word and holds until the next
        # word starts (the last holds to the chunk end). The union covers the
        # whole chunk with no gap or flicker.
        for j, (word_start, word_end, _word, _seg) in enumerate(group):
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
                f"{_format_ass_time(ev_end)},Default,,0,0,{ev_margin},,{text}"
            )

    if not lines:
        return False

    Path(out_path).write_text(
        _ass_header(margin_v) + "\n".join(lines) + "\n", encoding="utf-8"
    )
    return True


# Legacy alias kept for callers that still target a single window.
def write_ass_for_window(
    *,
    transcript: Transcript,
    window_start: float,
    window_end: float,
    out_path: str,
    chunk_words: int = 3,
) -> bool:
    segments = [MontageSegment(role="single", start=window_start, end=window_end)]
    return write_ass_for_montage(
        transcript=transcript,
        segments=segments,
        out_path=out_path,
        audio_crossfade_seconds=0.0,  # no crossfade with a single segment
        chunk_words=chunk_words,
    )
