from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest
from test_editorial_context_authority import KEY as CONTEXT_KEY
from test_editorial_context_authority import NOW as CONTEXT_NOW
from test_editorial_context_authority import _issued
from test_editorial_director_v22 import CAMPAIGN_ID as EDITORIAL_CAMPAIGN_ID
from test_editorial_director_v22 import SOURCE_ID as EDITORIAL_SOURCE_ID
from test_editorial_director_v22 import _payload

from app.pipeline.decision_outcomes import (
    EditorialExperiment,
    EffectEstimate,
    LearningEvaluation,
    LearningHypothesis,
    OutcomeObservation,
    OutcomeStatPolicy,
    PromotionEligibility,
)
from app.pipeline.decision_provenance import (
    HmacSha256VariantAuthority,
    IssuedVariantProvenance,
    issue_variant_provenance,
    materialize_director_decision_provenance,
)
from app.pipeline.editorial_context_authority import verify_editorial_context_capability
from app.pipeline.learning_registration import (
    HmacSha256LearningRegistrationAuthority,
    HmacSha256OutcomeAdapter,
    LearningRegistrationError,
    import_registered_outcomes,
    issue_learning_registration,
)
from app.pipeline.learning_authority import (
    AUTHORITY_SCHEMA_VERSION,
    HmacSha256Authority,
    LearningAuthorityError,
    PromotionAuthorityEnvelope,
    issue_promotion_authority,
    verified_promotion_eligibility,
    verify_promotion_authority,
)
from app.pipeline.learning_evaluation_authority import (
    HmacSha256LearningEvaluationAuthority,
    IssuedLearningEvaluationReview,
    LearningEvaluationAuthorityError,
    issue_learning_evaluation_review,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
DIGEST_D = "d" * 64
CAMPAIGN_ID = EDITORIAL_CAMPAIGN_ID
TENANT_ID = "tenant_01"
NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
REGISTRATION_NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
IMPORT_NOW = datetime(2026, 8, 13, 9, tzinfo=UTC)
POLICY_EXPIRY = "2026-08-15T12:00:00Z"


def _signer(*, secret: bytes = b"x" * 32, key_id: str = "local_hmac_01") -> HmacSha256Authority:
    return HmacSha256Authority(key_id=key_id, secret=secret)


def _hypothesis(**over: object) -> LearningHypothesis:
    data: dict[str, object] = {
        "hypothesis_id": "hyp_completion",
        "target_metric": "completion_rate",
        "direction": "increase",
        "comparison": "matched_variant",
        "scope": {"campaign_id": CAMPAIGN_ID, "paid": True},
        "owner": "owner_01",
        "support": (DIGEST_A,),
        "counterexample": (DIGEST_B,),
        "created_at": "2026-08-09T08:00:00Z",
        "expires_at": "2026-08-20T08:00:00Z",
    }
    data.update(over)
    return LearningHypothesis(**data)  # type: ignore[arg-type]


def _experiment(experiment_id: str, source_digest: str) -> EditorialExperiment:
    variants = (f"{experiment_id}_control", f"{experiment_id}_treatment")
    return EditorialExperiment(
        experiment_id=experiment_id,
        campaign_id=CAMPAIGN_ID,
        source_asset_digest=source_digest,
        objective="Improve completion rate without changing claims.",
        primary_metric="completion_rate",
        variants=variants,
        platform="youtube_shorts",
        account_id="account_01",
        cohort="uk-b2b-founders",
        posting_window_start="2026-08-10T08:00:00Z",
        posting_window_end="2026-08-12T08:00:00Z",
        paid=True,
        assignment={variants[0]: "control", variants[1]: "treatment"},
        registered_at="2026-08-09T09:00:00Z",
    )


def _outcome(experiment_id: str, arm: str, **over: object) -> OutcomeObservation:
    data: dict[str, object] = {
        "outcome_id": f"outcome_{experiment_id}_{arm}",
        "experiment_id": experiment_id,
        "variant_id": f"{experiment_id}_{arm}",
        "source_digest": DIGEST_A,
        "metric_name": "completion_rate",
        "observed_at": "2026-08-13T08:00:00Z",
        "window_start": "2026-08-10T08:00:00Z",
        "window_end": "2026-08-12T08:00:00Z",
        "platform": "youtube_shorts",
        "account_id": "account_01",
        "trust": "verified",
        "numerator": 50 if arm == "control" else 70,
        "denominator": 100,
        "delivery_mode": "paid",
        "qc_guardrail": "pass",
        "claim_guardrail": "pass",
    }
    data.update(over)
    return OutcomeObservation(**data)  # type: ignore[arg-type]


def _variant_signer() -> HmacSha256VariantAuthority:
    return HmacSha256VariantAuthority("variant_authority_01", b"v" * 32)


def _registration_signer() -> HmacSha256LearningRegistrationAuthority:
    return HmacSha256LearningRegistrationAuthority(
        key_id="registration_authority_01",
        secret=b"r" * 32,
    )


def _outcome_signer() -> HmacSha256OutcomeAdapter:
    return HmacSha256OutcomeAdapter(key_id="outcome_adapter_01", secret=b"o" * 32)


def _review_signer(
    *, secret: bytes = b"h" * 32, key_id: str = "human_review_01"
) -> HmacSha256LearningEvaluationAuthority:
    return HmacSha256LearningEvaluationAuthority(key_id=key_id, secret=secret)


def _provenance(variant_id: str) -> IssuedVariantProvenance:
    """Build a signed render-time envelope; Python tokens are not authority."""
    issued, snapshot, context, graph = _issued()
    verified = verify_editorial_context_capability(
        issued,
        snapshot,
        context,
        graph,
        verifier=CONTEXT_KEY,
        now=CONTEXT_NOW,
        expected_owner_id="owner_01",
        expected_campaign_id=CAMPAIGN_ID,
        expected_source_id=EDITORIAL_SOURCE_ID,
    )
    plan = verified.parse(_payload(), now=CONTEXT_NOW)
    bundle = materialize_director_decision_provenance(
        plan,
        verified=verified,
        now=CONTEXT_NOW,
        variant_id=variant_id,
        created_at=CONTEXT_NOW,
    )
    return issue_variant_provenance(
        _variant_signer(),
        bundle,
        plan,
        issued_context=issued,
        snapshot=snapshot,
        context=context,
        graph=graph,
        context_verifier=CONTEXT_KEY,
        expected_owner_id="owner_01",
        expected_campaign_id=CAMPAIGN_ID,
        expected_source_id=EDITORIAL_SOURCE_ID,
        now=CONTEXT_NOW,
        authority_id=f"authority_{variant_id}",
        expires_at="2026-08-10T12:00:00Z",
        render_artifact_digest="e" * 64,
        created_at=CONTEXT_NOW,
    )


def _inputs() -> tuple[
    LearningHypothesis,
    LearningEvaluation,
    tuple[EditorialExperiment, ...],
    tuple[OutcomeObservation, ...],
]:
    experiments = (_experiment("exp_one", DIGEST_C), _experiment("exp_two", DIGEST_D))
    outcomes = tuple(
        _outcome(experiment_id, arm)
        for experiment_id in ("exp_one", "exp_two")
        for arm in ("control", "treatment")
    )
    evaluation = LearningEvaluation(
        hypothesis_id="hyp_completion",
        experiment_ids=("exp_one", "exp_two"),
        outcome_ids=tuple(item.outcome_id for item in outcomes),
        effect=EffectEstimate("completion_rate", 0.7, 0.5, 0.4),
        confounders=(),
        verdict="supported",
        reviewer="reviewer_01",
        evaluated_at="2026-08-13T09:00:00Z",
    )
    return _hypothesis(), evaluation, experiments, outcomes


def _bound_inputs() -> tuple[
    LearningHypothesis,
    LearningEvaluation,
    tuple[EditorialExperiment, ...],
    tuple[OutcomeObservation, ...],
    tuple[IssuedVariantProvenance, ...],
]:
    hypothesis, evaluation, experiments, outcomes = _inputs()
    provenances = tuple(
        _provenance(variant)
        for experiment_id in ("exp_one", "exp_two")
        for variant in (f"{experiment_id}_control", f"{experiment_id}_treatment")
    )
    by_variant = {item.provenance.variant_id: item.provenance for item in provenances}
    bound_experiments = tuple(
        replace(
            item,
            variant_provenance_digests={
                variant: by_variant[variant].canonical_digest for variant in item.variants
            },
        )
        for item in experiments
    )
    bound_outcomes = tuple(
        replace(item, variant_provenance_digest=by_variant[item.variant_id].canonical_digest)
        for item in outcomes
    )
    return hypothesis, evaluation, bound_experiments, bound_outcomes, provenances


def _stat_policy(**over: object) -> OutcomeStatPolicy:
    data: dict[str, object] = {
        "schema_version": "1.0",
        "policy_version": "learning-1.0",
        "expires_at": POLICY_EXPIRY,
        "min_denominator_per_arm": 100,
        "min_independent_experiments": 2,
        "min_absolute_lift": 0.1,
        "interval_method": "newcombe_wilson_95",
        "preregistered_metrics": ("completion_rate",),
    }
    data.update(over)
    return OutcomeStatPolicy(**data)  # type: ignore[arg-type]


def _evaluation_review(
    evaluation: LearningEvaluation,
    registration: object,
    imported: object,
    **over: object,
) -> IssuedLearningEvaluationReview:
    data: dict[str, object] = {
        "signer": _review_signer(),
        "review_id": "review_01",
        "tenant_id": TENANT_ID,
        "campaign_id": CAMPAIGN_ID,
        "registration": registration,
        "registration_verifier": _registration_signer(),
        "imported_outcomes": imported,
        "outcome_adapter_verifier": _outcome_signer(),
        "evaluation": evaluation,
        "reviewer_id": evaluation.reviewer,
        "issued_at": NOW,
        "expires_at": "2026-08-14T14:00:00Z",
    }
    data.update(over)
    return issue_learning_evaluation_review(**data)  # type: ignore[arg-type]


def _promotion_sources() -> tuple[
    LearningEvaluation,
    object,
    object,
    IssuedLearningEvaluationReview,
]:
    """Build the exact signed preregistration, import, and human review."""
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
        import_id="outcome_import_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        outcomes=outcomes,
        now=IMPORT_NOW,
    )
    return evaluation, registration, imported, _evaluation_review(evaluation, registration, imported)


def _envelope(**over: object) -> PromotionAuthorityEnvelope:
    hypothesis, evaluation, experiments, outcomes, provenances = _bound_inputs()
    hypothesis = over.pop("hypothesis", hypothesis)  # type: ignore[assignment]
    evaluation = over.pop("evaluation", evaluation)  # type: ignore[assignment]
    experiments = over.pop("experiments", experiments)  # type: ignore[assignment]
    outcomes = over.pop("outcomes", outcomes)  # type: ignore[assignment]
    provenances = over.pop("issued_variant_provenances", provenances)  # type: ignore[assignment]
    policy = over.pop("outcome_stat_policy", _stat_policy())
    policy_version = over.pop("policy_version", None)
    policy_expiry = over.pop("policy_expires_at", None)
    if policy_version is not None or policy_expiry is not None:
        policy = replace(
            policy,
            policy_version=policy_version or policy.policy_version,
            expires_at=policy_expiry or policy.expires_at,
        )
    human_reviewer = over.pop("human_reviewer", None)
    if human_reviewer is not None:
        evaluation = replace(evaluation, reviewer=human_reviewer)
    registration = issue_learning_registration(
        _registration_signer(),
        registration_id="registration_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        hypothesis=hypothesis,
        experiments=experiments,
        outcome_stat_policy=policy,
        issued_variant_provenances=provenances,
        variant_provenance_verifier=_variant_signer(),
        variant_owner_id="owner_01",
        now=REGISTRATION_NOW,
    )
    imported = import_registered_outcomes(
        _outcome_signer(),
        registration,
        _registration_signer(),
        import_id="outcome_import_01",
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        outcomes=outcomes,
        now=IMPORT_NOW,
    )
    evaluation_review = over.pop("evaluation_review", None)
    if evaluation_review is None:
        evaluation_review = _evaluation_review(evaluation, registration, imported)
    data: dict[str, object] = {
        "signer": _signer(),
        "authority_id": "authority_01",
        "tenant_id": TENANT_ID,
        "campaign_id": CAMPAIGN_ID,
        "evaluation_review": evaluation_review,
        "evaluation_review_verifier": _review_signer(),
        "registration": registration,
        "registration_verifier": _registration_signer(),
        "imported_outcomes": imported,
        "outcome_adapter_verifier": _outcome_signer(),
        "variant_provenance_verifier": _variant_signer(),
        "variant_owner_id": "owner_01",
        "issued_at": NOW,
        "expires_at": "2026-08-14T14:00:00Z",
    }
    data.update(over)
    return issue_promotion_authority(**data)  # type: ignore[arg-type]


def _verify(envelope: PromotionAuthorityEnvelope, **over: object) -> PromotionAuthorityEnvelope:
    data: dict[str, object] = {
        "envelope": envelope,
        "verifier": _signer(),
        "tenant_id": TENANT_ID,
        "campaign_id": CAMPAIGN_ID,
        "now": datetime(2026, 8, 14, 13, tzinfo=UTC),
    }
    data.update(over)
    return verify_promotion_authority(**data)  # type: ignore[arg-type]


def test_issue_and_verify_recomputes_an_eligible_promotion() -> None:
    envelope = _envelope()
    verified = _verify(envelope)
    assert verified is envelope
    assert envelope.eligibility.eligible is True
    assert envelope.schema_version == AUTHORITY_SCHEMA_VERSION


def test_legacy_outcomes_can_be_diagnosed_but_never_signed_for_promotion() -> None:
    hypothesis, evaluation, experiments, outcomes = _inputs()
    with pytest.raises(LearningRegistrationError, match="nonempty"):
        _envelope(
            hypothesis=hypothesis,
            evaluation=evaluation,
            experiments=experiments,
            outcomes=outcomes,
            issued_variant_provenances=(),
        )


def test_public_raw_provenance_dataclasses_can_never_be_signed() -> None:
    hypothesis, evaluation, experiments, outcomes, capabilities = _bound_inputs()
    with pytest.raises(LearningRegistrationError, match="signed envelopes"):
        _envelope(
            hypothesis=hypothesis,
            evaluation=evaluation,
            experiments=experiments,
            outcomes=outcomes,
            issued_variant_provenances=tuple(item.provenance for item in capabilities),
        )


def test_adapter_only_returns_promotion_after_verification() -> None:
    eligibility = verified_promotion_eligibility(
        _envelope(),
        _signer(),
        tenant_id=TENANT_ID,
        campaign_id=CAMPAIGN_ID,
        now=datetime(2026, 8, 14, 13, tzinfo=UTC),
    )
    assert isinstance(eligibility, PromotionEligibility)
    assert eligibility.policy_version == "learning-1.0"


def test_hmac_requires_a_32_byte_secret_and_never_serializes_it() -> None:
    with pytest.raises(LearningAuthorityError, match="32 bytes"):
        _signer(secret=b"too-short")
    serialized = _envelope().to_dict()
    assert "secret" not in serialized
    assert b"x" * 32 not in repr(serialized).encode()


def test_envelope_and_artifacts_are_immutable() -> None:
    envelope = _envelope()
    with pytest.raises(FrozenInstanceError):
        envelope.tenant_id = "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        envelope.hypothesis.owner = "other"  # type: ignore[misc]


def test_signature_rejects_tenant_campaign_and_key_mismatches() -> None:
    envelope = _envelope()
    with pytest.raises(LearningAuthorityError, match="tenant"):
        _verify(envelope, tenant_id="tenant_02")
    with pytest.raises(LearningAuthorityError, match="campaign"):
        _verify(envelope, campaign_id="campaign_02")
    with pytest.raises(LearningAuthorityError, match="key_id"):
        _verify(envelope, verifier=_signer(key_id="other_key"))
    with pytest.raises(LearningAuthorityError, match="signature"):
        _verify(envelope, verifier=_signer(secret=b"y" * 32))


def test_signature_rejects_modified_artifact_and_eligibility() -> None:
    envelope = _envelope()
    changed_hypothesis = _hypothesis(owner="owner_02")
    changed = replace(envelope, hypothesis=changed_hypothesis)
    with pytest.raises(LearningAuthorityError, match="signature"):
        _verify(changed)
    fabricated = PromotionEligibility(
        eligible=True,
        verdict="supported",
        reasons=(),
        policy_version="learning-1.0",
        policy_expires_at=POLICY_EXPIRY,
        human_reviewer="reviewer_02",
        outcome_stat_policy_digest=envelope.outcome_stat_policy_digest,
    )
    changed_eligibility = replace(envelope, eligibility=fabricated)
    with pytest.raises(LearningAuthorityError, match="signature"):
        _verify(changed_eligibility)


def test_authority_rejects_reordered_duplicate_or_missing_artifacts() -> None:
    hypothesis, evaluation, experiments, outcomes = _inputs()
    with pytest.raises(LearningRegistrationError, match="canonical"):
        _envelope(experiments=tuple(reversed(experiments)))
    with pytest.raises(LearningRegistrationError, match="canonical"):
        _envelope(outcomes=(*outcomes, outcomes[-1]))
    with pytest.raises(LearningRegistrationError, match="exactly cover"):
        _envelope(outcomes=outcomes[:-1])
    assert hypothesis.hypothesis_id == evaluation.hypothesis_id


def test_authority_hard_caps_artifact_counts_before_gate_evaluation() -> None:
    _, _, experiments, outcomes = _inputs()
    with pytest.raises(LearningRegistrationError, match="hard"):
        _envelope(experiments=experiments * 17)
    with pytest.raises(LearningRegistrationError, match="hard"):
        _envelope(outcomes=outcomes * 17)


def test_authority_requires_full_scope_bound_artifacts() -> None:
    hypothesis, evaluation, experiments, outcomes = _inputs()
    bad_experiment = replace(experiments[0], campaign_id="campaign_02")
    with pytest.raises(LearningRegistrationError, match="campaign"):
        _envelope(experiments=(bad_experiment, experiments[1]))
    bad_evaluation = replace(evaluation, hypothesis_id="other_hypothesis")
    with pytest.raises(LearningEvaluationAuthorityError, match="registered hypothesis"):
        _envelope(evaluation=bad_evaluation)
    assert outcomes
    assert hypothesis.scope["campaign_id"] == CAMPAIGN_ID


def test_authority_rejects_expired_policy_at_issue() -> None:
    with pytest.raises(LearningAuthorityError, match="ineligible"):
        _envelope(policy_expires_at="2026-08-13T00:00:00Z")


def test_ttl_is_hard_capped_and_cannot_outlive_policy() -> None:
    with pytest.raises(LearningAuthorityError, match="24 hours"):
        _envelope(expires_at="2026-08-15T12:00:01Z")
    with pytest.raises(LearningAuthorityError, match="outlive"):
        _envelope(
            policy_expires_at="2026-08-14T13:00:00Z",
            outcome_stat_policy=_stat_policy(expires_at="2026-08-14T13:00:00Z"),
            expires_at="2026-08-14T14:00:00Z",
        )


def test_verification_rejects_not_yet_issued_or_expired_authority() -> None:
    envelope = _envelope()
    with pytest.raises(LearningAuthorityError, match="issuance"):
        _verify(envelope, now=datetime(2026, 8, 14, 11, 59, tzinfo=UTC))
    with pytest.raises(LearningAuthorityError, match="expired"):
        _verify(envelope, now=datetime(2026, 8, 14, 14, tzinfo=UTC))


def test_valid_signature_is_not_enough_when_signed_gate_inputs_are_incoherent() -> None:
    envelope = _envelope()
    incoherent = replace(
        envelope,
        eligibility=PromotionEligibility(
            eligible=True,
            verdict="supported",
            reasons=(),
            policy_version="learning-1.0",
            policy_expires_at=POLICY_EXPIRY,
            human_reviewer="reviewer_02",
            outcome_stat_policy_digest=envelope.outcome_stat_policy_digest,
        ),
    )
    forged = replace(incoherent, signature=_signer().sign(incoherent.signing_bytes))
    with pytest.raises(LearningAuthorityError, match="promotion gate"):
        _verify(forged)


def test_signature_covers_order_and_every_artifact_digest() -> None:
    envelope = _envelope()
    with pytest.raises(LearningAuthorityError, match="canonical identifier order"):
        replace(envelope, outcomes=tuple(reversed(envelope.outcomes)))
    altered_outcome = replace(envelope.outcomes[0], numerator=49)
    altered = replace(envelope, outcomes=(altered_outcome, *envelope.outcomes[1:]))
    with pytest.raises(LearningAuthorityError, match="signature"):
        _verify(altered)


def test_envelope_rejects_a_tampered_outcome_statistical_policy_digest() -> None:
    envelope = _envelope()
    with pytest.raises(LearningAuthorityError, match="outcome_stat_policy_digest"):
        replace(envelope, outcome_stat_policy_digest="0" * 64)

    changed_policy = _stat_policy(min_denominator_per_arm=101)
    with pytest.raises(LearningAuthorityError, match="outcome_stat_policy_digest"):
        replace(envelope, outcome_stat_policy=changed_policy)


def test_signed_authority_carries_the_exact_variant_provenance_chain() -> None:
    hypothesis, evaluation, experiments, outcomes, provenances = _bound_inputs()
    envelope = _envelope(
        hypothesis=hypothesis,
        evaluation=evaluation,
        experiments=experiments,
        outcomes=outcomes,
        issued_variant_provenances=provenances,
    )
    assert _verify(envelope) is envelope
    assert [item.variant_id for item in envelope.variant_provenances] == [
        "exp_one_control",
        "exp_one_treatment",
        "exp_two_control",
        "exp_two_treatment",
    ]

    with pytest.raises(LearningAuthorityError, match="canonical identifier order"):
        replace(envelope, variant_provenances=tuple(reversed(envelope.variant_provenances)))

    tampered = replace(
        envelope,
        variant_provenances=(
            replace(envelope.variant_provenances[0], source_id="other_source"),
            *envelope.variant_provenances[1:],
        ),
    )
    with pytest.raises(LearningAuthorityError, match="signature"):
        _verify(tampered)

    with pytest.raises(LearningRegistrationError, match="exactly cover"):
        _envelope(
            hypothesis=hypothesis,
            evaluation=evaluation,
            experiments=experiments,
            outcomes=outcomes,
            issued_variant_provenances=provenances[:-1],
        )
    with pytest.raises(LearningRegistrationError, match="exactly"):
        _envelope(
            hypothesis=hypothesis,
            evaluation=evaluation,
            experiments=experiments,
            outcomes=outcomes,
            issued_variant_provenances=(
                *provenances,
                _provenance("variant_extra"),
            ),
        )


def test_envelope_rejects_a_non_eligible_public_dataclass() -> None:
    envelope = _envelope()
    ineligible = PromotionEligibility(
        eligible=False,
        verdict="rejected",
        reasons=("external claim",),
        policy_version="learning-1.0",
        policy_expires_at=POLICY_EXPIRY,
        human_reviewer="reviewer_01",
        outcome_stat_policy_digest=envelope.outcome_stat_policy_digest,
    )
    signed = replace(envelope, eligibility=ineligible)
    signed = replace(signed, signature=_signer().sign(signed.signing_bytes))
    with pytest.raises(LearningAuthorityError, match="promotion gate"):
        _verify(signed)


def test_promotion_requires_a_signed_human_review_not_a_public_evaluation() -> None:
    evaluation, registration, imported, review = _promotion_sources()
    with pytest.raises(TypeError, match="unexpected keyword argument 'evaluation'"):
        issue_promotion_authority(
            _signer(),
            authority_id="authority_01",
            tenant_id=TENANT_ID,
            campaign_id=CAMPAIGN_ID,
            evaluation_review=review,
            evaluation_review_verifier=_review_signer(),
            registration=registration,  # type: ignore[arg-type]
            registration_verifier=_registration_signer(),
            imported_outcomes=imported,  # type: ignore[arg-type]
            outcome_adapter_verifier=_outcome_signer(),
            variant_provenance_verifier=_variant_signer(),
            variant_owner_id="owner_01",
            issued_at=NOW,
            expires_at="2026-08-14T14:00:00Z",
            evaluation=evaluation,
        )


def test_promotion_fails_closed_on_tampered_wrong_key_or_wrong_reviewer_review() -> None:
    _, _, _, review = _promotion_sources()
    with pytest.raises(LearningAuthorityError, match="evaluation review verification"):
        _envelope(evaluation_review=replace(review, signature="0" * 64))
    with pytest.raises(LearningAuthorityError, match="evaluation review verification"):
        _envelope(
            evaluation_review=review,
            evaluation_review_verifier=_review_signer(secret=b"z" * 32),
        )
    wrong_reviewer = replace(review, reviewer_id="reviewer_02")
    wrong_reviewer = replace(
        wrong_reviewer,
        signature=_review_signer().sign(wrong_reviewer.signing_bytes),
    )
    with pytest.raises(LearningAuthorityError, match="evaluation review verification"):
        _envelope(evaluation_review=wrong_reviewer)


def test_promotion_signature_binds_the_human_review_digest_for_audit() -> None:
    envelope = _envelope()
    assert envelope.to_dict()["evaluation_review_digest"] == envelope.evaluation_review_digest
    with pytest.raises(LearningAuthorityError, match="signature"):
        _verify(replace(envelope, evaluation_review_digest="0" * 64))
