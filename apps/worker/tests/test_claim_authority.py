from __future__ import annotations

from dataclasses import replace

import pytest
from test_editorial_context_authority import KEY, NOW, _issued
from test_editorial_director_v22 import CAMPAIGN_ID, SOURCE_ID, _payload, _transcript

from app.pipeline.claim_authority import (
    ClaimAtom,
    ClaimAuthorityError,
    ClaimEvidence,
    ClaimUse,
    ClaimUseEnvelope,
    HMACSHA256ClaimAuthority,
    IssuedClaimAuthority,
    authorize_claim_uses,
    claim_content_digest,
)
from app.pipeline.editorial_context import graph_digest
from app.pipeline.editorial_context_authority import verify_editorial_context_capability
from app.pipeline.knowledge_vault import GraphEvidenceRef

CLAIM_KEY = HMACSHA256ClaimAuthority("claim_authority_2026", b"c" * 32)


def _verified_and_plan():
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
    return verified, verified.parse(_payload(), now=NOW)


def _claim(
    *,
    origin: str = "source_transcript",
    state: str = "verified",
    valid_until: str = "2026-08-10T00:00:00Z",
) -> ClaimAtom:
    return ClaimAtom(
        "1.0",
        "proof_claim",
        origin,  # type: ignore[arg-type]
        state,  # type: ignore[arg-type]
        claim_content_digest("This is proof now"),
        CAMPAIGN_ID,
        SOURCE_ID,
        "2026-08-08T00:00:00Z",
        valid_until,
        "claims_requiring_verification" if origin == "research_finding" else None,
    )


def _evidence(
    graph, *, kind: str = "source_words", valid_until: str = "2026-08-10T00:00:00Z"
) -> ClaimEvidence:
    return ClaimEvidence(
        "1.0",
        "proof_evidence",
        "proof_claim",
        kind,  # type: ignore[arg-type]
        (GraphEvidenceRef("source_moment", "moment_proof"),),
        graph_digest(graph),
        "transcript_alignment_v1" if kind == "source_words" else "reviewer_01",
        "2026-08-08T00:00:00Z",
        valid_until,
    )


def _use(*, usage: str = "caption", beat_id: str = "beat_proof") -> ClaimUse:
    return ClaimUse(
        "1.0",
        "proof_claim",
        "proof",
        beat_id,
        "moment_proof",
        usage,  # type: ignore[arg-type]
        ("proof_evidence",),
    )


def _authorize(verified, plan, *, claims, evidences, uses):
    return authorize_claim_uses(
        verified,
        plan,
        claims=claims,
        evidences=evidences,
        uses=uses,
        signer=CLAIM_KEY,
        issuer_id="claim_service_01",
        reviewer_id="reviewer_01",
        issued_at="2026-08-09T11:00:00Z",
        expires_at="2026-08-09T23:00:00Z",
        authority_id="claim_batch_01",
    )


def test_source_words_authorise_exact_spoken_or_caption_use_and_bind_v22_validation() -> None:
    verified, plan = _verified_and_plan()
    authority = _authorize(
        verified, plan, claims=(_claim(),), evidences=(_evidence(verified.graph),), uses=(_use(),)
    )
    assert authority.audit_digest
    verified.validate(plan, now=NOW, claim_authority=authority, claim_authority_verifier=CLAIM_KEY)
    assert (
        verified.compile(
            plan,
            transcript=_transcript(),
            now=NOW,
            source_duration_ms=1600,
            claim_authority=authority,
            claim_authority_verifier=CLAIM_KEY,
        ).duration_ms
        == 1600
    )


def test_unresolved_research_claim_is_blocking_not_copy_or_incentive() -> None:
    verified, plan = _verified_and_plan()
    with pytest.raises(ClaimAuthorityError, match="unresolved claim"):
        _authorize(
            verified,
            plan,
            claims=(_claim(origin="research_finding", state="unresolved"),),
            evidences=(_evidence(verified.graph),),
            uses=(_use(usage="decision_rationale"),),
        )


@pytest.mark.parametrize(
    "mutate, match",
    [
        (
            lambda verified, claim, evidence, use: (
                claim,
                evidence,
                replace(use, beat_id="other_beat"),
            ),
            "exact decision beat",
        ),
        (
            lambda verified, claim, evidence, use: (
                replace(claim, valid_until="2026-08-08T12:00:00Z"),
                evidence,
                use,
            ),
            "claim is expired",
        ),
        (
            lambda verified, claim, evidence, use: (
                replace(claim, campaign_id="other_campaign"),
                evidence,
                use,
            ),
            "claim scope",
        ),
        (
            lambda verified, claim, evidence, use: (
                claim,
                replace(evidence, graph_digest="0" * 64),
                use,
            ),
            "graph digest",
        ),
    ],
)
def test_claim_authority_rejects_wrong_beat_expiry_cross_scope_and_graph_replay(
    mutate, match
) -> None:
    verified, plan = _verified_and_plan()
    claim, evidence, use = mutate(verified, _claim(), _evidence(verified.graph), _use())
    with pytest.raises(ClaimAuthorityError, match=match):
        _authorize(verified, plan, claims=(claim,), evidences=(evidence,), uses=(use,))


def test_approved_overlay_is_an_explicit_operator_only_path() -> None:
    verified, plan = _verified_and_plan()
    operator_claim = ClaimAtom(
        "1.0",
        "proof_claim",
        "operator",
        "approved",
        claim_content_digest("Approved legal offer overlay"),
        CAMPAIGN_ID,
        SOURCE_ID,
        "2026-08-08T00:00:00Z",
        "2026-08-10T00:00:00Z",
    )
    overlay_evidence = _evidence(verified.graph, kind="approved_overlay")
    authority = _authorize(
        verified,
        plan,
        claims=(operator_claim,),
        evidences=(overlay_evidence,),
        uses=(_use(usage="overlay"),),
    )
    verified.validate(plan, now=NOW, claim_authority=authority, claim_authority_verifier=CLAIM_KEY)
    with pytest.raises(ClaimAuthorityError, match="overlay claims require"):
        _authorize(
            verified,
            plan,
            claims=(_claim(),),
            evidences=(_evidence(verified.graph),),
            uses=(_use(usage="overlay"),),
        )


def test_signed_authority_cannot_be_forged_or_replayed_across_a_plan() -> None:
    verified, plan = _verified_and_plan()
    authority = _authorize(
        verified, plan, claims=(_claim(),), evidences=(_evidence(verified.graph),), uses=(_use(),)
    )
    forged = IssuedClaimAuthority(
        authority.envelope, authority.authority_key_id, authority.authority_id, "0" * 64
    )
    with pytest.raises(ClaimAuthorityError, match="signature"):
        verified.validate(plan, now=NOW, claim_authority=forged, claim_authority_verifier=CLAIM_KEY)
    altered = replace(plan, context_digest="0" * 64)
    with pytest.raises(Exception, match=r"context binding|claim authority"):
        verified.validate(
            altered, now=NOW, claim_authority=authority, claim_authority_verifier=CLAIM_KEY
        )


def test_self_declared_overlay_and_tampering_fail_without_a_valid_hmac() -> None:
    """Public claim/evidence projections cannot promote themselves to authority."""
    verified, plan = _verified_and_plan()
    claim = ClaimAtom(
        "1.0",
        "proof_claim",
        "operator",
        "approved",
        claim_content_digest("offer"),
        CAMPAIGN_ID,
        SOURCE_ID,
        "2026-08-08T00:00:00Z",
        "2026-08-10T00:00:00Z",
    )
    envelope = ClaimUseEnvelope(
        "1.0",
        verified.issued.owner_id,
        CAMPAIGN_ID,
        SOURCE_ID,
        verified.issued.issuance_id,
        verified.context.context_digest,
        graph_digest(verified.graph),
        "0" * 64,
        verified.issued.vision_evidence_audit_digest,
        (claim,),
        (_evidence(verified.graph, kind="approved_overlay"),),
        (_use(usage="overlay"),),
        "claim_service_01",
        "reviewer_01",
        "2026-08-09T11:00:00Z",
        "2026-08-09T23:00:00Z",
    )
    self_declared = IssuedClaimAuthority(envelope, CLAIM_KEY.key_id, "claim_batch_01", "0" * 64)
    with pytest.raises(ClaimAuthorityError, match="signature"):
        verified.validate(
            plan, now=NOW, claim_authority=self_declared, claim_authority_verifier=CLAIM_KEY
        )


def test_claim_authority_rechecks_key_and_expiry_at_point_of_use() -> None:
    verified, plan = _verified_and_plan()
    authority = _authorize(
        verified, plan, claims=(_claim(),), evidences=(_evidence(verified.graph),), uses=(_use(),)
    )
    wrong_key = HMACSHA256ClaimAuthority("other_claim_key", b"z" * 32)
    with pytest.raises(ClaimAuthorityError, match="key rotation"):
        verified.validate(
            plan, now=NOW, claim_authority=authority, claim_authority_verifier=wrong_key
        )
    with pytest.raises(ClaimAuthorityError, match="expired"):
        verified.validate(
            plan,
            now="2026-08-10T00:00:00Z",
            claim_authority=authority,
            claim_authority_verifier=CLAIM_KEY,
        )
