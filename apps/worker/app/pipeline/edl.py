"""Deterministic Edit Decision List compiler for ClipFactory V2.

The selection model is allowed to direct the edit — reorder or reuse spoken
moments, choose framing, effects, transitions, captions, music and SFX — but it
never emits raw FFmpeg syntax or authoritative floating-point timecodes.

Every spoken boundary is expressed as an inclusive transcript ``word_id``. The
compiler below resolves those IDs to source milliseconds, validates the closed
operation catalogue, builds a reproducible output timeline and groups nearby
source ranges into decode islands for the renderer.

This module is intentionally independent of providers and FFmpeg. It is the
trust boundary between an untrusted LLM payload and the render engine.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Literal

from ..models import Transcript

ShotRole = Literal["hook", "setup", "bridge", "proof", "payoff", "reaction", "cta"]
FramingMode = Literal[
    "source_safe",
    "fit_blur",
    "locked_face",
    "follow_primary_face",
    "screen_focus",
    "pip_proof",
]
EffectKind = Literal[
    "punch_in",
    "zoom_out",
    "freeze",
    "speed_ramp",
    "flash",
    "shake",
    "blur",
    "color_pop",
]
TransitionKind = Literal[
    "hard_cut",
    "time_jump",
    "reveal",
    "contrast",
    "hard_impact",
]
CaptionTheme = Literal[
    "hook_bold",
    "standard_karaoke",
    "proof_clean",
    "reaction_pop",
    "none",
]

SUPPORTED_FRAMING_MODES = frozenset(
    {
        "source_safe",
        "fit_blur",
        "locked_face",
        "follow_primary_face",
        "screen_focus",
        "pip_proof",
    }
)
SUPPORTED_SHOT_ROLES = frozenset(
    {"hook", "setup", "bridge", "proof", "payoff", "reaction", "cta"}
)
SUPPORTED_EFFECTS = frozenset(
    {
        "punch_in",
        "zoom_out",
        "freeze",
        "speed_ramp",
        "flash",
        "shake",
        "blur",
        "color_pop",
    }
)
SUPPORTED_TRANSITIONS = frozenset(
    {"hard_cut", "time_jump", "reveal", "contrast", "hard_impact"}
)
SUPPORTED_CAPTION_THEMES = frozenset(
    {"hook_bold", "standard_karaoke", "proof_clean", "reaction_pop", "none"}
)

MAX_SHOTS = 30
MAX_EFFECTS_PER_SHOT = 3
MIN_SHOT_SOURCE_MS = 250
MAX_SHOT_SOURCE_MS = 60_000
MIN_SPEED = 0.5
MAX_SPEED = 2.0
MAX_PRE_ROLL_MS = 250
MAX_POST_ROLL_MS = 400
MAX_EFFECT_DURATION_MS = 1_500
MAX_MUSIC_TRACKS = 2
MAX_SFX_CUES = 12

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_WORD_ID_RE = re.compile(r"^w_(\d{6})$")


class EDLValidationError(ValueError):
    """An LLM edit plan cannot be compiled safely or deterministically."""


@dataclass(frozen=True)
class FramingIntent:
    mode: FramingMode = "source_safe"
    center_x: float = 0.5
    base_scale: float = 1.0


@dataclass(frozen=True)
class EffectIntent:
    kind: EffectKind
    at_word_id: int | None = None
    duration_ms: int = 350
    intensity: float = 0.5


@dataclass(frozen=True)
class EditShotIntent:
    """One timeline shot. List order is the final editorial order.

    ``from_word_id`` and ``to_word_id`` are inclusive indices into
    ``Transcript.words``. Reusing, overlapping and reordering word ranges is
    allowed; reversing the word order inside a single shot is not.
    """

    shot_id: str
    role: ShotRole
    from_word_id: int
    to_word_id: int
    start_anchor: str = ""
    end_anchor: str = ""
    framing: FramingIntent = field(default_factory=FramingIntent)
    effects: tuple[EffectIntent, ...] = ()
    transition_out: TransitionKind = "hard_cut"
    caption_theme: CaptionTheme = "standard_karaoke"
    speed: float = 1.0
    pre_roll_ms: int = 0
    post_roll_ms: int = 120


@dataclass(frozen=True)
class MusicIntent:
    """A reference to a licensed/local catalogue entry, never a file path."""

    asset_id: str
    start_shot_id: str | None = None
    end_shot_id: str | None = None
    gain_db: float = -22.0
    ducking_db: float = -10.0
    fade_in_ms: int = 300
    fade_out_ms: int = 600
    loop: bool = True


@dataclass(frozen=True)
class SFXCueIntent:
    """A catalogue SFX placed on a word occurrence inside a specific shot."""

    asset_id: str
    shot_id: str
    at_word_id: int
    gain_db: float = -10.0


@dataclass(frozen=True)
class EditIntentPlan:
    schema_version: str
    editorial_thesis: str
    shots: tuple[EditShotIntent, ...]
    music: tuple[MusicIntent, ...] = ()
    sfx: tuple[SFXCueIntent, ...] = ()


@dataclass(frozen=True)
class InclusiveWordRange:
    """A compiler-owned inclusive range in the normalized transcript."""

    from_word_id: int
    to_word_id: int


@dataclass(frozen=True)
class EditScope:
    """Explicit authority granted to an edit plan.

    ``allowed_word_ranges`` can cover one selected arc or the full transcript,
    but that choice is made by pipeline policy rather than smuggled in by the
    model. ``protected_word_ranges`` may be omitted or kept whole, never cut in
    the middle (useful for negations, prices and verified payoff phrases).
    """

    allowed_word_ranges: tuple[InclusiveWordRange, ...]
    protected_word_ranges: tuple[InclusiveWordRange, ...] = ()
    required_word_ranges: tuple[InclusiveWordRange, ...] = ()


@dataclass(frozen=True)
class CompiledWordOccurrence:
    """One source word occurrence on the output timeline.

    Replayed source words deliberately get separate ``occurrence_id`` values,
    which keeps captions and word-anchored SFX deterministic.
    """

    occurrence_id: str
    shot_id: str
    word_id: int
    source_in_ms: int
    source_out_ms: int
    timeline_in_ms: int
    timeline_out_ms: int
    timeline_in_frame: int
    timeline_out_frame: int


@dataclass(frozen=True)
class CompiledShot:
    shot_id: str
    role: ShotRole
    from_word_id: int
    to_word_id: int
    source_in_ms: int
    source_out_ms: int
    timeline_in_ms: int
    timeline_out_ms: int
    timeline_in_frame: int
    timeline_out_frame: int
    speed: float
    framing: FramingIntent
    effects: tuple[EffectIntent, ...]
    transition_out: TransitionKind
    caption_theme: CaptionTheme
    word_occurrences: tuple[CompiledWordOccurrence, ...]

    @property
    def source_duration_ms(self) -> int:
        return self.source_out_ms - self.source_in_ms

    @property
    def timeline_duration_ms(self) -> int:
        return self.timeline_out_ms - self.timeline_in_ms


@dataclass(frozen=True)
class CompiledMusicTrack:
    asset_id: str
    timeline_in_ms: int
    timeline_out_ms: int
    gain_db: float
    ducking_db: float
    fade_in_ms: int
    fade_out_ms: int
    loop: bool


@dataclass(frozen=True)
class CompiledSFXCue:
    asset_id: str
    timeline_at_ms: int
    gain_db: float
    shot_id: str
    word_id: int


@dataclass(frozen=True)
class DecodeIsland:
    """One accurately-seeked decoder input shared by nearby source shots."""

    island_id: str
    source_in_ms: int
    source_out_ms: int
    shot_ids: tuple[str, ...]


@dataclass(frozen=True)
class CompiledEDL:
    schema_version: str
    editorial_thesis: str
    fps: int
    width: int
    height: int
    duration_ms: int
    duration_frames: int
    shots: tuple[CompiledShot, ...]
    music: tuple[CompiledMusicTrack, ...]
    sfx: tuple[CompiledSFXCue, ...]
    decode_islands: tuple[DecodeIsland, ...]


def _require_safe_id(value: str, *, label: str) -> None:
    if not _SAFE_ID_RE.fullmatch(value):
        raise EDLValidationError(
            f"{label} must be a catalogue-safe ID (letters, digits, _ or -), got {value!r}"
        )


def word_id_for_index(index: int) -> str:
    if not 0 <= index <= 999_999:
        raise ValueError("word index must be in [0, 999999]")
    return f"w_{index:06d}"


def word_index_from_id(word_id: str) -> int:
    match = _WORD_ID_RE.fullmatch(word_id)
    if match is None:
        raise EDLValidationError(f"invalid word_id {word_id!r}; expected w_000000")
    return int(match.group(1))


def _normalize_anchor(text: str) -> str:
    return " ".join(
        "".join(character if character.isalnum() else " " for character in text.lower()).split()
    )


def _validate_anchor_quote(
    quote: str,
    *,
    transcript: Transcript,
    boundary_word_id: int,
    shot_from_word_id: int,
    shot_to_word_id: int,
    edge: Literal["start", "end"],
    shot_id: str,
) -> None:
    if not quote:
        return  # programmatic/backward-compatible plans may rely on IDs alone
    normalized_quote = _normalize_anchor(quote)
    tokens = normalized_quote.split()
    if not 1 <= len(tokens) <= 12:
        raise EDLValidationError(
            f"shot {shot_id}: {edge}_anchor must contain between 1 and 12 words"
        )
    # A single ASR word can normalize to several whitespace-separated tokens
    # (for example ``J'ai`` -> ``j ai``). Accumulate source *words* until the
    # normalized phrase reaches the quote length instead of assuming one
    # normalized token equals one TranscriptWord.
    selected: list[str] = []
    if edge == "start":
        indices = range(boundary_word_id, shot_to_word_id + 1)
    else:
        indices = range(boundary_word_id, shot_from_word_id - 1, -1)
    for index in indices:
        normalized_word = _normalize_anchor(transcript.words[index].word)
        if edge == "start":
            selected.append(normalized_word)
        else:
            selected.insert(0, normalized_word)
        if len(" ".join(selected)) >= len(normalized_quote):
            break
    actual = " ".join(part for part in selected if part)
    if actual != normalized_quote:
        raise EDLValidationError(
            f"shot {shot_id}: {edge}_anchor does not match its declared word_id"
        )


def _validate_shot_intent(
    shot: EditShotIntent,
    *,
    transcript: Transcript,
) -> None:
    word_count = len(transcript.words)
    _require_safe_id(shot.shot_id, label="shot_id")
    if shot.role not in SUPPORTED_SHOT_ROLES:
        raise EDLValidationError(f"shot {shot.shot_id}: unsupported role {shot.role!r}")
    if not (0 <= shot.from_word_id <= shot.to_word_id < word_count):
        raise EDLValidationError(
            f"shot {shot.shot_id}: invalid inclusive word range "
            f"{shot.from_word_id}..{shot.to_word_id} for {word_count} words"
        )
    if shot.framing.mode not in SUPPORTED_FRAMING_MODES:
        raise EDLValidationError(
            f"shot {shot.shot_id}: unsupported framing {shot.framing.mode!r}"
        )
    if not 0.0 <= shot.framing.center_x <= 1.0:
        raise EDLValidationError(f"shot {shot.shot_id}: center_x must be in [0, 1]")
    if not 1.0 <= shot.framing.base_scale <= 1.35:
        raise EDLValidationError(f"shot {shot.shot_id}: base_scale must be in [1, 1.35]")
    if not MIN_SPEED <= shot.speed <= MAX_SPEED:
        raise EDLValidationError(
            f"shot {shot.shot_id}: speed must be in [{MIN_SPEED}, {MAX_SPEED}]"
        )
    if not 0 <= shot.pre_roll_ms <= MAX_PRE_ROLL_MS:
        raise EDLValidationError(
            f"shot {shot.shot_id}: pre_roll_ms must be in [0, {MAX_PRE_ROLL_MS}]"
        )
    if not 0 <= shot.post_roll_ms <= MAX_POST_ROLL_MS:
        raise EDLValidationError(
            f"shot {shot.shot_id}: post_roll_ms must be in [0, {MAX_POST_ROLL_MS}]"
        )
    if len(shot.effects) > MAX_EFFECTS_PER_SHOT:
        raise EDLValidationError(
            f"shot {shot.shot_id}: at most {MAX_EFFECTS_PER_SHOT} effects are allowed"
        )
    for effect in shot.effects:
        if effect.kind not in SUPPORTED_EFFECTS:
            raise EDLValidationError(
                f"shot {shot.shot_id}: unsupported effect {effect.kind!r}"
            )
        if not 50 <= effect.duration_ms <= MAX_EFFECT_DURATION_MS:
            raise EDLValidationError(
                f"shot {shot.shot_id}: effect duration must be in "
                f"[50, {MAX_EFFECT_DURATION_MS}]ms"
            )
        if not 0.0 <= effect.intensity <= 1.0:
            raise EDLValidationError(
                f"shot {shot.shot_id}: effect intensity must be in [0, 1]"
            )
        if effect.at_word_id is not None and not (
            shot.from_word_id <= effect.at_word_id <= shot.to_word_id
        ):
            raise EDLValidationError(
                f"shot {shot.shot_id}: effect word {effect.at_word_id} is outside the shot"
            )
    if shot.transition_out not in SUPPORTED_TRANSITIONS:
        raise EDLValidationError(
            f"shot {shot.shot_id}: unsupported transition {shot.transition_out!r}"
        )
    if shot.caption_theme not in SUPPORTED_CAPTION_THEMES:
        raise EDLValidationError(
            f"shot {shot.shot_id}: unsupported caption theme {shot.caption_theme!r}"
        )
    _validate_anchor_quote(
        shot.start_anchor,
        transcript=transcript,
        boundary_word_id=shot.from_word_id,
        shot_from_word_id=shot.from_word_id,
        shot_to_word_id=shot.to_word_id,
        edge="start",
        shot_id=shot.shot_id,
    )
    _validate_anchor_quote(
        shot.end_anchor,
        transcript=transcript,
        boundary_word_id=shot.to_word_id,
        shot_from_word_id=shot.from_word_id,
        shot_to_word_id=shot.to_word_id,
        edge="end",
        shot_id=shot.shot_id,
    )


def _validate_range(
    word_range: InclusiveWordRange,
    *,
    word_count: int,
    label: str,
) -> None:
    if not 0 <= word_range.from_word_id <= word_range.to_word_id < word_count:
        raise EDLValidationError(
            f"{label} has invalid inclusive word range "
            f"{word_range.from_word_id}..{word_range.to_word_id}"
        )


def _validate_edit_scope(scope: EditScope, *, word_count: int) -> None:
    if not scope.allowed_word_ranges:
        raise EDLValidationError("edit scope needs at least one allowed word range")
    for index, word_range in enumerate(scope.allowed_word_ranges):
        _validate_range(word_range, word_count=word_count, label=f"allowed range {index}")
    for index, word_range in enumerate(scope.protected_word_ranges):
        _validate_range(word_range, word_count=word_count, label=f"protected range {index}")
    for index, word_range in enumerate(scope.required_word_ranges):
        _validate_range(word_range, word_count=word_count, label=f"required range {index}")


def _validate_shot_scope(shot: EditShotIntent, *, scope: EditScope) -> None:
    if not any(
        allowed.from_word_id <= shot.from_word_id
        and shot.to_word_id <= allowed.to_word_id
        for allowed in scope.allowed_word_ranges
    ):
        raise EDLValidationError(
            f"shot {shot.shot_id}: word range is outside the allowed edit scope"
        )
    for protected in scope.protected_word_ranges:
        intersects = not (
            shot.to_word_id < protected.from_word_id
            or shot.from_word_id > protected.to_word_id
        )
        contains_all = (
            shot.from_word_id <= protected.from_word_id
            and shot.to_word_id >= protected.to_word_id
        )
        if intersects and not contains_all:
            raise EDLValidationError(
                f"shot {shot.shot_id}: cuts through protected word range "
                f"{protected.from_word_id}..{protected.to_word_id}"
            )


def _compile_music(
    music: tuple[MusicIntent, ...],
    *,
    shots_by_id: dict[str, CompiledShot],
    clip_duration_ms: int,
    allowed_asset_ids: set[str] | frozenset[str] | None,
) -> tuple[CompiledMusicTrack, ...]:
    if len(music) > MAX_MUSIC_TRACKS:
        raise EDLValidationError(f"at most {MAX_MUSIC_TRACKS} music tracks are allowed")
    out: list[CompiledMusicTrack] = []
    for item in music:
        _require_safe_id(item.asset_id, label="music asset_id")
        if allowed_asset_ids is not None and item.asset_id not in allowed_asset_ids:
            raise EDLValidationError(f"unknown music asset_id {item.asset_id!r}")
        if not -40.0 <= item.gain_db <= -6.0:
            raise EDLValidationError("music gain_db must be in [-40, -6]")
        if not -24.0 <= item.ducking_db <= 0.0:
            raise EDLValidationError("music ducking_db must be in [-24, 0]")
        if not 0 <= item.fade_in_ms <= 5_000 or not 0 <= item.fade_out_ms <= 5_000:
            raise EDLValidationError("music fades must be in [0, 5000]ms")

        start = 0
        end = clip_duration_ms
        if item.start_shot_id is not None:
            if item.start_shot_id not in shots_by_id:
                raise EDLValidationError(
                    f"music references unknown start shot {item.start_shot_id!r}"
                )
            start = shots_by_id[item.start_shot_id].timeline_in_ms
        if item.end_shot_id is not None:
            if item.end_shot_id not in shots_by_id:
                raise EDLValidationError(
                    f"music references unknown end shot {item.end_shot_id!r}"
                )
            end = shots_by_id[item.end_shot_id].timeline_out_ms
        if end <= start:
            raise EDLValidationError("music end must be after its start")
        out.append(
            CompiledMusicTrack(
                asset_id=item.asset_id,
                timeline_in_ms=start,
                timeline_out_ms=end,
                gain_db=item.gain_db,
                ducking_db=item.ducking_db,
                fade_in_ms=min(item.fade_in_ms, end - start),
                fade_out_ms=min(item.fade_out_ms, end - start),
                loop=item.loop,
            )
        )
    return tuple(out)


def _compile_sfx(
    cues: tuple[SFXCueIntent, ...],
    *,
    shots_by_id: dict[str, CompiledShot],
    allowed_asset_ids: set[str] | frozenset[str] | None,
) -> tuple[CompiledSFXCue, ...]:
    if len(cues) > MAX_SFX_CUES:
        raise EDLValidationError(f"at most {MAX_SFX_CUES} SFX cues are allowed")
    out: list[CompiledSFXCue] = []
    for cue in cues:
        _require_safe_id(cue.asset_id, label="SFX asset_id")
        if allowed_asset_ids is not None and cue.asset_id not in allowed_asset_ids:
            raise EDLValidationError(f"unknown SFX asset_id {cue.asset_id!r}")
        shot = shots_by_id.get(cue.shot_id)
        if shot is None:
            raise EDLValidationError(f"SFX references unknown shot {cue.shot_id!r}")
        if not shot.from_word_id <= cue.at_word_id <= shot.to_word_id:
            raise EDLValidationError(
                f"SFX word {cue.at_word_id} is outside shot {cue.shot_id}"
            )
        if not -30.0 <= cue.gain_db <= 6.0:
            raise EDLValidationError("SFX gain_db must be in [-30, 6]")
        occurrence = next(
            item for item in shot.word_occurrences if item.word_id == cue.at_word_id
        )
        out.append(
            CompiledSFXCue(
                asset_id=cue.asset_id,
                timeline_at_ms=occurrence.timeline_in_ms,
                gain_db=cue.gain_db,
                shot_id=cue.shot_id,
                word_id=cue.at_word_id,
            )
        )
    return tuple(out)


def plan_decode_islands(
    shots: tuple[CompiledShot, ...],
    *,
    max_gap_ms: int = 2_000,
    max_span_ms: int = 15_000,
) -> tuple[DecodeIsland, ...]:
    """Cluster source-near shots into a small number of decoder inputs.

    A long source with shots at 4s and 480s should not be decoded continuously,
    while six jump cuts inside the same 10s passage should not open six decoder
    contexts. Islands are independent of timeline order, so LLM reordering and
    duplicated source moments remain supported.
    """
    if max_gap_ms < 0 or max_span_ms <= 0:
        raise ValueError("decode island bounds must be positive")
    ordered = sorted(shots, key=lambda s: (s.source_in_ms, s.source_out_ms, s.shot_id))
    groups: list[list[CompiledShot]] = []
    for shot in ordered:
        if not groups:
            groups.append([shot])
            continue
        group = groups[-1]
        group_start = min(item.source_in_ms for item in group)
        group_end = max(item.source_out_ms for item in group)
        merged_end = max(group_end, shot.source_out_ms)
        gap = max(0, shot.source_in_ms - group_end)
        if gap <= max_gap_ms and merged_end - group_start <= max_span_ms:
            group.append(shot)
        else:
            groups.append([shot])

    return tuple(
        DecodeIsland(
            island_id=f"island_{idx:02d}",
            source_in_ms=min(shot.source_in_ms for shot in group),
            source_out_ms=max(shot.source_out_ms for shot in group),
            shot_ids=tuple(shot.shot_id for shot in group),
        )
        for idx, group in enumerate(groups)
    )


def compile_edit_intent(
    plan: EditIntentPlan,
    transcript: Transcript,
    *,
    source_duration_ms: int,
    fps: int = 30,
    width: int = 1080,
    height: int = 1920,
    target_duration_seconds: int | None = None,
    allowed_music_asset_ids: set[str] | frozenset[str] | None = None,
    allowed_sfx_asset_ids: set[str] | frozenset[str] | None = None,
    edit_scope: EditScope | None = None,
) -> CompiledEDL:
    """Compile an LLM-directed plan into a validated, reproducible timeline."""
    if plan.schema_version != "2.0":
        raise EDLValidationError(f"unsupported EDL schema version {plan.schema_version!r}")
    if not transcript.words:
        raise EDLValidationError("cannot compile an EDL without transcript words")
    if not plan.editorial_thesis.strip():
        raise EDLValidationError("editorial_thesis must not be empty")
    if not 1 <= len(plan.shots) <= MAX_SHOTS:
        raise EDLValidationError(f"an EDL needs between 1 and {MAX_SHOTS} shots")
    if source_duration_ms <= 0:
        raise EDLValidationError("source_duration_ms must be positive")
    if fps not in {24, 25, 30, 50, 60}:
        raise EDLValidationError("fps must be one of 24, 25, 30, 50 or 60")
    if width <= 0 or height <= 0:
        raise EDLValidationError("output dimensions must be positive")
    if target_duration_seconds is not None and target_duration_seconds <= 0:
        raise EDLValidationError("target_duration_seconds must be positive")
    if edit_scope is not None:
        _validate_edit_scope(edit_scope, word_count=len(transcript.words))

    compiled: list[CompiledShot] = []
    seen_ids: set[str] = set()
    timeline_cursor_frames = 0
    for intent in plan.shots:
        _validate_shot_intent(intent, transcript=transcript)
        if edit_scope is not None:
            _validate_shot_scope(intent, scope=edit_scope)
        if intent.shot_id in seen_ids:
            raise EDLValidationError(f"duplicate shot_id {intent.shot_id!r}")
        seen_ids.add(intent.shot_id)

        first_word = transcript.words[intent.from_word_id]
        last_word = transcript.words[intent.to_word_id]
        source_in = max(0, round(first_word.start * 1000) - intent.pre_roll_ms)
        source_out = min(
            source_duration_ms,
            round(last_word.end * 1000) + intent.post_roll_ms,
        )
        source_duration = source_out - source_in
        if not MIN_SHOT_SOURCE_MS <= source_duration <= MAX_SHOT_SOURCE_MS:
            raise EDLValidationError(
                f"shot {intent.shot_id}: source duration {source_duration}ms is outside "
                f"[{MIN_SHOT_SOURCE_MS}, {MAX_SHOT_SOURCE_MS}]ms"
            )
        # The output timeline is frame-authoritative. Audio is trimmed/padded to
        # these same boundaries by the renderer, so captions, mux duration and
        # repeated shots share one deterministic clock.
        timeline_frames = max(1, round((source_duration / intent.speed) * fps / 1000))
        timeline_in_frame = timeline_cursor_frames
        timeline_out_frame = timeline_cursor_frames + timeline_frames
        timeline_in_ms = round(timeline_in_frame * 1000 / fps)
        timeline_out_ms = round(timeline_out_frame * 1000 / fps)
        occurrences: list[CompiledWordOccurrence] = []
        for word_id in range(intent.from_word_id, intent.to_word_id + 1):
            word = transcript.words[word_id]
            source_word_in = max(source_in, round(word.start * 1000))
            source_word_out = min(source_out, round(word.end * 1000))
            occurrence_in_offset_frames = round(
                ((source_word_in - source_in) / intent.speed) * fps / 1000
            )
            occurrence_out_offset_frames = round(
                ((source_word_out - source_in) / intent.speed) * fps / 1000
            )
            # ASR providers occasionally emit zero-duration words.  Every word
            # occurrence still needs a visible/renderable interval, so clamp it
            # to at least one authoritative output frame inside the shot.
            occurrence_in_offset_frames = min(
                timeline_frames - 1,
                max(0, occurrence_in_offset_frames),
            )
            occurrence_out_offset_frames = min(
                timeline_frames,
                max(occurrence_in_offset_frames + 1, occurrence_out_offset_frames),
            )
            occurrence_in_frame = timeline_in_frame + occurrence_in_offset_frames
            occurrence_out_frame = timeline_in_frame + occurrence_out_offset_frames
            occurrence_in = round(occurrence_in_frame * 1000 / fps)
            occurrence_out = round(occurrence_out_frame * 1000 / fps)
            occurrences.append(
                CompiledWordOccurrence(
                    occurrence_id=f"{intent.shot_id}:{word_id_for_index(word_id)}",
                    shot_id=intent.shot_id,
                    word_id=word_id,
                    source_in_ms=source_word_in,
                    source_out_ms=source_word_out,
                    timeline_in_ms=occurrence_in,
                    timeline_out_ms=occurrence_out,
                    timeline_in_frame=occurrence_in_frame,
                    timeline_out_frame=occurrence_out_frame,
                )
            )
        compiled.append(
            CompiledShot(
                shot_id=intent.shot_id,
                role=intent.role,
                from_word_id=intent.from_word_id,
                to_word_id=intent.to_word_id,
                source_in_ms=source_in,
                source_out_ms=source_out,
                timeline_in_ms=timeline_in_ms,
                timeline_out_ms=timeline_out_ms,
                timeline_in_frame=timeline_in_frame,
                timeline_out_frame=timeline_out_frame,
                speed=intent.speed,
                framing=intent.framing,
                effects=intent.effects,
                transition_out=intent.transition_out,
                caption_theme=intent.caption_theme,
                word_occurrences=tuple(occurrences),
            )
        )
        timeline_cursor_frames = timeline_out_frame

    timeline_cursor_ms = round(timeline_cursor_frames * 1000 / fps)

    if compiled[-1].transition_out != "hard_cut":
        raise EDLValidationError("the final shot transition_out must be hard_cut")
    if edit_scope is not None:
        for required in edit_scope.required_word_ranges:
            if not any(
                shot.from_word_id <= required.from_word_id
                and shot.to_word_id >= required.to_word_id
                for shot in compiled
            ):
                raise EDLValidationError(
                    "required word range is missing from the compiled edit: "
                    f"{required.from_word_id}..{required.to_word_id}"
                )

    # Visual changes need a budget; unrestricted effect spam is not editorial
    # freedom. It is an invalid plan that should be repaired by the model.
    effect_count = sum(len(shot.effects) for shot in compiled)
    effect_budget = max(1, math.ceil(timeline_cursor_ms / 2_500))
    if effect_count > effect_budget:
        raise EDLValidationError(
            f"effect budget exceeded: {effect_count} requested, {effect_budget} allowed"
        )

    if target_duration_seconds is not None:
        target_ms = target_duration_seconds * 1000
        tolerance_ms = max(2_000, round(target_ms * 0.2))
        if abs(timeline_cursor_ms - target_ms) > tolerance_ms:
            raise EDLValidationError(
                f"compiled duration {timeline_cursor_ms}ms is outside target "
                f"{target_ms}ms +/- {tolerance_ms}ms"
            )

    shots = tuple(compiled)
    shots_by_id = {shot.shot_id: shot for shot in shots}
    music = _compile_music(
        plan.music,
        shots_by_id=shots_by_id,
        clip_duration_ms=timeline_cursor_ms,
        allowed_asset_ids=allowed_music_asset_ids,
    )
    sfx = _compile_sfx(
        plan.sfx,
        shots_by_id=shots_by_id,
        allowed_asset_ids=allowed_sfx_asset_ids,
    )
    return CompiledEDL(
        schema_version=plan.schema_version,
        editorial_thesis=plan.editorial_thesis.strip()[:500],
        fps=fps,
        width=width,
        height=height,
        duration_ms=timeline_cursor_ms,
        duration_frames=timeline_cursor_frames,
        shots=shots,
        music=music,
        sfx=sfx,
        decode_islands=plan_decode_islands(shots),
    )
