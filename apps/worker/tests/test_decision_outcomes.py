from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from app.pipeline.decision_outcomes import (
    DecisionEvidenceRefs,
    DecisionOutcomesError,
    EditorialExperiment,
    EffectEstimate,
    EvidenceSnapshot,
    LearningEvaluation,
    LearningHypothesis,
    OutcomeObservation,
    OutcomeStatPolicy,
    VariantProvenance,
    canonical_json,
    promotion_eligibility,
    stable_digest,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
DIGEST_D = "d" * 64
NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
START = "2026-08-10T08:00:00Z"
END = "2026-08-12T08:00:00Z"


def _hypothesis(**over: object) -> LearningHypothesis:
    data: dict[str, object] = {
        "hypothesis_id": "hyp_completion",
        "target_metric": "completion_rate",
        "direction": "increase",
        "comparison": "matched_variant",
        "scope": {"campaign_id": "789e4567-e89b-12d3-a456-426614174000", "paid": True},
        "owner": "123e4567-e89b-12d3-a456-426614174000",
        "support": (DIGEST_A,),
        "counterexample": (DIGEST_B,),
        "created_at": "2026-08-09T08:00:00Z",
        "expires_at": "2026-09-09T08:00:00Z",
    }
    data.update(over)
    return LearningHypothesis(**data)  # type: ignore[arg-type]


def _experiment(experiment_id: str, source_digest: str, **over: object) -> EditorialExperiment:
    variants = (f"{experiment_id}_control", f"{experiment_id}_treatment")
    data: dict[str, object] = {
        "experiment_id": experiment_id,
        "campaign_id": "789e4567-e89b-12d3-a456-426614174000",
        "source_asset_digest": source_digest,
        "objective": "Improve completion rate without changing claims.",
        "primary_metric": "completion_rate",
        "variants": variants,
        "platform": "youtube_shorts",
        "account_id": "123e4567-e89b-12d3-a456-426614174000",
        "cohort": "uk-b2b-founders",
        "posting_window_start": START,
        "posting_window_end": END,
        "paid": True,
        "assignment": {variants[0]: "control", variants[1]: "treatment"},
        "registered_at": "2026-08-09T09:00:00Z",
    }
    data.update(over)
    return EditorialExperiment(**data)  # type: ignore[arg-type]


def _outcome(experiment_id: str, arm: str, **over: object) -> OutcomeObservation:
    data: dict[str, object] = {
        "outcome_id": f"outcome_{experiment_id}_{arm}",
        "experiment_id": experiment_id,
        "variant_id": f"{experiment_id}_{arm}",
        "source_digest": DIGEST_A,
        "metric_name": "completion_rate",
        "observed_at": "2026-08-13T08:00:00Z",
        "window_start": START,
        "window_end": END,
        "platform": "youtube_shorts",
        "account_id": "123e4567-e89b-12d3-a456-426614174000",
        "trust": "verified",
        "numerator": 50 if arm == "control" else 70,
        "denominator": 100,
        "delivery_mode": "paid",
        "qc_guardrail": "pass",
        "claim_guardrail": "pass",
    }
    data.update(over)
    return OutcomeObservation(**data)  # type: ignore[arg-type]


def _provenance(variant_id: str, *, source_id: str) -> VariantProvenance:
    return VariantProvenance(
        variant_id=variant_id,
        decision_id=f"decision_{variant_id}",
        campaign_id="789e4567-e89b-12d3-a456-426614174000",
        source_id=source_id,
        campaign_fingerprint=DIGEST_A,
        research_content_digest=None,
        editorial_context_digest=DIGEST_B,
        graph_digest=DIGEST_C,
        director_plan_digest=DIGEST_D,
        editorial_policy_version="editorial-1.0",
        director_schema_version="2.2",
        campaign_hypothesis="proof_first",
        render_artifact_digest="e" * 64,
        created_at=START,
        snapshot_digest="f" * 64,
        context_issuance_id="issuance_01",
        decision_audit_digest="0" * 64,
    )


def _evaluation(*ids: str, **over: object) -> LearningEvaluation:
    outcome_ids = tuple(f"outcome_{item}_{arm}" for item in ids for arm in ("control", "treatment"))
    data: dict[str, object] = {
        "hypothesis_id": "hyp_completion",
        "experiment_ids": ids,
        "outcome_ids": outcome_ids,
        "effect": EffectEstimate("completion_rate", 0.7, 0.5, 0.4),
        "confounders": (),
        "verdict": "supported",
        "reviewer": "reviewer_01",
        "evaluated_at": "2026-08-13T09:00:00Z",
    }
    data.update(over)
    return LearningEvaluation(**data)  # type: ignore[arg-type]


def _eligible_inputs() -> tuple[
    LearningHypothesis,
    LearningEvaluation,
    tuple[EditorialExperiment, ...],
    tuple[OutcomeObservation, ...],
]:
    one = _experiment("exp_one", DIGEST_C)
    two = _experiment("exp_two", DIGEST_D)
    outcomes = tuple(
        _outcome(experiment, arm)
        for experiment in ("exp_one", "exp_two")
        for arm in ("control", "treatment")
    )
    return _hypothesis(), _evaluation("exp_one", "exp_two"), (one, two), outcomes


def _bound_inputs() -> tuple[
    LearningHypothesis,
    LearningEvaluation,
    tuple[EditorialExperiment, ...],
    tuple[OutcomeObservation, ...],
    tuple[VariantProvenance, ...],
]:
    hypothesis, evaluation, experiments, outcomes = _eligible_inputs()
    provenances = tuple(
        _provenance(variant, source_id=f"source_{experiment_id}")
        for experiment_id in ("exp_one", "exp_two")
        for variant in (f"{experiment_id}_control", f"{experiment_id}_treatment")
    )
    by_variant = {item.variant_id: item for item in provenances}
    bound_experiments = tuple(
        _experiment(
            item.experiment_id,
            item.source_asset_digest,
            variant_provenance_digests={
                variant: by_variant[variant].canonical_digest for variant in item.variants
            },
        )
        for item in experiments
    )
    bound_outcomes = tuple(
        _outcome(
            item.experiment_id,
            "control" if item.variant_id.endswith("_control") else "treatment",
            variant_provenance_digest=by_variant[item.variant_id].canonical_digest,
        )
        for item in outcomes
    )
    return hypothesis, evaluation, bound_experiments, bound_outcomes, provenances


def _gate(
    hypothesis: LearningHypothesis,
    evaluation: LearningEvaluation,
    experiments: tuple[EditorialExperiment, ...],
    outcomes: tuple[OutcomeObservation, ...],
    **over: object,
):
    options: dict[str, object] = {
        "policy_version": "learning-1.0",
        "policy_expires_at": "2026-09-01T00:00:00Z",
        "outcome_stat_policy": _stat_policy(),
        "human_reviewer": "reviewer_01",
        "now": NOW,
    }
    options.update(over)
    return promotion_eligibility(hypothesis, evaluation, experiments, outcomes, **options)  # type: ignore[arg-type]


def _stat_policy(**over: object) -> OutcomeStatPolicy:
    data: dict[str, object] = {
        "schema_version": "1.0",
        "policy_version": "learning-1.0",
        "expires_at": "2026-09-01T00:00:00Z",
        "min_denominator_per_arm": 100,
        "min_independent_experiments": 2,
        "min_absolute_lift": 0.1,
        "interval_method": "newcombe_wilson_95",
        "preregistered_metrics": ("completion_rate",),
    }
    data.update(over)
    return OutcomeStatPolicy(**data)  # type: ignore[arg-type]


def test_opaque_real_world_ids_are_accepted_but_metric_and_kind_stay_safe() -> None:
    snapshot = EvidenceSnapshot(
        evidence_id="123e4567-e89b-12d3-a456-426614174000",
        kind="transcript",
        trust="verified",
        digest=DIGEST_A,
        provenance={"model": "whisper", "words": ["hello"]},
        observed_at="2026-08-09T10:00:00+02:00",
    )
    assert snapshot.observed_at == "2026-08-09T08:00:00Z"
    with pytest.raises(DecisionOutcomesError, match="safe lowercase"):
        EvidenceSnapshot("e1", "Transcript", "verified", DIGEST_A, {}, START)
    with pytest.raises(DecisionOutcomesError, match="safe lowercase"):
        _hypothesis(target_metric="CompletionRate")


def test_evidence_refs_are_closed_namespaces_and_deeply_immutable() -> None:
    refs = DecisionEvidenceRefs(
        knowledge_ref_digests=(DIGEST_A,),
        campaign_ref_digests=(DIGEST_B,),
        source_ref_digests=(DIGEST_C,),
    )
    assert refs.to_dict()["campaign_ref_digests"] == [DIGEST_B]
    with pytest.raises(DecisionOutcomesError, match="overlap"):
        DecisionEvidenceRefs(knowledge_ref_digests=(DIGEST_A,), source_ref_digests=(DIGEST_A,))
    evidence = EvidenceSnapshot("e1", "transcript", "verified", DIGEST_A, {"x": ["y"]}, START)
    with pytest.raises(TypeError):
        evidence.provenance["x"] = "mutate"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        evidence.evidence_id = "e2"  # type: ignore[misc]


def test_variant_provenance_is_complete_and_closed() -> None:
    provenance = VariantProvenance(
        variant_id="variant_01",
        decision_id="decision_01",
        campaign_id="789e4567-e89b-12d3-a456-426614174000",
        source_id="source_01",
        campaign_fingerprint=DIGEST_A,
        research_content_digest=None,
        editorial_context_digest=DIGEST_B,
        graph_digest=DIGEST_C,
        director_plan_digest=DIGEST_D,
        editorial_policy_version="editorial-1.0",
        director_schema_version="2.0",
        campaign_hypothesis="proof_first",
        render_artifact_digest="e" * 64,
        created_at=START,
    )
    assert provenance.research_content_digest is None
    with pytest.raises(DecisionOutcomesError, match="not allowed"):
        VariantProvenance(**{**provenance.to_dict(), "campaign_hypothesis": "made_up"})
    with pytest.raises(DecisionOutcomesError, match="must bind together"):
        VariantProvenance(**{**provenance.to_dict(), "snapshot_digest": DIGEST_A})


def test_promotion_binds_exact_decision_variant_experiment_and_outcome_chain() -> None:
    hypothesis, evaluation, experiments, outcomes, provenances = _bound_inputs()
    result = _gate(
        hypothesis,
        evaluation,
        experiments,
        outcomes,
        variant_provenances=provenances,
    )
    assert result.eligible

    missing = _gate(
        hypothesis,
        evaluation,
        experiments,
        outcomes,
        variant_provenances=provenances[:-1],
    )
    assert not missing.eligible
    assert any("exactly cover" in reason for reason in missing.reasons)

    unbound_outcomes = tuple(
        _outcome(
            item.experiment_id,
            "control" if item.variant_id.endswith("_control") else "treatment",
        )
        for item in outcomes
    )
    free_digest = _gate(
        hypothesis,
        evaluation,
        experiments,
        unbound_outcomes,
        variant_provenances=provenances,
    )
    assert not free_digest.eligible
    assert any("outcome provenance digest" in reason for reason in free_digest.reasons)

    invalid_bindings = tuple(
        _experiment(
            item.experiment_id,
            item.source_asset_digest,
            variant_provenance_digests={variant: DIGEST_A for variant in item.variants},
        )
        for item in experiments
    )
    mismatched = _gate(
        hypothesis,
        evaluation,
        invalid_bindings,
        outcomes,
        variant_provenances=provenances,
    )
    assert not mismatched.eligible
    assert any("does not match artifact" in reason for reason in mismatched.reasons)

    split_source = tuple(
        (
            _provenance(item.variant_id, source_id="other_source")
            if item.variant_id == "exp_one_treatment"
            else item
        )
        for item in provenances
    )
    split_sources = _gate(
        hypothesis,
        evaluation,
        experiments,
        outcomes,
        variant_provenances=split_source,
    )
    assert not split_sources.eligible
    assert any("share a source" in reason for reason in split_sources.reasons)


def test_canonical_json_and_digest_are_deterministic() -> None:
    assert canonical_json({"z": (2, 1), "a": {"b": "x"}}) == '{"a":{"b":"x"},"z":[2,1]}'
    assert stable_digest({"a": {"b": "x"}, "z": [2, 1]}) == stable_digest(
        {"z": (2, 1), "a": {"b": "x"}}
    )


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: _experiment("exp_one", DIGEST_C, variants=("a", "b", "c")), "exactly two"),
        (
            lambda: _experiment(
                "exp_one",
                DIGEST_C,
                assignment={"exp_one_control": "control", "exp_one_treatment": "control"},
            ),
            "exactly control",
        ),
        (lambda: _hypothesis(comparison="free_text"), "not allowed"),
        (lambda: _outcome("exp_one", "control", numerator=1, scalar=1), "exactly one"),
        (lambda: _outcome("exp_one", "control", observed_at=START), "must not precede"),
    ],
)
def test_hostile_inputs_fail_closed(factory: object, message: str) -> None:
    with pytest.raises(DecisionOutcomesError, match=message):
        factory()  # type: ignore[operator]


def test_promotion_accepts_only_pre_registered_two_arm_verified_paid_evidence() -> None:
    hypothesis, evaluation, experiments, outcomes = _eligible_inputs()
    result = _gate(hypothesis, evaluation, experiments, outcomes)
    assert result.eligible
    assert result.verdict == "supported"


@pytest.mark.parametrize(
    "mutate, expected",
    [
        ("missing_control", "lacks control or treatment"),
        ("free_effect", "effect does not match"),
        ("untrusted", "trust is insufficient"),
        ("historical_organic", "inconclusive"),
        ("guardrail", "guardrail did not pass"),
        ("confounded", "has confounders"),
        ("wrong_reviewer", "must equal"),
        ("historical_comparison", "historical baseline is inconclusive"),
    ],
)
def test_false_promotions_are_rejected(mutate: str, expected: str) -> None:
    hypothesis, evaluation, experiments, outcomes = _eligible_inputs()
    if mutate == "missing_control":
        outcomes = tuple(item for item in outcomes if item.variant_id != "exp_two_control")
        evaluation = _evaluation(
            "exp_one", "exp_two", outcome_ids=tuple(item.outcome_id for item in outcomes)
        )
    elif mutate == "free_effect":
        evaluation = _evaluation(
            "exp_one", "exp_two", effect=EffectEstimate("completion_rate", 0.9, 0.5, 0.8)
        )
    elif mutate == "untrusted":
        outcomes = tuple(
            (
                _outcome("exp_one", "control", trust="observed")
                if item.outcome_id == "outcome_exp_one_control"
                else item
            )
            for item in outcomes
        )
    elif mutate == "historical_organic":
        outcomes = tuple(
            (
                _outcome("exp_one", "control", delivery_mode="organic", is_historical=True)
                if item.outcome_id == "outcome_exp_one_control"
                else item
            )
            for item in outcomes
        )
    elif mutate == "guardrail":
        outcomes = tuple(
            (
                _outcome("exp_one", "control", qc_guardrail="fail")
                if item.outcome_id == "outcome_exp_one_control"
                else item
            )
            for item in outcomes
        )
    elif mutate == "confounded":
        evaluation = _evaluation("exp_one", "exp_two", confounders=("weekday",))
    elif mutate == "wrong_reviewer":
        result = _gate(hypothesis, evaluation, experiments, outcomes, human_reviewer="reviewer_02")
        assert not result.eligible and any(expected in item for item in result.reasons)
        return
    elif mutate == "historical_comparison":
        hypothesis = _hypothesis(comparison="historical_baseline")
    result = _gate(hypothesis, evaluation, experiments, outcomes)
    assert not result.eligible
    assert any(expected in item for item in result.reasons)


def test_gate_requires_independence_scope_hypothesis_expiry_and_all_outcomes_for_effect() -> None:
    hypothesis, evaluation, experiments, outcomes = _eligible_inputs()
    same_asset = (_experiment("exp_one", DIGEST_C), _experiment("exp_two", DIGEST_C))
    result = _gate(hypothesis, evaluation, same_asset, outcomes)
    assert "experiments are not independent" in result.reasons
    expired = _gate(
        _hypothesis(expires_at="2026-08-14T11:00:00Z"), evaluation, experiments, outcomes
    )
    assert "hypothesis expired" in expired.reasons
    mismatched = _gate(
        _hypothesis(scope={"campaign_id": "campaign_other", "platform": "tiktok"}),
        evaluation,
        experiments,
        outcomes,
    )
    assert "experiment does not match hypothesis scope or target" in mismatched.reasons


def test_matched_organic_experiment_is_admissible_but_post_hoc_and_bad_dates_are_not() -> None:
    hypothesis = _hypothesis(
        scope={"campaign_id": "789e4567-e89b-12d3-a456-426614174000", "paid": False}
    )
    evaluation = _evaluation("exp_one", "exp_two")
    experiments = (
        _experiment("exp_one", DIGEST_C, paid=False),
        _experiment("exp_two", DIGEST_D, paid=False),
    )
    outcomes = tuple(
        _outcome(experiment, arm, delivery_mode="organic")
        for experiment in ("exp_one", "exp_two")
        for arm in ("control", "treatment")
    )
    assert _gate(hypothesis, evaluation, experiments, outcomes).eligible

    post_hoc = _gate(
        _hypothesis(created_at="2026-08-09T10:00:00Z"),
        evaluation,
        experiments,
        outcomes,
    )
    assert "hypothesis was created after experiment registration" in post_hoc.reasons
    early_evaluation = _gate(
        hypothesis,
        _evaluation("exp_one", "exp_two", evaluated_at="2026-08-13T07:00:00Z"),
        experiments,
        outcomes,
    )
    assert "evaluation precedes an outcome observation" in early_evaluation.reasons
    stale_window = tuple(
        (
            _outcome("exp_one", "control", window_start="2026-08-09T08:00:00Z")
            if item.outcome_id == "outcome_exp_one_control"
            else item
        )
        for item in outcomes
    )
    assert (
        "outcome dates do not follow experiment window"
        in _gate(
            hypothesis,
            evaluation,
            experiments,
            stale_window,
        ).reasons
    )


def test_ratio_bounds_required_support_and_zero_control_fail_closed() -> None:
    with pytest.raises(DecisionOutcomesError, match="must not exceed"):
        _outcome("exp_one", "control", numerator=101, denominator=100)
    with pytest.raises(DecisionOutcomesError, match="cannot be empty"):
        _hypothesis(support=())
    with pytest.raises(DecisionOutcomesError, match="campaign_id"):
        _hypothesis(scope={})
    hypothesis, _, experiments, outcomes = _eligible_inputs()
    zero_control = tuple(
        (
            _outcome("exp_one", "control", numerator=0)
            if item.outcome_id == "outcome_exp_one_control"
            else (
                _outcome("exp_two", "control", numerator=0)
                if item.outcome_id == "outcome_exp_two_control"
                else item
            )
        )
        for item in outcomes
    )
    evaluation = _evaluation(
        "exp_one",
        "exp_two",
        effect=EffectEstimate("completion_rate", 0.6, 0.0, 0.0),
    )
    assert any(
        "control rate is zero" in reason
        for reason in _gate(hypothesis, evaluation, experiments, zero_control).reasons
    )


def test_duplicate_arm_outcome_and_direction_mismatch_cannot_promote() -> None:
    hypothesis, evaluation, experiments, outcomes = _eligible_inputs()
    duplicate = _outcome("exp_one", "control", outcome_id="outcome_exp_one_control_retry")
    duplicate_evaluation = _evaluation(
        "exp_one",
        "exp_two",
        outcome_ids=(*evaluation.outcome_ids, duplicate.outcome_id),
    )
    duplicate_result = _gate(
        hypothesis,
        duplicate_evaluation,
        experiments,
        (*outcomes, duplicate),
    )
    assert any("multiple outcomes" in reason for reason in duplicate_result.reasons)
    assert any("exactly one outcome per arm" in reason for reason in duplicate_result.reasons)

    decreasing = _gate(
        _hypothesis(direction="decrease"),
        evaluation,
        experiments,
        outcomes,
    )
    no_effect = _gate(
        _hypothesis(direction="no_effect"),
        evaluation,
        experiments,
        outcomes,
    )
    assert "effect direction does not match hypothesis" in decreasing.reasons
    assert "effect direction does not match hypothesis" in no_effect.reasons


def test_outcome_stat_policy_rejects_eight_view_arms_and_legacy_diagnostics() -> None:
    hypothesis, _, experiments, _ = _eligible_inputs()
    outcomes = tuple(
        _outcome(
            experiment_id,
            arm,
            numerator=4 if arm == "control" else 7,
            denominator=8,
        )
        for experiment_id in ("exp_one", "exp_two")
        for arm in ("control", "treatment")
    )
    evaluation = _evaluation(
        "exp_one",
        "exp_two",
        effect=EffectEstimate("completion_rate", 0.875, 0.5, 0.75),
    )
    small = _gate(hypothesis, evaluation, experiments, outcomes)
    assert not small.eligible
    assert "outcome denominator is below outcome statistical policy minimum" in small.reasons
    legacy = _gate(
        hypothesis,
        evaluation,
        experiments,
        outcomes,
        outcome_stat_policy=None,
    )
    assert not legacy.eligible
    assert "missing outcome statistical policy" in legacy.reasons


def test_outcome_stat_policy_accepts_powered_preregistered_replicated_effect() -> None:
    hypothesis, evaluation, experiments, outcomes = _eligible_inputs()
    result = _gate(hypothesis, evaluation, experiments, outcomes)
    assert result.eligible
    assert result.outcome_stat_policy_digest == _stat_policy().canonical_digest


def test_outcome_stat_policy_rejects_uncertainty_and_forged_point_estimate() -> None:
    hypothesis, _, experiments, _ = _eligible_inputs()
    outcomes = tuple(
        _outcome(
            experiment_id,
            arm,
            numerator=50 if arm == "control" else 55,
        )
        for experiment_id in ("exp_one", "exp_two")
        for arm in ("control", "treatment")
    )
    evaluation = _evaluation(
        "exp_one",
        "exp_two",
        effect=EffectEstimate("completion_rate", 0.55, 0.5, 0.1),
    )
    uncertain = _gate(
        hypothesis,
        evaluation,
        experiments,
        outcomes,
        outcome_stat_policy=_stat_policy(min_absolute_lift=0.01),
    )
    assert not uncertain.eligible
    assert "statistical interval includes zero" in uncertain.reasons
    forged = _gate(
        hypothesis,
        replace(evaluation, effect=EffectEstimate("completion_rate", 0.99, 0.5, 0.98)),
        experiments,
        outcomes,
        outcome_stat_policy=_stat_policy(min_absolute_lift=0.01),
    )
    assert not forged.eligible
    assert "effect does not match aggregated outcome rates" in forged.reasons


def test_outcome_stat_policy_requires_registered_metric_and_directional_lift() -> None:
    _, _, experiments, _ = _eligible_inputs()
    outcomes = tuple(
        _outcome(
            experiment_id,
            arm,
            numerator=70 if arm == "control" else 50,
        )
        for experiment_id in ("exp_one", "exp_two")
        for arm in ("control", "treatment")
    )
    decrease = _hypothesis(direction="decrease")
    evaluation = _evaluation(
        "exp_one",
        "exp_two",
        effect=EffectEstimate("completion_rate", 0.5, 0.7, -(2.0 / 7.0)),
    )
    assert _gate(decrease, evaluation, experiments, outcomes).eligible
    unregistered = _gate(
        decrease,
        evaluation,
        experiments,
        outcomes,
        outcome_stat_policy=_stat_policy(preregistered_metrics=("average_watch_time",)),
    )
    assert not unregistered.eligible
    assert "metric is not preregistered by outcome statistical policy" in unregistered.reasons
