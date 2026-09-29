"""Caption planning and ASS rendering directly from a compiled V2 EDL.

The EDL compiler is the authority for all output-timeline timestamps.  This
module deliberately never looks at source segment seconds: it reads each
``CompiledWordOccurrence`` in final timeline order, retrieves its exact text
from the normalized transcript, then emits a small closed set of ASS styles.

That distinction matters for non-linear edits.  A source word may appear twice
in a replay, and may have a different duration after speed changes; each EDL
occurrence remains a separate caption occurrence with its own timestamp.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Literal

from ..models import Transcript
from .captions import BASE_FONT_SIZE, MAX_LINE_CHARS, MIN_FONT_SIZE, _layout_lines
from .edl import CaptionTheme, CompiledEDL, CompiledShot
from .opening import DEFAULT_HOOK_SECONDS, hook_dialogue_line, hook_style_line


class EDLCaptionError(ValueError):
    """The compiled EDL cannot produce an unambiguous caption timeline."""


CaptionPosition = Literal["upper", "lower"]

ASS_STYLE_FORMAT = (
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
    "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
    "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
    "MarginL, MarginR, MarginV, Encoding"
)

HIGHLIGHT_BGR = "76E600"  # #00E676 in ASS BBGGRR order.
_THEMES = frozenset({"hook_bold", "standard_karaoke", "proof_clean", "reaction_pop", "none"})


@dataclass(frozen=True)
class CaptionThemeStyle:
    """A closed ASS visual style.  The model can select a theme, not CSS."""

    name: str
    font_size: int
    bold: int
    outline: int
    shadow: int
    active_scale: int
    max_words: int


THEME_STYLES: dict[str, CaptionThemeStyle] = {
    "hook_bold": CaptionThemeStyle("CFHook", 122, 1, 7, 2, 118, 2),
    "standard_karaoke": CaptionThemeStyle("CFStandard", 110, 1, 6, 2, 112, 3),
    "proof_clean": CaptionThemeStyle("CFProof", 94, 1, 5, 1, 106, 3),
    "reaction_pop": CaptionThemeStyle("CFReaction", 116, 1, 7, 2, 120, 2),
}

# These preserve the safe placement policy in captions.py when no richer
# vision-derived safe zone is available.  A screen or PiP proof reserves more
# bottom space; a face crop keeps captions above the lower face/chest area.
_FALLBACK_POSITION_BY_FRAMING: dict[str, CaptionPosition] = {
    "source_safe": "lower",
    "fit_blur": "lower",
    "locked_face": "lower",
    "follow_primary_face": "lower",
    "screen_focus": "upper",
    "pip_proof": "upper",
}
_MARGIN_V_BY_POSITION: dict[CaptionPosition, int] = {"upper": 1_050, "lower": 400}
_PAUSE_CUT_MS = 300
_SENTENCE_WORD_END_TOLERANCE_SECONDS = 0.025


def sentence_word_ids(transcript: Transcript) -> tuple[int | None, ...]:
    """Conservatively assign real transcript words to timed ASR sentences.

    This is deliberately one shared timing contract for captions and editorial
    QC.  Sentence punctuation is useful only if it can be aligned forward to
    the transcript words that own output timing.  A word belongs to a sentence
    when it *ends* no later than that sentence end (with a tiny ASR tolerance),
    never because its midpoint happens to land in a neighbouring segment.

    Sentence starts are also checked against the next unconsumed word.  This
    filters stale or disconnected ASR segments while accepting normal slight
    overlap where a word straddles the next sentence start.  Empty word
    placeholders advance the cursor but cannot become semantic evidence.
    """

    words = transcript.words
    if not words or not transcript.sentences:
        return tuple(None for _ in words)
    if any(
        not math.isfinite(word.start) or not math.isfinite(word.end) or word.end < word.start
        for word in words
    ) or any((right.start, right.end) < (left.start, left.end) for left, right in pairwise(words)):
        return tuple(None for _ in words)

    sentence_ids: list[int | None] = [None] * len(words)
    word_cursor = 0
    previous_sentence_end: float | None = None
    for sentence_index, sentence in enumerate(
        sorted(transcript.sentences, key=lambda item: (item.start, item.end))
    ):
        if (
            not math.isfinite(sentence.start)
            or not math.isfinite(sentence.end)
            or sentence.end <= sentence.start
            or (previous_sentence_end is not None and sentence.end <= previous_sentence_end)
        ):
            continue
        if word_cursor >= len(words):
            break
        next_word = words[word_cursor]
        # The new segment must plausibly cover the next source word.  A slight
        # ASR segment overlap is accepted; a stale segment wholly before/after
        # that word is ignored rather than inventing a phrase boundary.
        if (
            sentence.start > next_word.end + _SENTENCE_WORD_END_TOLERANCE_SECONDS
            or sentence.end < next_word.start - _SENTENCE_WORD_END_TOLERANCE_SECONDS
        ):
            continue
        previous_sentence_end = sentence.end
        while word_cursor < len(words):
            word = words[word_cursor]
            if word.end > sentence.end + _SENTENCE_WORD_END_TOLERANCE_SECONDS:
                break
            if word.word.strip():
                sentence_ids[word_cursor] = sentence_index
            word_cursor += 1
    return tuple(sentence_ids)


def _semantic_break_after_word_ids(transcript: Transcript) -> frozenset[int]:
    """Return transcript word IDs which end a reliably mapped ASR sentence.

    ``Transcript.sentences`` and ``Transcript.words`` are parallel ASR views:
    the former has punctuation and semantic phrasing, while the latter owns the
    exact word timings.  We deliberately map a sentence boundary *only* when a
    forward, timestamp-based walk can assign real transcript words to it.  This
    keeps captions grounded in the compiled word occurrences: no segment text
    is copied, punctuated, or assigned an invented output time.

    Adjacent ASR segments may overlap by a few milliseconds.  That is normal,
    so sentence starts are not used as hard cutoffs; their increasing end times
    provide the unambiguous forward boundary.  A word must *finish* at that end
    (within a small ASR tolerance): midpoint matching can steal the first word
    of the next sentence when it straddles a segment boundary.  Empty ASR words
    advance the timing cursor but never become a semantic break. Crossed/nested
    segments and segments that map to zero meaningful words are ignored.  With
    no usable sentence boundary, callers retain the established pause-aware
    grouping behaviour.
    """

    breaks: set[int] = set()
    sentence_ids = sentence_word_ids(transcript)
    previous_meaningful_word_id: int | None = None
    previous_sentence_id: int | None = None
    for word_id, sentence_id in enumerate(sentence_ids):
        if not transcript.words[word_id].word.strip():
            continue
        # Empty timing placeholders never form a visual cue and must not hide
        # an otherwise validated sentence boundary between real words.
        if (
            previous_meaningful_word_id is not None
            and previous_sentence_id is not None
            and sentence_id is not None
            and previous_sentence_id != sentence_id
        ):
            breaks.add(previous_meaningful_word_id)
        previous_meaningful_word_id = word_id
        previous_sentence_id = sentence_id

    return frozenset(breaks)


@dataclass(frozen=True)
class CaptionSafeZone:
    """Trusted per-shot placement supplied by vision/QC, when available."""

    position: CaptionPosition

    @property
    def margin_v(self) -> int:
        return _MARGIN_V_BY_POSITION[self.position]


@dataclass(frozen=True)
class CaptionWord:
    """Exact transcript word at a resolved occurrence on the output timeline."""

    occurrence_id: str
    shot_id: str
    word_id: int
    text: str
    timeline_in_ms: int
    timeline_out_ms: int


@dataclass(frozen=True)
class CaptionCue:
    """One grouped karaoke cue; one ASS event is emitted for each active word."""

    cue_id: str
    shot_id: str
    theme: CaptionTheme
    style_name: str
    margin_v: int
    words: tuple[CaptionWord, ...]
    timeline_in_ms: int
    timeline_out_ms: int


@dataclass(frozen=True)
class CaptionPlan:
    """A deterministic, renderer-independent caption representation."""

    duration_ms: int
    cues: tuple[CaptionCue, ...]


def _format_ass_time(milliseconds: int) -> str:
    milliseconds = max(0, milliseconds)
    centiseconds = milliseconds // 10
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, seconds = divmod(remainder, 6_000)
    return f"{hours}:{minutes:02d}:{seconds // 100:02d}.{seconds % 100:02d}"


def _ass_text(text: str) -> str:
    """Keep transcript text verbatim except ASS control delimiters.

    Literal braces would be interpreted as override blocks by libass.  Replacing
    only those delimiters is the same safety rule as the existing caption path;
    every ordinary word, punctuation mark and casing remains transcript-owned.
    """

    return text.replace("{", "(").replace("}", ")").replace("\r", " ").replace("\n", " ")


def _is_highlightable(text: str) -> bool:
    token = "".join(character for character in text.lower() if character.isalnum())
    return len(token) > 2 and token not in {
        "les",
        "des",
        "une",
        "dans",
        "pour",
        "avec",
        "mais",
        "pas",
        "sans",
        "que",
        "qui",
        "est",
        "sont",
        "this",
        "that",
        "the",
        "and",
        "for",
        "with",
        "you",
        "are",
    }


def _style_lines() -> list[str]:
    lines: list[str] = []
    for style in THEME_STYLES.values():
        lines.append(
            "Style: "
            f"{style.name},Inter,{style.font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
            f"{style.bold},0,0,0,100,100,0,0,1,{style.outline},{style.shadow},2,80,80,400,1"
        )
    return lines


def ass_header(*, with_hook: bool = False) -> str:
    """Static header with every approved style; no caller can add a style.

    ``with_hook`` declares the opening-hook style as well; it is left out unless
    a hook is emitted so existing output stays byte-identical.
    """

    styles = [*_style_lines()]
    if with_hook:
        styles.append(hook_style_line())
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
            *styles,
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            "",
        ]
    )


def _safe_zone_for_shot(
    shot: CompiledShot,
    safe_zones: Mapping[str, CaptionSafeZone] | None,
) -> CaptionSafeZone:
    if safe_zones is not None and shot.shot_id in safe_zones:
        zone = safe_zones[shot.shot_id]
        if not isinstance(zone, CaptionSafeZone):
            raise EDLCaptionError(f"shot {shot.shot_id}: safe zone must be CaptionSafeZone")
        if zone.position not in _MARGIN_V_BY_POSITION:
            raise EDLCaptionError(f"shot {shot.shot_id}: unsupported caption safe zone")
        return zone
    try:
        position = _FALLBACK_POSITION_BY_FRAMING[shot.framing.mode]
    except KeyError as exc:
        raise EDLCaptionError(f"shot {shot.shot_id}: unsupported framing fallback") from exc
    return CaptionSafeZone(position)


def _caption_words_for_shot(
    shot: CompiledShot,
    transcript: Transcript,
) -> tuple[CaptionWord, ...]:
    words: list[CaptionWord] = []
    seen_occurrences: set[str] = set()
    for occurrence in sorted(
        shot.word_occurrences,
        key=lambda item: (item.timeline_in_ms, item.timeline_out_ms, item.occurrence_id),
    ):
        if occurrence.occurrence_id in seen_occurrences:
            raise EDLCaptionError(f"duplicate word occurrence {occurrence.occurrence_id!r}")
        seen_occurrences.add(occurrence.occurrence_id)
        if occurrence.shot_id != shot.shot_id:
            raise EDLCaptionError(
                f"word occurrence {occurrence.occurrence_id!r} belongs to {occurrence.shot_id!r}"
            )
        if not shot.from_word_id <= occurrence.word_id <= shot.to_word_id:
            raise EDLCaptionError(
                f"word occurrence {occurrence.occurrence_id!r} is outside shot word range"
            )
        if not 0 <= occurrence.word_id < len(transcript.words):
            raise EDLCaptionError(f"word occurrence has unknown word_id {occurrence.word_id}")
        if not (
            shot.timeline_in_ms
            <= occurrence.timeline_in_ms
            < occurrence.timeline_out_ms
            <= shot.timeline_out_ms
        ):
            raise EDLCaptionError(
                f"word occurrence {occurrence.occurrence_id!r} has invalid output timing"
            )
        if words and occurrence.timeline_in_ms < words[-1].timeline_in_ms:
            raise EDLCaptionError(f"word occurrence {occurrence.occurrence_id!r} is not monotonic")
        if not transcript.words[occurrence.word_id].word.strip():
            continue
        words.append(
            CaptionWord(
                occurrence_id=occurrence.occurrence_id,
                shot_id=shot.shot_id,
                word_id=occurrence.word_id,
                text=transcript.words[occurrence.word_id].word,
                timeline_in_ms=occurrence.timeline_in_ms,
                timeline_out_ms=occurrence.timeline_out_ms,
            )
        )
    return tuple(words)


def _groups(
    words: tuple[CaptionWord, ...],
    *,
    max_words: int,
    semantic_break_after_word_ids: frozenset[int] = frozenset(),
) -> list[tuple[CaptionWord, ...]]:
    """Split one shot into semantic, pause-aware, balanced caption cues.

    A simple fixed-width chunker creates distracting orphan tails: four words
    become ``3 + 1`` and seven words become ``3 + 3 + 1``.  Within each
    uninterrupted phrase we instead choose the minimum number of cues and
    distribute the words as evenly as possible (``2 + 2`` and ``3 + 2 + 2``).
    When ASR sentence timing maps unambiguously to transcript word IDs, those
    semantic boundaries are authoritative too.  A replay remains correct
    because the grouping reads the occurrence's output timing but asks only
    whether its real source word ends a mapped sentence.  Without sentences,
    this is exactly the existing pause-aware/balancing path.
    """

    if max_words <= 0:
        raise EDLCaptionError("caption max_words must be positive")

    phrases: list[tuple[CaptionWord, ...]] = []
    current: list[CaptionWord] = []
    for word in words:
        gap = word.timeline_in_ms - current[-1].timeline_out_ms if current else 0
        semantic_boundary = bool(current and current[-1].word_id in semantic_break_after_word_ids)
        if current and (semantic_boundary or gap >= _PAUSE_CUT_MS):
            phrases.append(tuple(current))
            current = []
        current.append(word)
    if current:
        phrases.append(tuple(current))

    groups: list[tuple[CaptionWord, ...]] = []
    for phrase in phrases:
        cue_count = (len(phrase) + max_words - 1) // max_words
        base_size, larger_cues = divmod(len(phrase), cue_count)
        cursor = 0
        for cue_index in range(cue_count):
            cue_size = base_size + (1 if cue_index < larger_cues else 0)
            groups.append(phrase[cursor : cursor + cue_size])
            cursor += cue_size
    # Several ASR words can start on the same output frame, including words
    # whose source duration is zero. Never put that indivisible time cluster
    # in two cues with the same start: clamping the first cue to the next
    # would otherwise hide it entirely. Keep all text at its compiled time.
    resolved: list[tuple[CaptionWord, ...]] = []
    for group in groups:
        if resolved and resolved[-1][0].timeline_in_ms // 10 == group[0].timeline_in_ms // 10:
            group = resolved.pop() + group
        resolved.append(group)
    return resolved


def build_caption_plan(
    edl: CompiledEDL,
    transcript: Transcript,
    *,
    safe_zones: Mapping[str, CaptionSafeZone] | None = None,
) -> CaptionPlan:
    """Build captions solely from compiled output occurrences.

    The shot list is already the editorial timeline order.  Therefore a replay
    naturally creates a second set of cues, while speed changes are inherited
    from occurrence timestamps without any source-time recalculation.
    """

    if edl.duration_ms <= 0:
        raise EDLCaptionError("EDL duration must be positive")
    if not transcript.words:
        raise EDLCaptionError("a transcript is required for EDL captions")

    cues: list[CaptionCue] = []
    semantic_break_after_word_ids = _semantic_break_after_word_ids(transcript)
    for shot_index, shot in enumerate(edl.shots):
        if shot.caption_theme not in _THEMES:
            raise EDLCaptionError(f"shot {shot.shot_id}: unsupported caption theme")
        if shot.caption_theme == "none":
            continue
        style = THEME_STYLES[shot.caption_theme]
        zone = _safe_zone_for_shot(shot, safe_zones)
        words = _caption_words_for_shot(shot, transcript)
        for group_index, group in enumerate(
            _groups(
                words,
                max_words=style.max_words,
                semantic_break_after_word_ids=semantic_break_after_word_ids,
            )
        ):
            start, end = group[0].timeline_in_ms, group[-1].timeline_out_ms
            if not 0 <= start < end <= edl.duration_ms:
                raise EDLCaptionError(f"shot {shot.shot_id}: cue lies outside EDL timeline")
            cues.append(
                CaptionCue(
                    cue_id=f"cue_{shot_index:02d}_{group_index:02d}",
                    shot_id=shot.shot_id,
                    theme=shot.caption_theme,
                    style_name=style.name,
                    margin_v=zone.margin_v,
                    words=group,
                    timeline_in_ms=start,
                    timeline_out_ms=end,
                )
            )
    return CaptionPlan(duration_ms=edl.duration_ms, cues=tuple(cues))


def _cue_text(cue: CaptionCue, *, active_index: int) -> str:
    style = THEME_STYLES[cue.theme]
    pieces: list[str] = []
    for index, word in enumerate(cue.words):
        text = _ass_text(word.text)
        if index == active_index and _is_highlightable(word.text):
            pieces.append(
                f"{{\\c&H{HIGHLIGHT_BGR}&\\fscx{style.active_scale}\\fscy{style.active_scale}}}"
                f"{text}{{\\c&HFFFFFF&\\fscx100\\fscy100}}"
            )
        else:
            pieces.append(text)
    # Reuse the shipped caption width budget. A fixed word count alone clips
    # long phrases such as "différencier maintenant les" on a vertical frame.
    displays = [_ass_text(word.text) for word in cue.words]
    lines = _layout_lines(displays)
    longest = max(sum(len(displays[i]) for i in line) + len(line) - 1 for line in lines)
    font_size = style.font_size
    if longest * font_size > MAX_LINE_CHARS * BASE_FONT_SIZE:
        font_size = max(MIN_FONT_SIZE, BASE_FONT_SIZE * MAX_LINE_CHARS // longest)
    if longest * font_size > MAX_LINE_CHARS * BASE_FONT_SIZE:
        raise EDLCaptionError(f"cue {cue.cue_id}: token exceeds readable caption width")
    prefix = f"{{\\fs{font_size}}}" if font_size != style.font_size else ""
    return prefix + "\\N".join(" ".join(pieces[i] for i in line) for line in lines)


def render_ass(
    plan: CaptionPlan,
    *,
    hook_text: str | None = None,
    hook_seconds: float = DEFAULT_HOOK_SECONDS,
) -> str:
    """Render a fixed-style ASS document from a previously validated plan.

    ``hook_text`` (optional, absent by default) prints the clip's promise as a
    static title over the first ``hook_seconds`` of the timeline. It occupies
    the reserved top band, so it cannot collide with either caption position.
    """

    lines: list[str] = []
    hook_line = None
    if hook_text:
        hook_line = hook_dialogue_line(
            hook_text,
            start_seconds=0.0,
            end_seconds=min(hook_seconds, plan.duration_ms / 1000.0),
        )
    if hook_line:
        lines.append(hook_line)
    for cue_index, cue in enumerate(plan.cues):
        if cue.theme not in THEME_STYLES:
            raise EDLCaptionError(f"cue {cue.cue_id}: unsupported theme")
        cue_limit = (
            plan.cues[cue_index + 1].timeline_in_ms
            if cue_index + 1 < len(plan.cues)
            else plan.duration_ms
        )
        emitted = 0
        for index, word in enumerate(cue.words):
            start = word.timeline_in_ms
            end = (
                cue.words[index + 1].timeline_in_ms
                if index + 1 < len(cue.words)
                else word.timeline_out_ms
            )
            end = min(end, cue_limit)
            if end // 10 <= start // 10:
                # Tied ASR timestamps share the next visible active-word event;
                # the whole cue stays visible, without two superimposed lines.
                continue
            lines.append(
                "Dialogue: 0,"
                f"{_format_ass_time(start)},{_format_ass_time(end)},"
                f"{cue.style_name},,0,0,{cue.margin_v},,{_cue_text(cue, active_index=index)}"
            )
            emitted += 1
        if not emitted:
            raise EDLCaptionError(f"cue {cue.cue_id}: no visible ASS interval")
    return ass_header(with_hook=hook_line is not None) + "\n".join(lines) + ("\n" if lines else "")


def write_ass_for_edl(
    plan: CaptionPlan,
    *,
    out_path: str,
    hook_text: str | None = None,
    hook_seconds: float = DEFAULT_HOOK_SECONDS,
) -> bool:
    """Write the ASS file when there is anything to burn in.

    Without a hook this keeps the old contract exactly: no cue, no file. A hook
    alone is still worth burning — the promise is what holds the viewer.
    """

    document = render_ass(plan, hook_text=hook_text, hook_seconds=hook_seconds)
    if "Dialogue:" not in document:
        return False
    Path(out_path).write_text(document, encoding="utf-8")
    return True
