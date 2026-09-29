"""The researched pack must reach the Director as paired, scoped advice."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Transcript, TranscriptWord
from app.pipeline.context_intelligence import prepare_editorial_context
from app.pipeline.editorial_beats import EditorialBeat, EditorialBeatGraph, SourceMoment
from app.pipeline.editorial_context import EditorialQuestion
from app.pipeline.editorial_context_authority import (
    HMACSHA256Authority,
    issue_editorial_context,
    verify_editorial_context_capability,
)
from app.pipeline.editorial_knowledge import (
    load_editorial_retention_sources,
    load_editorial_retention_vault,
)
from app.pipeline.edl import EditScope, InclusiveWordRange
from app.pipeline.knowledge_tenant_authority import (
    HMACSHA256TenantAuthority,
    issue_tenant_vault_authority,
)

CAMPAIGN_ID = "018fbe6c-2fc6-7c6a-8a29-81d4a2ce3f0c"
SOURCE_ID = "018fbe6c-2fc6-7c6a-8a29-81d4a2ce3f0d"


def _graph() -> EditorialBeatGraph:
    word_range = InclusiveWordRange(0, 3)
    return EditorialBeatGraph(
        "1.0",
        4,
        EditScope((word_range,)),
        (SourceMoment("moment_1", word_range, 0, 1600, "proof"),),
        (),
        (),
        (EditorialBeat("beat_1", "moment_1", (), (), "prove", ("source_safe",)),),
        (),
    )


def test_editorial_pack_reaches_bounded_context_with_its_risk() -> None:
    vault = load_editorial_retention_vault()
    catalogue = load_editorial_retention_sources()
    assert {item["note_id"] for item in catalogue["sources"]} == {
        note.id for note in vault.notes if note.status == "raw_source"
    }

    now = datetime(2026, 9, 25, 12, tzinfo=UTC)
    signer = HMACSHA256TenantAuthority("test_editorial_pack", b"e" * 32)
    authority = issue_tenant_vault_authority(
        vault,
        owner_id="editorial_test",
        campaign_id=CAMPAIGN_ID,
        source_id=SOURCE_ID,
        signer=signer,
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        authority_id="editorial_pack_test",
    )
    question = EditorialQuestion(
        "hook",
        CAMPAIGN_ID,
        SOURCE_ID,
        ("beat_1",),
        ("moment_1",),
        "Create a clear relevant hook with a real curiosity gap, not a confusing opening",
    )
    prepared = prepare_editorial_context(
        base_vault=vault,
        campaign={
            "name": "Editorial test",
            "audience": "B2B founders",
            "niche": "SaaS",
            "tone": "direct",
            "goal": "Explain a source-backed result",
        },
        graph=_graph(),
        question=question,
        owner_id="editorial_test",
        revision="test_r1",
        editorial_policy_version="1.0",
        as_of=now,
        tenant_authority=authority,
        tenant_authority_verifier=signer,
    )
    selected = {item.note.note_id for item in prepared.context.selected_notes}
    assert {"curiosity_gap", "curiosity_confusion"} <= selected
    assert "src_gap" not in selected
    assert "src_curiosity" not in selected
    prompt = prepared.context.to_prompt_json()
    assert "https://" not in prompt
    assert len(prompt) <= 4_800

    context_signer = HMACSHA256Authority("test_context", b"c" * 32)
    issued = issue_editorial_context(
        prepared.snapshot,
        prepared.context,
        _graph(),
        signer=context_signer,
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        issuance_id="editorial_pack_context",
        tenant_authority=authority,
        tenant_authority_verifier=signer,
    )
    verified = verify_editorial_context_capability(
        issued,
        prepared.snapshot,
        prepared.context,
        _graph(),
        verifier=context_signer,
        now=now.isoformat(),
        expected_owner_id="editorial_test",
        expected_campaign_id=CAMPAIGN_ID,
        expected_source_id=SOURCE_ID,
    )
    transcript = Transcript(
        "A real proof arrives",
        [
            TranscriptWord("A", 0, 0.4),
            TranscriptWord("real", 0.4, 0.8),
            TranscriptWord("proof", 0.8, 1.2),
            TranscriptWord("arrives", 1.2, 1.6),
        ],
    )
    director_prompt = verified.prompt(
        transcript=transcript, target_duration_seconds=30, now=now.isoformat()
    )
    assert "curiosity_gap" in director_prompt
    assert "curiosity_confusion" in director_prompt
    assert "https://" not in director_prompt


def test_editorial_pack_covers_every_curated_note_with_a_risk_pair_and_source() -> None:
    vault = load_editorial_retention_vault()
    source_ids = {note.id for note in vault.notes if note.status == "raw_source"}
    curated = {note.id: note for note in vault.notes if note.status != "raw_source"}
    paired_ids = {
        note_id
        for relation in vault.relations
        if relation.relation == "risks"
        for note_id in (relation.source_id, relation.target_id)
    }
    assert paired_ids == set(curated)
    assert all(
        note.source_refs and {ref.note_id for ref in note.source_refs} <= source_ids
        for note in curated.values()
    )
