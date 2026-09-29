"""Deterministic editorial-reflex QC for a compiled V2 edit.

The beat graph contains bounded evidence, not ground truth about everything in
the source.  This pass therefore rejects only contradictions with explicit
graph evidence or protected structure.  Unknown continuity and presentation
risks are reported as deterministic fallbacks for a director/preview pass.

No provider, filesystem or media operation is performed here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from ..models import Transcript
from .editorial_beats import (
    BeatEdge,
    EditorialBeat,
    EditorialBeatError,
    EditorialBeatGraph,
    SourceMoment,
    VisualBeat,
    validate_editorial_beat_graph,
)
from .edl import CompiledEDL, CompiledShot
from .edl_captions import sentence_word_ids

EditorialReflexStatus = Literal["pass", "pass_with_fallback", "reject"]
EditorialReflexSeverity = Literal["fallback", "reject"]

_STYLIZED_TRANSITIONS = frozenset({"reveal", "contrast", "time_jump", "hard_impact"})
_VISIBLE_PROOF_KINDS = frozenset({"screen_proof", "object_proof", "demo"})


@dataclass(frozen=True)
class EditorialReflexPolicy:
    """Thresholds for evidence-backed, repairable editorial risks."""

    min_proof_hold_ms: int = 1_200
    min_readable_screen_hold_ms: int = 1_000
    same_scale_jump_max_source_gap_ms: int = 2_000
    locked_crop_center_tolerance: float = 0.025
    locked_crop_scale_tolerance: float = 0.02


@dataclass(frozen=True)
class ShotEvidenceMapping:
    """The single graph moment/beat authorised to explain one compiled shot."""

    shot_id: str
    moment_id: str
    beat_id: str


@dataclass(frozen=True)
class EditorialReflexFinding:
    """Stable machine-readable QC finding."""

    code: str
    severity: EditorialReflexSeverity
    message: str
    shot_id: str | None = None
    next_shot_id: str | None = None
    moment_id: str | None = None
    fallback: str | None = None


@dataclass(frozen=True)
class EditorialReflexReport:
    """Pure result of comparing an EDL with its bounded evidence graph."""

    status: EditorialReflexStatus
    findings: tuple[EditorialReflexFinding, ...]
    shot_mappings: tuple[ShotEvidenceMapping, ...]

    @property
    def passed(self) -> bool:
        return self.status != "reject"

    @property
    def reject_count(self) -> int:
        return sum(item.severity == "reject" for item in self.findings)

    @property
    def fallback_count(self) -> int:
        return sum(item.severity == "fallback" for item in self.findings)


@dataclass(frozen=True)
class _MappedShot:
    shot: CompiledShot
    moment: SourceMoment
    beat: EditorialBeat


def _validate_policy(policy: EditorialReflexPolicy) -> None:
    integer_values = (
        policy.min_proof_hold_ms,
        policy.min_readable_screen_hold_ms,
        policy.same_scale_jump_max_source_gap_ms,
    )
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in integer_values
    ):
        raise ValueError("editorial reflex millisecond thresholds must be non-negative integers")
    tolerances = (
        policy.locked_crop_center_tolerance,
        policy.locked_crop_scale_tolerance,
    )
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value < 0
        for value in tolerances
    ):
        raise ValueError("editorial reflex crop tolerances must be finite and non-negative")


def _report(
    findings: list[EditorialReflexFinding],
    mappings: list[_MappedShot],
) -> EditorialReflexReport:
    if any(item.severity == "reject" for item in findings):
        status: EditorialReflexStatus = "reject"
    elif findings:
        status = "pass_with_fallback"
    else:
        status = "pass"
    return EditorialReflexReport(
        status=status,
        findings=tuple(findings),
        shot_mappings=tuple(
            ShotEvidenceMapping(item.shot.shot_id, item.moment.moment_id, item.beat.beat_id)
            for item in mappings
        ),
    )


def _map_shots(
    edl: CompiledEDL,
    graph: EditorialBeatGraph,
    findings: list[EditorialReflexFinding],
) -> list[_MappedShot]:
    beat_by_moment = {item.source_moment_id: item for item in graph.editorial_beats}
    mapped: list[_MappedShot] = []
    for shot in edl.shots:
        containing = [
            moment
            for moment in graph.source_moments
            if moment.word_range.from_word_id <= shot.from_word_id
            and shot.to_word_id <= moment.word_range.to_word_id
        ]
        if len(containing) != 1:
            code = "shot_outside_source_moment" if not containing else "ambiguous_source_moment"
            findings.append(
                EditorialReflexFinding(
                    code=code,
                    severity="reject",
                    message=(
                        f"shot {shot.shot_id!r} must be contained by exactly one source "
                        f"moment; found {len(containing)}"
                    ),
                    shot_id=shot.shot_id,
                )
            )
            continue
        moment = containing[0]
        beat = beat_by_moment[moment.moment_id]
        mapped.append(_MappedShot(shot, moment, beat))
    return mapped


def _visuals_for(mapped: _MappedShot, visuals: dict[str, VisualBeat]) -> tuple[VisualBeat, ...]:
    return tuple(visuals[visual_id] for visual_id in mapped.beat.visual_ids)


def _overlap_ms(start: int, end: int, other_start: int, other_end: int) -> int:
    return max(0, min(end, other_end) - max(start, other_start))


def _merged_overlap_ms(shot: CompiledShot, visual_beats: tuple[VisualBeat, ...]) -> int:
    """Visible source overlap, merged so overlapping observations are not double-counted."""
    intervals = sorted(
        (
            max(shot.source_in_ms, visual.source_in_ms),
            min(shot.source_out_ms, visual.source_out_ms),
        )
        for visual in visual_beats
        if _overlap_ms(
            shot.source_in_ms,
            shot.source_out_ms,
            visual.source_in_ms,
            visual.source_out_ms,
        )
        > 0
    )
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    source_ms = sum(end - start for start, end in merged)
    return round(source_ms / shot.speed) if shot.speed > 0 else 0


def _framing_findings(
    mapped: _MappedShot,
    visuals: dict[str, VisualBeat],
) -> list[EditorialReflexFinding]:
    shot, beat = mapped.shot, mapped.beat
    linked = _visuals_for(mapped, visuals)
    if shot.framing.mode == "screen_focus":
        readable_rois = tuple(
            visual
            for visual in linked
            if _overlap_ms(
                shot.source_in_ms,
                shot.source_out_ms,
                visual.source_in_ms,
                visual.source_out_ms,
            )
            > 0
            and visual.kind == "screen_proof"
            and visual.screen_readability == "readable"
            and visual.focus_region is not None
            and visual.provenance == "verified_candidate"
        )
        if len(readable_rois) != 1:
            return [
                EditorialReflexFinding(
                    code="screen_focus_without_unique_readable_roi",
                    severity="reject",
                    message=(
                        f"shot {shot.shot_id!r} requests screen_focus but has "
                        f"{len(readable_rois)} verified readable ROIs in its real source window"
                    ),
                    shot_id=shot.shot_id,
                    moment_id=mapped.moment.moment_id,
                )
            ]
        expected = readable_rois[0].focus_region
        actual = shot.framing.screen_region
        assert expected is not None
        if actual is None or (
            actual.x,
            actual.y,
            actual.width,
            actual.height,
        ) != (expected.x, expected.y, expected.width, expected.height):
            return [
                EditorialReflexFinding(
                    code="screen_focus_region_mismatch",
                    severity="reject",
                    message=(
                        f"shot {shot.shot_id!r} does not carry the unique graph-backed "
                        "screen ROI that the renderer must preserve"
                    ),
                    shot_id=shot.shot_id,
                    moment_id=mapped.moment.moment_id,
                )
            ]
    if shot.framing.mode == "locked_face":
        has_verified_face = any(
            _overlap_ms(
                shot.source_in_ms,
                shot.source_out_ms,
                visual.source_in_ms,
                visual.source_out_ms,
            )
            > 0
            and visual.face_state == "primary"
            and visual.provenance == "verified_candidate"
            for visual in linked
        )
        if not has_verified_face:
            return [
                EditorialReflexFinding(
                    code="locked_face_without_verified_face",
                    severity="reject",
                    message=(
                        f"shot {shot.shot_id!r} requests locked_face without a "
                        "verified candidate-window primary-face observation"
                    ),
                    shot_id=shot.shot_id,
                    moment_id=mapped.moment.moment_id,
                )
            ]
    if shot.framing.mode not in beat.available_framings:
        return [
            EditorialReflexFinding(
                code="framing_not_available",
                severity="reject",
                message=(
                    f"shot {shot.shot_id!r} requests framing {shot.framing.mode!r}; "
                    f"graph beat {beat.beat_id!r} allows {beat.available_framings!r}"
                ),
                shot_id=shot.shot_id,
                moment_id=mapped.moment.moment_id,
            )
        ]
    return []


def _hold_findings(
    mapped: _MappedShot,
    visuals: dict[str, VisualBeat],
    policy: EditorialReflexPolicy,
) -> list[EditorialReflexFinding]:
    shot, moment, beat = mapped.shot, mapped.moment, mapped.beat
    out: list[EditorialReflexFinding] = []
    linked = _visuals_for(mapped, visuals)
    visible_proof = tuple(
        item
        for item in linked
        if item.kind in _VISIBLE_PROOF_KINDS and item.provenance == "verified_candidate"
    )
    visible_proof_in_shot = tuple(
        item
        for item in visible_proof
        if _overlap_ms(
            shot.source_in_ms, shot.source_out_ms, item.source_in_ms, item.source_out_ms
        )
        > 0
    )
    if moment.proof_requirement in {"visible", "both"} and not visible_proof_in_shot:
        out.append(
            EditorialReflexFinding(
                code="required_visible_proof_not_in_shot",
                severity="reject",
                message=(
                    f"shot {shot.shot_id!r} selects moment {moment.moment_id!r} but "
                    "does not overlap its required visible proof evidence"
                ),
                shot_id=shot.shot_id,
                moment_id=moment.moment_id,
            )
        )

    is_proof_beat = moment.semantic_role == "proof" or beat.purpose == "prove"
    proof_hold_ms = (
        _merged_overlap_ms(shot, visible_proof_in_shot)
        if visible_proof_in_shot
        else shot.timeline_duration_ms
    )
    if is_proof_beat and proof_hold_ms < policy.min_proof_hold_ms:
        out.append(
            EditorialReflexFinding(
                code="proof_hold_too_short",
                severity="fallback",
                message=(
                    f"proof evidence in shot {shot.shot_id!r} is held for {proof_hold_ms}ms; "
                    f"policy requires {policy.min_proof_hold_ms}ms"
                ),
                shot_id=shot.shot_id,
                moment_id=moment.moment_id,
                fallback="extend_to_a_graph_backed_cut_safe_boundary",
            )
        )

    readable_screens = tuple(
        item
        for item in linked
        if item.kind == "screen_proof"
        and item.screen_readability == "readable"
        and item.provenance == "verified_candidate"
    )
    if readable_screens:
        readable_hold_ms = _merged_overlap_ms(shot, readable_screens)
        if readable_hold_ms < policy.min_readable_screen_hold_ms:
            out.append(
                EditorialReflexFinding(
                    code="readable_screen_hold_too_short",
                    severity="fallback",
                    message=(
                        f"readable screen evidence in shot {shot.shot_id!r} is held for "
                        f"{readable_hold_ms}ms; policy requires "
                        f"{policy.min_readable_screen_hold_ms}ms"
                    ),
                    shot_id=shot.shot_id,
                    moment_id=moment.moment_id,
                    fallback="extend_or_choose_fit_blur_until_the_proof_is_readable",
                )
            )
    return out


def _edge_for(
    left: _MappedShot,
    right: _MappedShot,
    edges: tuple[BeatEdge, ...],
) -> BeatEdge | None:
    matches = [
        edge
        for edge in edges
        if edge.from_beat_id == left.beat.beat_id and edge.to_beat_id == right.beat.beat_id
    ]
    return matches[0] if len(matches) == 1 else None


def _transition_is_supported(
    transition: str,
    edge: BeatEdge,
    right: _MappedShot,
) -> bool:
    if transition == "reveal":
        return edge.relation in {"answers", "proves"}
    if transition == "contrast":
        return edge.relation == "contrasts"
    if transition == "time_jump":
        # The graph has no invented "distant" claim.  Non-contiguous source
        # moments are deliberately encoded as unknown semantic continuity.
        return edge.semantic_continuity == "unknown"
    if transition == "hard_impact":
        return right.beat.purpose in {"prove", "payoff"} or right.moment.semantic_role == "reaction"
    return True


def _stylized_transition_finding(
    left: _MappedShot,
    right: _MappedShot,
    edges: tuple[BeatEdge, ...],
) -> EditorialReflexFinding | None:
    transition = left.shot.transition_out
    if transition not in _STYLIZED_TRANSITIONS:
        return None
    edge = _edge_for(left, right, edges)
    if edge is None:
        reason = "no unique directed BeatEdge supports this joint"
    elif _transition_is_supported(transition, edge, right):
        return None
    else:
        reason = f"BeatEdge {edge.edge_id!r} relation/continuity is incompatible"
    return EditorialReflexFinding(
        code="unmotivated_stylized_transition",
        severity="fallback",
        message=(
            f"transition {transition!r} from {left.shot.shot_id!r} to "
            f"{right.shot.shot_id!r} is not supported: {reason}"
        ),
        shot_id=left.shot.shot_id,
        next_shot_id=right.shot.shot_id,
        moment_id=left.moment.moment_id,
        fallback="use_hard_cut_or_choose_a_graph_compatible_transition",
    )


def _same_talking_head_visual(
    left: _MappedShot,
    right: _MappedShot,
    visuals: dict[str, VisualBeat],
) -> bool:
    left_ids = {
        visuals[item].source_event_id
        for item in left.beat.visual_ids
        if visuals[item].kind == "talking_head"
    }
    right_ids = {
        visuals[item].source_event_id
        for item in right.beat.visual_ids
        if visuals[item].kind == "talking_head"
    }
    return bool(left_ids & right_ids)


def _source_joint_gap_ms(left: CompiledShot, right: CompiledShot) -> int:
    if left.source_in_ms <= right.source_in_ms:
        return max(0, right.source_in_ms - left.source_out_ms)
    return max(0, left.source_in_ms - right.source_out_ms)


def _same_scale_jump_finding(
    left: _MappedShot,
    right: _MappedShot,
    visuals: dict[str, VisualBeat],
    policy: EditorialReflexPolicy,
) -> EditorialReflexFinding | None:
    left_frame, right_frame = left.shot.framing, right.shot.framing
    if (
        left_frame.mode != "locked_face"
        or right_frame.mode != "locked_face"
        or not _same_talking_head_visual(left, right, visuals)
        or _source_joint_gap_ms(left.shot, right.shot)
        > policy.same_scale_jump_max_source_gap_ms
        or abs(left_frame.center_x - right_frame.center_x)
        > policy.locked_crop_center_tolerance
        or abs(left_frame.base_scale - right_frame.base_scale)
        > policy.locked_crop_scale_tolerance
    ):
        return None
    return EditorialReflexFinding(
        code="same_scale_jump",
        severity="fallback",
        message=(
            f"short joint {left.shot.shot_id!r}->{right.shot.shot_id!r} keeps the "
            "same talking-head event and effectively identical locked crop"
        ),
        shot_id=left.shot.shot_id,
        next_shot_id=right.shot.shot_id,
        fallback="change_scale_or_keep_the_continuous_source_moment",
    )


def _contains_word(shot: CompiledShot, word_id: int) -> bool:
    return shot.from_word_id <= word_id <= shot.to_word_id


def _dramatic_pause_findings(
    mapped: list[_MappedShot],
    graph: EditorialBeatGraph,
) -> list[EditorialReflexFinding]:
    out: list[EditorialReflexFinding] = []
    for pause in graph.audio_beats:
        if (
            pause.kind != "dramatic_pause"
            or pause.left_word_id is None
            or pause.right_word_id is None
        ):
            continue
        containing = [
            item
            for item in mapped
            if _contains_word(item.shot, pause.left_word_id)
            and _contains_word(item.shot, pause.right_word_id)
        ]
        if containing:
            continue
        # This is intentionally global rather than a neighbouring-joint check:
        # a replay, insertion or source reorder must not mask a split protected
        # pause elsewhere in the edit.
        left_occurrences = [
            item for item in mapped if _contains_word(item.shot, pause.left_word_id)
        ]
        right_occurrences = [
            item for item in mapped if _contains_word(item.shot, pause.right_word_id)
        ]
        if not left_occurrences and not right_occurrences:
            continue
        out.append(
            EditorialReflexFinding(
                code="dramatic_pause_split",
                severity="reject",
                message=(
                    f"dramatic pause {pause.audio_id!r} requires word edges "
                    f"{pause.left_word_id} and {pause.right_word_id} to coexist in one shot"
                ),
                shot_id=left_occurrences[0].shot.shot_id if left_occurrences else None,
                next_shot_id=right_occurrences[0].shot.shot_id if right_occurrences else None,
            )
        )
    return out


def _source_bound_findings(
    mapped: list[_MappedShot],
    graph: EditorialBeatGraph,
    transcript: Transcript,
) -> list[EditorialReflexFinding]:
    """Verify persisted graph time claims and compiled-source speech bounds.

    SourceMoment times are context derived from word IDs, never editable
    metadata.  A compiled shot may retain a little silence roll, but its
    source window must not contain a spoken word outside its mapped moment.
    """

    findings: list[EditorialReflexFinding] = []
    for moment in graph.source_moments:
        expected_in = round(transcript.words[moment.word_range.from_word_id].start * 1000)
        expected_out = round(transcript.words[moment.word_range.to_word_id].end * 1000)
        if (moment.source_in_ms, moment.source_out_ms) != (expected_in, expected_out):
            findings.append(
                EditorialReflexFinding(
                    code="forged_source_moment_bounds",
                    severity="reject",
                    message=(
                        f"moment {moment.moment_id!r} source bounds do not match its "
                        "declared transcript word range"
                    ),
                    moment_id=moment.moment_id,
                )
            )
    for item in mapped:
        moment = item.moment
        leaked_word_id = next(
            (
                word_id
                for word_id, word in enumerate(transcript.words)
                if not (moment.word_range.from_word_id <= word_id <= moment.word_range.to_word_id)
                and round(word.end * 1000) > item.shot.source_in_ms
                and round(word.start * 1000) < item.shot.source_out_ms
            ),
            None,
        )
        if leaked_word_id is not None:
            findings.append(
                EditorialReflexFinding(
                    code="source_window_leaks_neighboring_speech",
                    severity="reject",
                    message=(
                        f"shot {item.shot.shot_id!r} source window includes spoken word "
                        f"{leaked_word_id} outside mapped moment {moment.moment_id!r}"
                    ),
                    shot_id=item.shot.shot_id,
                    moment_id=moment.moment_id,
                )
            )
    return findings


def _mid_thought_findings(
    mapped: list[_MappedShot],
    transcript: Transcript | None,
) -> list[EditorialReflexFinding]:
    if transcript is None or not transcript.sentences:
        return []
    sentence_ids = sentence_word_ids(transcript)
    out: list[EditorialReflexFinding] = []
    for item in mapped:
        shot = item.shot
        if not 0 <= shot.from_word_id <= shot.to_word_id < len(sentence_ids):
            continue
        sides: list[str] = []
        if shot.from_word_id > 0:
            current = sentence_ids[shot.from_word_id]
            previous = sentence_ids[shot.from_word_id - 1]
            if current is not None and current == previous:
                sides.append("entry")
        if shot.to_word_id + 1 < len(sentence_ids):
            current = sentence_ids[shot.to_word_id]
            following = sentence_ids[shot.to_word_id + 1]
            if current is not None and current == following:
                sides.append("exit")
        if sides:
            out.append(
                EditorialReflexFinding(
                    code="mid_thought_cut",
                    severity="fallback",
                    message=(
                        f"shot {shot.shot_id!r} has an ASR-sentence-backed mid-thought "
                        f"boundary at {', '.join(sides)}"
                    ),
                    shot_id=shot.shot_id,
                    moment_id=item.moment.moment_id,
                    fallback="move_to_the_nearest_authorised_sentence_boundary",
                )
            )
    return out


def evaluate_editorial_reflex_qc(
    edl: CompiledEDL,
    graph: EditorialBeatGraph,
    *,
    transcript: Transcript | None = None,
    policy: EditorialReflexPolicy | None = None,
) -> EditorialReflexReport:
    """Compare a compiled edit with graph evidence without mutating either.

    A structurally invalid persisted graph is represented as a reject report;
    callers do not need an exception path for untrusted cached artefacts.
    Policy construction errors still raise ``ValueError`` because they are a
    programmer/configuration error rather than an editorial result.
    """
    active_policy = policy or EditorialReflexPolicy()
    _validate_policy(active_policy)
    findings: list[EditorialReflexFinding] = []
    if not edl.shots:
        findings.append(
            EditorialReflexFinding(
                code="empty_edl",
                severity="reject",
                message="editorial reflex QC requires at least one compiled shot",
            )
        )
        return _report(findings, [])
    try:
        validate_editorial_beat_graph(graph)
    except EditorialBeatError as exc:
        findings.append(
            EditorialReflexFinding(
                code="invalid_beat_graph",
                severity="reject",
                message=str(exc),
            )
        )
        return _report(findings, [])
    if transcript is not None and len(transcript.words) != graph.transcript_word_count:
        findings.append(
            EditorialReflexFinding(
                code="transcript_graph_mismatch",
                severity="reject",
                message=(
                    f"transcript has {len(transcript.words)} words but graph declares "
                    f"{graph.transcript_word_count}"
                ),
            )
        )
        return _report(findings, [])

    mapped = _map_shots(edl, graph, findings)
    visuals = {item.visual_id: item for item in graph.visual_beats}
    for item in mapped:
        findings.extend(_framing_findings(item, visuals))
        findings.extend(_hold_findings(item, visuals, active_policy))
    if transcript is not None and len(mapped) == len(edl.shots):
        findings.extend(_source_bound_findings(mapped, graph, transcript))

    # Mapping failures remove shots from ``mapped``.  Joint checks would then
    # accidentally join non-adjacent shots, so only run them after full mapping.
    if len(mapped) == len(edl.shots):
        for left, right in pairwise(mapped):
            transition = _stylized_transition_finding(left, right, graph.edges)
            if transition is not None:
                findings.append(transition)
            same_scale = _same_scale_jump_finding(left, right, visuals, active_policy)
            if same_scale is not None:
                findings.append(same_scale)
        findings.extend(_dramatic_pause_findings(mapped, graph))
        findings.extend(_mid_thought_findings(mapped, transcript))
    return _report(findings, mapped)
