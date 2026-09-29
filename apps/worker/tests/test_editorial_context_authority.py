from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest
from test_editorial_director_v22 import (
    CAMPAIGN_ID,
    SOURCE_ID,
    _context,
    _graph,
    _payload,
    _transcript,
)

from app.pipeline.editorial_context_authority import (
    EditorialContextAuthorityError,
    HMACSHA256Authority,
    IssuedEditorialContext,
    VerifiedEditorialContext,
    compile_issued_editorial_director_plan_v22,
    editorial_director_user_prompt_issued_v22,
    issue_editorial_context,
    parse_issued_editorial_director_plan_v22,
    verify_editorial_context_capability,
    verify_issued_editorial_context,
)
from app.pipeline.knowledge_ingestion import KnowledgeVaultSnapshot
from app.pipeline.knowledge_tenant_authority import (
    HMACSHA256TenantAuthority,
    issue_tenant_vault_authority,
)
from app.pipeline.knowledge_vault import KnowledgeNote, KnowledgeRelation, KnowledgeVault

KEY = HMACSHA256Authority("authority_2026", b"x" * 32)
NOW = "2026-08-09T12:00:00Z"


def _snapshot(context=None) -> KnowledgeVaultSnapshot:
    context = context or _context()
    notes = tuple(
        KnowledgeNote(
            item.note.note_id,
            item.note.type,
            item.note.vault,
            item.note.status,
            item.note.confidence,
            item.note.title,
            item.note.content,
            version=item.note.version,
            campaign_id=CAMPAIGN_ID if item.note.vault != "global" else None,
            source_id=SOURCE_ID if item.note.vault == "source" else None,
            graph_refs=item.note.graph_refs,
        )
        for item in context.selected_notes
    )
    snapshot = KnowledgeVaultSnapshot(
        1,
        "owner_01",
        CAMPAIGN_ID,
        SOURCE_ID,
        "r1",
        KnowledgeVault(notes),
        campaign_fingerprint=context.campaign_fingerprint,
        research_digest=context.research_digest,
        graph_digest=context.graph_digest,
    )
    tenant, _ = _tenant_authority(snapshot)
    return replace(
        snapshot,
        tenant_authority_digest=tenant.authority_digest,
        base_vault_digest=tenant.vault_digest,
    )


def _tenant_authority(snapshot: KnowledgeVaultSnapshot):
    signer = HMACSHA256TenantAuthority("tenant_authority_2026", b"t" * 32)
    issued = issue_tenant_vault_authority(
        snapshot.vault,
        owner_id=snapshot.owner_id,
        campaign_id=snapshot.campaign_id,
        source_id=snapshot.source_id,
        signer=signer,
        issued_at=datetime.fromisoformat("2026-08-09T10:00:00+00:00"),
        expires_at=datetime.fromisoformat("2026-08-10T10:00:00+00:00"),
        authority_id="tenant_context_authority",
    )
    return issued, signer


def _issued():
    context, graph = _context(), _graph()
    snapshot = _snapshot(context)
    issued = issue_editorial_context(
        snapshot,
        context,
        graph,
        signer=KEY,
        issued_at="2026-08-09T10:00:00Z",
        expires_at="2026-08-10T10:00:00Z",
        issuance_id="issue_01",
        tenant_authority=_tenant_authority(snapshot)[0],
        tenant_authority_verifier=_tenant_authority(snapshot)[1],
    )
    return issued, snapshot, context, graph


def test_issue_verify_and_canonical_payload_are_stable() -> None:
    issued, snapshot, context, graph = _issued()
    assert issued.canonical_payload() == issued.canonical_payload()
    verify_issued_editorial_context(
        issued,
        snapshot,
        context,
        graph,
        verifier=KEY,
        now=NOW,
        expected_owner_id="owner_01",
        expected_campaign_id=CAMPAIGN_ID,
        expected_source_id=SOURCE_ID,
    )
    assert "secret" not in issued.unsigned_payload()
    assert len(issued.retrieval_result_digest) == 64
    assert len(issued.retrieval_policy_digest) == 64


def test_context_authority_recomputes_retrieval_and_refuses_blocked_constraints() -> None:
    context, graph = _context(), _graph()
    snapshot = _snapshot(context)
    first = KnowledgeNote(
        "constraint_never_claim",
        "observation",
        "campaign",
        "observation",
        "high",
        "Never claim",
        "Never make product claims",
        tags=("hard_constraint",),
        campaign_id=CAMPAIGN_ID,
    )
    second = KnowledgeNote(
        "constraint_always_claim",
        "observation",
        "campaign",
        "observation",
        "high",
        "Always claim",
        "Always make product claims",
        tags=("hard_constraint",),
        campaign_id=CAMPAIGN_ID,
    )
    blocked = replace(
        snapshot,
        vault=KnowledgeVault(
            (*snapshot.vault.notes, first, second),
            (
                KnowledgeRelation(
                    "constraint_never_claim",
                    "constraint_always_claim",
                    "contradicts",
                ),
            ),
        ),
    )
    with pytest.raises(EditorialContextAuthorityError, match="blocked editorial retrieval"):
        issue_editorial_context(
            blocked,
            context,
            graph,
            signer=KEY,
            issued_at="2026-08-09T10:00:00Z",
            expires_at="2026-08-10T10:00:00Z",
            issuance_id="issue_blocked",
            tenant_authority=_tenant_authority(snapshot)[0],
            tenant_authority_verifier=_tenant_authority(snapshot)[1],
        )


def test_context_authority_refuses_a_context_that_omits_retrieved_evidence() -> None:
    context, graph = _context(), _graph()
    snapshot = _snapshot(context)
    extra = KnowledgeNote(
        "campaign_extra_proof",
        "proof",
        "campaign",
        "validated",
        "high",
        "Extra proof",
        "Show proof",
        campaign_id=CAMPAIGN_ID,
    )
    widened = replace(
        snapshot,
        vault=KnowledgeVault((*snapshot.vault.notes, extra)),
    )
    with pytest.raises(EditorialContextAuthorityError, match="exactly match"):
        issue_editorial_context(
            widened,
            context,
            graph,
            signer=KEY,
            issued_at="2026-08-09T10:00:00Z",
            expires_at="2026-08-10T10:00:00Z",
            issuance_id="issue_omitted",
            tenant_authority=_tenant_authority(snapshot)[0],
            tenant_authority_verifier=_tenant_authority(snapshot)[1],
        )


def test_verified_capability_is_the_safe_prompt_parse_validate_compile_surface() -> None:
    issued, snapshot, context, graph = _issued()
    verified = verify_editorial_context_capability(
        issued,
        snapshot,
        context,
        graph,
        verifier=KEY,
        now=NOW,
        expected_owner_id="owner_01",
        expected_campaign_id=CAMPAIGN_ID,
        expected_source_id=SOURCE_ID,
    )
    prompt = verified.prompt(transcript=_transcript(), target_duration_seconds=2, now=NOW)
    assert "UNIFIED_EDITORIAL_CONTEXT_JSON" in prompt
    plan = verified.parse(_payload(), now=NOW)
    verified.validate(plan, now=NOW)
    edl = verified.compile(plan, _transcript(), now=NOW, source_duration_ms=1600)
    assert edl.duration_ms == 1600


def test_capability_constructor_and_expired_use_fail_closed() -> None:
    issued, snapshot, context, graph = _issued()
    with pytest.raises(EditorialContextAuthorityError, match="must be created"):
        VerifiedEditorialContext(issued, snapshot, context, graph, _token=object())
    verified = verify_editorial_context_capability(
        issued,
        snapshot,
        context,
        graph,
        verifier=KEY,
        now=NOW,
        expected_owner_id="owner_01",
        expected_campaign_id=CAMPAIGN_ID,
        expected_source_id=SOURCE_ID,
    )
    with pytest.raises(EditorialContextAuthorityError, match="expired"):
        verified.prompt(
            transcript=_transcript(),
            target_duration_seconds=2,
            now="2026-08-11T00:00:00Z",
        )


def test_issued_prompt_wrapper_verifies_before_emitting_context() -> None:
    issued, snapshot, context, graph = _issued()
    prompt = editorial_director_user_prompt_issued_v22(
        _transcript(),
        issued=issued,
        snapshot=snapshot,
        context=context,
        graph=graph,
        verifier=KEY,
        now=NOW,
        expected_owner_id="owner_01",
        expected_campaign_id=CAMPAIGN_ID,
        expected_source_id=SOURCE_ID,
        target_duration_seconds=2,
    )
    assert "source_proof" in prompt
    with pytest.raises(EditorialContextAuthorityError, match="signature"):
        editorial_director_user_prompt_issued_v22(
            _transcript(),
            issued=replace(issued, signature="0" * 64),
            snapshot=snapshot,
            context=context,
            graph=graph,
            verifier=KEY,
            now=NOW,
            expected_owner_id="owner_01",
            expected_campaign_id=CAMPAIGN_ID,
            expected_source_id=SOURCE_ID,
            target_duration_seconds=2,
        )


def test_issued_parse_and_compile_wrappers_delegate_to_verified_capability() -> None:
    issued, snapshot, context, graph = _issued()
    plan = parse_issued_editorial_director_plan_v22(
        _payload(),
        issued=issued,
        snapshot=snapshot,
        context=context,
        graph=graph,
        verifier=KEY,
        now=NOW,
        expected_owner_id="owner_01",
        expected_campaign_id=CAMPAIGN_ID,
        expected_source_id=SOURCE_ID,
    )
    edl = compile_issued_editorial_director_plan_v22(
        plan,
        graph,
        _transcript(),
        issued=issued,
        snapshot=snapshot,
        context=context,
        verifier=KEY,
        now=NOW,
        expected_owner_id="owner_01",
        expected_campaign_id=CAMPAIGN_ID,
        expected_source_id=SOURCE_ID,
        source_duration_ms=1600,
    )
    assert edl.duration_ms == 1600


@pytest.mark.parametrize(
    "mutate, match",
    [
        (lambda i: replace(i, signature="0" * 64), "signature"),
        (lambda i: replace(i, context_digest="b" * 64), "signature"),
        (lambda i: replace(i, authority_key_id="old_key"), "rotation"),
        (lambda i: replace(i, expires_at="2026-08-09T11:00:00Z"), "signature"),
    ],
)
def test_tampered_envelope_is_rejected(mutate, match: str) -> None:
    issued, snapshot, context, graph = _issued()
    with pytest.raises(EditorialContextAuthorityError, match=match):
        verify_issued_editorial_context(
            mutate(issued),
            snapshot,
            context,
            graph,
            verifier=KEY,
            now=NOW,
            expected_owner_id="owner_01",
            expected_campaign_id=CAMPAIGN_ID,
            expected_source_id=SOURCE_ID,
        )


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"expected_owner_id": "owner_02"}, "tenant"),
        ({"expected_campaign_id": "a4c282cc-848f-4a80-bf53-9b3c82080d41"}, "tenant"),
        ({"expected_source_id": "52bb1d18-7e1e-4e63-b517-73f78d0a9229"}, "tenant"),
        ({"now": "2026-08-09T09:00:00Z"}, "not yet"),
        ({"now": "2026-08-11T12:00:00Z"}, "expired"),
    ],
)
def test_scope_and_time_are_fail_closed(kwargs, match: str) -> None:
    issued, snapshot, context, graph = _issued()
    options = {
        "now": NOW,
        "expected_owner_id": "owner_01",
        "expected_campaign_id": CAMPAIGN_ID,
        "expected_source_id": SOURCE_ID,
    }
    options.update(kwargs)
    with pytest.raises(EditorialContextAuthorityError, match=match):
        verify_issued_editorial_context(issued, snapshot, context, graph, verifier=KEY, **options)


def test_removed_or_version_changed_snapshot_note_is_rejected() -> None:
    issued, snapshot, context, graph = _issued()
    removed = replace(snapshot, vault=KnowledgeVault(snapshot.vault.notes[:1]))
    with pytest.raises(EditorialContextAuthorityError, match="cover"):
        verify_issued_editorial_context(
            issued,
            removed,
            context,
            graph,
            verifier=KEY,
            now=NOW,
            expected_owner_id="owner_01",
            expected_campaign_id=CAMPAIGN_ID,
            expected_source_id=SOURCE_ID,
        )
    changed_notes = tuple(
        replace(note, version=2) if note.id == "source_proof" else note
        for note in snapshot.vault.notes
    )
    changed = replace(snapshot, vault=KnowledgeVault(changed_notes))
    with pytest.raises(EditorialContextAuthorityError, match="version"):
        verify_issued_editorial_context(
            issued,
            changed,
            context,
            graph,
            verifier=KEY,
            now=NOW,
            expected_owner_id="owner_01",
            expected_campaign_id=CAMPAIGN_ID,
            expected_source_id=SOURCE_ID,
        )


def test_same_key_id_with_wrong_rotated_secret_is_rejected() -> None:
    issued, snapshot, context, graph = _issued()
    wrong = HMACSHA256Authority("authority_2026", b"y" * 32)
    with pytest.raises(EditorialContextAuthorityError, match="signature"):
        verify_issued_editorial_context(
            issued,
            snapshot,
            context,
            graph,
            verifier=wrong,
            now=NOW,
            expected_owner_id="owner_01",
            expected_campaign_id=CAMPAIGN_ID,
            expected_source_id=SOURCE_ID,
        )


def test_envelope_constructor_rejects_malformed_fields_and_oversized_lifetime() -> None:
    issued, *_ = _issued()
    with pytest.raises(EditorialContextAuthorityError, match="snapshot_digest"):
        replace(issued, snapshot_digest="not-a-digest")
    with pytest.raises(EditorialContextAuthorityError, match="signature"):
        replace(issued, signature="no")
    with pytest.raises(EditorialContextAuthorityError, match="lifetime"):
        replace(issued, expires_at="2026-08-11T10:00:01Z")
    with pytest.raises(EditorialContextAuthorityError, match="campaign_id"):
        replace(issued, campaign_id="../../other")


def test_issue_rejects_noncanonical_snapshot_note_projection() -> None:
    context, graph = _context(), _graph()
    snapshot = _snapshot(context)
    forged_note = replace(snapshot.vault.notes[0], title="Different title without version bump")
    forged_snapshot = replace(
        snapshot,
        vault=KnowledgeVault((forged_note, *snapshot.vault.notes[1:])),
    )
    with pytest.raises(EditorialContextAuthorityError, match="canonical snapshot projection"):
        issue_editorial_context(
            forged_snapshot,
            context,
            graph,
            signer=KEY,
            issued_at="2026-08-09T10:00:00Z",
            expires_at="2026-08-10T10:00:00Z",
            issuance_id="issue_forged",
            tenant_authority=_tenant_authority(snapshot)[0],
            tenant_authority_verifier=_tenant_authority(snapshot)[1],
        )


def test_direct_envelope_construction_normalizes_timestamps() -> None:
    issued, *_ = _issued()
    rebuilt = IssuedEditorialContext(
        **{
            **issued.unsigned_payload(),
            "issued_at": "2026-08-09T11:00:00+01:00",
            "expires_at": "2026-08-10T11:00:00+01:00",
        },
        signature=issued.signature,
    )
    assert rebuilt.issued_at == "2026-08-09T10:00:00Z"
    assert rebuilt.expires_at == "2026-08-10T10:00:00Z"


def test_hmac_authority_repr_never_exposes_secret_material() -> None:
    authority = HMACSHA256Authority("safe_key", b"super-secret-material-that-is-long-enough")
    assert "super-secret-material" not in repr(authority)
