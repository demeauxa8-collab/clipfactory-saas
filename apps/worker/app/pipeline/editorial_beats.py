"""Evidence-backed editorial beat graph for the local ClipFactory V2 path.

The EDL compiler owns edit timing and FFmpeg execution.  This module owns an
earlier, deliberately pure artefact: a compact map of the *authorised* spoken,
visual and audio evidence from which an editing director may choose.  It does
not call a provider, extract media, or generate an edit.

All speech references are inclusive transcript word indexes.  The graph derives
milliseconds from those words only as context for visual/audio evidence; they
are never alternate edit timecodes.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import pairwise
from typing import Literal

from ..models import MontageCandidate, Transcript, VideoEvent, VideoMap
from .audio_map import AudioMap, ProtectedWordSpan, TimedWord, classify_silences
from .edl import EditScope, InclusiveWordRange, word_id_for_index


class EditorialBeatError(ValueError):
    """The supplied evidence cannot form a safe, reproducible beat graph."""


SemanticRole = Literal[
    "unknown",
    "claim",
    "question",
    "setup",
    "constraint",
    "contrast",
    "proof",
    "reveal",
    "reaction",
    "payoff",
    "cta",
]
ProofRequirement = Literal["none", "spoken", "visible", "both"]
VisualKind = Literal[
    "talking_head",
    "reaction",
    "screen_proof",
    "object_proof",
    "demo",
    "broll",
    "scene_change",
]
FaceState = Literal["primary", "multiple", "none", "unknown"]
ScreenReadability = Literal["readable", "unreadable", "none", "unknown"]
MotionKind = Literal["still", "gesture", "action", "camera_change", "unknown"]
SafeZone = Literal["upper", "lower", "unknown"]
AudioBeatKind = Literal[
    "dead_air",
    "micro_pause",
    "dramatic_pause",
    "kept_pause",
]
BeatPurpose = Literal["hook", "orient", "escalate", "prove", "release", "payoff", "cta"]
BeatRelation = Literal[
    "answers",
    "proves",
    "contrasts",
    "causes",
    "escalates",
    "reframes",
    "repeats",
    "continues",
]
ContinuityState = Literal["continuous", "scene_change", "pause", "unknown"]

_SAFE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_SEMANTIC_ROLES = frozenset(
    {
        "unknown",
        "claim",
        "question",
        "setup",
        "constraint",
        "contrast",
        "proof",
        "reveal",
        "reaction",
        "payoff",
        "cta",
    }
)
_PROOF_REQUIREMENTS = frozenset({"none", "spoken", "visible", "both"})
_VISUAL_KINDS = frozenset(
    {"talking_head", "reaction", "screen_proof", "object_proof", "demo", "broll", "scene_change"}
)
_AUDIO_KINDS = frozenset({"dead_air", "micro_pause", "dramatic_pause", "kept_pause"})
_PURPOSES = frozenset({"hook", "orient", "escalate", "prove", "release", "payoff", "cta"})
_RELATIONS = frozenset(
    {"answers", "proves", "contrasts", "causes", "escalates", "reframes", "repeats", "continues"}
)
_CONTINUITY = frozenset({"continuous", "scene_change", "pause", "unknown"})
_VISIBLE_PROOF_KINDS = frozenset({"screen_proof", "object_proof", "demo"})
_FACE_STATES = frozenset({"primary", "multiple", "none", "unknown"})
_SCREEN_READABILITIES = frozenset({"readable", "unreadable", "none", "unknown"})
_MOTION_KINDS = frozenset({"still", "gesture", "action", "camera_change", "unknown"})
_SAFE_ZONES = frozenset({"upper", "lower", "unknown"})
_MOMENT_PROVENANCE = frozenset({"candidate_segment", "scope_range"})
_AUDIO_PROVENANCE = frozenset({"ffmpeg_silencedetect"})
_FRAMINGS = frozenset({"source_safe", "fit_blur", "locked_face", "screen_focus"})
_VISUAL_PROVENANCE = frozenset({"video_map", "verified_candidate"})


@dataclass(frozen=True)
class SourceMoment:
    """A contiguous, scoped spoken moment with transcript provenance."""

    moment_id: str
    word_range: InclusiveWordRange
    source_in_ms: int
    source_out_ms: int
    semantic_role: SemanticRole
    proof_requirement: ProofRequirement = "none"
    provenance: Literal["candidate_segment", "scope_range"] = "candidate_segment"


@dataclass(frozen=True)
class VisualFocusRegion:
    """Trusted normalized screen ROI that a renderer may preserve in frame."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class VisualBeat:
    """A visual observation. Overlap is intentional: several observations may
    describe the same source window without asserting a false single timeline.
    """

    visual_id: str
    source_event_id: str
    source_in_ms: int
    source_out_ms: int
    kind: VisualKind
    face_state: FaceState
    screen_readability: ScreenReadability
    motion: MotionKind
    safe_zone: SafeZone
    confidence: int
    focus_region: VisualFocusRegion | None = None
    # A coarse global VideoMap is useful discovery context, but may not prove
    # that a particular candidate window contains readable proof or a stable
    # face.  Only a candidate-window verification pass may unlock those
    # stronger editorial claims.  The default keeps older persisted/test
    # artefacts parseable while making them conservative.
    provenance: Literal["video_map", "verified_candidate"] = "video_map"


@dataclass(frozen=True)
class AudioBeat:
    """A measured silence/pause bounded by transcript word IDs where possible."""

    audio_id: str
    source_in_ms: int
    source_out_ms: int
    kind: AudioBeatKind
    left_word_id: int | None
    right_word_id: int | None
    provenance: Literal["ffmpeg_silencedetect"] = "ffmpeg_silencedetect"


@dataclass(frozen=True)
class EditorialBeat:
    """One director-facing choice grounded in a source moment and observations."""

    beat_id: str
    source_moment_id: str
    visual_ids: tuple[str, ...]
    audio_ids: tuple[str, ...]
    purpose: BeatPurpose
    available_framings: tuple[
        Literal["source_safe", "fit_blur", "locked_face", "screen_focus"], ...
    ]


@dataclass(frozen=True)
class BeatEdge:
    """A candidate editorial relation; it never itself moves a cut boundary."""

    edge_id: str
    from_beat_id: str
    to_beat_id: str
    relation: BeatRelation
    semantic_continuity: ContinuityState
    visual_continuity: ContinuityState
    audio_continuity: ContinuityState


@dataclass(frozen=True)
class EditorialBeatGraph:
    """Serializable local artefact offered to the edit-director prompt."""

    schema_version: Literal["1.0"]
    transcript_word_count: int
    scope: EditScope
    source_moments: tuple[SourceMoment, ...]
    visual_beats: tuple[VisualBeat, ...]
    audio_beats: tuple[AudioBeat, ...]
    editorial_beats: tuple[EditorialBeat, ...]
    edges: tuple[BeatEdge, ...]

    def to_prompt_payload(self) -> dict[str, object]:
        """Return JSON primitives only, with graph-owned IDs and bounded evidence.

        Raw provider objects, paths and FFmpeg output are deliberately absent.
        The editing prompt receives word IDs plus evidence labels, not authority
        to manufacture source timing.
        """
        validate_editorial_beat_graph(self)
        return {
            "schema_version": self.schema_version,
            "transcript_word_count": self.transcript_word_count,
            "scope": _scope_payload(self.scope),
            "source_moments": [_moment_payload(item) for item in self.source_moments],
            "visual_beats": [_visual_payload(item) for item in self.visual_beats],
            "audio_beats": [_audio_payload(item) for item in self.audio_beats],
            "editorial_beats": [_editorial_payload(item) for item in self.editorial_beats],
            "edges": [asdict(item) for item in self.edges],
        }

    def to_prompt_json(self) -> str:
        """Stable, prompt-safe JSON for provider callers."""
        return json.dumps(
            self.to_prompt_payload(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )


def _require_id(value: str, *, label: str) -> None:
    if not isinstance(value, str) or not _SAFE_ID_RE.fullmatch(value):
        raise EditorialBeatError(f"{label} must be a safe graph ID, got {value!r}")


def _finite_ms(value: int, *, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise EditorialBeatError(f"{label} must be a non-negative integer millisecond value")


def _validate_focus_region(region: VisualFocusRegion, *, label: str) -> None:
    if not isinstance(region, VisualFocusRegion):
        raise EditorialBeatError(f"{label} must be a VisualFocusRegion")
    values = (region.x, region.y, region.width, region.height)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise EditorialBeatError(f"{label} must contain numeric normalized coordinates")
    if not all(math.isfinite(float(value)) for value in values):
        raise EditorialBeatError(f"{label} must contain finite normalized coordinates")
    if (
        region.x < 0.0
        or region.y < 0.0
        or region.width < 0.05
        or region.height < 0.05
        or region.x + region.width > 1.0
        or region.y + region.height > 1.0
    ):
        raise EditorialBeatError(
            f"{label} must be at least 0.05 wide/high and contained inside the source frame"
        )


def _range_ms(transcript: Transcript, word_range: InclusiveWordRange) -> tuple[int, int]:
    first, last = transcript.words[word_range.from_word_id], transcript.words[word_range.to_word_id]
    source_in, source_out = round(first.start * 1000), round(last.end * 1000)
    if source_in < 0 or source_out <= source_in:
        raise EditorialBeatError("transcript word range has a non-positive source duration")
    return source_in, source_out


def _validate_scope(scope: EditScope, *, word_count: int) -> None:
    if not scope.allowed_word_ranges:
        raise EditorialBeatError("editorial beat graph needs at least one allowed scope range")
    for label, ranges in (
        ("allowed", scope.allowed_word_ranges),
        ("protected", scope.protected_word_ranges),
        ("required", scope.required_word_ranges),
    ):
        for item in ranges:
            if not 0 <= item.from_word_id <= item.to_word_id < word_count:
                raise EditorialBeatError(
                    f"{label} scope range is outside transcript: "
                    f"{item.from_word_id}..{item.to_word_id}"
                )


def _range_in_scope(word_range: InclusiveWordRange, scope: EditScope) -> bool:
    return any(
        allowed.from_word_id <= word_range.from_word_id
        and word_range.to_word_id <= allowed.to_word_id
        for allowed in scope.allowed_word_ranges
    )


def _overlaps_ms(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and other_start < end


def _candidate_moments(
    transcript: Transcript,
    scope: EditScope,
    candidate: MontageCandidate | None,
    proof_requirements: Mapping[str, ProofRequirement],
) -> tuple[SourceMoment, ...]:
    raw: list[tuple[InclusiveWordRange, SemanticRole, str]] = []
    if candidate is not None:
        role_map: dict[str, SemanticRole] = {
            "setup": "setup",
            "transition": "contrast",
            "payoff": "payoff",
            "single": "claim",
        }
        for index, segment in enumerate(candidate.segments):
            matched = [
                word_index
                for word_index, word in enumerate(transcript.words)
                if word.end > segment.start and word.start < segment.end
            ]
            if not matched:
                raise EditorialBeatError(
                    f"candidate segment {index} does not overlap transcript words"
                )
            raw.append(
                (
                    InclusiveWordRange(matched[0], matched[-1]),
                    role_map[segment.role],
                    "candidate_segment",
                )
            )
    else:
        raw.extend((item, "unknown", "scope_range") for item in scope.allowed_word_ranges)

    moments: list[SourceMoment] = []
    for index, (word_range, role, provenance) in enumerate(raw):
        if not _range_in_scope(word_range, scope):
            raise EditorialBeatError(
                f"source moment {index} is outside the explicitly authorised edit scope"
            )
        moment_id = f"moment_{index:02d}"
        requirement = proof_requirements.get(moment_id, "none")
        if requirement not in _PROOF_REQUIREMENTS:
            raise EditorialBeatError(
                f"moment {moment_id}: invalid proof requirement {requirement!r}"
            )
        source_in, source_out = _range_ms(transcript, word_range)
        moments.append(
            SourceMoment(
                moment_id=moment_id,
                word_range=word_range,
                source_in_ms=source_in,
                source_out_ms=source_out,
                semantic_role=role,
                proof_requirement=requirement,
                provenance=provenance,  # type: ignore[arg-type]
            )
        )
    unknown = sorted(set(proof_requirements) - {item.moment_id for item in moments})
    if unknown:
        raise EditorialBeatError(f"proof requirements reference unknown moments: {unknown}")
    return tuple(moments)


def _visual_kind(event: VideoEvent) -> VisualKind:
    haystack = " ".join([event.decor, event.action, *event.objects]).casefold()
    if "screen" in haystack or "desktop" in haystack or "dashboard" in haystack:
        return "screen_proof"
    if any(token in haystack for token in ("demo", "demonstr", "showing", "montr")):
        return "demo"
    if event.narrative_role == "transition":
        return "scene_change"
    if any(token in haystack for token in ("reaction", "react")):
        return "reaction"
    if event.objects and event.narrative_role == "payoff":
        return "object_proof"
    if "person" in event.people.casefold() or "talk" in event.action.casefold():
        return "talking_head"
    return "broll"


def _visual_beats(
    video_map: VideoMap | None,
    moments: Sequence[SourceMoment],
    readable_visual_event_ids: Collection[str],
    verified_visual_event_ids: Collection[str],
    visual_focus_regions: Mapping[str, VisualFocusRegion],
) -> tuple[VisualBeat, ...]:
    if video_map is None:
        if readable_visual_event_ids or verified_visual_event_ids or visual_focus_regions:
            raise EditorialBeatError(
                "visual verification/readability/ROI evidence requires a VideoMap"
            )
        return ()
    beats: list[VisualBeat] = []
    event_ids: set[str] = set()
    known_event_ids = {event.id for event in video_map.events}
    unknown_readability_ids = sorted(set(readable_visual_event_ids) - known_event_ids)
    if unknown_readability_ids:
        raise EditorialBeatError(
            f"readability evidence references unknown video-map events: {unknown_readability_ids}"
        )
    unknown_focus_ids = sorted(set(visual_focus_regions) - known_event_ids)
    if unknown_focus_ids:
        raise EditorialBeatError(
            f"focus-region evidence references unknown video-map events: {unknown_focus_ids}"
        )
    unknown_verified_ids = sorted(set(verified_visual_event_ids) - known_event_ids)
    if unknown_verified_ids:
        raise EditorialBeatError(
            f"verified visual evidence references unknown video-map events: {unknown_verified_ids}"
        )
    unverified_readability_ids = sorted(
        set(readable_visual_event_ids) - set(verified_visual_event_ids)
    )
    if unverified_readability_ids:
        raise EditorialBeatError(
            "readability evidence requires verified candidate visual events: "
            f"{unverified_readability_ids}"
        )
    unverified_focus_ids = sorted(set(visual_focus_regions) - set(verified_visual_event_ids))
    if unverified_focus_ids:
        raise EditorialBeatError(
            "focus-region evidence requires verified candidate visual events: "
            f"{unverified_focus_ids}"
        )
    for event_index, event in enumerate(video_map.events):
        if event.id in event_ids:
            raise EditorialBeatError(f"video map has duplicate event ID {event.id!r}")
        _require_id(event.id, label="video event ID")
        event_ids.add(event.id)
        if (
            not all(math.isfinite(value) for value in (event.start, event.end))
            or event.start < 0
            or event.end <= event.start
        ):
            raise EditorialBeatError(f"video event {event.id!r} has invalid source bounds")
        event_in, event_out = round(event.start * 1000), round(event.end * 1000)
        if not any(
            _overlaps_ms(event_in, event_out, item.source_in_ms, item.source_out_ms)
            for item in moments
        ):
            continue
        kind = _visual_kind(event)
        haystack = " ".join([event.decor, event.action, *event.objects]).casefold()
        face_state: FaceState = "primary" if kind in {"talking_head", "reaction"} else "none"
        # A generic VideoMap records that a screen exists, not whether text is
        # legible at a vertical crop.  Only a separate trusted observation may
        # mark it readable and unlock screen_focus.
        screen: ScreenReadability = "unknown" if kind == "screen_proof" else "none"
        if event.id in readable_visual_event_ids:
            if kind != "screen_proof":
                raise EditorialBeatError(
                    f"readability evidence {event.id!r} is not a screen-proof observation"
                )
            screen = "readable"
        elif "unreadable" in haystack or "blurry" in haystack:
            screen = "unreadable"
        motion: MotionKind = "action" if kind in {"demo", "reaction"} else "still"
        if kind == "scene_change":
            motion = "camera_change"
        safe_zone: SafeZone = (
            "upper" if kind == "screen_proof" else "lower" if face_state == "primary" else "unknown"
        )
        focus_region = visual_focus_regions.get(event.id)
        if focus_region is not None:
            if kind != "screen_proof":
                raise EditorialBeatError(
                    f"focus-region evidence {event.id!r} is not a screen-proof observation"
                )
            _validate_focus_region(focus_region, label=f"focus region {event.id!r}")
        beats.append(
            VisualBeat(
                visual_id=f"visual_{event_index:03d}",
                source_event_id=event.id[:120],
                source_in_ms=event_in,
                source_out_ms=event_out,
                kind=kind,
                face_state=face_state,
                screen_readability=screen,
                motion=motion,
                safe_zone=safe_zone,
                confidence=max(0, min(100, int(event.visual_importance))),
                focus_region=focus_region,
                provenance=(
                    "verified_candidate"
                    if event.id in verified_visual_event_ids
                    else "video_map"
                ),
            )
        )
    return tuple(beats)


def _audio_beats(
    transcript: Transcript,
    scope: EditScope,
    audio_map: AudioMap | None,
    protected_pause_ranges: Sequence[InclusiveWordRange],
) -> tuple[AudioBeat, ...]:
    if audio_map is None:
        return ()
    for item in protected_pause_ranges:
        if not _range_in_scope(item, scope):
            raise EditorialBeatError("protected pause range is outside the edit scope")
    timed_words = tuple(
        TimedWord(word_id_for_index(index), word.start, word.end)
        for index, word in enumerate(transcript.words)
    )
    protected = tuple(
        ProtectedWordSpan(word_id_for_index(item.from_word_id), word_id_for_index(item.to_word_id))
        for item in protected_pause_ranges
    )
    try:
        silences = classify_silences(audio_map, timed_words, protected_spans=protected)
    except ValueError as exc:
        raise EditorialBeatError(f"audio evidence is invalid: {exc}") from exc
    out: list[AudioBeat] = []
    scope_windows = [_range_ms(transcript, item) for item in scope.allowed_word_ranges]
    for index, silence in enumerate(silences):
        start, end = round(silence.interval.start * 1000), round(silence.interval.end * 1000)
        if end <= start or not any(_overlaps_ms(start, end, a, b) for a, b in scope_windows):
            continue
        kind: AudioBeatKind
        if silence.kind == "dead_air":
            kind = "dead_air"
        elif silence.kind == "protected_pause":
            kind = "dramatic_pause"
        elif silence.kind == "too_short":
            kind = "micro_pause"
        else:
            kind = "kept_pause"
        left = _word_index(silence.left_word_id)
        right = _word_index(silence.right_word_id)
        out.append(AudioBeat(f"audio_{index:03d}", start, end, kind, left, right))
    return tuple(out)


def _word_index(word_id: str | None) -> int | None:
    if word_id is None:
        return None
    try:
        return int(word_id.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        raise EditorialBeatError(f"audio evidence returned invalid word ID {word_id!r}") from None


def _purpose(role: SemanticRole) -> BeatPurpose:
    return {
        "setup": "orient",
        "constraint": "escalate",
        "contrast": "escalate",
        "proof": "prove",
        "reveal": "release",
        "reaction": "hook",
        "payoff": "payoff",
        "cta": "cta",
    }.get(role, "orient" if role == "unknown" else "hook")


def _available_framings(
    visuals: Sequence[VisualBeat],
) -> tuple[Literal["source_safe", "fit_blur", "locked_face", "screen_focus"], ...]:
    options: list[Literal["source_safe", "fit_blur", "locked_face", "screen_focus"]] = [
        "source_safe"
    ]
    if any(
        item.face_state == "primary" and item.provenance == "verified_candidate"
        for item in visuals
    ):
        options.append("locked_face")
    if any(item.kind == "screen_proof" for item in visuals):
        # This is the cautious full-frame treatment, not a claim that screen
        # text remains legible in a vertical output.
        options.append("fit_blur")
    if any(
        item.kind == "screen_proof"
        and item.screen_readability == "readable"
        and item.focus_region is not None
        and item.provenance == "verified_candidate"
        for item in visuals
    ):
        options.append("screen_focus")
    return tuple(options)


def _editorial_beats(
    moments: Sequence[SourceMoment], visuals: Sequence[VisualBeat], audio: Sequence[AudioBeat]
) -> tuple[EditorialBeat, ...]:
    out: list[EditorialBeat] = []
    for index, moment in enumerate(moments):
        linked_visuals = tuple(
            item
            for item in visuals
            if _overlaps_ms(
                item.source_in_ms, item.source_out_ms, moment.source_in_ms, moment.source_out_ms
            )
        )
        linked_audio = tuple(
            item
            for item in audio
            if _overlaps_ms(
                item.source_in_ms, item.source_out_ms, moment.source_in_ms, moment.source_out_ms
            )
        )
        out.append(
            EditorialBeat(
                beat_id=f"beat_{index:02d}",
                source_moment_id=moment.moment_id,
                visual_ids=tuple(item.visual_id for item in linked_visuals),
                audio_ids=tuple(item.audio_id for item in linked_audio),
                purpose=_purpose(moment.semantic_role),
                available_framings=_available_framings(linked_visuals),
            )
        )
    return tuple(out)


def _edge_relation(left: SourceMoment, right: SourceMoment) -> BeatRelation:
    if right.semantic_role in {"proof", "payoff"} and left.semantic_role in {
        "setup",
        "question",
        "claim",
    }:
        return "answers" if right.semantic_role == "payoff" else "proves"
    if right.semantic_role == "contrast":
        return "contrasts"
    return "continues"


def _continuity(
    left: EditorialBeat,
    right: EditorialBeat,
    *,
    kind: str,
    visuals: Mapping[str, VisualBeat],
    audio: Mapping[str, AudioBeat],
) -> ContinuityState:
    if kind == "audio":
        shared = set(left.audio_ids) & set(right.audio_ids)
        return (
            "pause" if any(audio[item].kind == "dramatic_pause" for item in shared) else "unknown"
        )
    if kind == "visual":
        shared = set(left.visual_ids) & set(right.visual_ids)
        if shared:
            return "continuous"
        if left.visual_ids and right.visual_ids:
            return "scene_change"
        return "unknown"
    return "continuous"


def _semantic_continuity(left: SourceMoment, right: SourceMoment) -> ContinuityState:
    """Only adjacent/overlapping transcript ranges earn a continuous label."""
    return (
        "continuous"
        if right.word_range.from_word_id <= left.word_range.to_word_id + 1
        and left.word_range.from_word_id <= right.word_range.to_word_id + 1
        else "unknown"
    )


def _edges(
    moments: Sequence[SourceMoment],
    beats: Sequence[EditorialBeat],
    visuals: Sequence[VisualBeat],
    audio: Sequence[AudioBeat],
) -> tuple[BeatEdge, ...]:
    visual_by_id, audio_by_id = (
        {item.visual_id: item for item in visuals},
        {item.audio_id: item for item in audio},
    )
    return tuple(
        BeatEdge(
            edge_id=f"edge_{index:02d}",
            from_beat_id=left.beat_id,
            to_beat_id=right.beat_id,
            relation=_edge_relation(moments[index], moments[index + 1]),
            semantic_continuity=_semantic_continuity(moments[index], moments[index + 1]),
            visual_continuity=_continuity(
                left, right, kind="visual", visuals=visual_by_id, audio=audio_by_id
            ),
            audio_continuity=_continuity(
                left, right, kind="audio", visuals=visual_by_id, audio=audio_by_id
            ),
        )
        for index, (left, right) in enumerate(pairwise(beats))
    )


def build_editorial_beat_graph(
    *,
    transcript: Transcript,
    scope: EditScope,
    candidate: MontageCandidate | None = None,
    video_map: VideoMap | None = None,
    audio_map: AudioMap | None = None,
    protected_pause_ranges: Sequence[InclusiveWordRange] = (),
    proof_requirements: Mapping[str, ProofRequirement] | None = None,
    readable_visual_event_ids: Collection[str] = (),
    verified_visual_event_ids: Collection[str] = (),
    visual_focus_regions: Mapping[str, VisualFocusRegion] | None = None,
) -> EditorialBeatGraph:
    """Build the local evidence graph without contacting a model or touching media."""
    if not transcript.words:
        raise EditorialBeatError("cannot build editorial beats without transcript words")
    _validate_scope(scope, word_count=len(transcript.words))
    requirements = dict(proof_requirements or {})
    moments = _candidate_moments(transcript, scope, candidate, requirements)
    visuals = _visual_beats(
        video_map,
        moments,
        readable_visual_event_ids,
        verified_visual_event_ids,
        dict(visual_focus_regions or {}),
    )
    audio = _audio_beats(transcript, scope, audio_map, protected_pause_ranges)
    beats = _editorial_beats(moments, visuals, audio)
    graph = EditorialBeatGraph(
        schema_version="1.0",
        transcript_word_count=len(transcript.words),
        scope=scope,
        source_moments=moments,
        visual_beats=visuals,
        audio_beats=audio,
        editorial_beats=beats,
        edges=_edges(moments, beats, visuals, audio),
    )
    validate_editorial_beat_graph(graph)
    return graph


def validate_editorial_beat_graph(graph: EditorialBeatGraph) -> None:
    """Validate external/persisted graphs before they reach a prompt or compiler."""
    if graph.schema_version != "1.0" or graph.transcript_word_count <= 0:
        raise EditorialBeatError("unsupported or empty editorial beat graph")
    _validate_scope(graph.scope, word_count=graph.transcript_word_count)
    moments = {item.moment_id: item for item in graph.source_moments}
    if len(moments) != len(graph.source_moments) or not moments:
        raise EditorialBeatError("source moments must have unique IDs and not be empty")
    for item in graph.source_moments:
        _require_id(item.moment_id, label="moment_id")
        if (
            item.semantic_role not in _SEMANTIC_ROLES
            or item.proof_requirement not in _PROOF_REQUIREMENTS
            or item.provenance not in _MOMENT_PROVENANCE
        ):
            raise EditorialBeatError(f"moment {item.moment_id}: unsupported closed value")
        if not _range_in_scope(item.word_range, graph.scope):
            raise EditorialBeatError(f"moment {item.moment_id} is outside edit scope")
        _finite_ms(item.source_in_ms, label="moment.source_in_ms")
        _finite_ms(item.source_out_ms, label="moment.source_out_ms")
        if item.source_out_ms <= item.source_in_ms:
            raise EditorialBeatError(f"moment {item.moment_id} has non-positive duration")

    visuals = {item.visual_id: item for item in graph.visual_beats}
    if len(visuals) != len(graph.visual_beats):
        raise EditorialBeatError("visual beats must have unique IDs")
    for item in graph.visual_beats:
        _require_id(item.visual_id, label="visual_id")
        _require_id(item.source_event_id, label="visual.source_event_id")
        _finite_ms(item.source_in_ms, label="visual.source_in_ms")
        _finite_ms(item.source_out_ms, label="visual.source_out_ms")
        if (
            item.source_out_ms <= item.source_in_ms
            or item.kind not in _VISUAL_KINDS
            or item.face_state not in _FACE_STATES
            or item.screen_readability not in _SCREEN_READABILITIES
            or item.motion not in _MOTION_KINDS
            or item.safe_zone not in _SAFE_ZONES
            or item.provenance not in _VISUAL_PROVENANCE
        ):
            raise EditorialBeatError(f"visual beat {item.visual_id} is invalid")
        if not 0 <= item.confidence <= 100:
            raise EditorialBeatError(
                f"visual beat {item.visual_id}: confidence must be in [0, 100]"
            )
        if item.focus_region is not None:
            if item.kind != "screen_proof":
                raise EditorialBeatError(
                    f"visual beat {item.visual_id}: focus region requires a screen proof"
                )
            _validate_focus_region(
                item.focus_region,
                label=f"visual beat {item.visual_id}.focus_region",
            )
        if item.screen_readability == "readable" and item.provenance != "verified_candidate":
            raise EditorialBeatError(
                f"visual beat {item.visual_id}: readable screen requires verified provenance"
            )
        if item.focus_region is not None and item.provenance != "verified_candidate":
            raise EditorialBeatError(
                f"visual beat {item.visual_id}: focus region requires verified provenance"
            )

    audio = {item.audio_id: item for item in graph.audio_beats}
    if len(audio) != len(graph.audio_beats):
        raise EditorialBeatError("audio beats must have unique IDs")
    for item in graph.audio_beats:
        _require_id(item.audio_id, label="audio_id")
        if item.kind not in _AUDIO_KINDS or item.provenance not in _AUDIO_PROVENANCE:
            raise EditorialBeatError(f"audio beat {item.audio_id}: unsupported kind")
        _finite_ms(item.source_in_ms, label="audio.source_in_ms")
        _finite_ms(item.source_out_ms, label="audio.source_out_ms")
        if item.source_out_ms <= item.source_in_ms:
            raise EditorialBeatError(f"audio beat {item.audio_id} has non-positive duration")
        for word_id in (item.left_word_id, item.right_word_id):
            if word_id is not None and not 0 <= word_id < graph.transcript_word_count:
                raise EditorialBeatError(f"audio beat {item.audio_id} references unknown word ID")
        if (
            item.left_word_id is not None
            and item.right_word_id is not None
            and item.left_word_id >= item.right_word_id
        ):
            raise EditorialBeatError(
                f"audio beat {item.audio_id} has reversed or unbounded word edges"
            )

    beats = {item.beat_id: item for item in graph.editorial_beats}
    if len(beats) != len(graph.editorial_beats) or len(beats) != len(moments):
        raise EditorialBeatError(
            "editorial beats must be unique and cover every source moment once"
        )
    source_refs: set[str] = set()
    for item in graph.editorial_beats:
        _require_id(item.beat_id, label="beat_id")
        if item.source_moment_id not in moments or item.source_moment_id in source_refs:
            raise EditorialBeatError(
                f"beat {item.beat_id} has an unknown or duplicate source moment"
            )
        source_refs.add(item.source_moment_id)
        if (
            item.purpose not in _PURPOSES
            or not item.available_framings
            or item.available_framings[0] != "source_safe"
            or len(set(item.available_framings)) != len(item.available_framings)
            or any(framing not in _FRAMINGS for framing in item.available_framings)
        ):
            raise EditorialBeatError(f"beat {item.beat_id} has invalid editorial controls")
        if any(ref not in visuals for ref in item.visual_ids) or any(
            ref not in audio for ref in item.audio_ids
        ):
            raise EditorialBeatError(
                f"beat {item.beat_id} references unknown visual/audio evidence"
            )
        source_moment = moments[item.source_moment_id]
        if any(
            not _overlaps_ms(
                visuals[ref].source_in_ms,
                visuals[ref].source_out_ms,
                source_moment.source_in_ms,
                source_moment.source_out_ms,
            )
            for ref in item.visual_ids
        ) or any(
            not _overlaps_ms(
                audio[ref].source_in_ms,
                audio[ref].source_out_ms,
                source_moment.source_in_ms,
                source_moment.source_out_ms,
            )
            for ref in item.audio_ids
        ):
            raise EditorialBeatError(
                f"beat {item.beat_id} references evidence outside its source moment"
            )
        if "screen_focus" in item.available_framings and not any(
            visuals[ref].kind == "screen_proof"
            and visuals[ref].screen_readability == "readable"
            and visuals[ref].focus_region is not None
            and visuals[ref].provenance == "verified_candidate"
            for ref in item.visual_ids
        ):
            raise EditorialBeatError(
                f"beat {item.beat_id} enables screen_focus without a readable focus region"
            )
        if "locked_face" in item.available_framings and not any(
            visuals[ref].face_state == "primary"
            and visuals[ref].provenance == "verified_candidate"
            for ref in item.visual_ids
        ):
            raise EditorialBeatError(
                f"beat {item.beat_id} enables locked_face without a verified primary face"
            )

    for moment in graph.source_moments:
        if moment.proof_requirement in {"visible", "both"}:
            linked = next(
                item for item in graph.editorial_beats if item.source_moment_id == moment.moment_id
            )
            has_visible_proof = any(
                visuals[visual_id].kind in _VISIBLE_PROOF_KINDS
                and visuals[visual_id].provenance == "verified_candidate"
                and _overlaps_ms(
                    visuals[visual_id].source_in_ms,
                    visuals[visual_id].source_out_ms,
                    moment.source_in_ms,
                    moment.source_out_ms,
                )
                for visual_id in linked.visual_ids
            )
            if not has_visible_proof:
                raise EditorialBeatError(
                    f"moment {moment.moment_id} requires visible proof but no "
                    "qualifying visual evidence exists"
                )

    edge_ids: set[str] = set()
    for edge in graph.edges:
        _require_id(edge.edge_id, label="edge_id")
        if edge.edge_id in edge_ids:
            raise EditorialBeatError("edges must have unique IDs")
        edge_ids.add(edge.edge_id)
        if (
            edge.from_beat_id not in beats
            or edge.to_beat_id not in beats
            or edge.from_beat_id == edge.to_beat_id
        ):
            raise EditorialBeatError(
                f"edge {edge.edge_id} references an unknown/self editorial beat"
            )
        if edge.relation not in _RELATIONS or any(
            value not in _CONTINUITY
            for value in (edge.semantic_continuity, edge.visual_continuity, edge.audio_continuity)
        ):
            raise EditorialBeatError(f"edge {edge.edge_id} has unsupported closed values")


def _word_range_payload(item: InclusiveWordRange) -> dict[str, str]:
    return {
        "from_word_id": word_id_for_index(item.from_word_id),
        "to_word_id": word_id_for_index(item.to_word_id),
    }


def _scope_payload(scope: EditScope) -> dict[str, list[dict[str, str]]]:
    return {
        "allowed_word_ranges": [_word_range_payload(item) for item in scope.allowed_word_ranges],
        "protected_word_ranges": [
            _word_range_payload(item) for item in scope.protected_word_ranges
        ],
        "required_word_ranges": [_word_range_payload(item) for item in scope.required_word_ranges],
    }


def _moment_payload(item: SourceMoment) -> dict[str, object]:
    return {
        "moment_id": item.moment_id,
        "word_range": _word_range_payload(item.word_range),
        "semantic_role": item.semantic_role,
        "proof_requirement": item.proof_requirement,
        "provenance": item.provenance,
    }


def _visual_payload(item: VisualBeat) -> dict[str, object]:
    return {
        "visual_id": item.visual_id,
        "source_event_id": item.source_event_id,
        "source_in_ms": item.source_in_ms,
        "source_out_ms": item.source_out_ms,
        "kind": item.kind,
        "face_state": item.face_state,
        "screen_readability": item.screen_readability,
        "motion": item.motion,
        "safe_zone": item.safe_zone,
        "confidence": item.confidence,
        "provenance": item.provenance,
        "focus_region": (
            {
                "x": item.focus_region.x,
                "y": item.focus_region.y,
                "width": item.focus_region.width,
                "height": item.focus_region.height,
            }
            if item.focus_region is not None
            else None
        ),
    }


def _audio_payload(item: AudioBeat) -> dict[str, object]:
    return {
        "audio_id": item.audio_id,
        "source_in_ms": item.source_in_ms,
        "source_out_ms": item.source_out_ms,
        "kind": item.kind,
        "left_word_id": word_id_for_index(item.left_word_id)
        if item.left_word_id is not None
        else None,
        "right_word_id": word_id_for_index(item.right_word_id)
        if item.right_word_id is not None
        else None,
    }


def _editorial_payload(item: EditorialBeat) -> dict[str, object]:
    return {
        "beat_id": item.beat_id,
        "source_moment_id": item.source_moment_id,
        "visual_ids": list(item.visual_ids),
        "audio_ids": list(item.audio_ids),
        "purpose": item.purpose,
        "available_framings": list(item.available_framings),
    }
