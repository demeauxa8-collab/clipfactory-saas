from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest
from test_editorial_context_authority import KEY, NOW, _issued
from test_editorial_director_v22 import _payload

from app.pipeline.decision_provenance import (
    DecisionProvenanceBundle,
    DecisionProvenanceError,
    HmacSha256VariantAuthority,
    IssuedVariantProvenance,
    VerifiedVariantProvenance,
    attest_variant_provenance,
    build_variant_provenance,
    director_plan_digest,
    issue_variant_provenance,
    materialize_director_decision_provenance,
    verify_issued_variant_provenance,
)
from app.pipeline.editorial_context_authority import (
    EditorialContextAuthorityError,
    parse_issued_editorial_director_plan_v22,
    verify_editorial_context_capability,
)


def _plan_and_authority():
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
        expected_campaign_id=context.question.campaign_id,
        expected_source_id=context.question.source_id,
    )
    return plan, issued, snapshot, context, graph


def _verified(**changes):
    issued, snapshot, context, graph = _issued()
    values = {
        "issued": issued,
        "snapshot": snapshot,
        "context": context,
        "graph": graph,
        "verifier": KEY,
        "now": NOW,
        "expected_owner_id": "owner_01",
        "expected_campaign_id": context.question.campaign_id,
        "expected_source_id": context.question.source_id,
    }
    values.update(changes)
    return verify_editorial_context_capability(**values)


def _audit(**changes) -> DecisionProvenanceBundle:
    plan, *_ = _plan_and_authority()
    values = {
        "plan": plan,
        "verified": _verified(),
        "now": NOW,
        "variant_id": "variant_proof_01",
        "created_at": NOW,
    }
    values.update(changes)
    return materialize_director_decision_provenance(**values)


def test_materializes_plan_and_shot_records_with_digest_only_evidence() -> None:
    audit = _audit()
    assert [item.subject_id for item in audit.records] == ["plan", "proof"]
    assert len(audit.resolved_references) == 2
    assert len(audit.audit_digest) == 64
    serialized_records = str([item.to_dict() for item in audit.records])
    assert "campaign_proof" not in serialized_records
    assert "source_proof" not in serialized_records
    assert all(len(item.note_digest) == 64 for item in audit.resolved_references)


def test_plan_digest_and_audit_are_stable_when_evidence_input_order_changes() -> None:
    plan, *_ = _plan_and_authority()
    reordered = replace(plan, decision_evidence=tuple(reversed(plan.decision_evidence)))
    first = _audit()
    second = _audit(plan=reordered)
    assert director_plan_digest(plan) == director_plan_digest(reordered)
    assert first.audit_digest == second.audit_digest


def test_note_version_and_context_are_part_of_resolved_reference_digest() -> None:
    audit = _audit()
    first = audit.resolved_references[0]
    with pytest.raises(DecisionProvenanceError, match="resolved note identity"):
        replace(first, version=first.version + 1)
    with pytest.raises(DecisionProvenanceError, match="resolved note identity"):
        replace(first, context_digest="b" * 64)


def test_authority_tampering_is_rejected_before_materialization() -> None:
    _, issued, *_ = _plan_and_authority()
    with pytest.raises(EditorialContextAuthorityError, match="signature"):
        _verified(issued=replace(issued, signature="0" * 64))


def test_plan_context_tampering_is_rejected_before_audit() -> None:
    plan, *_ = _plan_and_authority()
    with pytest.raises(ValueError, match="context binding"):
        _audit(plan=replace(plan, context_digest="b" * 64))


def test_wrong_expected_tenant_is_rejected() -> None:
    with pytest.raises(EditorialContextAuthorityError, match="tenant"):
        _verified(expected_owner_id="other_owner")


def test_attests_variant_provenance_from_exact_audit_and_render_digest() -> None:
    plan, *_ = _plan_and_authority()
    audit = _audit(plan=plan)
    verified = _verified()
    attestation = attest_variant_provenance(
        audit,
        plan,
        verified=verified,
        now=NOW,
        render_artifact_digest="f" * 64,
        created_at=NOW,
    )
    provenance = attestation.provenance
    assert isinstance(attestation, VerifiedVariantProvenance)
    assert provenance.variant_id == audit.variant_id
    assert provenance.director_plan_digest == audit.director_plan_digest
    assert provenance.editorial_context_digest == audit.context_digest
    assert provenance.campaign_hypothesis == "proof_first"
    assert provenance.snapshot_digest == audit.snapshot_digest
    assert provenance.context_issuance_id == audit.issuance_id
    assert provenance.decision_audit_digest == audit.audit_digest


def test_variant_provenance_refuses_unverified_or_mismatched_inputs() -> None:
    plan, _, _, context, _ = _plan_and_authority()
    audit = _audit(plan=plan)
    with pytest.raises(DecisionProvenanceError, match="exactly match"):
        attest_variant_provenance(
            audit,
            replace(plan, graph_digest="b" * 64),
            verified=_verified(),
            now=NOW,
            render_artifact_digest="f" * 64,
            created_at=NOW,
        )
    with pytest.raises(DecisionProvenanceError, match="raw variant provenance is disabled"):
        build_variant_provenance(
            audit,
            plan,
            context,
            render_artifact_digest="f" * 64,
            created_at=NOW,
        )


def test_verified_variant_capability_cannot_be_constructed_or_replay_a_changed_audit() -> None:
    plan, *_ = _plan_and_authority()
    audit = _audit(plan=plan)
    with pytest.raises(DecisionProvenanceError, match="must be created"):
        VerifiedVariantProvenance(  # type: ignore[call-arg]
            attest_variant_provenance(
                audit,
                plan,
                verified=_verified(),
                now=NOW,
                render_artifact_digest="f" * 64,
                created_at=NOW,
            ).provenance,
            _token=object(),
        )


def test_signed_variant_authority_is_the_only_promotion_safe_boundary() -> None:
    plan, issued, snapshot, context, graph = _plan_and_authority()
    audit = _audit(plan=plan)
    signer = HmacSha256VariantAuthority("variant_authority_01", b"v" * 32)
    sealed = issue_variant_provenance(
        signer,
        audit,
        plan,
        issued_context=issued,
        snapshot=snapshot,
        context=context,
        graph=graph,
        context_verifier=KEY,
        expected_owner_id="owner_01",
        expected_campaign_id=context.question.campaign_id,
        expected_source_id=context.question.source_id,
        now=NOW,
        authority_id="variant_issue_01",
        expires_at="2026-08-10T12:00:00Z",
        render_artifact_digest="f" * 64,
        created_at=NOW,
    )
    assert isinstance(sealed, IssuedVariantProvenance)
    assert (
        verify_issued_variant_provenance(
            sealed,
            signer,
            owner_id="owner_01",
            campaign_id=context.question.campaign_id,
            source_id=context.question.source_id,
            now=NOW,
        )
        == sealed.provenance
    )
    with pytest.raises(DecisionProvenanceError, match="binding mismatch"):
        verify_issued_variant_provenance(
            replace(sealed, render_artifact_digest="a" * 64),
            signer,
            owner_id="owner_01",
            campaign_id=context.question.campaign_id,
            now=NOW,
        )


def test_imported_private_capability_token_is_not_a_variant_consumer_bypass() -> None:
    """A module-level token is not relied on by the promotion-safe verifier."""
    from app.pipeline.decision_provenance import _VERIFIED_VARIANT_PROVENANCE_TOKEN

    plan, *_ = _plan_and_authority()
    audit = _audit(plan=plan)
    token_forged = VerifiedVariantProvenance(
        attest_variant_provenance(
            audit,
            plan,
            verified=_verified(),
            now=NOW,
            render_artifact_digest="f" * 64,
            created_at=NOW,
        ).provenance,
        _token=_VERIFIED_VARIANT_PROVENANCE_TOKEN,
    )
    with pytest.raises(DecisionProvenanceError, match="IssuedVariantProvenance"):
        verify_issued_variant_provenance(
            token_forged,  # type: ignore[arg-type]
            HmacSha256VariantAuthority("variant_authority_01", b"v" * 32),
            owner_id="owner_01",
            campaign_id="campaign_01",
            now=NOW,
        )
    with pytest.raises(DecisionProvenanceError, match="exactly match"):
        attest_variant_provenance(
            replace(audit, variant_id="another_variant"),
            plan,
            verified=_verified(),
            now=NOW,
            render_artifact_digest="f" * 64,
            created_at=NOW,
        )


def test_audit_is_frozen_and_rejects_missing_reference_resolution() -> None:
    audit = _audit()
    with pytest.raises(FrozenInstanceError):
        audit.variant_id = "mutate"  # type: ignore[misc]
    with pytest.raises(DecisionProvenanceError, match="exactly cover"):
        replace(audit, resolved_references=audit.resolved_references[:1])
