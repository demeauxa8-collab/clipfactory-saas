from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.pipeline.editorial_beats import (
    AudioBeat,
    EditorialBeat,
    EditorialBeatGraph,
    SourceMoment,
    VisualBeat,
)
from app.pipeline.editorial_context import EditorialQuestion, graph_digest
from app.pipeline.editorial_retrieval import (
    MAX_RETRIEVAL_JSON_CHARS,
    EditorialRetrievalError,
    RetrievalPolicy,
    RetrievalResult,
    RetrievalSelection,
    retrieve_editorial_evidence,
)
from app.pipeline.edl import EditScope, InclusiveWordRange
from app.pipeline.knowledge_ingestion import KnowledgeVaultSnapshot
from app.pipeline.knowledge_vault import (
    ContextNote,
    GraphEvidenceRef,
    KnowledgeNote,
    KnowledgeRelation,
    KnowledgeVault,
)

CAMPAIGN_ID = "b4c282cc-848f-4a80-bf53-9b3c82080d41"
SOURCE_ID = "42bb1d18-7e1e-4e63-b517-73f78d0a9229"
OTHER_SOURCE = "52bb1d18-7e1e-4e63-b517-73f78d0a9229"


def _graph() -> EditorialBeatGraph:
    first = SourceMoment("moment_proof", InclusiveWordRange(0, 3), 0, 900, "proof")
    second = SourceMoment("moment_payoff", InclusiveWordRange(4, 7), 1_000, 1_900, "payoff")
    visual_one = VisualBeat(
        "visual_dashboard",
        "event_one",
        10,
        800,
        "screen_proof",
        "none",
        "unknown",
        "still",
        "upper",
        70,
    )
    visual_two = VisualBeat(
        "visual_other",
        "event_two",
        1_100,
        1_800,
        "talking_head",
        "primary",
        "none",
        "gesture",
        "upper",
        70,
    )
    audio_one = AudioBeat("audio_pause", 250, 350, "micro_pause", None, None)
    return EditorialBeatGraph(
        "1.0",
        8,
        EditScope((InclusiveWordRange(0, 7),)),
        (first, second),
        (visual_one, visual_two),
        (audio_one,),
        (
            EditorialBeat(
                "beat_proof",
                "moment_proof",
                ("visual_dashboard",),
                ("audio_pause",),
                "prove",
                ("source_safe",),
            ),
            EditorialBeat(
                "beat_payoff", "moment_payoff", ("visual_other",), (), "payoff", ("source_safe",)
            ),
        ),
        (),
    )


def _question(**over: object) -> EditorialQuestion:
    values: dict[str, object] = {
        "kind": "proof",
        "campaign_id": CAMPAIGN_ID,
        "source_id": SOURCE_ID,
        "beat_ids": ("beat_proof",),
        "source_moment_ids": ("moment_proof",),
        "goal": "Show credible dashboard proof to founders",
        "hypothesis": "proof_first",
    }
    values.update(over)
    return EditorialQuestion(**values)  # type: ignore[arg-type]


def _note(
    note_id: str,
    vault: str,
    note_type: str,
    *,
    status: str = "validated",
    tags: tuple[str, ...] = (),
    content: str = "Credible dashboard proof supports founders.",
    refs: tuple[GraphEvidenceRef, ...] = (),
    source_id: str = SOURCE_ID,
) -> KnowledgeNote:
    return KnowledgeNote(
        note_id,
        note_type,
        vault,
        status,
        "high",
        note_id.replace("_", " "),
        content,
        tags=tags,
        graph_refs=refs,
        campaign_id=None if vault == "global" else CAMPAIGN_ID,
        source_id=source_id if vault == "source" else None,
    )  # type: ignore[arg-type]


def _source(note_id: str = "source_proof", **over: object) -> KnowledgeNote:
    values: dict[str, object] = {
        "refs": (GraphEvidenceRef("source_moment", "moment_proof"),),
        "status": "observation",
        "note_type": "source_moment",
    }
    values.update(over)
    return _note(note_id, "source", **values)  # type: ignore[arg-type]


def _base_notes() -> tuple[KnowledgeNote, ...]:
    return (
        _source(),
        _note(
            "campaign_goal",
            "campaign",
            "offer",
            tags=("goal",),
            content="Show dashboard proof to founders.",
        ),
        _note(
            "campaign_objection", "campaign", "objection", content="Founders need credible proof."
        ),
        _note(
            "global_principle",
            "global",
            "principle",
            status="curated",
            content="Show proof before claims.",
        ),
        _note(
            "global_risk",
            "global",
            "problem",
            status="validated",
            content="Unreadable proof creates doubt.",
        ),
    )


def _snapshot(
    notes: tuple[KnowledgeNote, ...] | None = None,
    relations: tuple[KnowledgeRelation, ...] | None = None,
    *,
    graph_bound: bool = True,
    source_id: str = SOURCE_ID,
    research_digest: str | None = None,
    active_research_note_ids: tuple[str, ...] = (),
) -> KnowledgeVaultSnapshot:
    graph = _graph()
    records = notes if notes is not None else _base_notes()
    ids = {note.id for note in records}
    edges = (
        relations
        if relations is not None
        else (
            (KnowledgeRelation("global_risk", "global_principle", "risks"),)
            if {"global_risk", "global_principle"} <= ids
            else ()
        )
    )
    return KnowledgeVaultSnapshot(
        1,
        "owner_one",
        CAMPAIGN_ID,
        source_id,
        "rev_one",
        KnowledgeVault(records, edges),
        research_digest=research_digest,
        graph_digest=graph_digest(graph) if graph_bound else None,
        active_research_note_ids=active_research_note_ids,
    )


def _result() -> RetrievalResult:
    result = retrieve_editorial_evidence(_question(), _graph(), _snapshot(), RetrievalPolicy())
    assert result.status == "ready"
    return result


def test_retrieves_complementary_roles_with_auditable_selection() -> None:
    result = _result()
    roles = {item.role for item in result.selections}
    assert {"source_evidence", "campaign_goal", "campaign_objection_or_proof"} <= roles
    assert {"global_principle", "counterexample_or_risk"} <= roles
    assert all("role=" in item.selection_reason for item in result.selections)
    assert all(item.score >= 0 for item in result.selections)


def test_source_selection_requires_exact_question_graph_evidence() -> None:
    mixed = _source(
        "source_mixed",
        refs=(
            GraphEvidenceRef("source_moment", "moment_proof"),
            GraphEvidenceRef("visual_beat", "visual_other"),
        ),
    )
    result = retrieve_editorial_evidence(
        _question(), _graph(), _snapshot((_source(), mixed, *_base_notes()[1:])), RetrievalPolicy()
    )
    assert "source_mixed" not in {item.note.note_id for item in result.selections}


def test_active_stale_source_reference_fails_closed() -> None:
    stale = _source("source_stale", refs=(GraphEvidenceRef("source_moment", "unknown_moment"),))
    with pytest.raises(EditorialRetrievalError, match="stale graph evidence"):
        retrieve_editorial_evidence(
            _question(), _graph(), _snapshot((stale, *_base_notes()[1:])), RetrievalPolicy()
        )


def test_snapshot_graph_binding_fails_when_graph_changes() -> None:
    changed = replace(
        _graph(),
        visual_beats=(replace(_graph().visual_beats[0], confidence=71), _graph().visual_beats[1]),
    )
    with pytest.raises(EditorialRetrievalError, match="snapshot graph digest"):
        retrieve_editorial_evidence(_question(), changed, _snapshot(), RetrievalPolicy())


def test_snapshot_scope_must_match_question() -> None:
    foreign_source = replace(_source(), source_id=OTHER_SOURCE)
    with pytest.raises(EditorialRetrievalError, match="scope does not match"):
        retrieve_editorial_evidence(
            _question(),
            _graph(),
            _snapshot((foreign_source, *_base_notes()[1:]), source_id=OTHER_SOURCE),
            RetrievalPolicy(),
        )


def test_deterministic_tie_uses_note_id() -> None:
    left = _note("campaign_alpha", "campaign", "objection", content="Unrelated text")
    right = _note("campaign_zulu", "campaign", "objection", content="Unrelated text")
    notes = (_source(), _base_notes()[1], left, right)
    first = retrieve_editorial_evidence(
        _question(), _graph(), _snapshot(notes, ()), RetrievalPolicy()
    )
    second = retrieve_editorial_evidence(
        _question(), _graph(), _snapshot(tuple(reversed(notes)), ()), RetrievalPolicy()
    )
    assert first.result_digest == second.result_digest
    choices = [
        item.note.note_id for item in first.selections if item.role == "campaign_objection_or_proof"
    ]
    assert choices == ["campaign_alpha", "campaign_zulu"]


def test_role_quotas_are_strict() -> None:
    extras = tuple(_source(f"source_extra_{index}") for index in range(5))
    result = retrieve_editorial_evidence(
        _question(), _graph(), _snapshot((*_base_notes(), *extras)), RetrievalPolicy()
    )
    assert sum(item.role == "source_evidence" for item in result.selections) == 3
    assert len(result.selections) <= 10


def test_raw_and_deprecated_notes_are_excluded() -> None:
    raw = _source("source_raw", status="raw_source")
    deprecated = _note("campaign_old", "campaign", "objection", status="deprecated")
    result = retrieve_editorial_evidence(
        _question(), _graph(), _snapshot((*_base_notes(), raw, deprecated)), RetrievalPolicy()
    )
    selected = {item.note.note_id for item in result.selections}
    assert {"source_raw", "campaign_old"}.isdisjoint(selected)


def test_hostile_url_note_is_never_serialized() -> None:
    unsafe = _note(
        "campaign_url", "campaign", "objection", content="Read https://private.example now"
    )
    result = retrieve_editorial_evidence(
        _question(), _graph(), _snapshot((_source(), _base_notes()[1], unsafe)), RetrievalPolicy()
    )
    assert "campaign_url" not in {item.note.note_id for item in result.selections}
    assert "https://" not in result.to_json()


def test_transcript_or_timing_note_is_never_serialized() -> None:
    unsafe = _note(
        "campaign_time", "campaign", "objection", content="At 00:42 use transcript word_id 7"
    )
    result = retrieve_editorial_evidence(
        _question(), _graph(), _snapshot((_source(), _base_notes()[1], unsafe)), RetrievalPolicy()
    )
    assert "campaign_time" not in {item.note.note_id for item in result.selections}
    assert "word_id" not in result.to_json()


def test_research_source_audit_is_excluded_but_finding_is_allowed() -> None:
    audit = _note(
        "research_audit",
        "campaign",
        "observation",
        tags=("research_source_audit",),
        content="Research source summary",
    )
    finding = _note(
        "research_finding",
        "campaign",
        "observation",
        tags=("research_finding",),
        content=json.dumps(
            {
                "content_role": "untrusted_external_research_data",
                "fields": {
                    "finding_kind": "vocabulary",
                    "observation_text": "Proof expectation for founders",
                    "scope": "market_context",
                },
                "record_type": "synthesized_observation",
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    result = retrieve_editorial_evidence(
        _question(),
        _graph(),
        _snapshot(
            (_source(), _base_notes()[1], audit, finding),
            research_digest="a" * 64,
            active_research_note_ids=("research_audit", "research_finding"),
        ),
        RetrievalPolicy(),
    )
    selected = {item.note.note_id for item in result.selections}
    assert "research_audit" not in selected
    assert "research_finding" in selected
    selected_finding = next(
        item.note for item in result.selections if item.note.note_id == "research_finding"
    )
    assert json.loads(selected_finding.content) == {
        "data_role": "external_research",
        "kind": "vocabulary",
        "scope": "market_context",
        "text": "Proof expectation for founders",
    }


def test_historical_research_finding_is_not_selected_without_active_lineage() -> None:
    historical = _note(
        "research_finding_historical",
        "campaign",
        "observation",
        tags=("research_finding",),
        content=json.dumps(
            {
                "content_role": "untrusted_external_research_data",
                "fields": {
                    "finding_kind": "fact",
                    "observation_text": "Old proof claim for founders",
                    "scope": "market_context",
                },
                "record_type": "synthesized_observation",
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    result = retrieve_editorial_evidence(
        _question(),
        _graph(),
        _snapshot((_source(), _base_notes()[1], historical)),
        RetrievalPolicy(),
    )

    assert result.status == "ready"
    assert historical.id not in {item.note.note_id for item in result.selections}


def test_unresolved_research_claim_warning_is_never_selected_as_editorial_evidence() -> None:
    warning = _note(
        "research_claim_warning",
        "campaign",
        "observation",
        tags=("claim_requires_verification", "research_finding"),
        content=json.dumps(
            {
                "content_role": "untrusted_external_research_data",
                "fields": {
                    "finding_kind": "fact",
                    "observation_text": "Unverified market claim for founders",
                    "scope": "market_context",
                },
                "record_type": "synthesized_observation",
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    result = retrieve_editorial_evidence(
        _question(),
        _graph(),
        _snapshot(
            (_source(), _base_notes()[1], warning),
            research_digest="b" * 64,
            active_research_note_ids=(warning.id,),
        ),
        RetrievalPolicy(),
    )

    assert result.status == "ready"
    assert warning.id not in {item.note.note_id for item in result.selections}


def test_missing_exact_source_evidence_fails_closed() -> None:
    no_source = (_base_notes()[1], _base_notes()[2])
    with pytest.raises(EditorialRetrievalError, match="no authorised source"):
        retrieve_editorial_evidence(
            _question(), _graph(), _snapshot(no_source, ()), RetrievalPolicy()
        )


def test_missing_campaign_evidence_fails_closed() -> None:
    global_only = (_source(), _base_notes()[3], _base_notes()[4])
    with pytest.raises(EditorialRetrievalError, match="no authorised campaign"):
        retrieve_editorial_evidence(
            _question(),
            _graph(),
            _snapshot(
                global_only, (KnowledgeRelation("global_risk", "global_principle", "risks"),)
            ),
            RetrievalPolicy(),
        )


def test_validated_global_pair_is_atomic_and_has_direct_path() -> None:
    result = _result()
    selected = {item.role: item for item in result.selections}
    assert (
        selected["global_principle"].relation_path
        == selected["counterexample_or_risk"].relation_path
    )
    assert "--risks-->" in selected["global_principle"].relation_path[0]


def test_unrelated_global_notes_never_make_a_false_pair() -> None:
    unrelated = KnowledgeRelation("campaign_objection", "global_principle", "supports")
    result = retrieve_editorial_evidence(
        _question(), _graph(), _snapshot(_base_notes(), (unrelated,)), RetrievalPolicy()
    )
    assert not {"global_principle", "counterexample_or_risk"} & {
        item.role for item in result.selections
    }


def test_reverse_global_risk_edge_does_not_make_a_false_pair() -> None:
    reverse = KnowledgeRelation("global_principle", "global_risk", "risks")
    result = retrieve_editorial_evidence(
        _question(), _graph(), _snapshot(_base_notes(), (reverse,)), RetrievalPolicy()
    )
    assert not {"global_principle", "counterexample_or_risk"} & {
        item.role for item in result.selections
    }


def test_contradictory_live_hard_constraints_block_with_finding() -> None:
    first = _note(
        "constraint_claim",
        "campaign",
        "observation",
        tags=("hard_constraint",),
        content="Never use claims",
    )
    second = _note(
        "constraint_proof",
        "campaign",
        "observation",
        tags=("hard_constraint",),
        content="Always use claims",
    )
    notes = (_source(), _base_notes()[1], first, second)
    result = retrieve_editorial_evidence(
        _question(),
        _graph(),
        _snapshot(
            notes, (KnowledgeRelation("constraint_claim", "constraint_proof", "contradicts"),)
        ),
        RetrievalPolicy(),
    )
    assert result.status == "blocked"
    assert not result.selections
    assert result.findings[0].note_ids == ("constraint_claim", "constraint_proof")


def test_directional_risk_between_hard_constraints_does_not_claim_a_contradiction() -> None:
    first = _note(
        "constraint_claim",
        "campaign",
        "observation",
        tags=("hard_constraint",),
        content="Avoid unsupported claims",
    )
    second = _note(
        "constraint_proof",
        "campaign",
        "observation",
        tags=("hard_constraint",),
        content="Show concrete proof",
    )
    result = retrieve_editorial_evidence(
        _question(),
        _graph(),
        _snapshot(
            (_source(), _base_notes()[1], first, second),
            (KnowledgeRelation("constraint_claim", "constraint_proof", "risks"),),
        ),
        RetrievalPolicy(),
    )
    assert result.status == "ready"
    assert not result.findings


def test_hostile_hard_constraint_cannot_bypass_contradiction_gate() -> None:
    first = _note(
        "constraint_safe",
        "campaign",
        "observation",
        tags=("hard_constraint",),
        content="Never add claims",
    )
    second = _note(
        "constraint_hostile",
        "campaign",
        "observation",
        tags=("hard_constraint",),
        content="See https://unsafe.example",
    )
    notes = (_source(), _base_notes()[1], first, second)
    result = retrieve_editorial_evidence(
        _question(),
        _graph(),
        _snapshot(
            notes, (KnowledgeRelation("constraint_hostile", "constraint_safe", "contradicts"),)
        ),
        RetrievalPolicy(),
    )
    assert result.status == "blocked"


def test_noncontradictory_hard_constraints_are_selected_under_quota() -> None:
    constraints = (
        _note("constraint_a", "campaign", "observation", tags=("hard_constraint",)),
        _note("constraint_b", "campaign", "observation", tags=("hard_constraint",)),
        _note("constraint_c", "campaign", "observation", tags=("hard_constraint",)),
    )
    result = retrieve_editorial_evidence(
        _question(),
        _graph(),
        _snapshot((_source(), _base_notes()[1], *constraints), ()),
        RetrievalPolicy(),
    )
    assert sum(item.role == "hard_constraint" for item in result.selections) == 2


def test_policy_is_closed_versioned_and_digest_stable() -> None:
    policy = RetrievalPolicy()
    assert policy.digest == RetrievalPolicy().digest
    with pytest.raises(EditorialRetrievalError, match="unsupported"):
        RetrievalPolicy(schema_version="2.0")
    with pytest.raises(EditorialRetrievalError, match="closed"):
        RetrievalPolicy(max_total=9)


def test_result_digest_is_stable_and_json_is_bounded() -> None:
    first, second = _result(), _result()
    assert first.result_digest == second.result_digest
    assert len(first.to_json()) <= MAX_RETRIEVAL_JSON_CHARS


def test_result_rejects_duplicate_note_across_roles() -> None:
    note = ContextNote(
        "note_one", 1, "observation", "campaign", "validated", "high", "One", "Safe", (), ()
    )
    selection = RetrievalSelection("campaign_goal", note, 1, "role=campaign_goal")
    with pytest.raises(EditorialRetrievalError, match="repeat"):
        RetrievalResult(
            "1.0", "ready", "a" * 64, "b" * 64, "c" * 64, "d" * 64, (selection, selection), ()
        )
