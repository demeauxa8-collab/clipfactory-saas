"""Pure immutable contracts from evidence through editorial learning.

There is intentionally no runner, persistence, provider, or knowledge-vault
integration here. Outcomes are observations only: no model in this module can
use one to alter an already recorded provenance or knowledge reference.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Literal, TypeAlias

SCHEMA_VERSION = "1.0"
_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_SAFE_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_DIGEST_RE = re.compile(r"^[a-f0-9]{64}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_TRUST = frozenset({"unverified", "observed", "verified", "human_reviewed"})
_GUARDRAILS = frozenset({"pass", "fail", "unknown"})
_VERDICTS = frozenset({"supported", "rejected", "inconclusive"})
_DIRECTIONS = frozenset({"increase", "decrease", "no_effect"})
_CAMPAIGN_HYPOTHESES = frozenset(
    {
        "proof_first",
        "objection_first",
        "curiosity_first",
        "authority_first",
        "transformation_first",
    }
)
_COMPARISONS = frozenset({"matched_variant", "historical_baseline"})
_STATISTICAL_INTERVAL_METHODS = frozenset({"newcombe_wilson_95"})
_MAX_TEXT = 1000
_MAX_JSON_DEPTH = 6
_MAX_JSON_ITEMS = 64

EvidenceTrust: TypeAlias = Literal["unverified", "observed", "verified", "human_reviewed"]
OutcomeTrust: TypeAlias = Literal["unverified", "observed", "verified", "human_reviewed"]
GuardrailStatus: TypeAlias = Literal["pass", "fail", "unknown"]
LearningVerdict: TypeAlias = Literal["supported", "rejected", "inconclusive"]
LearningDirection: TypeAlias = Literal["increase", "decrease", "no_effect"]
LearningComparison: TypeAlias = Literal["matched_variant", "historical_baseline"]


class DecisionOutcomesError(ValueError):
    """A hostile or incoherent value was rejected by the closed contract."""


def _text(value: Any, label: str, *, maximum: int = _MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise DecisionOutcomesError(f"{label} must be a string")
    value = unicodedata.normalize("NFC", value).strip()
    if not value:
        raise DecisionOutcomesError(f"{label} cannot be empty")
    if len(value) > maximum:
        raise DecisionOutcomesError(f"{label} exceeds {maximum} characters")
    return value


def _opaque_id(value: Any, label: str) -> str:
    value = _text(value, label, maximum=128)
    if not _OPAQUE_ID_RE.fullmatch(value):
        raise DecisionOutcomesError(f"{label} must be an opaque identifier")
    return value


def _safe_name(value: Any, label: str) -> str:
    value = _text(value, label, maximum=64)
    if not _SAFE_NAME_RE.fullmatch(value):
        raise DecisionOutcomesError(f"{label} must be a safe lowercase name")
    return value


def _digest(value: Any, label: str) -> str:
    value = _text(value, label, maximum=64).lower()
    if not _DIGEST_RE.fullmatch(value):
        raise DecisionOutcomesError(f"{label} must be a SHA-256 hex digest")
    return value


def _version(value: Any, label: str) -> str:
    value = _text(value, label, maximum=64)
    if not _VERSION_RE.fullmatch(value):
        raise DecisionOutcomesError(f"{label} is invalid")
    return value


def _instant(value: Any, label: str) -> str:
    value = _text(value, label, maximum=40)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionOutcomesError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DecisionOutcomesError(f"{label} must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _number(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DecisionOutcomesError(f"{label} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise DecisionOutcomesError(f"{label} must be a finite number")
    if minimum is not None and value < minimum:
        raise DecisionOutcomesError(f"{label} must be at least {minimum}")
    return value


def _freeze_json(value: Any, *, label: str, depth: int = 0) -> Any:
    if depth > _MAX_JSON_DEPTH:
        raise DecisionOutcomesError(f"{label} exceeds maximum nesting")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _text(value, label)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return _number(value, label)
    if isinstance(value, Mapping):
        if len(value) > _MAX_JSON_ITEMS:
            raise DecisionOutcomesError(f"{label} has too many entries")
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            key = _text(key, f"{label} key", maximum=128)
            if key in frozen:
                raise DecisionOutcomesError(f"{label} has duplicate normalized keys")
            frozen[key] = _freeze_json(item, label=label, depth=depth + 1)
        return MappingProxyType(dict(sorted(frozen.items())))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) > _MAX_JSON_ITEMS:
            raise DecisionOutcomesError(f"{label} has too many entries")
        return tuple(_freeze_json(item, label=label, depth=depth + 1) for item in value)
    raise DecisionOutcomesError(f"{label} must contain JSON values only")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Canonical JSON used for every digest: sorted keys and compact UTF-8 data."""
    if isinstance(value, _CanonicalModel):
        value = value.to_dict()
    return json.dumps(
        _thaw_json(_freeze_json(value, label="canonical value")),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def stable_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _digest_tuple(value: Any, label: str, *, required: bool = False) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise DecisionOutcomesError(f"{label} must be a tuple")
    values = tuple(sorted(_digest(item, label) for item in value))
    if len(values) != len(set(values)):
        raise DecisionOutcomesError(f"{label} must be unique")
    if required and not values:
        raise DecisionOutcomesError(f"{label} cannot be empty")
    return values


def _id_tuple(value: Any, label: str, *, required: bool = True) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise DecisionOutcomesError(f"{label} must be a tuple")
    values = tuple(sorted(_opaque_id(item, label) for item in value))
    if len(values) != len(set(values)):
        raise DecisionOutcomesError(f"{label} must be unique")
    if required and not values:
        raise DecisionOutcomesError(f"{label} cannot be empty")
    return values


class _CanonicalModel:
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @property
    def canonical_digest(self) -> str:
        return stable_digest(self.to_dict())


@dataclass(frozen=True)
class EvidenceSnapshot(_CanonicalModel):
    evidence_id: str
    kind: str
    trust: EvidenceTrust
    digest: str
    provenance: Mapping[str, Any]
    observed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _opaque_id(self.evidence_id, "evidence.evidence_id")
        )
        object.__setattr__(self, "kind", _safe_name(self.kind, "evidence.kind"))
        if self.trust not in _TRUST:
            raise DecisionOutcomesError("evidence.trust is not allowed")
        object.__setattr__(self, "digest", _digest(self.digest, "evidence.digest"))
        if not isinstance(self.provenance, Mapping):
            raise DecisionOutcomesError("evidence.provenance must be an object")
        object.__setattr__(
            self,
            "provenance",
            _freeze_json(self.provenance, label="evidence.provenance"),
        )
        object.__setattr__(self, "observed_at", _instant(self.observed_at, "evidence.observed_at"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "trust": self.trust,
            "digest": self.digest,
            "provenance": _thaw_json(self.provenance),
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True)
class DecisionEvidenceRefs(_CanonicalModel):
    """Closed digest namespaces; outcomes are deliberately absent."""

    knowledge_ref_digests: tuple[str, ...] = ()
    campaign_ref_digests: tuple[str, ...] = ()
    source_ref_digests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        knowledge = _digest_tuple(self.knowledge_ref_digests, "refs.knowledge_ref_digests")
        campaign = _digest_tuple(self.campaign_ref_digests, "refs.campaign_ref_digests")
        source = _digest_tuple(self.source_ref_digests, "refs.source_ref_digests")
        if len(knowledge + campaign + source) != len(set(knowledge + campaign + source)):
            raise DecisionOutcomesError("refs digests must not overlap across namespaces")
        object.__setattr__(self, "knowledge_ref_digests", knowledge)
        object.__setattr__(self, "campaign_ref_digests", campaign)
        object.__setattr__(self, "source_ref_digests", source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_ref_digests": list(self.knowledge_ref_digests),
            "campaign_ref_digests": list(self.campaign_ref_digests),
            "source_ref_digests": list(self.source_ref_digests),
        }


@dataclass(frozen=True)
class EditorialDecisionRecord(_CanonicalModel):
    decision_id: str
    campaign_id: str
    subject_id: str
    created_at: str
    decision_type: str
    decision: Mapping[str, Any]
    rationale: str
    evidence_refs: DecisionEvidenceRefs
    policy_version: str

    def __post_init__(self) -> None:
        for field in ("decision_id", "campaign_id", "subject_id"):
            object.__setattr__(self, field, _opaque_id(getattr(self, field), f"decision.{field}"))
        object.__setattr__(self, "created_at", _instant(self.created_at, "decision.created_at"))
        object.__setattr__(
            self, "decision_type", _safe_name(self.decision_type, "decision.decision_type")
        )
        if not isinstance(self.decision, Mapping):
            raise DecisionOutcomesError("decision.decision must be an object")
        object.__setattr__(self, "decision", _freeze_json(self.decision, label="decision.decision"))
        object.__setattr__(self, "rationale", _text(self.rationale, "decision.rationale"))
        if not isinstance(self.evidence_refs, DecisionEvidenceRefs):
            raise DecisionOutcomesError("decision.evidence_refs is invalid")
        object.__setattr__(
            self, "policy_version", _version(self.policy_version, "decision.policy_version")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "campaign_id": self.campaign_id,
            "subject_id": self.subject_id,
            "created_at": self.created_at,
            "decision_type": self.decision_type,
            "decision": _thaw_json(self.decision),
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs.to_dict(),
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True)
class VariantProvenance(_CanonicalModel):
    variant_id: str
    decision_id: str
    campaign_id: str
    source_id: str
    campaign_fingerprint: str
    research_content_digest: str | None
    editorial_context_digest: str
    graph_digest: str
    director_plan_digest: str
    editorial_policy_version: str
    director_schema_version: str
    campaign_hypothesis: Literal[
        "proof_first",
        "objection_first",
        "curiosity_first",
        "authority_first",
        "transformation_first",
    ]
    render_artifact_digest: str
    created_at: str
    # These bindings were added after the first local outcome contracts.  ``None``
    # is tolerated only for reading a legacy artifact; no partially-bound chain
    # is admissible to the promotion gate below.
    snapshot_digest: str | None = None
    context_issuance_id: str | None = None
    decision_audit_digest: str | None = None

    def __post_init__(self) -> None:
        for field in ("variant_id", "decision_id", "campaign_id", "source_id"):
            object.__setattr__(self, field, _opaque_id(getattr(self, field), f"variant.{field}"))
        for field in (
            "campaign_fingerprint",
            "editorial_context_digest",
            "graph_digest",
            "director_plan_digest",
            "render_artifact_digest",
        ):
            object.__setattr__(self, field, _digest(getattr(self, field), f"variant.{field}"))
        if self.research_content_digest is not None:
            object.__setattr__(
                self,
                "research_content_digest",
                _digest(self.research_content_digest, "variant.research_content_digest"),
            )
        for name in ("snapshot_digest", "decision_audit_digest"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _digest(value, f"variant.{name}"))
        if self.context_issuance_id is not None:
            object.__setattr__(
                self,
                "context_issuance_id",
                _opaque_id(self.context_issuance_id, "variant.context_issuance_id"),
            )
        bound = (
            self.snapshot_digest,
            self.context_issuance_id,
            self.decision_audit_digest,
        )
        if any(item is not None for item in bound) and any(item is None for item in bound):
            raise DecisionOutcomesError(
                "variant snapshot, context issuance, and decision audit must bind together"
            )
        object.__setattr__(
            self,
            "editorial_policy_version",
            _version(self.editorial_policy_version, "variant.editorial_policy_version"),
        )
        object.__setattr__(
            self,
            "director_schema_version",
            _version(self.director_schema_version, "variant.director_schema_version"),
        )
        if self.campaign_hypothesis not in _CAMPAIGN_HYPOTHESES:
            raise DecisionOutcomesError("variant.campaign_hypothesis is not allowed")
        object.__setattr__(self, "created_at", _instant(self.created_at, "variant.created_at"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "decision_id": self.decision_id,
            "campaign_id": self.campaign_id,
            "source_id": self.source_id,
            "campaign_fingerprint": self.campaign_fingerprint,
            "research_content_digest": self.research_content_digest,
            "editorial_context_digest": self.editorial_context_digest,
            "graph_digest": self.graph_digest,
            "director_plan_digest": self.director_plan_digest,
            "editorial_policy_version": self.editorial_policy_version,
            "director_schema_version": self.director_schema_version,
            "campaign_hypothesis": self.campaign_hypothesis,
            "render_artifact_digest": self.render_artifact_digest,
            "created_at": self.created_at,
            "snapshot_digest": self.snapshot_digest,
            "context_issuance_id": self.context_issuance_id,
            "decision_audit_digest": self.decision_audit_digest,
        }


@dataclass(frozen=True)
class OutcomeObservation(_CanonicalModel):
    outcome_id: str
    experiment_id: str
    variant_id: str
    source_digest: str
    metric_name: str
    observed_at: str
    window_start: str
    window_end: str
    platform: str
    account_id: str
    trust: OutcomeTrust
    numerator: float | None = None
    denominator: float | None = None
    scalar: float | None = None
    delivery_mode: Literal["organic", "paid", "mixed"] = "organic"
    is_historical: bool = False
    qc_guardrail: GuardrailStatus = "unknown"
    claim_guardrail: GuardrailStatus = "unknown"
    variant_provenance_digest: str | None = None

    def __post_init__(self) -> None:
        for field in ("outcome_id", "experiment_id", "variant_id", "account_id"):
            object.__setattr__(self, field, _opaque_id(getattr(self, field), f"outcome.{field}"))
        object.__setattr__(self, "metric_name", _safe_name(self.metric_name, "outcome.metric_name"))
        object.__setattr__(
            self, "source_digest", _digest(self.source_digest, "outcome.source_digest")
        )
        if self.variant_provenance_digest is not None:
            object.__setattr__(
                self,
                "variant_provenance_digest",
                _digest(
                    self.variant_provenance_digest,
                    "outcome.variant_provenance_digest",
                ),
            )
        observed = _instant(self.observed_at, "outcome.observed_at")
        start = _instant(self.window_start, "outcome.window_start")
        end = _instant(self.window_end, "outcome.window_end")
        if _dt(end) <= _dt(start):
            raise DecisionOutcomesError("outcome.window_end must be after outcome.window_start")
        if _dt(observed) < _dt(end):
            raise DecisionOutcomesError("outcome.observed_at must not precede outcome.window_end")
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "window_start", start)
        object.__setattr__(self, "window_end", end)
        object.__setattr__(self, "platform", _safe_name(self.platform, "outcome.platform"))
        if self.trust not in _TRUST:
            raise DecisionOutcomesError("outcome.trust is not allowed")
        has_ratio = self.numerator is not None or self.denominator is not None
        if has_ratio == (self.scalar is not None):
            raise DecisionOutcomesError("outcome requires exactly one of ratio or scalar")
        if has_ratio:
            numerator = _number(self.numerator, "outcome.numerator", minimum=0.0)
            denominator = _number(self.denominator, "outcome.denominator", minimum=0.0)
            if denominator == 0:
                raise DecisionOutcomesError("outcome.denominator must be greater than zero")
            if numerator > denominator:
                raise DecisionOutcomesError("outcome.numerator must not exceed outcome.denominator")
            object.__setattr__(self, "numerator", numerator)
            object.__setattr__(self, "denominator", denominator)
            object.__setattr__(self, "scalar", None)
        else:
            object.__setattr__(self, "scalar", _number(self.scalar, "outcome.scalar", minimum=0.0))
        if self.delivery_mode not in {"organic", "paid", "mixed"}:
            raise DecisionOutcomesError("outcome.delivery_mode is not allowed")
        if not isinstance(self.is_historical, bool):
            raise DecisionOutcomesError("outcome.is_historical must be a boolean")
        if self.qc_guardrail not in _GUARDRAILS or self.claim_guardrail not in _GUARDRAILS:
            raise DecisionOutcomesError("outcome guardrail status is not allowed")

    @property
    def rate(self) -> float | None:
        return None if self.denominator is None else self.numerator / self.denominator

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "experiment_id": self.experiment_id,
            "variant_id": self.variant_id,
            "source_digest": self.source_digest,
            "metric_name": self.metric_name,
            "observed_at": self.observed_at,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "platform": self.platform,
            "account_id": self.account_id,
            "trust": self.trust,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "scalar": self.scalar,
            "delivery_mode": self.delivery_mode,
            "is_historical": self.is_historical,
            "qc_guardrail": self.qc_guardrail,
            "claim_guardrail": self.claim_guardrail,
            "variant_provenance_digest": self.variant_provenance_digest,
        }


@dataclass(frozen=True)
class EditorialExperiment(_CanonicalModel):
    experiment_id: str
    campaign_id: str
    source_asset_digest: str
    objective: str
    primary_metric: str
    variants: tuple[str, ...]
    platform: str
    account_id: str
    cohort: str
    posting_window_start: str
    posting_window_end: str
    paid: bool
    assignment: Mapping[str, Literal["control", "treatment"]]
    registered_at: str
    # Canonical ``variant_id -> VariantProvenance.canonical_digest`` bindings.
    # An empty mapping is a legacy experiment. A nonempty mapping is always
    # verified against the complete supplied provenance set at promotion time.
    variant_provenance_digests: Mapping[str, str] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "experiment_id", _opaque_id(self.experiment_id, "experiment.experiment_id")
        )
        object.__setattr__(
            self, "campaign_id", _opaque_id(self.campaign_id, "experiment.campaign_id")
        )
        object.__setattr__(
            self,
            "source_asset_digest",
            _digest(self.source_asset_digest, "experiment.source_asset_digest"),
        )
        object.__setattr__(self, "objective", _text(self.objective, "experiment.objective"))
        object.__setattr__(
            self, "primary_metric", _safe_name(self.primary_metric, "experiment.primary_metric")
        )
        variants = _id_tuple(self.variants, "experiment.variants")
        if len(variants) != 2:
            raise DecisionOutcomesError("experiment V1 requires exactly two variants")
        object.__setattr__(self, "variants", variants)
        object.__setattr__(self, "platform", _safe_name(self.platform, "experiment.platform"))
        object.__setattr__(self, "account_id", _opaque_id(self.account_id, "experiment.account_id"))
        object.__setattr__(self, "cohort", _text(self.cohort, "experiment.cohort", maximum=240))
        start = _instant(self.posting_window_start, "experiment.posting_window_start")
        end = _instant(self.posting_window_end, "experiment.posting_window_end")
        if _dt(end) <= _dt(start):
            raise DecisionOutcomesError("experiment.posting_window_end must be after start")
        object.__setattr__(self, "posting_window_start", start)
        object.__setattr__(self, "posting_window_end", end)
        if not isinstance(self.paid, bool):
            raise DecisionOutcomesError("experiment.paid must be a boolean")
        if not isinstance(self.assignment, Mapping):
            raise DecisionOutcomesError("experiment.assignment must be an object")
        assignment = {
            _opaque_id(variant, "experiment.assignment variant"): _text(
                arm,
                "experiment.assignment arm",
                maximum=16,
            )
            for variant, arm in self.assignment.items()
        }
        if set(assignment) != set(variants) or set(assignment.values()) != {"control", "treatment"}:
            raise DecisionOutcomesError(
                "experiment.assignment must be exactly control and treatment"
            )
        object.__setattr__(self, "assignment", MappingProxyType(dict(sorted(assignment.items()))))
        registered = _instant(self.registered_at, "experiment.registered_at")
        if _dt(registered) > _dt(start):
            raise DecisionOutcomesError("experiment.registered_at must be before posting window")
        object.__setattr__(self, "registered_at", registered)
        if not isinstance(self.variant_provenance_digests, Mapping):
            raise DecisionOutcomesError("experiment.variant_provenance_digests must be an object")
        bindings = {
            _opaque_id(variant, "experiment.provenance variant"): _digest(
                digest,
                "experiment.variant provenance digest",
            )
            for variant, digest in self.variant_provenance_digests.items()
        }
        if bindings and set(bindings) != set(variants):
            raise DecisionOutcomesError(
                "experiment provenance bindings must exactly cover its two variants"
            )
        object.__setattr__(
            self,
            "variant_provenance_digests",
            MappingProxyType(dict(sorted(bindings.items()))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "campaign_id": self.campaign_id,
            "source_asset_digest": self.source_asset_digest,
            "objective": self.objective,
            "primary_metric": self.primary_metric,
            "variants": list(self.variants),
            "platform": self.platform,
            "account_id": self.account_id,
            "cohort": self.cohort,
            "posting_window_start": self.posting_window_start,
            "posting_window_end": self.posting_window_end,
            "paid": self.paid,
            "assignment": dict(self.assignment),
            "registered_at": self.registered_at,
            "variant_provenance_digests": dict(self.variant_provenance_digests),
        }


@dataclass(frozen=True)
class LearningHypothesis(_CanonicalModel):
    hypothesis_id: str
    target_metric: str
    direction: LearningDirection
    comparison: LearningComparison
    scope: Mapping[str, Any]
    owner: str
    support: tuple[str, ...]
    counterexample: tuple[str, ...]
    created_at: str
    expires_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "hypothesis_id", _opaque_id(self.hypothesis_id, "hypothesis.hypothesis_id")
        )
        object.__setattr__(
            self, "target_metric", _safe_name(self.target_metric, "hypothesis.target_metric")
        )
        if self.direction not in _DIRECTIONS:
            raise DecisionOutcomesError("hypothesis.direction is not allowed")
        if self.comparison not in _COMPARISONS:
            raise DecisionOutcomesError("hypothesis.comparison is not allowed")
        if not isinstance(self.scope, Mapping):
            raise DecisionOutcomesError("hypothesis.scope must be an object")
        scope = dict(self.scope)
        allowed_scope = {"campaign_id", "platform", "account_id", "paid"}
        if set(scope) - allowed_scope or "campaign_id" not in scope:
            raise DecisionOutcomesError("hypothesis.scope requires closed campaign_id scope")
        scope["campaign_id"] = _opaque_id(scope["campaign_id"], "hypothesis.scope.campaign_id")
        if "platform" in scope:
            scope["platform"] = _safe_name(scope["platform"], "hypothesis.scope.platform")
        if "account_id" in scope:
            scope["account_id"] = _opaque_id(scope["account_id"], "hypothesis.scope.account_id")
        if "paid" in scope and not isinstance(scope["paid"], bool):
            raise DecisionOutcomesError("hypothesis.scope.paid must be a boolean")
        object.__setattr__(self, "scope", _freeze_json(scope, label="hypothesis.scope"))
        object.__setattr__(self, "owner", _opaque_id(self.owner, "hypothesis.owner"))
        support = _digest_tuple(self.support, "hypothesis.support", required=True)
        counterexample = _digest_tuple(self.counterexample, "hypothesis.counterexample")
        if set(support) & set(counterexample):
            raise DecisionOutcomesError("hypothesis.support and counterexample must not overlap")
        object.__setattr__(self, "support", support)
        object.__setattr__(self, "counterexample", counterexample)
        created = _instant(self.created_at, "hypothesis.created_at")
        expires = _instant(self.expires_at, "hypothesis.expires_at")
        if _dt(expires) <= _dt(created):
            raise DecisionOutcomesError("hypothesis.expires_at must be after created_at")
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "expires_at", expires)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "target_metric": self.target_metric,
            "direction": self.direction,
            "comparison": self.comparison,
            "scope": _thaw_json(self.scope),
            "owner": self.owner,
            "support": list(self.support),
            "counterexample": list(self.counterexample),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True)
class EffectEstimate(_CanonicalModel):
    metric_name: str
    treatment_value: float
    control_value: float
    relative_delta: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_name", _safe_name(self.metric_name, "effect.metric_name"))
        object.__setattr__(
            self, "treatment_value", _number(self.treatment_value, "effect.treatment_value")
        )
        object.__setattr__(
            self, "control_value", _number(self.control_value, "effect.control_value")
        )
        object.__setattr__(
            self, "relative_delta", _number(self.relative_delta, "effect.relative_delta")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "treatment_value": self.treatment_value,
            "control_value": self.control_value,
            "relative_delta": self.relative_delta,
        }


@dataclass(frozen=True)
class LearningEvaluation(_CanonicalModel):
    hypothesis_id: str
    experiment_ids: tuple[str, ...]
    outcome_ids: tuple[str, ...]
    effect: EffectEstimate
    confounders: tuple[str, ...]
    verdict: LearningVerdict
    reviewer: str
    evaluated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "hypothesis_id", _opaque_id(self.hypothesis_id, "evaluation.hypothesis_id")
        )
        object.__setattr__(
            self, "experiment_ids", _id_tuple(self.experiment_ids, "evaluation.experiment_ids")
        )
        object.__setattr__(
            self, "outcome_ids", _id_tuple(self.outcome_ids, "evaluation.outcome_ids")
        )
        if not isinstance(self.effect, EffectEstimate):
            raise DecisionOutcomesError("evaluation.effect is invalid")
        if not isinstance(self.confounders, tuple):
            raise DecisionOutcomesError("evaluation.confounders must be a tuple")
        object.__setattr__(
            self,
            "confounders",
            tuple(
                sorted(
                    {
                        _text(item, "evaluation.confounders", maximum=240)
                        for item in self.confounders
                    }
                )
            ),
        )
        if self.verdict not in _VERDICTS:
            raise DecisionOutcomesError("evaluation.verdict is not allowed")
        object.__setattr__(self, "reviewer", _opaque_id(self.reviewer, "evaluation.reviewer"))
        object.__setattr__(
            self, "evaluated_at", _instant(self.evaluated_at, "evaluation.evaluated_at")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "experiment_ids": list(self.experiment_ids),
            "outcome_ids": list(self.outcome_ids),
            "effect": self.effect.to_dict(),
            "confounders": list(self.confounders),
            "verdict": self.verdict,
            "reviewer": self.reviewer,
            "evaluated_at": self.evaluated_at,
        }


@dataclass(frozen=True)
class OutcomeStatPolicy(_CanonicalModel):
    """Closed, versioned statistical gate for a performance-derived policy.

    The gate intentionally uses the Newcombe (Wilson score) confidence
    interval for the absolute difference of two binomial rates.  It is fully
    deterministic, needs only the standard library, and is deliberately more
    conservative than trusting a reviewer-supplied point estimate.
    """

    schema_version: Literal["1.0"]
    policy_version: str
    expires_at: str
    min_denominator_per_arm: int
    min_independent_experiments: int
    min_absolute_lift: float
    interval_method: Literal["newcombe_wilson_95"]
    preregistered_metrics: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise DecisionOutcomesError("unsupported outcome statistical policy schema")
        object.__setattr__(
            self, "policy_version", _version(self.policy_version, "stat_policy.policy_version")
        )
        object.__setattr__(self, "expires_at", _instant(self.expires_at, "stat_policy.expires_at"))
        for field in ("min_denominator_per_arm", "min_independent_experiments"):
            value = getattr(self, field)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
                or value > 10_000_000
            ):
                raise DecisionOutcomesError(
                    f"stat_policy.{field} must be a bounded positive integer"
                )
        if self.min_independent_experiments < 2:
            raise DecisionOutcomesError(
                "stat_policy.min_independent_experiments must be at least two"
            )
        lift = _number(self.min_absolute_lift, "stat_policy.min_absolute_lift", minimum=0.0)
        if lift <= 0.0 or lift > 1.0:
            raise DecisionOutcomesError("stat_policy.min_absolute_lift must be in (0, 1]")
        object.__setattr__(self, "min_absolute_lift", lift)
        if self.interval_method not in _STATISTICAL_INTERVAL_METHODS:
            raise DecisionOutcomesError("stat_policy.interval_method is not supported")
        if not isinstance(self.preregistered_metrics, tuple):
            raise DecisionOutcomesError("stat_policy.preregistered_metrics must be a tuple")
        metrics = tuple(
            sorted(
                _safe_name(item, "stat_policy.preregistered_metrics")
                for item in self.preregistered_metrics
            )
        )
        if not metrics:
            raise DecisionOutcomesError("stat_policy.preregistered_metrics cannot be empty")
        if len(metrics) != len(set(metrics)):
            raise DecisionOutcomesError("stat_policy.preregistered_metrics must be unique")
        object.__setattr__(self, "preregistered_metrics", metrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "expires_at": self.expires_at,
            "min_denominator_per_arm": self.min_denominator_per_arm,
            "min_independent_experiments": self.min_independent_experiments,
            "min_absolute_lift": self.min_absolute_lift,
            "interval_method": self.interval_method,
            "preregistered_metrics": list(self.preregistered_metrics),
        }


@dataclass(frozen=True)
class PromotionEligibility(_CanonicalModel):
    eligible: bool
    verdict: LearningVerdict
    reasons: tuple[str, ...]
    policy_version: str | None
    policy_expires_at: str | None
    human_reviewer: str | None
    outcome_stat_policy_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.eligible, bool):
            raise DecisionOutcomesError("promotion.eligible must be a boolean")
        if self.verdict not in _VERDICTS or not isinstance(self.reasons, tuple):
            raise DecisionOutcomesError("promotion result is invalid")
        reasons = tuple(
            sorted({_text(item, "promotion.reasons", maximum=240) for item in self.reasons})
        )
        object.__setattr__(self, "reasons", reasons)
        if self.eligible != (self.verdict == "supported" and not reasons):
            raise DecisionOutcomesError("promotion.eligible conflicts with verdict or reasons")
        if self.policy_version is not None:
            object.__setattr__(
                self, "policy_version", _version(self.policy_version, "promotion.policy_version")
            )
        if self.policy_expires_at is not None:
            object.__setattr__(
                self,
                "policy_expires_at",
                _instant(self.policy_expires_at, "promotion.policy_expires_at"),
            )
        if self.human_reviewer is not None:
            object.__setattr__(
                self,
                "human_reviewer",
                _opaque_id(self.human_reviewer, "promotion.human_reviewer"),
            )
        if self.outcome_stat_policy_digest is not None:
            object.__setattr__(
                self,
                "outcome_stat_policy_digest",
                _digest(self.outcome_stat_policy_digest, "promotion.outcome_stat_policy_digest"),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "policy_version": self.policy_version,
            "policy_expires_at": self.policy_expires_at,
            "human_reviewer": self.human_reviewer,
            "outcome_stat_policy_digest": self.outcome_stat_policy_digest,
        }


def _scope_matches(hypothesis: LearningHypothesis, experiment: EditorialExperiment) -> bool:
    scope = _thaw_json(hypothesis.scope)
    return all(
        scope.get(key, getattr(experiment, key)) == getattr(experiment, key) for key in scope
    )


def _effect_matches(
    effect: EffectEstimate, control: tuple[float, float], treatment: tuple[float, float]
) -> bool:
    control_rate = control[0] / control[1]
    treatment_rate = treatment[0] / treatment[1]
    relative = (treatment_rate - control_rate) / control_rate if control_rate else 0.0
    return (
        math.isclose(effect.control_value, control_rate, rel_tol=1e-9, abs_tol=1e-12)
        and math.isclose(effect.treatment_value, treatment_rate, rel_tol=1e-9, abs_tol=1e-12)
        and math.isclose(effect.relative_delta, relative, rel_tol=1e-9, abs_tol=1e-12)
    )


def _direction_matches(direction: LearningDirection, relative_delta: float) -> bool:
    if direction == "increase":
        return relative_delta > 1e-12
    if direction == "decrease":
        return relative_delta < -1e-12
    return math.isclose(relative_delta, 0.0, abs_tol=1e-12)


_WILSON_95_Z = 1.959963984540054


def _wilson_interval(successes: float, observations: float) -> tuple[float, float]:
    """Two-sided 95% Wilson score interval, calculated in stdlib math only."""
    if observations <= 0:
        raise DecisionOutcomesError("Wilson interval requires a positive denominator")
    proportion = successes / observations
    z_squared = _WILSON_95_Z * _WILSON_95_Z
    denominator = 1.0 + z_squared / observations
    center = (proportion + z_squared / (2.0 * observations)) / denominator
    radius = (
        _WILSON_95_Z
        * math.sqrt(
            (proportion * (1.0 - proportion) + z_squared / (4.0 * observations)) / observations
        )
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def _newcombe_wilson_difference_interval(
    treatment: tuple[float, float], control: tuple[float, float]
) -> tuple[float, float]:
    """Conservative 95% Newcombe interval for treatment-rate minus control-rate."""
    treatment_low, treatment_high = _wilson_interval(*treatment)
    control_low, control_high = _wilson_interval(*control)
    return treatment_low - control_high, treatment_high - control_low


def _provenance_chain_reasons(
    hypothesis: LearningHypothesis,
    experiments: Sequence[EditorialExperiment],
    outcomes: Sequence[OutcomeObservation],
    variant_provenances: Sequence[VariantProvenance] | None,
) -> list[str]:
    """Validate the optional modern Decision->Variant->Outcome binding.

    The first local outcome schema predates Director decision audits.  We can
    still read those legacy observations, but as soon as one chain field is
    present every link must be present and exact.  This avoids allowing a
    caller to mix a real provenance with a free-form outcome digest.
    """

    chain_started = (
        variant_provenances is not None
        or any(item.variant_provenance_digests for item in experiments)
        or any(item.variant_provenance_digest is not None for item in outcomes)
    )
    if not chain_started:
        return []
    if variant_provenances is None:
        return ["missing complete variant provenance set"]
    if not isinstance(variant_provenances, Sequence) or isinstance(
        variant_provenances, (str, bytes, bytearray)
    ):
        raise DecisionOutcomesError("variant_provenances must be a sequence")
    if not all(isinstance(item, VariantProvenance) for item in variant_provenances):
        raise DecisionOutcomesError("variant_provenances contains an invalid artifact")
    provenance_by_id = {item.variant_id: item for item in variant_provenances}
    if len(provenance_by_id) != len(variant_provenances):
        raise DecisionOutcomesError("variant_provenances must have unique variant_id values")

    expected_ids = [variant for experiment in experiments for variant in experiment.variants]
    if len(expected_ids) != len(set(expected_ids)):
        return ["evaluated experiments repeat a variant ID"]
    expected = set(expected_ids)
    reasons: list[str] = []
    if set(provenance_by_id) != expected:
        reasons.append("variant provenance set must exactly cover evaluated experiment variants")

    scope_campaign = _thaw_json(hypothesis.scope)["campaign_id"]
    for experiment in experiments:
        bindings = experiment.variant_provenance_digests
        if set(bindings) != set(experiment.variants):
            reasons.append(
                "experiment "
                f"{experiment.experiment_id} is missing exact variant provenance bindings"
            )
            continue
        paired: list[VariantProvenance] = []
        for variant_id in experiment.variants:
            provenance = provenance_by_id.get(variant_id)
            if provenance is None:
                continue
            paired.append(provenance)
            if provenance.canonical_digest != bindings[variant_id]:
                reasons.append("experiment variant provenance digest does not match artifact")
            if (
                provenance.campaign_id != experiment.campaign_id
                or provenance.campaign_id != scope_campaign
            ):
                reasons.append(
                    "variant provenance campaign does not match experiment or hypothesis"
                )
            if (
                provenance.snapshot_digest is None
                or provenance.context_issuance_id is None
                or provenance.decision_audit_digest is None
            ):
                reasons.append("variant provenance is missing decision audit bindings")
        if len(paired) == 2 and len({item.source_id for item in paired}) != 1:
            reasons.append("experiment variants do not share a source provenance")

    for outcome in outcomes:
        provenance = provenance_by_id.get(outcome.variant_id)
        if provenance is None:
            reasons.append("outcome variant does not have supplied provenance")
        elif outcome.variant_provenance_digest != provenance.canonical_digest:
            reasons.append("outcome provenance digest does not match its variant")
    return reasons


def promotion_eligibility(
    hypothesis: LearningHypothesis,
    evaluation: LearningEvaluation,
    experiments: Sequence[EditorialExperiment],
    outcomes: Sequence[OutcomeObservation],
    *,
    policy_version: str | None,
    policy_expires_at: str | None,
    human_reviewer: str | None,
    now: datetime,
    variant_provenances: Sequence[VariantProvenance] | None = None,
    outcome_stat_policy: OutcomeStatPolicy | None = None,
) -> PromotionEligibility:
    """Return a deterministic, fail-closed policy decision without mutating knowledge.

    Legacy inputs remain diagnostic-only: without a closed statistical policy
    this function returns an ineligible result. A promotion is calculated from
    raw ratio observations, never from a reviewer-supplied point estimate.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise DecisionOutcomesError("now must include a timezone")
    reasons: list[str] = []
    normalized_version = _version(policy_version, "policy_version") if policy_version else None
    normalized_expiry = (
        _instant(policy_expires_at, "policy_expires_at") if policy_expires_at else None
    )
    reviewer = _opaque_id(human_reviewer, "human_reviewer") if human_reviewer else None
    stat_policy_digest: str | None = None
    if outcome_stat_policy is None:
        reasons.append("missing outcome statistical policy")
    elif not isinstance(outcome_stat_policy, OutcomeStatPolicy):
        raise DecisionOutcomesError("outcome_stat_policy is invalid")
    else:
        stat_policy_digest = outcome_stat_policy.canonical_digest
        if normalized_version != outcome_stat_policy.policy_version:
            reasons.append("policy version does not match outcome statistical policy")
        if normalized_expiry != outcome_stat_policy.expires_at:
            reasons.append("policy expiry does not match outcome statistical policy")
        if _dt(outcome_stat_policy.expires_at) <= now.astimezone(UTC):
            reasons.append("expired outcome statistical policy")
    if normalized_version is None:
        reasons.append("missing policy version")
    if normalized_expiry is None:
        reasons.append("missing policy expiry")
    elif _dt(normalized_expiry) <= now.astimezone(UTC):
        reasons.append("expired policy")
    if reviewer is None:
        reasons.append("missing human reviewer")
    elif reviewer != evaluation.reviewer:
        reasons.append("human reviewer must equal evaluation reviewer")
    if evaluation.hypothesis_id != hypothesis.hypothesis_id:
        reasons.append("evaluation hypothesis does not match")
    if _dt(hypothesis.expires_at) <= now.astimezone(UTC):
        reasons.append("hypothesis expired")
    if hypothesis.comparison == "historical_baseline":
        reasons.append("historical baseline is inconclusive")
    if evaluation.verdict != "supported":
        reasons.append("evaluation verdict is not supported")
    if evaluation.confounders:
        reasons.append("evaluation has confounders")

    experiment_by_id = {item.experiment_id: item for item in experiments}
    if len(experiment_by_id) != len(experiments):
        raise DecisionOutcomesError("experiments must have unique experiment_id values")
    selected = [
        experiment_by_id[item] for item in evaluation.experiment_ids if item in experiment_by_id
    ]
    if len(selected) != len(evaluation.experiment_ids):
        reasons.append("evaluation references unknown experiment")
    if len(selected) < 2:
        reasons.append("requires at least two experiments")
    if selected:
        key = (
            selected[0].campaign_id,
            selected[0].objective,
            selected[0].platform,
            selected[0].account_id,
            selected[0].primary_metric,
            selected[0].paid,
        )
        for experiment in selected:
            if (
                experiment.campaign_id,
                experiment.objective,
                experiment.platform,
                experiment.account_id,
                experiment.primary_metric,
                experiment.paid,
            ) != key:
                reasons.append("experiments are not comparable")
            if experiment.primary_metric != hypothesis.target_metric or not _scope_matches(
                hypothesis, experiment
            ):
                reasons.append("experiment does not match hypothesis scope or target")
            if _dt(hypothesis.created_at) > _dt(experiment.registered_at):
                reasons.append("hypothesis was created after experiment registration")
        if (
            len({item.source_asset_digest for item in selected}) < 2
            and len({item.cohort for item in selected}) < 2
        ):
            reasons.append("experiments are not independent")
        if evaluation.effect.metric_name != selected[0].primary_metric:
            reasons.append("effect metric does not match primary metric")

    outcome_by_id = {item.outcome_id: item for item in outcomes}
    if len(outcome_by_id) != len(outcomes):
        raise DecisionOutcomesError("outcomes must have unique outcome_id values")
    selected_outcomes = [
        outcome_by_id[item] for item in evaluation.outcome_ids if item in outcome_by_id
    ]
    if len(selected_outcomes) != len(evaluation.outcome_ids):
        reasons.append("evaluation references unknown outcome")
    reasons.extend(
        _provenance_chain_reasons(
            hypothesis,
            selected,
            selected_outcomes,
            variant_provenances,
        )
    )
    selected_ids = {item.experiment_id for item in selected}
    totals: dict[str, list[float]] = {"control": [0.0, 0.0], "treatment": [0.0, 0.0]}
    arms_by_experiment: dict[str, set[str]] = {item.experiment_id: set() for item in selected}
    arm_counts: dict[tuple[str, str], int] = {}
    arm_outcomes: dict[tuple[str, str], OutcomeObservation] = {}
    outcome_keys: set[tuple[str, str, str]] = set()
    for outcome in selected_outcomes:
        experiment = experiment_by_id.get(outcome.experiment_id)
        if experiment is None or outcome.experiment_id not in selected_ids:
            reasons.append("outcome does not belong to an evaluated experiment")
            continue
        arm = experiment.assignment.get(outcome.variant_id)
        outcome_key = (outcome.experiment_id, outcome.variant_id, outcome.metric_name)
        if outcome_key in outcome_keys:
            reasons.append("multiple outcomes for the same experiment variant metric")
        outcome_keys.add(outcome_key)
        if (
            arm is None
            or outcome.metric_name != experiment.primary_metric
            or outcome.platform != experiment.platform
            or outcome.account_id != experiment.account_id
            or outcome.delivery_mode != ("paid" if experiment.paid else "organic")
        ):
            reasons.append("outcome context does not match experiment preregistration")
        if (
            _dt(outcome.window_start) < _dt(experiment.posting_window_start)
            or _dt(outcome.window_end) < _dt(experiment.posting_window_end)
            or _dt(outcome.observed_at) < _dt(experiment.posting_window_end)
        ):
            reasons.append("outcome dates do not follow experiment window")
        if outcome.denominator is None or outcome.numerator is None:
            reasons.append("outcome requires a ratio denominator")
            continue
        if outcome.trust not in {"verified", "human_reviewed"}:
            reasons.append("outcome trust is insufficient")
        if outcome.qc_guardrail != "pass" or outcome.claim_guardrail != "pass":
            reasons.append("outcome guardrail did not pass")
        if outcome.is_historical and outcome.delivery_mode == "organic":
            reasons.append("historical baseline or organic outcome is inconclusive")
        if arm is not None:
            totals[arm][0] += outcome.numerator
            totals[arm][1] += outcome.denominator
            arms_by_experiment[experiment.experiment_id].add(arm)
            arm_key = (experiment.experiment_id, arm)
            arm_counts[arm_key] = arm_counts.get(arm_key, 0) + 1
            arm_outcomes[arm_key] = outcome
    if not selected_outcomes:
        reasons.append("requires evaluated outcomes")
    if any(_dt(evaluation.evaluated_at) < _dt(item.observed_at) for item in selected_outcomes):
        reasons.append("evaluation precedes an outcome observation")
    if _dt(evaluation.evaluated_at) > now.astimezone(UTC):
        reasons.append("evaluation is after now")
    for experiment_id, arms in arms_by_experiment.items():
        if arms != {"control", "treatment"}:
            reasons.append(f"experiment {experiment_id} lacks control or treatment outcome")
        if any(arm_counts.get((experiment_id, arm), 0) != 1 for arm in ("control", "treatment")):
            reasons.append(f"experiment {experiment_id} requires exactly one outcome per arm")
    if totals["control"][1] == 0 or totals["treatment"][1] == 0:
        reasons.append("requires control and treatment ratio denominators")
    elif totals["control"][0] == 0:
        reasons.append("control rate is zero and relative effect is undefined")
    else:
        control_rate = totals["control"][0] / totals["control"][1]
        treatment_rate = totals["treatment"][0] / totals["treatment"][1]
        relative_delta = (treatment_rate - control_rate) / control_rate
        if not _effect_matches(
            evaluation.effect, tuple(totals["control"]), tuple(totals["treatment"])
        ):
            reasons.append("effect does not match aggregated outcome rates")
        if not _direction_matches(hypothesis.direction, relative_delta):
            reasons.append("effect direction does not match hypothesis")

        if outcome_stat_policy is not None:
            preregistered = set(outcome_stat_policy.preregistered_metrics)
            observed_metrics = {item.metric_name for item in selected_outcomes}
            if (
                hypothesis.target_metric not in preregistered
                or evaluation.effect.metric_name not in preregistered
                or not observed_metrics.issubset(preregistered)
            ):
                reasons.append("metric is not preregistered by outcome statistical policy")
            independent_experiments = {(item.source_asset_digest, item.cohort) for item in selected}
            if len(independent_experiments) < outcome_stat_policy.min_independent_experiments:
                reasons.append(
                    "insufficient independent experiments for outcome statistical policy"
                )
            for experiment in selected:
                for arm in ("control", "treatment"):
                    observed = arm_outcomes.get((experiment.experiment_id, arm))
                    if observed is None:
                        continue
                    if (
                        observed.denominator is None
                        or observed.denominator < outcome_stat_policy.min_denominator_per_arm
                    ):
                        reasons.append(
                            "outcome denominator is below outcome statistical policy minimum"
                        )
                    if (
                        observed.numerator is None
                        or observed.denominator is None
                        or not observed.numerator.is_integer()
                        or not observed.denominator.is_integer()
                    ):
                        reasons.append(
                            "outcome ratio counts must be whole observations for statistical policy"
                        )
            absolute_lift = treatment_rate - control_rate
            interval_low, interval_high = _newcombe_wilson_difference_interval(
                tuple(totals["treatment"]), tuple(totals["control"])
            )
            if interval_low <= 0.0 <= interval_high:
                reasons.append("statistical interval includes zero")
            if hypothesis.direction == "increase":
                if absolute_lift < outcome_stat_policy.min_absolute_lift:
                    reasons.append("absolute lift is below outcome statistical policy minimum")
            elif hypothesis.direction == "decrease":
                if -absolute_lift < outcome_stat_policy.min_absolute_lift:
                    reasons.append("absolute lift is below outcome statistical policy minimum")
            else:
                reasons.append("outcome statistical policy cannot promote a no_effect hypothesis")

    reasons = sorted(set(reasons))
    verdict: LearningVerdict = (
        "inconclusive"
        if any("inconclusive" in reason for reason in reasons)
        else evaluation.verdict
    )
    return PromotionEligibility(
        eligible=not reasons and verdict == "supported",
        verdict=verdict,
        reasons=tuple(reasons),
        policy_version=normalized_version,
        policy_expires_at=normalized_expiry,
        human_reviewer=reviewer,
        outcome_stat_policy_digest=stat_policy_digest,
    )


evaluate_promotion_eligibility = promotion_eligibility
can_promote_learning = promotion_eligibility
