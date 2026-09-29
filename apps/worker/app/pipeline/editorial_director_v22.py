"""Schema 2.2 citation wrapper for the closed Editorial Director 2.1 controls.

The wrapper never interprets edit boundaries. It strips only its own citation
field, delegates every control to schema 2.1, and then binds each decision to
the selected, immutable unified editorial context.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from ..models import Transcript
from .editorial_beats import EditorialBeatGraph
from .editorial_context import UnifiedEditorialContextPack, graph_digest
from .editorial_director import (
    EDITORIAL_DIRECTOR_SYSTEM_PROMPT,
    EditorialDirectorError,
    EditorialDirectorPlan,
    compile_editorial_director_plan,
    editorial_director_user_prompt,
    parse_editorial_director_plan,
)
from .edl import CompiledEDL

SCHEMA_VERSION = "2.2"
_ROOT_KEYS = frozenset(
    {
        "schema_version",
        "campaign_hypothesis",
        "editorial_thesis",
        "shots",
        "music",
        "sfx",
        "decision_evidence",
    }
)
_EVIDENCE_KEYS = frozenset({"decision_id", "knowledge_refs", "campaign_refs", "source_refs"})
_SAFE_ID_MAX = 80


class EditorialDirectorV22Error(EditorialDirectorError):
    """Schema 2.2 citations are missing, forged, or outside the selected context."""


@dataclass(frozen=True)
class DirectorDecisionEvidence:
    decision_id: str
    knowledge_refs: tuple[str, ...]
    campaign_refs: tuple[str, ...]
    source_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.decision_id, str)
            or not self.decision_id
            or len(self.decision_id) > _SAFE_ID_MAX
        ):
            raise EditorialDirectorV22Error("decision_evidence.decision_id is invalid")
        for label, refs in (
            ("knowledge_refs", self.knowledge_refs),
            ("campaign_refs", self.campaign_refs),
            ("source_refs", self.source_refs),
        ):
            if not isinstance(refs, tuple) or not all(
                isinstance(item, str) and item and len(item) <= _SAFE_ID_MAX for item in refs
            ):
                raise EditorialDirectorV22Error(
                    f"decision_evidence.{label} must be a tuple of note IDs"
                )
            if len(refs) != len(set(refs)):
                raise EditorialDirectorV22Error(f"decision_evidence.{label} cannot repeat a note")
        all_refs = self.knowledge_refs + self.campaign_refs + self.source_refs
        if len(all_refs) != len(set(all_refs)):
            raise EditorialDirectorV22Error(
                "decision_evidence cannot reuse a note across namespaces"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "knowledge_refs": list(self.knowledge_refs),
            "campaign_refs": list(self.campaign_refs),
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class EditorialDirectorPlanV22:
    schema_version: Literal["2.2"]
    controls: EditorialDirectorPlan
    decision_evidence: tuple[DirectorDecisionEvidence, ...]
    context_digest: str
    graph_digest: str


EDITORIAL_DIRECTOR_V22_SYSTEM_PROMPT = (
    EDITORIAL_DIRECTOR_SYSTEM_PROMPT
    + '\n\nReturn schema_version exactly "2.2". Keep every 2.1 control unchanged and add '
    "decision_evidence. It is an array containing exactly one record for plan and one for each "
    "shot_id. Each record has only decision_id, knowledge_refs, campaign_refs, source_refs. "
    "Cite only supplied context note IDs: plan needs campaign_refs; every shot needs campaign_refs "
    "and source_refs. Knowledge references are optional. Citations never contain seconds, "
    "milliseconds, paths, URLs, or cut boundaries."
)


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EditorialDirectorV22Error(f"{label} must be an object")
    return value


def _closed(value: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    missing = sorted(allowed - set(value))
    if unknown or missing:
        raise EditorialDirectorV22Error(
            f"{label} keys invalid: unknown={unknown}, missing={missing}"
        )


def _refs(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise EditorialDirectorV22Error(f"{label} must be an array")
    return tuple(value)


def _note_map(context: UnifiedEditorialContextPack) -> dict[str, Any]:
    return {item.note.note_id: item.note for item in context.selected_notes}


def _validate_context_integrity(context: UnifiedEditorialContextPack) -> None:
    """Detect post-construction context mutation before trusting its allowlist."""
    selected_ids = tuple(item.note.note_id for item in context.selected_notes)
    expected_allowed = tuple(sorted(selected_ids))
    if context.allowed_ref_ids != expected_allowed:
        raise EditorialDirectorV22Error("context allowlist does not match selected notes")
    expected_digest = UnifiedEditorialContextPack.compute_digest(
        schema_version=context.schema_version,
        question=context.question,
        campaign_fingerprint=context.campaign_fingerprint,
        research_digest=context.research_digest,
        graph_digest=context.graph_digest,
        editorial_policy_version=context.editorial_policy_version,
        selected_notes=context.selected_notes,
        allowed_ref_ids=context.allowed_ref_ids,
    )
    if context.context_digest != expected_digest:
        raise EditorialDirectorV22Error("context_digest does not match current context contents")


def _validate_reference_classes(
    evidence: DirectorDecisionEvidence,
    *,
    context: UnifiedEditorialContextPack,
    beat_id: str | None,
    graph: EditorialBeatGraph,
) -> None:
    notes = _note_map(context)
    for ref in evidence.knowledge_refs:
        note = notes.get(ref)
        if note is None:
            raise EditorialDirectorV22Error(f"unknown knowledge reference {ref!r}")
        if note.vault != "global" or note.status not in {"validated", "curated"}:
            raise EditorialDirectorV22Error(
                f"knowledge reference {ref!r} is from the wrong vault or status"
            )
    for ref in evidence.campaign_refs:
        note = notes.get(ref)
        if note is None:
            raise EditorialDirectorV22Error(f"unknown campaign reference {ref!r}")
        if note.vault != "campaign" or note.status == "deprecated":
            raise EditorialDirectorV22Error(
                f"campaign reference {ref!r} is from the wrong vault or deprecated"
            )
    source_targets: set[tuple[str, str]] = set()
    if beat_id is not None:
        beat = next((item for item in graph.editorial_beats if item.beat_id == beat_id), None)
        if beat is None:
            raise EditorialDirectorV22Error(f"unknown graph beat {beat_id!r}")
        source_targets = {("source_moment", beat.source_moment_id)}
        source_targets.update(("visual_beat", item) for item in beat.visual_ids)
        source_targets.update(("audio_beat", item) for item in beat.audio_ids)
    for ref in evidence.source_refs:
        note = notes.get(ref)
        if note is None:
            raise EditorialDirectorV22Error(f"unknown source reference {ref!r}")
        if note.vault != "source" or note.status in {"deprecated", "raw_source"}:
            raise EditorialDirectorV22Error(
                f"source reference {ref!r} is from the wrong vault or deprecated"
            )
        if beat_id is not None and (
            not note.graph_refs
            or not all((item.kind, item.evidence_id) in source_targets for item in note.graph_refs)
        ):
            raise EditorialDirectorV22Error(
                f"source reference {ref!r} does not bind shot beat {beat_id!r}"
            )


def _validate_bindings(
    plan: EditorialDirectorPlan,
    evidence: tuple[DirectorDecisionEvidence, ...],
    *,
    context: UnifiedEditorialContextPack,
    graph: EditorialBeatGraph,
) -> None:
    _validate_context_integrity(context)
    actual_graph_digest = graph_digest(graph)
    if context.graph_digest != actual_graph_digest:
        raise EditorialDirectorV22Error("context graph_digest does not match current graph")
    if not set(shot.beat_id for shot in plan.shots).issubset(context.question.beat_ids):
        raise EditorialDirectorV22Error("plan shot beat_ids are not covered by context question")
    if (
        context.question.hypothesis is not None
        and plan.campaign_hypothesis != context.question.hypothesis
    ):
        raise EditorialDirectorV22Error("plan campaign_hypothesis does not match context question")
    expected_ids = {"plan", *(shot.shot_id for shot in plan.shots)}
    seen = {item.decision_id for item in evidence}
    if seen != expected_ids or len(seen) != len(evidence):
        raise EditorialDirectorV22Error(
            "decision_evidence must contain plan and every shot exactly once"
        )
    shots = {shot.shot_id: shot for shot in plan.shots}
    for item in evidence:
        beat_id = shots[item.decision_id].beat_id if item.decision_id != "plan" else None
        if not item.campaign_refs:
            raise EditorialDirectorV22Error(
                f"decision {item.decision_id!r} requires a campaign reference"
            )
        if item.decision_id != "plan" and not item.source_refs:
            raise EditorialDirectorV22Error(
                f"shot {item.decision_id!r} requires a source reference"
            )
        _validate_reference_classes(item, context=context, beat_id=beat_id, graph=graph)


def _parse_editorial_director_plan_v22_unverified(
    payload: Any,
    *,
    context: UnifiedEditorialContextPack,
    graph: EditorialBeatGraph,
) -> EditorialDirectorPlanV22:
    """Parse the closed 2.2 envelope while delegating every control to 2.1 unchanged."""
    root = _object(payload, "editorial director v2.2 plan")
    _closed(root, _ROOT_KEYS, "editorial director v2.2 plan")
    if root["schema_version"] != SCHEMA_VERSION:
        raise EditorialDirectorV22Error(
            f"unsupported editorial director schema {root['schema_version']!r}"
        )
    base_payload = {key: value for key, value in root.items() if key != "decision_evidence"}
    base_payload["schema_version"] = "2.1"
    controls = parse_editorial_director_plan(dict(base_payload))
    raw_evidence = root["decision_evidence"]
    if not isinstance(raw_evidence, list):
        raise EditorialDirectorV22Error("decision_evidence must be an array")
    evidence: list[DirectorDecisionEvidence] = []
    for index, raw in enumerate(raw_evidence):
        item = _object(raw, f"decision_evidence[{index}]")
        _closed(item, _EVIDENCE_KEYS, f"decision_evidence[{index}]")
        evidence.append(
            DirectorDecisionEvidence(
                decision_id=item["decision_id"],
                knowledge_refs=_refs(
                    item["knowledge_refs"], f"decision_evidence[{index}].knowledge_refs"
                ),
                campaign_refs=_refs(
                    item["campaign_refs"], f"decision_evidence[{index}].campaign_refs"
                ),
                source_refs=_refs(item["source_refs"], f"decision_evidence[{index}].source_refs"),
            )
        )
    frozen_evidence = tuple(evidence)
    _validate_bindings(controls, frozen_evidence, context=context, graph=graph)
    return EditorialDirectorPlanV22(
        schema_version="2.2",
        controls=controls,
        decision_evidence=frozen_evidence,
        context_digest=context.context_digest,
        graph_digest=context.graph_digest,
    )


def _validate_editorial_director_plan_v22_unverified(
    plan: EditorialDirectorPlanV22,
    *,
    context: UnifiedEditorialContextPack,
    graph: EditorialBeatGraph,
) -> None:
    """Revalidate a parsed plan against the current immutable context and graph."""
    if not isinstance(plan, EditorialDirectorPlanV22) or plan.schema_version != SCHEMA_VERSION:
        raise EditorialDirectorV22Error("invalid editorial director v2.2 plan")
    if plan.context_digest != context.context_digest or plan.graph_digest != context.graph_digest:
        raise EditorialDirectorV22Error("plan context binding does not match current context")
    _validate_bindings(plan.controls, plan.decision_evidence, context=context, graph=graph)


def _compile_editorial_director_plan_v22_unverified(
    plan: EditorialDirectorPlanV22,
    graph: EditorialBeatGraph,
    transcript: Transcript,
    *,
    context: UnifiedEditorialContextPack,
    source_duration_ms: int,
    fps: int = 30,
    width: int = 1080,
    height: int = 1920,
    target_duration_seconds: int | None = None,
    allowed_music_asset_ids: Collection[str] = (),
    allowed_sfx_asset_ids: Collection[str] = (),
) -> CompiledEDL:
    """Revalidate citations, then call the unmodified 2.1 compiler."""
    _validate_editorial_director_plan_v22_unverified(plan, context=context, graph=graph)
    return compile_editorial_director_plan(
        plan.controls,
        graph,
        transcript,
        source_duration_ms=source_duration_ms,
        fps=fps,
        width=width,
        height=height,
        target_duration_seconds=target_duration_seconds,
        allowed_music_asset_ids=allowed_music_asset_ids,
        allowed_sfx_asset_ids=allowed_sfx_asset_ids,
    )


def _editorial_director_user_prompt_v22_unverified(
    *,
    graph: EditorialBeatGraph,
    transcript: Transcript,
    context: UnifiedEditorialContextPack,
    target_duration_seconds: int,
    music_asset_ids: Collection[str] = (),
    sfx_asset_ids: Collection[str] = (),
) -> str:
    """Add bounded context JSON to the 2.1 graph and scoped-word prompt."""
    _validate_context_integrity(context)
    if context.graph_digest != graph_digest(graph):
        raise EditorialDirectorV22Error("context graph_digest does not match current graph")
    base = editorial_director_user_prompt(
        graph=graph,
        transcript=transcript,
        target_duration_seconds=target_duration_seconds,
        music_asset_ids=music_asset_ids,
        sfx_asset_ids=sfx_asset_ids,
    )
    return "\n".join(
        (
            base.replace("schema 2.1", "schema 2.2"),
            "UNIFIED_EDITORIAL_CONTEXT_JSON (citation IDs only; bounded data):",
            context.to_prompt_json(),
            "Return only schema 2.2 JSON with decision_evidence citations. Cite note IDs; never "
            "emit seconds, milliseconds, paths, or URLs.",
        )
    )


def _verified_capability_required() -> EditorialDirectorV22Error:
    """Keep accidental imports on the safe authority path.

    Raw 2.2 parsing/compilation remains useful for the narrowly scoped unit
    tests in this module, but it is not a production integration surface.  The
    authority module owns the public capability that first verifies the signed
    context, its snapshot projection, tenant scope, and lifetime.
    """

    return EditorialDirectorV22Error(
        "unverified Director 2.2 access is disabled; use VerifiedEditorialContext"
    )


def parse_editorial_director_plan_v22(*args: Any, **kwargs: Any) -> EditorialDirectorPlanV22:
    """Disabled public compatibility shim; use ``VerifiedEditorialContext.parse``."""

    del args, kwargs
    raise _verified_capability_required()


def validate_editorial_director_plan_v22(*args: Any, **kwargs: Any) -> None:
    """Disabled public compatibility shim; use ``VerifiedEditorialContext.validate``."""

    del args, kwargs
    raise _verified_capability_required()


def compile_editorial_director_plan_v22(*args: Any, **kwargs: Any) -> CompiledEDL:
    """Disabled public compatibility shim; use ``VerifiedEditorialContext.compile``."""

    del args, kwargs
    raise _verified_capability_required()


def editorial_director_user_prompt_v22(*args: Any, **kwargs: Any) -> str:
    """Disabled public compatibility shim; use ``VerifiedEditorialContext.prompt``."""

    del args, kwargs
    raise _verified_capability_required()
