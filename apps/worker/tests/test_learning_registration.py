from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from test_learning_authority import (
    CAMPAIGN_ID,
    POLICY_EXPIRY,
    TENANT_ID,
    _bound_inputs,
    _provenance,
    _evaluation_review,
    _review_signer,
    _stat_policy,
    _variant_signer,
)

from app.pipeline.learning_authority import (
    HmacSha256Authority,
    issue_promotion_authority,
    verify_promotion_authority,
)
from app.pipeline.learning_registration import (
    MAX_IMPORTED_OUTCOMES,
    MAX_REGISTERED_EXPERIMENTS,
    HmacSha256LearningRegistrationAuthority,
    HmacSha256OutcomeAdapter,
    LearningRegistrationError,
    import_registered_outcomes,
    issue_learning_registration,
    verify_imported_outcomes,
    verify_learning_registration,
)

REGISTRATION_NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
IMPORT_NOW = datetime(2026, 8, 13, 9, tzinfo=UTC)


def _registration():
    hypothesis, _, experiments, _, provenances = _bound_inputs()
    return issue_learning_registration(
        HmacSha256LearningRegistrationAuthority(key_id="registration_01", secret=b"r" * 32),
        registration_id="registration_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        hypothesis=hypothesis,
        experiments=experiments,
        outcome_stat_policy=_stat_policy(expires_at=POLICY_EXPIRY),
        issued_variant_provenances=provenances,
        variant_provenance_verifier=_variant_signer(),
        variant_owner_id="owner_01",
        now=REGISTRATION_NOW,
    )


def _registration_key():
    return HmacSha256LearningRegistrationAuthority(key_id="registration_01", secret=b"r" * 32)


def _issue_registration(
    *,
    signer: HmacSha256LearningRegistrationAuthority | None = None,
    provenances: tuple | None = None,
    now: datetime = REGISTRATION_NOW,
):
    hypothesis, _, experiments, _, default_provenances = _bound_inputs()
    return issue_learning_registration(
        signer or _registration_key(),
        registration_id="registration_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        hypothesis=hypothesis,
        experiments=experiments,
        outcome_stat_policy=_stat_policy(expires_at=POLICY_EXPIRY),
        issued_variant_provenances=provenances or default_provenances,
        variant_provenance_verifier=_variant_signer(),
        variant_owner_id="owner_01",
        now=now,
    )


def test_registration_server_stamps_hypothesis_and_experiments_and_binds_variants() -> None:
    registration = _registration()
    assert registration.hypothesis.created_at == "2026-08-09T12:00:00Z"
    assert all(item.registered_at == "2026-08-09T12:00:00Z" for item in registration.experiments)
    assert all(item.variant_provenance_digests for item in registration.experiments)
    assert (
        verify_learning_registration(
            registration, _registration_key(), tenant_id=TENANT_ID, campaign_id=CAMPAIGN_ID
        )
        is registration
    )


def test_import_is_adapter_signed_server_stamped_and_exactly_bound() -> None:
    registration = _registration()
    _, _, _, outcomes, _ = _bound_inputs()
    adapter = HmacSha256OutcomeAdapter(key_id="youtube_adapter_01", secret=b"a" * 32)
    imported = import_registered_outcomes(
        adapter,
        registration,
        _registration_key(),
        import_id="import_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        outcomes=outcomes,
        now=IMPORT_NOW,
    )
    assert {item.observed_at for item in imported.outcomes} == {"2026-08-13T09:00:00Z"}
    assert {item.trust for item in imported.outcomes} == {"verified"}
    assert (
        verify_imported_outcomes(
            imported,
            adapter,
            registration,
            _registration_key(),
            tenant_id=TENANT_ID,
            campaign_id=CAMPAIGN_ID,
        )
        == imported.outcomes
    )


def test_tampered_registration_or_unregistered_window_is_rejected() -> None:
    registration = _registration()
    with pytest.raises(LearningRegistrationError, match="signature"):
        verify_learning_registration(
            replace(registration, signature="0" * 64),
            _registration_key(),
            tenant_id=TENANT_ID,
            campaign_id=CAMPAIGN_ID,
        )


def test_key_ids_are_typed_separately_from_opaque_ids() -> None:
    registration_key = HmacSha256LearningRegistrationAuthority(
        key_id="registration.v1", secret=b"r" * 32
    )
    registration = _issue_registration(signer=registration_key)
    adapter = HmacSha256OutcomeAdapter(key_id="youtube.adapter.v1", secret=b"a" * 32)
    _, _, _, outcomes, _ = _bound_inputs()
    imported = import_registered_outcomes(
        adapter,
        registration,
        registration_key,
        import_id="import_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        outcomes=outcomes,
        now=IMPORT_NOW,
    )
    assert registration.key_id == "registration.v1"
    assert imported.adapter_key_id == "youtube.adapter.v1"
    assert (
        verify_imported_outcomes(
            imported,
            adapter,
            registration,
            registration_key,
            tenant_id=TENANT_ID,
            campaign_id=CAMPAIGN_ID,
        )
        == imported.outcomes
    )


def test_registration_requires_exact_signed_variant_cover_and_strict_preregistration() -> None:
    _, _, _, _, provenances = _bound_inputs()
    with pytest.raises(LearningRegistrationError, match="exactly cover"):
        _issue_registration(provenances=(*provenances, _provenance("unused_variant")))

    with pytest.raises(LearningRegistrationError, match="strictly predate"):
        _issue_registration(now=datetime(2026, 8, 10, 8, tzinfo=UTC))

    with pytest.raises(LearningRegistrationError, match="provenance verification"):
        _issue_registration(now=datetime(2026, 8, 10, 12, tzinfo=UTC))


def test_registration_and_import_enforce_canonical_order_scope_and_hard_caps() -> None:
    registration = _registration()
    with pytest.raises(LearningRegistrationError, match="canonical IDs"):
        replace(registration, experiments=tuple(reversed(registration.experiments)))
    with pytest.raises(LearningRegistrationError, match="hard cap"):
        replace(
            registration,
            experiments=(registration.experiments[0],) * (MAX_REGISTERED_EXPERIMENTS + 1),
        )
    with pytest.raises(LearningRegistrationError, match="tenant or campaign"):
        verify_learning_registration(
            registration,
            _registration_key(),
            tenant_id="tenant_02",
            campaign_id=CAMPAIGN_ID,
        )

    _, _, _, outcomes, _ = _bound_inputs()
    adapter = HmacSha256OutcomeAdapter(key_id="youtube_adapter_01", secret=b"a" * 32)
    imported = import_registered_outcomes(
        adapter,
        registration,
        _registration_key(),
        import_id="import_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        outcomes=outcomes,
        now=IMPORT_NOW,
    )
    with pytest.raises(LearningRegistrationError, match="canonical IDs"):
        replace(imported, outcomes=tuple(reversed(imported.outcomes)))
    with pytest.raises(LearningRegistrationError, match="hard cap"):
        replace(imported, outcomes=(imported.outcomes[0],) * (MAX_IMPORTED_OUTCOMES + 1))
    with pytest.raises(LearningRegistrationError, match="signature"):
        verify_imported_outcomes(
            replace(imported, signature="0" * 64),
            adapter,
            registration,
            _registration_key(),
            tenant_id=TENANT_ID,
            campaign_id=CAMPAIGN_ID,
        )


def test_import_cannot_server_stamp_outcomes_before_the_registered_window_ends() -> None:
    registration = _registration()
    _, _, _, outcomes, _ = _bound_inputs()
    with pytest.raises(LearningRegistrationError, match="cannot be server-stamped"):
        import_registered_outcomes(
            HmacSha256OutcomeAdapter(key_id="youtube_adapter_01", secret=b"a" * 32),
            registration,
            _registration_key(),
            import_id="import_01",
            tenant_id=TENANT_ID,
            campaign_id=CAMPAIGN_ID,
            outcomes=outcomes,
            now=datetime(2026, 8, 11, 9, tzinfo=UTC),
        )


def test_promotion_accepts_only_the_verified_registration_and_adapter_import() -> None:
    registration = _registration()
    _, evaluation, _, outcomes, _ = _bound_inputs()
    adapter = HmacSha256OutcomeAdapter(key_id="youtube_adapter_01", secret=b"a" * 32)
    imported = import_registered_outcomes(
        adapter,
        registration,
        _registration_key(),
        import_id="import_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        outcomes=outcomes,
        now=IMPORT_NOW,
    )
    authority = HmacSha256Authority(key_id="learning_authority_01", secret=b"p" * 32)
    envelope = issue_promotion_authority(
        authority,
        authority_id="promotion_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        evaluation_review=_evaluation_review(
            evaluation,
            registration,
            imported,
            registration_verifier=_registration_key(),
            outcome_adapter_verifier=adapter,
        ),
        evaluation_review_verifier=_review_signer(),
        issued_at=datetime(2026, 8, 14, 12, tzinfo=UTC),
        expires_at="2026-08-14T14:00:00Z",
        registration=registration,
        registration_verifier=_registration_key(),
        imported_outcomes=imported,
        outcome_adapter_verifier=adapter,
        variant_provenance_verifier=_variant_signer(),
        variant_owner_id="owner_01",
    )
    assert (
        verify_promotion_authority(
            envelope,
            authority,
            tenant_id=TENANT_ID,
            campaign_id=CAMPAIGN_ID,
            now=datetime(2026, 8, 14, 13, tzinfo=UTC),
        )
        is envelope
    )
    _, _, _, outcomes, _ = _bound_inputs()
    with pytest.raises(LearningRegistrationError, match="exactly match"):
        import_registered_outcomes(
            HmacSha256OutcomeAdapter(key_id="youtube_adapter_01", secret=b"a" * 32),
            registration,
            _registration_key(),
            import_id="import_01",
            tenant_id=TENANT_ID,
            campaign_id=CAMPAIGN_ID,
            outcomes=(replace(outcomes[0], window_end="2026-08-12T07:00:00Z"), *outcomes[1:]),
            now=IMPORT_NOW,
        )
