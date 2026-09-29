from dataclasses import replace
from datetime import UTC, datetime

import pytest
from test_editorial_director_v22 import CAMPAIGN_ID as EDITORIAL_CAMPAIGN_ID
from test_learning_authority import (
    _evaluation_review,
    _provenance,
    _review_signer,
    _variant_signer,
)

from app.pipeline.decision_outcomes import (
    EditorialExperiment,
    EffectEstimate,
    LearningEvaluation,
    LearningHypothesis,
    OutcomeObservation,
    OutcomeStatPolicy,
    PromotionEligibility,
)
from app.pipeline.knowledge_governance import (
    GOVERNANCE_SCHEMA_VERSION,
    GovernanceTransitionRequest,
    KnowledgeGovernanceError,
    KnowledgeGovernanceState,
    KnowledgeVersionRef,
    apply_governance_transition,
    deprecate_governance_state,
    supersede_governance_state,
)
from app.pipeline.learning_authority import (
    HmacSha256Authority,
    PromotionAuthorityEnvelope,
    issue_promotion_authority,
)
from app.pipeline.learning_registration import (
    HmacSha256LearningRegistrationAuthority,
    HmacSha256OutcomeAdapter,
    import_registered_outcomes,
    issue_learning_registration,
)

OWNER = "reviewer_1"
CAMPAIGN = EDITORIAL_CAMPAIGN_ID
SOURCE = "018fbe6c-2fc6-7c6a-8a29-81d4a2ce3f0d"
T0 = "2026-08-09T10:00:00Z"
T1 = "2026-08-10T10:00:00Z"
T2 = "2026-08-11T10:00:00Z"
EXPIRY = "2026-09-01T10:00:00Z"
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
DIGEST_D = "d" * 64
TENANT = "tenant_01"
POLICY_EXPIRY = "2026-08-15T12:00:00Z"
AUTHORITY_NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
REGISTRATION_NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
OUTCOME_IMPORT_NOW = datetime(2026, 8, 13, 9, tzinfo=UTC)


def _state(
    kind: str = "raw_source",
    *,
    scope: str = "campaign",
    version: int = 1,
    created_at: str = T0,
    expires_at: str | None = None,
    review_state: str = "unreviewed",
    reviewed_by: str | None = None,
    evidence: tuple[str, ...] = (),
    counterexamples: tuple[str, ...] = (),
    evaluation: str | None = None,
    policy_version: str | None = None,
) -> KnowledgeGovernanceState:
    return KnowledgeGovernanceState(
        GOVERNANCE_SCHEMA_VERSION,
        KnowledgeVersionRef("campaign_learning", version),
        kind,  # type: ignore[arg-type]
        review_state,  # type: ignore[arg-type]
        reviewed_by,
        "active",
        scope,  # type: ignore[arg-type]
        OWNER,
        CAMPAIGN if scope != "global" else None,
        SOURCE if scope == "source" else None,
        evidence,
        counterexamples,
        evaluation,
        policy_version,
        created_at,
        expires_at,
    )


def _request(
    transition: str,
    *,
    evidence: tuple[str, ...] = (),
    counterexamples: tuple[str, ...] = (),
    expiry: str | None = None,
    policy_version: str | None = None,
) -> GovernanceTransitionRequest:
    return GovernanceTransitionRequest(
        f"request_{transition}",
        transition,
        OWNER,
        "Reviewed local governance transition.",
        evidence,
        counterexamples,
        expiry,
        policy_version,  # type: ignore[arg-type]
    )


def _evaluation(note_id: str = "campaign_learning", reviewer: str = OWNER) -> LearningEvaluation:
    return LearningEvaluation(
        note_id,
        ("experiment_a",),
        ("outcome_a",),
        EffectEstimate("retention", 0.2, 0.1, 1.0),
        (),
        "supported",
        reviewer,
        T1,
    )


def _authority_signer(*, secret: bytes = b"x" * 32) -> HmacSha256Authority:
    return HmacSha256Authority(key_id="governance_hmac_01", secret=secret)


def _registration_signer() -> HmacSha256LearningRegistrationAuthority:
    return HmacSha256LearningRegistrationAuthority(
        key_id="governance_registration_01", secret=b"r" * 32
    )


def _outcome_adapter() -> HmacSha256OutcomeAdapter:
    return HmacSha256OutcomeAdapter(key_id="governance_outcome_adapter_01", secret=b"o" * 32)


def _stat_policy() -> OutcomeStatPolicy:
    return OutcomeStatPolicy(
        schema_version="1.0",
        policy_version="learning-1.0",
        expires_at=POLICY_EXPIRY,
        min_denominator_per_arm=100,
        min_independent_experiments=2,
        min_absolute_lift=0.1,
        interval_method="newcombe_wilson_95",
        preregistered_metrics=("completion_rate",),
    )


def _policy_authority() -> (
    tuple[PromotionAuthorityEnvelope, HmacSha256Authority, LearningEvaluation]
):
    """Build an independently promotable, signed authority fixture."""

    experiments = tuple(
        EditorialExperiment(
            experiment_id=experiment_id,
            campaign_id=CAMPAIGN,
            source_asset_digest=source_digest,
            objective="Improve completion rate without changing claims.",
            primary_metric="completion_rate",
            variants=(f"{experiment_id}_control", f"{experiment_id}_treatment"),
            platform="youtube_shorts",
            account_id="account_01",
            cohort="uk-b2b-founders",
            posting_window_start="2026-08-10T08:00:00Z",
            posting_window_end="2026-08-12T08:00:00Z",
            paid=True,
            assignment={
                f"{experiment_id}_control": "control",
                f"{experiment_id}_treatment": "treatment",
            },
            registered_at="2026-08-09T09:00:00Z",
        )
        for experiment_id, source_digest in (
            ("experiment_one", DIGEST_C),
            ("experiment_two", DIGEST_D),
        )
    )
    provenances = tuple(
        _provenance(variant_id)
        for experiment_id in ("experiment_one", "experiment_two")
        for variant_id in (f"{experiment_id}_control", f"{experiment_id}_treatment")
    )
    provenance_by_variant = {item.provenance.variant_id: item.provenance for item in provenances}
    experiments = tuple(
        replace(
            item,
            variant_provenance_digests={
                variant_id: provenance_by_variant[variant_id].canonical_digest
                for variant_id in item.variants
            },
        )
        for item in experiments
    )
    outcomes = tuple(
        OutcomeObservation(
            outcome_id=f"outcome_{experiment.experiment_id}_{arm}",
            experiment_id=experiment.experiment_id,
            variant_id=f"{experiment.experiment_id}_{arm}",
            source_digest=DIGEST_A,
            metric_name="completion_rate",
            observed_at="2026-08-13T08:00:00Z",
            window_start="2026-08-10T08:00:00Z",
            window_end="2026-08-12T08:00:00Z",
            platform="youtube_shorts",
            account_id="account_01",
            trust="verified",
            numerator=50 if arm == "control" else 70,
            denominator=100,
            delivery_mode="paid",
            qc_guardrail="pass",
            claim_guardrail="pass",
        )
        for experiment in experiments
        for arm in ("control", "treatment")
    )
    outcomes = tuple(
        replace(
            item,
            variant_provenance_digest=provenance_by_variant[item.variant_id].canonical_digest,
        )
        for item in outcomes
    )
    evaluation = LearningEvaluation(
        hypothesis_id="campaign_learning",
        experiment_ids=tuple(item.experiment_id for item in experiments),
        outcome_ids=tuple(item.outcome_id for item in outcomes),
        effect=EffectEstimate("completion_rate", 0.7, 0.5, 0.4),
        confounders=(),
        verdict="supported",
        reviewer=OWNER,
        evaluated_at="2026-08-13T09:00:00Z",
    )
    hypothesis = LearningHypothesis(
        hypothesis_id="campaign_learning",
        target_metric="completion_rate",
        direction="increase",
        comparison="matched_variant",
        scope={"campaign_id": CAMPAIGN, "paid": True},
        owner=OWNER,
        support=(DIGEST_A,),
        counterexample=(DIGEST_B,),
        created_at="2026-08-09T08:00:00Z",
        expires_at="2026-08-20T08:00:00Z",
    )
    registration = issue_learning_registration(
        _registration_signer(),
        registration_id="governance_registration_01",
        tenant_id=TENANT,
        campaign_id=CAMPAIGN,
        hypothesis=hypothesis,
        experiments=experiments,
        outcome_stat_policy=_stat_policy(),
        issued_variant_provenances=provenances,
        variant_provenance_verifier=_variant_signer(),
        variant_owner_id="owner_01",
        now=REGISTRATION_NOW,
    )
    imported_outcomes = import_registered_outcomes(
        _outcome_adapter(),
        registration,
        _registration_signer(),
        import_id="governance_outcome_import_01",
        tenant_id=TENANT,
        campaign_id=CAMPAIGN,
        outcomes=outcomes,
        now=OUTCOME_IMPORT_NOW,
    )
    signer = _authority_signer()
    envelope = issue_promotion_authority(
        signer,
        authority_id="governance_authority_01",
        tenant_id=TENANT,
        campaign_id=CAMPAIGN,
        evaluation_review=_evaluation_review(
            evaluation,
            registration,
            imported_outcomes,
            registration_verifier=_registration_signer(),
            outcome_adapter_verifier=_outcome_adapter(),
        ),
        evaluation_review_verifier=_review_signer(),
        registration=registration,
        registration_verifier=_registration_signer(),
        imported_outcomes=imported_outcomes,
        outcome_adapter_verifier=_outcome_adapter(),
        variant_provenance_verifier=_variant_signer(),
        variant_owner_id="owner_01",
        issued_at=AUTHORITY_NOW,
        expires_at="2026-08-14T14:00:00Z",
    )
    return envelope, signer, evaluation


def _authority_bound_learning() -> (
    tuple[KnowledgeGovernanceState, PromotionAuthorityEnvelope, HmacSha256Authority]
):
    envelope, signer, evaluation = _policy_authority()
    learning = _state(
        "learning",
        version=4,
        created_at="2026-08-13T10:00:00Z",
        expires_at=POLICY_EXPIRY,
        review_state="approved",
        reviewed_by=OWNER,
        evidence=(DIGEST_A, DIGEST_B),
        counterexamples=(DIGEST_C,),
        evaluation=evaluation.canonical_digest,
    )
    return learning, envelope, signer


def _hypothesis() -> KnowledgeGovernanceState:
    observation = apply_governance_transition(
        _state(), _request("capture_observation"), occurred_at=T1
    ).current
    return apply_governance_transition(
        observation,
        _request(
            "propose_hypothesis", evidence=(DIGEST_A,), counterexamples=(DIGEST_B,), expiry=EXPIRY
        ),
        occurred_at=T2,
        reviewed_by=OWNER,
    ).current


def test_state_axes_require_human_identity_for_approved_review() -> None:
    with pytest.raises(KnowledgeGovernanceError, match="approved review requires"):
        _state(
            "hypothesis",
            expires_at=EXPIRY,
            review_state="approved",
            evidence=(DIGEST_A,),
            counterexamples=(DIGEST_B,),
        )


def test_raw_cannot_jump_directly_to_learning() -> None:
    with pytest.raises(KnowledgeGovernanceError, match="illegal transition"):
        apply_governance_transition(
            _state(), _request("validate_learning"), occurred_at=T1, reviewed_by=OWNER
        )


def test_hypothesis_requires_human_expiry_support_and_counterexample() -> None:
    observation = apply_governance_transition(
        _state(), _request("capture_observation"), occurred_at=T1
    ).current
    with pytest.raises(KnowledgeGovernanceError, match="hypothesis requires"):
        apply_governance_transition(
            observation, _request("propose_hypothesis"), occurred_at=T2, reviewed_by=OWNER
        )


def test_linear_raw_observation_hypothesis_transition() -> None:
    hypothesis = _hypothesis()
    assert hypothesis.epistemic_kind == "hypothesis"
    assert hypothesis.review_state == "approved"
    assert hypothesis.reviewed_by == OWNER
    assert hypothesis.note.version == 3


def test_non_policy_transitions_remain_authority_free() -> None:
    observation = apply_governance_transition(
        _state(), _request("capture_observation"), occurred_at=T1
    ).current
    learning = apply_governance_transition(
        _hypothesis(),
        _request("validate_learning", expiry=EXPIRY),
        occurred_at="2026-08-12T10:00:00Z",
        reviewed_by=OWNER,
        evaluation=_evaluation(),
    ).current

    assert observation.epistemic_kind == "observation"
    assert learning.epistemic_kind == "learning"


def test_learning_requires_supported_evaluation_and_matching_reviewer() -> None:
    with pytest.raises(KnowledgeGovernanceError, match="reviewer must match"):
        apply_governance_transition(
            _hypothesis(),
            _request("validate_learning", expiry=EXPIRY),
            occurred_at="2026-08-12T10:00:00Z",
            reviewed_by=OWNER,
            evaluation=_evaluation(reviewer="other_reviewer"),
        )


def test_learning_transition_keeps_reviewed_evaluation_digest() -> None:
    learning = apply_governance_transition(
        _hypothesis(),
        _request("validate_learning", expiry=EXPIRY),
        occurred_at="2026-08-12T10:00:00Z",
        reviewed_by=OWNER,
        evaluation=_evaluation(),
    ).current
    assert learning.epistemic_kind == "learning"
    assert learning.evaluation_digest == _evaluation().canonical_digest
    assert learning.reviewed_by == OWNER


def test_data_derived_global_learning_cannot_promote_to_policy() -> None:
    global_learning = _state(
        "learning",
        scope="global",
        version=4,
        created_at=T2,
        expires_at=EXPIRY,
        review_state="approved",
        reviewed_by=OWNER,
        evidence=(DIGEST_A, DIGEST_B),
        counterexamples=(DIGEST_C,),
        evaluation=DIGEST_A,
    )
    promotion = PromotionEligibility(True, "supported", (), "1.0", EXPIRY, OWNER)
    with pytest.raises(KnowledgeGovernanceError, match="global policy"):
        apply_governance_transition(
            global_learning,
            _request("promote_policy", policy_version="1.0", expiry=EXPIRY),
            occurred_at="2026-08-12T10:00:00Z",
            reviewed_by=OWNER,
            promotion=promotion,
        )


def test_raw_forged_promotion_eligibility_cannot_authorize_policy() -> None:
    learning = _state(
        "learning",
        version=4,
        created_at=T2,
        expires_at=EXPIRY,
        review_state="approved",
        reviewed_by=OWNER,
        evidence=(DIGEST_A,),
        counterexamples=(DIGEST_B,),
        evaluation=DIGEST_C,
    )
    promotion = PromotionEligibility(True, "supported", (), "1.0", EXPIRY, OWNER)
    with pytest.raises(KnowledgeGovernanceError, match="verified PromotionAuthorityEnvelope"):
        apply_governance_transition(
            learning,
            _request("promote_policy", policy_version="1.0", expiry=EXPIRY),
            occurred_at="2026-08-12T10:00:00Z",
            reviewed_by=OWNER,
            promotion=promotion,
        )


def test_verified_signed_authority_promotes_matching_learning_to_policy() -> None:
    learning, envelope, signer = _authority_bound_learning()

    result = apply_governance_transition(
        learning,
        _request("promote_policy", policy_version="learning-1.0", expiry=POLICY_EXPIRY),
        occurred_at="2026-08-14T13:00:00Z",
        reviewed_by=OWNER,
        promotion_authority=envelope,
        authority_verifier=signer,
        tenant_id=TENANT,
    )

    assert result.current.epistemic_kind == "policy"
    assert result.event.authority_digest is not None
    assert len(result.event.authority_digest) == 64
    assert result.current.policy_version == "learning-1.0"
    assert result.current.evaluation_digest == learning.evaluation_digest


@pytest.mark.parametrize(
    ("mutation", "tenant_id", "occurred_at"),
    (
        ("none", "tenant_other", "2026-08-14T13:00:00Z"),
        ("campaign", TENANT, "2026-08-14T13:00:00Z"),
        ("tamper", TENANT, "2026-08-14T13:00:00Z"),
        ("none", TENANT, "2026-08-14T14:00:00Z"),
    ),
)
def test_policy_authority_rejects_wrong_scope_tampering_or_expiry(
    mutation: str,
    tenant_id: str,
    occurred_at: str,
) -> None:
    learning, envelope, signer = _authority_bound_learning()
    if mutation == "campaign":
        learning = replace(learning, campaign_id="campaign_other")
    elif mutation == "tamper":
        envelope = replace(envelope, signature="0" * 64)

    with pytest.raises(KnowledgeGovernanceError, match="authority is invalid"):
        apply_governance_transition(
            learning,
            _request("promote_policy", policy_version="learning-1.0", expiry=POLICY_EXPIRY),
            occurred_at=occurred_at,
            reviewed_by=OWNER,
            promotion_authority=envelope,
            authority_verifier=signer,
            tenant_id=tenant_id,
        )


def test_policy_authority_must_bind_the_current_learning_evaluation() -> None:
    learning, envelope, signer = _authority_bound_learning()
    learning = replace(learning, evaluation_digest=DIGEST_D)

    with pytest.raises(KnowledgeGovernanceError, match="evaluation does not match"):
        apply_governance_transition(
            learning,
            _request("promote_policy", policy_version="learning-1.0", expiry=POLICY_EXPIRY),
            occurred_at="2026-08-14T13:00:00Z",
            reviewed_by=OWNER,
            promotion_authority=envelope,
            authority_verifier=signer,
            tenant_id=TENANT,
        )


def test_expired_knowledge_cannot_advance_but_can_be_deprecated() -> None:
    expired = _state(
        "hypothesis",
        version=3,
        created_at=T0,
        expires_at=T1,
        review_state="approved",
        reviewed_by=OWNER,
        evidence=(DIGEST_A,),
        counterexamples=(DIGEST_B,),
    )
    with pytest.raises(KnowledgeGovernanceError, match="expired knowledge"):
        apply_governance_transition(
            expired,
            _request("validate_learning", expiry=EXPIRY),
            occurred_at=T2,
            reviewed_by=OWNER,
            evaluation=_evaluation(),
        )
    deprecated = deprecate_governance_state(
        expired,
        transition_id="deprecate_1",
        requested_by=OWNER,
        reviewed_by=OWNER,
        rationale="Expired hypothesis.",
        occurred_at=T2,
    )
    assert deprecated.current.lifecycle == "deprecated"


def test_supersede_returns_closed_previous_and_replacement() -> None:
    current = _hypothesis()
    replacement = replace(
        current,
        note=KnowledgeVersionRef(current.note.note_id, current.note.version + 1),
        created_at="2026-08-12T10:00:00Z",
    )
    result = supersede_governance_state(
        current,
        replacement,
        transition_id="supersede_1",
        requested_by=OWNER,
        reviewed_by=OWNER,
        rationale="Superseded by reviewed replacement.",
        occurred_at="2026-08-12T10:00:00Z",
    )
    assert result.current.lifecycle == "superseded"
    assert result.current.superseded_by == replacement.note
    assert result.replacement == replacement
    assert result.event.to_state_digest == replacement.canonical_digest
    assert result.current.canonical_digest != result.previous.canonical_digest


def test_supersede_rejects_incoherent_replacement_payload() -> None:
    current = _hypothesis()
    replacement = replace(
        current,
        note=KnowledgeVersionRef("other_note", current.note.version + 1),
        created_at="2026-08-12T10:00:00Z",
    )
    with pytest.raises(KnowledgeGovernanceError, match="replacement is not"):
        supersede_governance_state(
            current,
            replacement,
            transition_id="supersede_bad",
            requested_by=OWNER,
            reviewed_by=OWNER,
            rationale="Bad replacement.",
            occurred_at="2026-08-12T10:00:00Z",
        )


def test_forged_payload_rejects_duplicate_and_overlapping_digest_namespaces() -> None:
    with pytest.raises(KnowledgeGovernanceError, match="cannot repeat"):
        _state(
            "hypothesis",
            expires_at=EXPIRY,
            review_state="approved",
            reviewed_by=OWNER,
            evidence=(DIGEST_A, DIGEST_A),
            counterexamples=(DIGEST_B,),
        )
    with pytest.raises(KnowledgeGovernanceError, match="cannot overlap"):
        _state(
            "hypothesis",
            expires_at=EXPIRY,
            review_state="approved",
            reviewed_by=OWNER,
            evidence=(DIGEST_A,),
            counterexamples=(DIGEST_A,),
        )


def test_canonical_digests_are_stable_for_equivalent_frozen_state() -> None:
    first = _state(
        "hypothesis",
        expires_at=EXPIRY,
        review_state="approved",
        reviewed_by=OWNER,
        evidence=(DIGEST_B, DIGEST_A),
        counterexamples=(DIGEST_C,),
    )
    second = _state(
        "hypothesis",
        expires_at=EXPIRY,
        review_state="approved",
        reviewed_by=OWNER,
        evidence=(DIGEST_A, DIGEST_B),
        counterexamples=(DIGEST_C,),
    )
    assert first == second
    assert first.canonical_digest == second.canonical_digest
