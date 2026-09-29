"""Motivated LLM contract between the editorial beat graph and EDL V2.

This module is deliberately provider-free.  It prepares a bounded prompt,
defensively parses schema 2.1 editorial decisions, validates every decision
against an :class:`EditorialBeatGraph`, then lowers the plan to the existing
schema 2.0 compiler.  Transcript word IDs remain the only cut authority; graph
milliseconds are evidence for understanding the source, never edit boundaries.
"""

from __future__ import annotations

import json
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any, Literal

from ..models import Transcript
from .edit_intent import parse_edit_intent
from .editorial_beats import (
    BeatEdge,
    EditorialBeat,
    EditorialBeatError,
    EditorialBeatGraph,
    SourceMoment,
    VisualBeat,
    validate_editorial_beat_graph,
)
from .edl import (
    CaptionTheme,
    CompiledEDL,
    EditIntentPlan,
    EditShotIntent,
    EDLValidationError,
    EffectIntent,
    EffectKind,
    FramingIntent,
    FramingRegion,
    MusicIntent,
    SFXCueIntent,
    ShotRole,
    TransitionKind,
    compile_edit_intent,
    word_id_for_index,
)


class EditorialDirectorError(EDLValidationError):
    """A schema 2.1 director decision is unsafe or editorially ungrounded."""


EntryMotivation = Literal[
    "scroll_stop",
    "context",
    "escalation",
    "proof_arrival",
    "payoff_arrival",
    "cta_arrival",
    "continuation",
    "replay",
    "context_reset",
]
ExitMotivation = Literal[
    "question_open",
    "context_complete",
    "proof_delivered",
    "payoff_delivered",
    "energy_shift",
    "cta_complete",
    "continue",
]
JointMotivation = Literal[
    "opening",
    "semantic_continuity",
    "proof_reveal",
    "payoff_reveal",
    "contrast",
    "time_compression",
    "reaction_payoff",
    "replay",
    "context_reset",
]
ContinuityStrategy = Literal[
    "establish",
    "preserve",
    "match_content",
    "mask_with_motion",
    "acknowledge_time_jump",
    "hard_reset",
]
EffectReason = Literal[
    "emphasis",
    "proof_focus",
    "reaction_accent",
    "time_compression",
    "transition_mask",
    "pattern_interrupt",
]
CampaignHypothesis = Literal[
    "proof_first",
    "objection_first",
    "curiosity_first",
    "authority_first",
    "transformation_first",
]

_ENTRY_MOTIVATIONS = frozenset(
    {
        "scroll_stop",
        "context",
        "escalation",
        "proof_arrival",
        "payoff_arrival",
        "cta_arrival",
        "continuation",
        "replay",
        "context_reset",
    }
)
_EXIT_MOTIVATIONS = frozenset(
    {
        "question_open",
        "context_complete",
        "proof_delivered",
        "payoff_delivered",
        "energy_shift",
        "cta_complete",
        "continue",
    }
)
_JOINT_MOTIVATIONS = frozenset(
    {
        "opening",
        "semantic_continuity",
        "proof_reveal",
        "payoff_reveal",
        "contrast",
        "time_compression",
        "reaction_payoff",
        "replay",
        "context_reset",
    }
)
_CONTINUITY_STRATEGIES = frozenset(
    {
        "establish",
        "preserve",
        "match_content",
        "mask_with_motion",
        "acknowledge_time_jump",
        "hard_reset",
    }
)
_EFFECT_REASONS = frozenset(
    {
        "emphasis",
        "proof_focus",
        "reaction_accent",
        "time_compression",
        "transition_mask",
        "pattern_interrupt",
    }
)
_CAMPAIGN_HYPOTHESES = frozenset(
    {
        "proof_first",
        "objection_first",
        "curiosity_first",
        "authority_first",
        "transformation_first",
    }
)

_ROOT_KEYS = frozenset(
    {"schema_version", "campaign_hypothesis", "editorial_thesis", "shots", "music", "sfx"}
)
_SHOT_KEYS = frozenset(
    {
        "shot_id",
        "beat_id",
        "role",
        "from_word_id",
        "to_word_id",
        "start_anchor",
        "end_anchor",
        "entry_motivation",
        "exit_motivation",
        "joint_motivation",
        "continuity_strategy",
        "framing",
        "effects",
        "transition_out",
        "caption_theme",
        "speed",
        "pre_roll_ms",
        "post_roll_ms",
    }
)
_FRAMING_KEYS = frozenset({"mode", "center_x", "base_scale"})
_EFFECT_KEYS = frozenset({"kind", "at_word_id", "duration_ms", "intensity", "reason"})

_ROLE_BY_PURPOSE: dict[str, frozenset[str]] = {
    # Beat purpose describes the source affordance; shot role describes its job
    # after reordering on the output timeline.  The mapping is intentionally
    # many-to-many so a strong claim/proof can open, then become context later.
    "hook": frozenset({"hook", "setup", "bridge", "reaction"}),
    "orient": frozenset({"hook", "setup", "bridge"}),
    "escalate": frozenset({"hook", "setup", "bridge"}),
    "prove": frozenset({"hook", "proof"}),
    "release": frozenset({"hook", "bridge", "reaction", "payoff"}),
    "payoff": frozenset({"hook", "payoff", "reaction"}),
    "cta": frozenset({"cta"}),
}
_ENTRY_BY_PURPOSE: dict[str, frozenset[str]] = {
    "hook": frozenset({"scroll_stop", "replay"}),
    "orient": frozenset({"context", "continuation"}),
    "escalate": frozenset({"escalation", "continuation"}),
    "prove": frozenset({"proof_arrival", "continuation"}),
    "release": frozenset({"payoff_arrival", "continuation"}),
    "payoff": frozenset({"payoff_arrival", "continuation", "replay"}),
    "cta": frozenset({"cta_arrival", "continuation"}),
}
_EXIT_BY_PURPOSE: dict[str, frozenset[str]] = {
    "hook": frozenset({"question_open", "energy_shift", "continue"}),
    "orient": frozenset({"context_complete", "continue"}),
    "escalate": frozenset({"question_open", "energy_shift", "continue"}),
    "prove": frozenset({"proof_delivered", "continue"}),
    "release": frozenset({"payoff_delivered", "energy_shift", "continue"}),
    "payoff": frozenset({"payoff_delivered", "energy_shift", "continue"}),
    "cta": frozenset({"cta_complete"}),
}
_JOINT_BY_RELATION: dict[str, frozenset[str]] = {
    "answers": frozenset({"payoff_reveal", "proof_reveal"}),
    "proves": frozenset({"proof_reveal"}),
    "contrasts": frozenset({"contrast"}),
    "causes": frozenset({"semantic_continuity"}),
    "escalates": frozenset({"semantic_continuity", "reaction_payoff"}),
    "reframes": frozenset({"contrast", "semantic_continuity"}),
    "repeats": frozenset({"replay"}),
    "continues": frozenset({"semantic_continuity", "reaction_payoff"}),
}
_JOINT_BY_TRANSITION: dict[str, frozenset[str]] = {
    "hard_cut": _JOINT_MOTIVATIONS - {"opening"},
    "time_jump": frozenset({"time_compression", "replay"}),
    "reveal": frozenset({"proof_reveal", "payoff_reveal", "reaction_payoff"}),
    "contrast": frozenset({"contrast"}),
    "hard_impact": frozenset({"reaction_payoff"}),
}
_REASONS_BY_EFFECT: dict[str, frozenset[str]] = {
    "punch_in": frozenset({"emphasis", "proof_focus", "reaction_accent", "pattern_interrupt"}),
    "zoom_out": frozenset({"emphasis", "pattern_interrupt"}),
    "freeze": frozenset({"emphasis", "proof_focus", "reaction_accent"}),
    "speed_ramp": frozenset({"time_compression"}),
    "flash": frozenset({"transition_mask", "reaction_accent", "pattern_interrupt"}),
    "shake": frozenset({"reaction_accent", "pattern_interrupt"}),
    "blur": frozenset({"proof_focus", "transition_mask"}),
    "color_pop": frozenset({"emphasis", "proof_focus", "pattern_interrupt"}),
}


@dataclass(frozen=True)
class MotivatedEffectIntent:
    kind: EffectKind
    at_word_id: int | None
    duration_ms: int
    intensity: float
    reason: EffectReason

    def to_edl_intent(self) -> EffectIntent:
        return EffectIntent(self.kind, self.at_word_id, self.duration_ms, self.intensity)


@dataclass(frozen=True)
class MotivatedShotIntent:
    shot_id: str
    beat_id: str
    role: ShotRole
    from_word_id: int
    to_word_id: int
    start_anchor: str
    end_anchor: str
    entry_motivation: EntryMotivation
    exit_motivation: ExitMotivation
    joint_motivation: JointMotivation
    continuity_strategy: ContinuityStrategy
    framing: FramingIntent
    effects: tuple[MotivatedEffectIntent, ...]
    transition_out: TransitionKind
    caption_theme: CaptionTheme
    speed: float
    pre_roll_ms: int
    post_roll_ms: int

    def to_edl_intent(self, *, screen_region: FramingRegion | None = None) -> EditShotIntent:
        return EditShotIntent(
            shot_id=self.shot_id,
            role=self.role,
            from_word_id=self.from_word_id,
            to_word_id=self.to_word_id,
            start_anchor=self.start_anchor,
            end_anchor=self.end_anchor,
            framing=FramingIntent(
                mode=self.framing.mode,
                center_x=self.framing.center_x,
                base_scale=self.framing.base_scale,
                screen_region=screen_region,
            ),
            effects=tuple(item.to_edl_intent() for item in self.effects),
            transition_out=self.transition_out,
            caption_theme=self.caption_theme,
            speed=self.speed,
            pre_roll_ms=self.pre_roll_ms,
            post_roll_ms=self.post_roll_ms,
        )


@dataclass(frozen=True)
class EditorialDirectorPlan:
    schema_version: Literal["2.1"]
    campaign_hypothesis: CampaignHypothesis
    editorial_thesis: str
    shots: tuple[MotivatedShotIntent, ...]
    music: tuple[MusicIntent, ...] = ()
    sfx: tuple[SFXCueIntent, ...] = ()


@dataclass(frozen=True)
class DirectorVariantDiversityReport:
    """Deterministic proof that three variants are editorially distinct."""

    status: Literal["pass", "reject"]
    findings: tuple[str, ...]
    pairwise_word_overlap: tuple[float, ...]


EDITORIAL_DIRECTOR_SYSTEM_PROMPT = """You are ClipFactory's senior short-form editing director.

You receive a validated editorial evidence graph and only the transcript words
inside its authorised EditScope. Build one motivated edit. Every cut is an
inclusive word-ID subrange of the shot's referenced source moment. Word IDs and
their matching verbatim anchors are the only boundary authority. Milliseconds
inside visual/audio evidence describe observations only: never return seconds,
milliseconds, FFmpeg expressions, paths, URLs, or invented IDs as edit bounds.

Return one JSON object and no markdown. Its schema_version is exactly "2.1".
Root keys are: schema_version, campaign_hypothesis, editorial_thesis, shots,
music, sfx. campaign_hypothesis is one of proof_first | objection_first |
curiosity_first | authority_first | transformation_first.

Every shot must declare exactly these decision fields in addition to the closed
EDL 2.0 controls:
- beat_id: an editorial_beats[].beat_id from the supplied graph
- from_word_id/to_word_id plus matching verbatim start_anchor/end_anchor
- entry_motivation: scroll_stop | context | escalation | proof_arrival |
  payoff_arrival | cta_arrival | continuation | replay | context_reset
- exit_motivation: question_open | context_complete | proof_delivered |
  payoff_delivered | energy_shift | cta_complete | continue
- joint_motivation: opening | semantic_continuity | proof_reveal |
  payoff_reveal | contrast | time_compression | reaction_payoff | replay |
  context_reset
- continuity_strategy: establish | preserve | match_content |
  mask_with_motion | acknowledge_time_jump | hard_reset

Use only these EDL controls:
- role: hook | setup | bridge | proof | payoff | reaction | cta
- framing.mode: source_safe | fit_blur | locked_face | screen_focus; it must
  appear in the referenced beat's available_framings
- effect.kind: punch_in | zoom_out | freeze | flash | shake |
  blur | color_pop. Every effect also requires reason: emphasis | proof_focus |
  reaction_accent | time_compression | transition_mask | pattern_interrupt
- transition_out: hard_cut | time_jump | reveal | contrast | hard_impact
- caption_theme: hook_bold | standard_karaoke | proof_clean | reaction_pop | none
- speed, pre_roll_ms and post_roll_ms retain the bounded EDL 2.0 meanings

The first shot uses joint_motivation=opening and continuity_strategy=establish.
Every later shot needs one supplied directed edge from the previous beat to its
beat. Its joint motivation, continuity strategy and the previous shot's
transition must agree with that edge. Prefer hard cuts. Music/SFX are optional
and may reference only supplied catalogue IDs; never return a file path.

Two bounded exceptions preserve real non-linear editing without inventing an
edge: a repeated beat must declare replay, while a distinct unlinked beat must
declare either context_reset/hard_reset after a hard cut or
time_compression/acknowledge_time_jump after a time_jump.
"""


def _reject_unknown_keys(value: dict[str, Any], *, allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise EditorialDirectorError(f"{label} contains unsupported fields: {unknown}")


def _object(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EditorialDirectorError(f"{label} must be an object")
    return value


def _array(value: Any, *, label: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EditorialDirectorError(f"{label} must be an array")
    return value


def _closed_text(value: Any, *, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise EditorialDirectorError(f"{label} must be one of {sorted(allowed)}, got {value!r}")
    return value


def _validate_graph_for_transcript(graph: EditorialBeatGraph, transcript: Transcript) -> None:
    try:
        validate_editorial_beat_graph(graph)
    except EditorialBeatError as exc:
        raise EditorialDirectorError(f"invalid editorial graph: {exc}") from exc
    if graph.transcript_word_count != len(transcript.words):
        raise EditorialDirectorError(
            "editorial graph transcript_word_count does not match the transcript"
        )
    for moment in graph.source_moments:
        expected_in = round(transcript.words[moment.word_range.from_word_id].start * 1000)
        expected_out = round(transcript.words[moment.word_range.to_word_id].end * 1000)
        if (moment.source_in_ms, moment.source_out_ms) != (expected_in, expected_out):
            raise EditorialDirectorError(
                f"source moment {moment.moment_id!r} time bounds do not match its word range"
            )


def scoped_transcript_word_payload(
    graph: EditorialBeatGraph,
    transcript: Transcript,
) -> list[dict[str, str]]:
    """Return only graph-scoped words, with IDs and text but no cut seconds."""

    _validate_graph_for_transcript(graph, transcript)
    allowed_ids = {
        word_id
        for word_range in graph.scope.allowed_word_ranges
        for word_id in range(word_range.from_word_id, word_range.to_word_id + 1)
    }
    return [
        {"word_id": word_id_for_index(index), "text": word.word}
        for index, word in enumerate(transcript.words)
        if index in allowed_ids
    ]


def editorial_director_user_prompt(
    *,
    graph: EditorialBeatGraph,
    transcript: Transcript,
    target_duration_seconds: int,
    music_asset_ids: Collection[str] = (),
    sfx_asset_ids: Collection[str] = (),
) -> str:
    """Build a prompt from graph JSON plus the least-privilege word transcript."""

    if target_duration_seconds <= 0:
        raise EditorialDirectorError("target_duration_seconds must be positive")
    words = scoped_transcript_word_payload(graph, transcript)
    catalogue = {
        "music_asset_ids": sorted(set(music_asset_ids)),
        "sfx_asset_ids": sorted(set(sfx_asset_ids)),
    }
    return "\n".join(
        (
            "Build one schema 2.1 motivated edit plan.",
            f"TARGET_DURATION_SECONDS: {target_duration_seconds} (output constraint only)",
            "EDITORIAL_GRAPH_JSON (milliseconds are observation context only):",
            graph.to_prompt_json(),
            "SCOPED_WORD_ID_TRANSCRIPT_JSON (the only cut authority):",
            json.dumps(words, ensure_ascii=False, separators=(",", ":")),
            "LICENSED_AUDIO_CATALOGUE_IDS_JSON:",
            json.dumps(catalogue, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            "Return only the JSON object. Do not emit any free cut timecode field.",
        )
    )


def parse_editorial_director_plan(payload: Any) -> EditorialDirectorPlan:
    """Parse hostile schema 2.1 JSON and reuse the closed EDL 2.0 parser."""

    root = _object(payload, label="editorial director plan")
    _reject_unknown_keys(root, allowed=_ROOT_KEYS, label="editorial director plan")
    if root.get("schema_version") != "2.1":
        raise EditorialDirectorError(
            f"unsupported editorial director schema {root.get('schema_version')!r}"
        )
    campaign_hypothesis = _closed_text(
        root.get("campaign_hypothesis"),
        allowed=_CAMPAIGN_HYPOTHESES,
        label="campaign_hypothesis",
    )

    stripped_shots: list[dict[str, Any]] = []
    director_fields: list[tuple[str, str, str, str, str, list[str]]] = []
    for shot_index, raw_shot in enumerate(_array(root.get("shots"), label="shots")):
        label = f"shots[{shot_index}]"
        shot = _object(raw_shot, label=label)
        _reject_unknown_keys(shot, allowed=_SHOT_KEYS, label=label)
        framing = _object(shot.get("framing") or {}, label=f"{label}.framing")
        _reject_unknown_keys(framing, allowed=_FRAMING_KEYS, label=f"{label}.framing")

        beat_id = shot.get("beat_id")
        if not isinstance(beat_id, str) or not beat_id:
            raise EditorialDirectorError(f"{label}.beat_id must be a non-empty string")
        entry = _closed_text(
            shot.get("entry_motivation"),
            allowed=_ENTRY_MOTIVATIONS,
            label=f"{label}.entry_motivation",
        )
        exit_reason = _closed_text(
            shot.get("exit_motivation"),
            allowed=_EXIT_MOTIVATIONS,
            label=f"{label}.exit_motivation",
        )
        joint = _closed_text(
            shot.get("joint_motivation"),
            allowed=_JOINT_MOTIVATIONS,
            label=f"{label}.joint_motivation",
        )
        continuity = _closed_text(
            shot.get("continuity_strategy"),
            allowed=_CONTINUITY_STRATEGIES,
            label=f"{label}.continuity_strategy",
        )

        stripped_effects: list[dict[str, Any]] = []
        effect_reasons: list[str] = []
        for effect_index, raw_effect in enumerate(
            _array(shot.get("effects"), label=f"{label}.effects")
        ):
            effect_label = f"{label}.effects[{effect_index}]"
            effect = _object(raw_effect, label=effect_label)
            _reject_unknown_keys(effect, allowed=_EFFECT_KEYS, label=effect_label)
            effect_reasons.append(
                _closed_text(
                    effect.get("reason"),
                    allowed=_EFFECT_REASONS,
                    label=f"{effect_label}.reason",
                )
            )
            stripped_effects.append(
                {key: value for key, value in effect.items() if key != "reason"}
            )

        stripped_shots.append(
            {
                key: value
                for key, value in shot.items()
                if key
                not in {
                    "beat_id",
                    "entry_motivation",
                    "exit_motivation",
                    "joint_motivation",
                    "continuity_strategy",
                    "effects",
                }
            }
            | {"effects": stripped_effects}
        )
        director_fields.append((beat_id, entry, exit_reason, joint, continuity, effect_reasons))

    base_payload = {
        "schema_version": "2.0",
        "editorial_thesis": root.get("editorial_thesis"),
        "shots": stripped_shots,
        "music": root.get("music"),
        "sfx": root.get("sfx"),
    }
    try:
        base_plan = parse_edit_intent(base_payload)
    except EDLValidationError as exc:
        raise EditorialDirectorError(f"invalid EDL controls: {exc}") from exc

    motivated_shots: list[MotivatedShotIntent] = []
    for base_shot, fields in zip(base_plan.shots, director_fields, strict=True):
        beat_id, entry, exit_reason, joint, continuity, effect_reasons = fields
        effects = tuple(
            MotivatedEffectIntent(
                kind=effect.kind,
                at_word_id=effect.at_word_id,
                duration_ms=effect.duration_ms,
                intensity=effect.intensity,
                reason=reason,  # type: ignore[arg-type]
            )
            for effect, reason in zip(base_shot.effects, effect_reasons, strict=True)
        )
        motivated_shots.append(
            MotivatedShotIntent(
                shot_id=base_shot.shot_id,
                beat_id=beat_id,
                role=base_shot.role,
                from_word_id=base_shot.from_word_id,
                to_word_id=base_shot.to_word_id,
                start_anchor=base_shot.start_anchor,
                end_anchor=base_shot.end_anchor,
                entry_motivation=entry,  # type: ignore[arg-type]
                exit_motivation=exit_reason,  # type: ignore[arg-type]
                joint_motivation=joint,  # type: ignore[arg-type]
                continuity_strategy=continuity,  # type: ignore[arg-type]
                framing=base_shot.framing,
                effects=effects,
                transition_out=base_shot.transition_out,
                caption_theme=base_shot.caption_theme,
                speed=base_shot.speed,
                pre_roll_ms=base_shot.pre_roll_ms,
                post_roll_ms=base_shot.post_roll_ms,
            )
        )

    return EditorialDirectorPlan(
        schema_version="2.1",
        campaign_hypothesis=campaign_hypothesis,  # type: ignore[arg-type]
        editorial_thesis=base_plan.editorial_thesis,
        shots=tuple(motivated_shots),
        music=base_plan.music,
        sfx=base_plan.sfx,
    )


def _is_subrange(shot: MotivatedShotIntent, moment: SourceMoment) -> bool:
    return (
        moment.word_range.from_word_id <= shot.from_word_id
        and shot.to_word_id <= moment.word_range.to_word_id
    )


def _range_is_scoped(shot: MotivatedShotIntent, graph: EditorialBeatGraph) -> bool:
    return any(
        item.from_word_id <= shot.from_word_id and shot.to_word_id <= item.to_word_id
        for item in graph.scope.allowed_word_ranges
    )


def _trusted_screen_region_for_shot(
    shot: MotivatedShotIntent,
    beat: EditorialBeat,
    visuals: dict[str, VisualBeat],
    transcript: Transcript,
) -> FramingRegion:
    """Resolve one trusted ROI overlapping the selected words, not just its beat."""

    source_in_ms = round(transcript.words[shot.from_word_id].start * 1000)
    source_out_ms = round(transcript.words[shot.to_word_id].end * 1000)
    candidates = tuple(
        visuals[visual_id]
        for visual_id in beat.visual_ids
        if visuals[visual_id].kind == "screen_proof"
        and visuals[visual_id].screen_readability == "readable"
        and visuals[visual_id].focus_region is not None
        and visuals[visual_id].provenance == "verified_candidate"
        and visuals[visual_id].source_in_ms < source_out_ms
        and source_in_ms < visuals[visual_id].source_out_ms
    )
    if len(candidates) != 1:
        raise EditorialDirectorError(
            f"shot {shot.shot_id}: screen_focus needs exactly one trusted readable ROI "
            f"overlapping its selected words; found {len(candidates)}"
        )
    region = candidates[0].focus_region
    assert region is not None  # narrowed by the candidate predicate
    return FramingRegion(region.x, region.y, region.width, region.height)


def _validate_effect_reason(shot: MotivatedShotIntent, effect: MotivatedEffectIntent) -> None:
    if effect.kind == "speed_ramp":
        raise EditorialDirectorError(
            f"shot {shot.shot_id}: speed_ramp is not renderable; use bounded shot.speed"
        )
    if effect.at_word_id is None:
        raise EditorialDirectorError(
            f"shot {shot.shot_id}: every schema 2.1 effect requires at_word_id"
        )
    allowed = _REASONS_BY_EFFECT.get(effect.kind, frozenset())
    if effect.reason not in allowed:
        raise EditorialDirectorError(
            f"shot {shot.shot_id}: effect {effect.kind!r} is not motivated by {effect.reason!r}"
        )
    if effect.reason == "proof_focus" and shot.entry_motivation not in {
        "proof_arrival",
        "payoff_arrival",
        "scroll_stop",
    }:
        raise EditorialDirectorError(
            f"shot {shot.shot_id}: proof_focus effect requires proof/payoff motivation"
        )
    if effect.reason == "reaction_accent" and shot.role not in {"hook", "reaction", "payoff"}:
        raise EditorialDirectorError(
            f"shot {shot.shot_id}: reaction_accent effect is incompatible with role {shot.role!r}"
        )
    if effect.reason == "transition_mask" and shot.transition_out == "hard_cut":
        raise EditorialDirectorError(
            f"shot {shot.shot_id}: transition_mask cannot motivate a plain hard cut"
        )


def _edge_for_joint(
    previous: MotivatedShotIntent,
    current: MotivatedShotIntent,
    edges: tuple[BeatEdge, ...],
) -> BeatEdge | None:
    matches = tuple(
        edge
        for edge in edges
        if edge.from_beat_id == previous.beat_id and edge.to_beat_id == current.beat_id
    )
    if len(matches) > 1:
        raise EditorialDirectorError(
            f"shots {previous.shot_id}->{current.shot_id}: expected exactly one graph edge, "
            f"found {len(matches)}"
        )
    return matches[0] if matches else None


def _validate_unlinked_joint(
    previous: MotivatedShotIntent,
    current: MotivatedShotIntent,
) -> None:
    if previous.beat_id == current.beat_id:
        if current.joint_motivation != "replay" or current.entry_motivation != "replay":
            raise EditorialDirectorError(
                f"shots {previous.shot_id}->{current.shot_id}: a repeated beat must declare replay"
            )
        if previous.transition_out == "hard_cut" and current.continuity_strategy in {
            "preserve",
            "match_content",
        }:
            return
        if (
            previous.transition_out == "time_jump"
            and current.continuity_strategy == "acknowledge_time_jump"
        ):
            return
        raise EditorialDirectorError(
            f"shot {current.shot_id}: replay transition and continuity are incompatible"
        )

    if (
        current.joint_motivation == "context_reset"
        and current.entry_motivation == "context_reset"
        and current.continuity_strategy == "hard_reset"
        and previous.transition_out == "hard_cut"
    ):
        return
    if (
        current.joint_motivation == "time_compression"
        and current.continuity_strategy == "acknowledge_time_jump"
        and previous.transition_out == "time_jump"
    ):
        return
    raise EditorialDirectorError(
        f"shots {previous.shot_id}->{current.shot_id}: no directed graph edge; "
        "use an explicit bounded replay, context_reset or time_compression"
    )


def _validate_joint(
    previous: MotivatedShotIntent,
    current: MotivatedShotIntent,
    edge: BeatEdge,
) -> None:
    if current.joint_motivation not in _JOINT_BY_RELATION[edge.relation]:
        raise EditorialDirectorError(
            f"shots {previous.shot_id}->{current.shot_id}: joint motivation "
            f"{current.joint_motivation!r} is incompatible with edge relation {edge.relation!r}"
        )
    if current.joint_motivation not in _JOINT_BY_TRANSITION[previous.transition_out]:
        raise EditorialDirectorError(
            f"shots {previous.shot_id}->{current.shot_id}: transition "
            f"{previous.transition_out!r} is not motivated by {current.joint_motivation!r}"
        )
    if previous.transition_out == "time_jump":
        if current.continuity_strategy != "acknowledge_time_jump":
            raise EditorialDirectorError(
                f"shot {current.shot_id}: time_jump requires acknowledge_time_jump continuity"
            )
    elif current.continuity_strategy == "acknowledge_time_jump":
        raise EditorialDirectorError(
            f"shot {current.shot_id}: acknowledge_time_jump requires a time_jump transition"
        )
    if current.continuity_strategy == "preserve" and edge.semantic_continuity != "continuous":
        raise EditorialDirectorError(
            f"shot {current.shot_id}: preserve requires continuous semantic evidence"
        )


def compile_editorial_director_plan(
    plan: EditorialDirectorPlan,
    graph: EditorialBeatGraph,
    transcript: Transcript,
    *,
    source_duration_ms: int,
    fps: int = 30,
    width: int = 1080,
    height: int = 1920,
    target_duration_seconds: int | None = None,
    allowed_music_asset_ids: Collection[str] = (),
    allowed_sfx_asset_ids: Collection[str] = (),
) -> CompiledEDL:
    """Validate motivated decisions and lower them to frame-authoritative EDL 2.0."""

    if plan.schema_version != "2.1":
        raise EditorialDirectorError(
            f"unsupported editorial director schema {plan.schema_version!r}"
        )
    _validate_graph_for_transcript(graph, transcript)
    if not plan.shots:
        raise EditorialDirectorError("an editorial director plan needs at least one shot")

    beats = {item.beat_id: item for item in graph.editorial_beats}
    moments = {item.moment_id: item for item in graph.source_moments}
    visuals = {item.visual_id: item for item in graph.visual_beats}
    screen_regions: dict[str, FramingRegion] = {}

    for shot_index, shot in enumerate(plan.shots):
        beat = beats.get(shot.beat_id)
        if beat is None:
            raise EditorialDirectorError(
                f"shot {shot.shot_id}: references unknown beat {shot.beat_id!r}"
            )
        moment = moments[beat.source_moment_id]
        if not _is_subrange(shot, moment):
            raise EditorialDirectorError(
                f"shot {shot.shot_id}: word range escapes source moment {moment.moment_id}"
            )
        if not _range_is_scoped(shot, graph):
            raise EditorialDirectorError(f"shot {shot.shot_id}: word range escapes edit scope")
        if shot.framing.mode not in beat.available_framings:
            raise EditorialDirectorError(
                f"shot {shot.shot_id}: framing {shot.framing.mode!r} is unavailable for "
                f"beat {beat.beat_id}"
            )
        if shot.framing.mode == "screen_focus":
            screen_regions[shot.shot_id] = _trusted_screen_region_for_shot(
                shot,
                beat,
                visuals,
                transcript,
            )
        opening_override = (
            shot_index == 0
            and beat.purpose != "cta"
            and shot.role in {"hook", "reaction"}
        )
        if not opening_override and shot.role not in _ROLE_BY_PURPOSE[beat.purpose]:
            raise EditorialDirectorError(
                f"shot {shot.shot_id}: role {shot.role!r} is incompatible with "
                f"beat purpose {beat.purpose!r}"
            )
        if not (
            (opening_override and shot.entry_motivation == "scroll_stop")
            or shot.entry_motivation == "context_reset"
        ) and shot.entry_motivation not in _ENTRY_BY_PURPOSE[beat.purpose]:
            raise EditorialDirectorError(
                f"shot {shot.shot_id}: entry motivation is incompatible with "
                f"beat purpose {beat.purpose!r}"
            )
        if shot.exit_motivation not in _EXIT_BY_PURPOSE[beat.purpose]:
            raise EditorialDirectorError(
                f"shot {shot.shot_id}: exit motivation is incompatible with "
                f"beat purpose {beat.purpose!r}"
            )
        for effect in shot.effects:
            _validate_effect_reason(shot, effect)

        if shot_index == 0:
            if shot.joint_motivation != "opening" or shot.continuity_strategy != "establish":
                raise EditorialDirectorError(
                    "the first shot must declare opening/establish motivations"
                )
        else:
            if shot.joint_motivation == "opening" or shot.continuity_strategy == "establish":
                raise EditorialDirectorError(
                    f"shot {shot.shot_id}: opening/establish are first-shot controls only"
                )
            previous = plan.shots[shot_index - 1]
            edge = _edge_for_joint(previous, shot, graph.edges)
            if edge is None:
                _validate_unlinked_joint(previous, shot)
            else:
                _validate_joint(previous, shot, edge)

    lowered = EditIntentPlan(
        schema_version="2.0",
        editorial_thesis=plan.editorial_thesis,
        shots=tuple(
            shot.to_edl_intent(screen_region=screen_regions.get(shot.shot_id))
            for shot in plan.shots
        ),
        music=plan.music,
        sfx=plan.sfx,
    )
    try:
        return compile_edit_intent(
            lowered,
            transcript,
            source_duration_ms=source_duration_ms,
            fps=fps,
            width=width,
            height=height,
            target_duration_seconds=target_duration_seconds,
            allowed_music_asset_ids=frozenset(allowed_music_asset_ids),
            allowed_sfx_asset_ids=frozenset(allowed_sfx_asset_ids),
            edit_scope=graph.scope,
        )
    except EDLValidationError as exc:
        raise EditorialDirectorError(f"EDL 2.0 rejected the motivated plan: {exc}") from exc


def evaluate_director_variant_diversity(
    plans: Collection[EditorialDirectorPlan],
    *,
    max_pairwise_word_overlap: float = 0.9,
) -> DirectorVariantDiversityReport:
    """Reject three cosmetic copies before spending render time on them."""

    ordered = tuple(plans)
    findings: list[str] = []
    if len(ordered) != 3:
        findings.append("exactly_three_variants_required")
    hypotheses = {plan.campaign_hypothesis for plan in ordered}
    if len(hypotheses) != len(ordered):
        findings.append("campaign_hypotheses_must_be_distinct")
    opening_beats = {plan.shots[0].beat_id for plan in ordered if plan.shots}
    if len(opening_beats) < min(2, len(ordered)):
        findings.append("opening_beats_are_not_diverse")
    signatures = {
        tuple((shot.beat_id, shot.from_word_id, shot.to_word_id, shot.role) for shot in plan.shots)
        for plan in ordered
    }
    if len(signatures) != len(ordered):
        findings.append("timeline_structures_are_duplicates")

    word_sets = [
        {
            word_id
            for shot in plan.shots
            for word_id in range(shot.from_word_id, shot.to_word_id + 1)
        }
        for plan in ordered
    ]
    overlaps: list[float] = []
    for left_index, left in enumerate(word_sets):
        for right in word_sets[left_index + 1 :]:
            union = left | right
            overlap = len(left & right) / len(union) if union else 1.0
            overlaps.append(overlap)
            if overlap > max_pairwise_word_overlap:
                findings.append("variant_source_overlap_too_high")
    return DirectorVariantDiversityReport(
        status="reject" if findings else "pass",
        findings=tuple(dict.fromkeys(findings)),
        pairwise_word_overlap=tuple(overlaps),
    )
