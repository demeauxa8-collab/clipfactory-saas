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

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..models import Transcript
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


def _groups(words: tuple[CaptionWord, ...], *, max_words: int) -> list[tuple[CaptionWord, ...]]:
    """Split one shot into pause-aware, visually balanced caption cues.

    A simple fixed-width chunker creates distracting orphan tails: four words
    become ``3 + 1`` and seven words become ``3 + 3 + 1``.  Within each
    uninterrupted phrase we instead choose the minimum number of cues and
    distribute the words as evenly as possible (``2 + 2`` and ``3 + 2 + 2``).
    Pause boundaries remain authoritative and are never crossed.
    """

    if max_words <= 0:
        raise EDLCaptionError("caption max_words must be positive")

    phrases: list[tuple[CaptionWord, ...]] = []
    current: list[CaptionWord] = []
    for word in words:
        gap = word.timeline_in_ms - current[-1].timeline_out_ms if current else 0
        if current and gap >= _PAUSE_CUT_MS:
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
    return groups


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
    for shot_index, shot in enumerate(edl.shots):
        if shot.caption_theme not in _THEMES:
            raise EDLCaptionError(f"shot {shot.shot_id}: unsupported caption theme")
        if shot.caption_theme == "none":
            continue
        style = THEME_STYLES[shot.caption_theme]
        zone = _safe_zone_for_shot(shot, safe_zones)
        words = _caption_words_for_shot(shot, transcript)
        for group_index, group in enumerate(_groups(words, max_words=style.max_words)):
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
    return " ".join(piece for piece in pieces if piece)


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
    for cue in plan.cues:
        if cue.theme not in THEME_STYLES:
            raise EDLCaptionError(f"cue {cue.cue_id}: unsupported theme")
        for index, word in enumerate(cue.words):
            start = word.timeline_in_ms
            end = (
                cue.words[index + 1].timeline_in_ms
                if index + 1 < len(cue.words)
                else word.timeline_out_ms
            )
            if end <= start:
                end = word.timeline_out_ms
            if end <= start:
                raise EDLCaptionError(f"cue {cue.cue_id}: non-positive active-word interval")
            lines.append(
                "Dialogue: 0,"
                f"{_format_ass_time(start)},{_format_ass_time(end)},"
                f"{cue.style_name},,0,0,{cue.margin_v},,{_cue_text(cue, active_index=index)}"
            )
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
