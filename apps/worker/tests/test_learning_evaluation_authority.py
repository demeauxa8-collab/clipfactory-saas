from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from test_learning_authority import (
    CAMPAIGN_ID,
    IMPORT_NOW,
    REGISTRATION_NOW,
    TENANT_ID,
    _bound_inputs,
    _outcome_signer,
    _registration_signer,
    _stat_policy,
    _variant_signer,
)

from app.pipeline.learning_evaluation_authority import (
    HmacSha256LearningEvaluationAuthority,
    LearningEvaluationAuthorityError,
    issue_learning_evaluation_review,
    verify_learning_evaluation_review,
)
from app.pipeline.learning_registration import (
    LearningRegistrationError,
    import_registered_outcomes,
    issue_learning_registration,
)

REVIEW_NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)


def _reviewer(*, secret: bytes = b"h" * 32) -> HmacSha256LearningEvaluationAuthority:
    return HmacSha256LearningEvaluationAuthority(key_id="human_review_01", secret=secret)


def _sources():
    hypothesis, evaluation, experiments, outcomes, provenances = _bound_inputs()
    registration = issue_learning_registration(
        _registration_signer(),
        registration_id="registration_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        hypothesis=hypothesis,
        experiments=experiments,
        outcome_stat_policy=_stat_policy(),
        issued_variant_provenances=provenances,
        variant_provenance_verifier=_variant_signer(),
        variant_owner_id="owner_01",
        now=REGISTRATION_NOW,
    )
    imported = import_registered_outcomes(
        _outcome_signer(),
        registration,
        _registration_signer(),
        import_id="import_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        outcomes=outcomes,
        now=IMPORT_NOW,
    )
    return registration, imported, evaluation


def _issued(**over: object):
    registration, imported, evaluation = _sources()
    data: dict[str, object] = {
        "signer": _reviewer(),
        "review_id": "review_01",
        "tenant_id": TENANT_ID,
        "campaign_id": CAMPAIGN_ID,
        "registration": registration,
        "registration_verifier": _registration_signer(),
        "imported_outcomes": imported,
        "outcome_adapter_verifier": _outcome_signer(),
        "evaluation": evaluation,
        "reviewer_id": "reviewer_01",
        "issued_at": REVIEW_NOW,
        "expires_at": "2026-08-14T14:00:00Z",
    }
    data.update(over)
    return issue_learning_evaluation_review(**data), registration, imported


def _verify(review, registration, imported, **over: object):
    data: dict[str, object] = {
        "review": review,
        "verifier": _reviewer(),
        "registration": registration,
        "registration_verifier": _registration_signer(),
        "imported_outcomes": imported,
        "outcome_adapter_verifier": _outcome_signer(),
        "tenant_id": TENANT_ID,
        "campaign_id": CAMPAIGN_ID,
        "now": datetime(2026, 8, 14, 13, tzinfo=UTC),
    }
    data.update(over)
    return verify_learning_evaluation_review(**data)


def test_issued_review_binds_exact_human_and_signed_sources() -> None:
    review, registration, imported = _issued()
    verified = _verify(review, registration, imported)
    assert verified is review.evaluation
    assert review.registration_digest == registration.canonical_digest
    assert review.imported_outcome_digest != "0" * 64


def test_tampering_or_wrong_secret_is_rejected() -> None:
    review, registration, imported = _issued()
    with pytest.raises(LearningEvaluationAuthorityError, match="signature"):
        _verify(replace(review, signature="0" * 64), registration, imported)
    with pytest.raises(LearningEvaluationAuthorityError, match="signature"):
        _verify(review, registration, imported, verifier=_reviewer(secret=b"z" * 32))


def test_reviewer_scope_ttl_and_source_digests_are_fail_closed() -> None:
    review, registration, imported = _issued()
    with pytest.raises(LearningEvaluationAuthorityError, match="tenant or campaign"):
        _verify(review, registration, imported, campaign_id="campaign_other")
    with pytest.raises(LearningEvaluationAuthorityError, match="expired"):
        _verify(review, registration, imported, now=datetime(2026, 8, 14, 14, tzinfo=UTC))
    with pytest.raises(LearningEvaluationAuthorityError, match="reviewer_id"):
        _issued(reviewer_id="human_other")
    with pytest.raises(LearningEvaluationAuthorityError, match="24 hours"):
        _issued(expires_at="2026-08-15T12:00:01Z")
    forged = replace(review, registration_digest="0" * 64, signature="0" * 64)
    forged = replace(forged, signature=_reviewer().sign(forged.signing_bytes))
    with pytest.raises(LearningEvaluationAuthorityError, match="registration digest"):
        _verify(forged, registration, imported)


def test_missing_outcome_cannot_be_reviewed_or_used() -> None:
    registration, imported, evaluation = _sources()
    missing = replace(imported, outcomes=imported.outcomes[:-1])
    with pytest.raises(LearningRegistrationError, match=r"signature|cover"):
        issue_learning_evaluation_review(
            _reviewer(),
            review_id="review_01",
            tenant_id=TENANT_ID,
            campaign_id=CAMPAIGN_ID,
            registration=registration,
            registration_verifier=_registration_signer(),
            imported_outcomes=missing,
            outcome_adapter_verifier=_outcome_signer(),
            evaluation=evaluation,
            reviewer_id="reviewer_01",
            issued_at=REVIEW_NOW,
            expires_at="2026-08-14T14:00:00Z",
        )
