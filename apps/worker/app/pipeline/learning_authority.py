"""Short-lived, signed authority for a learning-to-policy promotion.

``PromotionEligibility`` and ``LearningEvaluation`` are useful immutable value
objects, but they are intentionally public dataclasses.  They are therefore
not sufficient proof that a caller actually ran the promotion gate over the
complete set of experiments and outcomes.  This module provides that missing
boundary without introducing a database, a runner dependency, or a network
call: an issuer recomputes the gate and signs a compact, canonical manifest;
the consumer verifies both the signature and every source artifact before it
may hand the eligibility to governance.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

from .decision_outcomes import (
    EditorialExperiment,
    LearningEvaluation,
    LearningHypothesis,
    OutcomeObservation,
    OutcomeStatPolicy,
    PromotionEligibility,
    VariantProvenance,
    canonical_json,
    promotion_eligibility,
    stable_digest,
)
from .decision_provenance import (
    IssuedVariantProvenance,
    VariantProvenanceVerifier,
    verify_issued_variant_provenance,
)
from .learning_registration import (
    ImportedOutcomeEnvelope,
    LearningRegistrationEnvelope,
    OutcomeAdapterVerifier,
    RegistrationVerifier,
    verify_imported_outcomes,
    verify_learning_registration,
)
from .learning_evaluation_authority import (
    IssuedLearningEvaluationReview,
    LearningEvaluationReviewVerifier,
    verify_learning_evaluation_review,
)

AUTHORITY_SCHEMA_VERSION = "1.0"
MAX_AUTHORITY_TTL = timedelta(hours=24)
MAX_AUTHORITY_EXPERIMENTS = 32
MAX_AUTHORITY_OUTCOMES = 64
MAX_AUTHORITY_VARIANT_PROVENANCES = 64

_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SIGNATURE_RE = re.compile(r"^[a-f0-9]{64}$")


class LearningAuthorityError(ValueError):
    """A signed promotion authority is malformed, stale, or untrustworthy."""


@runtime_checkable
class AuthoritySigner(Protocol):
    """Signs canonical bytes; implementations must never serialize key material."""

    @property
    def key_id(self) -> str: ...

    def sign(self, payload: bytes) -> str: ...


@runtime_checkable
class AuthorityVerifier(Protocol):
    """Verifies canonical bytes signed by the corresponding trusted key."""

    @property
    def key_id(self) -> str: ...

    def verify(self, payload: bytes, signature: str) -> bool: ...


class HmacSha256Authority:
    """Local HMAC-SHA256 signer/verifier for development and worker-local use."""

    def __init__(self, *, key_id: str, secret: bytes) -> None:
        self._key_id = _key_id(key_id)
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise LearningAuthorityError("HMAC secret must contain at least 32 bytes")
        self._secret = secret

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, payload: bytes) -> str:
        if not isinstance(payload, bytes):
            raise LearningAuthorityError("authority payload must be bytes")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        if not isinstance(payload, bytes) or not isinstance(signature, str):
            return False
        expected = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


def _text(value: object, label: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise LearningAuthorityError(f"{label} must be a string")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        raise LearningAuthorityError(f"{label} cannot be empty")
    if len(normalized) > maximum:
        raise LearningAuthorityError(f"{label} exceeds {maximum} characters")
    return normalized


def _opaque_id(value: object, label: str) -> str:
    value = _text(value, label, maximum=128)
    if not _OPAQUE_ID_RE.fullmatch(value):
        raise LearningAuthorityError(f"{label} must be a bounded opaque identifier")
    return value


def _key_id(value: object) -> str:
    value = _text(value, "key_id", maximum=64)
    if not _KEY_ID_RE.fullmatch(value):
        raise LearningAuthorityError("key_id is invalid")
    return value


def _signature(value: object) -> str:
    value = _text(value, "signature", maximum=64).lower()
    if not _SIGNATURE_RE.fullmatch(value):
        raise LearningAuthorityError("signature must be an HMAC-SHA256 hex digest")
    return value


def _digest(value: object, label: str) -> str:
    value = _text(value, label, maximum=64).lower()
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise LearningAuthorityError(f"{label} must be an SHA-256 hex digest")
    return value


def _instant(value: object, label: str) -> str:
    value = _text(value, label, maximum=40)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LearningAuthorityError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LearningAuthorityError(f"{label} must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _now(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LearningAuthorityError("now must be a timezone-aware datetime")
    return value.astimezone(UTC).replace(microsecond=0)


def _artifact_tuple(
    values: object,
    artifact_type: type[EditorialExperiment] | type[OutcomeObservation],
    attribute: str,
    label: str,
) -> tuple[EditorialExperiment, ...] | tuple[OutcomeObservation, ...]:
    if not isinstance(values, tuple):
        raise LearningAuthorityError(f"{label} must be a tuple")
    if not values:
        raise LearningAuthorityError(f"{label} cannot be empty")
    maximum = MAX_AUTHORITY_EXPERIMENTS if label == "experiments" else MAX_AUTHORITY_OUTCOMES
    if len(values) > maximum:
        raise LearningAuthorityError(f"{label} exceeds the hard artifact limit")
    if not all(isinstance(value, artifact_type) for value in values):
        raise LearningAuthorityError(f"{label} contains an invalid artifact")
    identifiers = tuple(getattr(value, attribute) for value in values)
    if identifiers != tuple(sorted(identifiers)):
        raise LearningAuthorityError(f"{label} must be in canonical identifier order")
    if len(identifiers) != len(set(identifiers)):
        raise LearningAuthorityError(f"{label} cannot contain duplicate identifiers")
    return values


def _issued_provenance_tuple(
    values: object,
    *,
    required: bool = False,
) -> tuple[IssuedVariantProvenance, ...]:
    """Accept signed envelopes, never importable Python-token capabilities."""
    if not isinstance(values, tuple):
        raise LearningAuthorityError("issued_variant_provenances must be a tuple")
    if len(values) > MAX_AUTHORITY_VARIANT_PROVENANCES:
        raise LearningAuthorityError("issued_variant_provenances exceeds the hard artifact limit")
    if required and not values:
        raise LearningAuthorityError("issued_variant_provenances cannot be empty for promotion")
    if not all(isinstance(value, IssuedVariantProvenance) for value in values):
        raise LearningAuthorityError(
            "issued_variant_provenances must contain signed variant envelopes"
        )
    identifiers = tuple(value.provenance.variant_id for value in values)
    if identifiers != tuple(sorted(identifiers)):
        raise LearningAuthorityError(
            "issued_variant_provenances must be in canonical identifier order"
        )
    if len(identifiers) != len(set(identifiers)):
        raise LearningAuthorityError(
            "issued_variant_provenances cannot contain duplicate identifiers"
        )
    return values


def _serialized_provenance_tuple(
    values: object,
    *,
    required: bool = False,
) -> tuple[VariantProvenance, ...]:
    """Validate raw provenance only after it has crossed the signed boundary."""
    if not isinstance(values, tuple):
        raise LearningAuthorityError("variant_provenances must be a tuple")
    if len(values) > MAX_AUTHORITY_VARIANT_PROVENANCES:
        raise LearningAuthorityError("variant_provenances exceeds the hard artifact limit")
    if required and not values:
        raise LearningAuthorityError("variant_provenances cannot be empty for promotion")
    if not all(isinstance(value, VariantProvenance) for value in values):
        raise LearningAuthorityError("variant_provenances contains an invalid artifact")
    identifiers = tuple(value.variant_id for value in values)
    if identifiers != tuple(sorted(identifiers)):
        raise LearningAuthorityError("variant_provenances must be in canonical identifier order")
    if len(identifiers) != len(set(identifiers)):
        raise LearningAuthorityError("variant_provenances cannot contain duplicate identifiers")
    return values


def _validate_artifact_set(
    hypothesis: LearningHypothesis,
    evaluation: LearningEvaluation,
    experiments: tuple[EditorialExperiment, ...],
    outcomes: tuple[OutcomeObservation, ...],
    campaign_id: str,
    variant_provenances: tuple[VariantProvenance, ...],
) -> None:
    if not isinstance(hypothesis, LearningHypothesis):
        raise LearningAuthorityError("hypothesis is invalid")
    if not isinstance(evaluation, LearningEvaluation):
        raise LearningAuthorityError("evaluation is invalid")
    if evaluation.hypothesis_id != hypothesis.hypothesis_id:
        raise LearningAuthorityError("evaluation does not target the hypothesis")
    if hypothesis.scope.get("campaign_id") != campaign_id:
        raise LearningAuthorityError("campaign_id does not match the hypothesis scope")
    experiment_ids = tuple(item.experiment_id for item in experiments)
    outcome_ids = tuple(item.outcome_id for item in outcomes)
    if experiment_ids != evaluation.experiment_ids:
        raise LearningAuthorityError("experiments must exactly match evaluation experiment_ids")
    if outcome_ids != evaluation.outcome_ids:
        raise LearningAuthorityError("outcomes must exactly match evaluation outcome_ids")
    if any(item.campaign_id != campaign_id for item in experiments):
        raise LearningAuthorityError("experiment campaign_id does not match authority campaign")
    experiment_by_id = {item.experiment_id: item for item in experiments}
    if any(item.experiment_id not in experiment_by_id for item in outcomes):
        raise LearningAuthorityError("outcome references an unknown experiment")
    if any(item.campaign_id != campaign_id for item in variant_provenances):
        raise LearningAuthorityError(
            "variant provenance campaign_id does not match authority campaign"
        )


@dataclass(frozen=True)
class PromotionAuthorityEnvelope:
    """Immutable complete artifact bundle plus a signature over canonical digests.

    The bundle may be persisted or transported, but its ``to_dict`` output
    intentionally contains no secret or key bytes. Artifact bodies remain in
    the envelope so a verifier can recompute the gate rather than trusting a
    stale boolean or an unbound digest list. They are audit data, never prompt
    context, and remain subject to tenant access control in a future adapter.
    """

    schema_version: str
    authority_id: str
    key_id: str
    tenant_id: str
    campaign_id: str
    hypothesis: LearningHypothesis
    evaluation: LearningEvaluation
    evaluation_review_digest: str
    experiments: tuple[EditorialExperiment, ...]
    outcomes: tuple[OutcomeObservation, ...]
    variant_provenances: tuple[VariantProvenance, ...]
    outcome_stat_policy: OutcomeStatPolicy
    outcome_stat_policy_digest: str
    eligibility: PromotionEligibility
    issued_at: str
    expires_at: str
    signature: str

    def __post_init__(self) -> None:
        if self.schema_version != AUTHORITY_SCHEMA_VERSION:
            raise LearningAuthorityError("unsupported learning authority schema version")
        object.__setattr__(self, "authority_id", _opaque_id(self.authority_id, "authority_id"))
        object.__setattr__(self, "key_id", _key_id(self.key_id))
        object.__setattr__(self, "tenant_id", _opaque_id(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "campaign_id", _opaque_id(self.campaign_id, "campaign_id"))
        experiments = _artifact_tuple(
            self.experiments,
            EditorialExperiment,
            "experiment_id",
            "experiments",
        )
        outcomes = _artifact_tuple(self.outcomes, OutcomeObservation, "outcome_id", "outcomes")
        provenances = _serialized_provenance_tuple(self.variant_provenances, required=True)
        object.__setattr__(self, "experiments", experiments)
        object.__setattr__(self, "outcomes", outcomes)
        object.__setattr__(self, "variant_provenances", provenances)
        _validate_artifact_set(
            self.hypothesis,
            self.evaluation,
            experiments,
            outcomes,
            self.campaign_id,
            provenances,
        )
        object.__setattr__(
            self,
            "evaluation_review_digest",
            _digest(self.evaluation_review_digest, "evaluation_review_digest"),
        )
        if not isinstance(self.outcome_stat_policy, OutcomeStatPolicy):
            raise LearningAuthorityError("outcome_stat_policy is invalid")
        object.__setattr__(
            self,
            "outcome_stat_policy_digest",
            _digest(self.outcome_stat_policy_digest, "outcome_stat_policy_digest"),
        )
        if self.outcome_stat_policy_digest != self.outcome_stat_policy.canonical_digest:
            raise LearningAuthorityError(
                "outcome_stat_policy_digest does not match statistical policy"
            )
        if not isinstance(self.eligibility, PromotionEligibility):
            raise LearningAuthorityError("eligibility is invalid")
        if self.eligibility.policy_version != self.outcome_stat_policy.policy_version:
            raise LearningAuthorityError(
                "eligibility policy version does not match statistical policy"
            )
        if self.eligibility.policy_expires_at != self.outcome_stat_policy.expires_at:
            raise LearningAuthorityError(
                "eligibility policy expiry does not match statistical policy"
            )
        if self.eligibility.outcome_stat_policy_digest != self.outcome_stat_policy_digest:
            raise LearningAuthorityError("eligibility does not bind the statistical policy digest")
        object.__setattr__(self, "issued_at", _instant(self.issued_at, "issued_at"))
        object.__setattr__(self, "expires_at", _instant(self.expires_at, "expires_at"))
        if _datetime(self.expires_at) <= _datetime(self.issued_at):
            raise LearningAuthorityError("authority expiry must follow issuance")
        if _datetime(self.expires_at) - _datetime(self.issued_at) > MAX_AUTHORITY_TTL:
            raise LearningAuthorityError("authority TTL must not exceed 24 hours")
        if self.eligibility.policy_expires_at is None:
            raise LearningAuthorityError("authority eligibility requires a policy expiry")
        if _datetime(self.expires_at) > _datetime(self.eligibility.policy_expires_at):
            raise LearningAuthorityError("authority cannot outlive the signed policy expiry")
        object.__setattr__(self, "signature", _signature(self.signature))

    @property
    def scope_digest(self) -> str:
        return stable_digest(self.hypothesis.to_dict()["scope"])

    @property
    def signature_payload(self) -> dict[str, object]:
        return {
            "authority_id": self.authority_id,
            "campaign_id": self.campaign_id,
            "eligibility_digest": self.eligibility.canonical_digest,
            "evaluation_digest": self.evaluation.canonical_digest,
            "evaluation_review_digest": self.evaluation_review_digest,
            "experiment_digests": [item.canonical_digest for item in self.experiments],
            "expires_at": self.expires_at,
            "hypothesis_digest": self.hypothesis.canonical_digest,
            "issued_at": self.issued_at,
            "key_id": self.key_id,
            "outcome_digests": [item.canonical_digest for item in self.outcomes],
            "outcome_stat_policy_digest": self.outcome_stat_policy_digest,
            "variant_provenance_digests": [
                item.canonical_digest for item in self.variant_provenances
            ],
            "schema_version": self.schema_version,
            "scope_digest": self.scope_digest,
            "tenant_id": self.tenant_id,
        }

    @property
    def signing_bytes(self) -> bytes:
        return canonical_json(self.signature_payload).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        """Safe serialization; it includes signature, never the HMAC secret."""
        return {
            "schema_version": self.schema_version,
            "authority_id": self.authority_id,
            "key_id": self.key_id,
            "tenant_id": self.tenant_id,
            "campaign_id": self.campaign_id,
            "hypothesis": self.hypothesis.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "evaluation_review_digest": self.evaluation_review_digest,
            "experiments": [item.to_dict() for item in self.experiments],
            "outcomes": [item.to_dict() for item in self.outcomes],
            "outcome_stat_policy": self.outcome_stat_policy.to_dict(),
            "outcome_stat_policy_digest": self.outcome_stat_policy_digest,
            "variant_provenances": [item.to_dict() for item in self.variant_provenances],
            "eligibility": self.eligibility.to_dict(),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "signature": self.signature,
        }


def issue_promotion_authority(
    signer: AuthoritySigner,
    *,
    authority_id: str,
    tenant_id: str,
    campaign_id: str,
    evaluation_review: IssuedLearningEvaluationReview,
    evaluation_review_verifier: LearningEvaluationReviewVerifier,
    issued_at: datetime,
    expires_at: str,
    registration: LearningRegistrationEnvelope,
    registration_verifier: RegistrationVerifier,
    imported_outcomes: ImportedOutcomeEnvelope,
    outcome_adapter_verifier: OutcomeAdapterVerifier,
    variant_provenance_verifier: VariantProvenanceVerifier,
    variant_owner_id: str,
) -> PromotionAuthorityEnvelope:
    """Promote only a signed preregistration plus verified adapter outcomes.

    Public ``LearningHypothesis``, ``EditorialExperiment``,
    ``OutcomeObservation``, ``OutcomeStatPolicy`` and ``LearningEvaluation``
    dataclasses deliberately do not appear in this interface.  They may be
    inspected elsewhere, but a caller cannot backdate or selectively assemble
    them at this authority boundary.  The human evaluation must first cross a
    separate signed review boundary tied to this exact registration and import.
    """

    if not isinstance(signer, AuthoritySigner):
        raise LearningAuthorityError("signer must implement AuthoritySigner")
    issued = _now(issued_at)
    issued_text = _instant(issued.isoformat(), "issued_at")
    normalized_campaign = _opaque_id(campaign_id, "campaign_id")
    normalized_expiry = _instant(expires_at, "expires_at")
    try:
        checked_registration = verify_learning_registration(
            registration,
            registration_verifier,
            tenant_id=tenant_id,
            campaign_id=normalized_campaign,
        )
        imported = verify_imported_outcomes(
            imported_outcomes,
            outcome_adapter_verifier,
            checked_registration,
            registration_verifier,
            tenant_id=tenant_id,
            campaign_id=normalized_campaign,
        )
        evaluation = verify_learning_evaluation_review(
            evaluation_review,
            evaluation_review_verifier,
            registration=checked_registration,
            registration_verifier=registration_verifier,
            imported_outcomes=imported_outcomes,
            outcome_adapter_verifier=outcome_adapter_verifier,
            tenant_id=tenant_id,
            campaign_id=normalized_campaign,
            now=issued,
        )
    except ValueError as exc:
        raise LearningAuthorityError(
            "signed registration, outcome import, or evaluation review verification failed"
        ) from exc
    hypothesis = checked_registration.hypothesis
    checked_experiments = _artifact_tuple(
        checked_registration.experiments,
        EditorialExperiment,
        "experiment_id",
        "experiments",
    )
    checked_outcomes = _artifact_tuple(imported, OutcomeObservation, "outcome_id", "outcomes")
    checked_envelopes = _issued_provenance_tuple(
        checked_registration.issued_variant_provenances,
        required=True,
    )
    if not hasattr(variant_provenance_verifier, "key_id") or not callable(
        getattr(variant_provenance_verifier, "verify", None)
    ):
        raise LearningAuthorityError("variant_provenance_verifier is invalid")
    normalized_variant_owner = _opaque_id(variant_owner_id, "variant_owner_id")
    try:
        checked_provenances = tuple(
            verify_issued_variant_provenance(
                item,
                variant_provenance_verifier,
                owner_id=normalized_variant_owner,
                campaign_id=normalized_campaign,
                now=issued_text,
                require_current=False,
            )
            for item in checked_envelopes
        )
    except ValueError as exc:
        raise LearningAuthorityError("signed variant provenance verification failed") from exc
    outcome_stat_policy = checked_registration.outcome_stat_policy
    _validate_artifact_set(
        hypothesis,
        evaluation,
        checked_experiments,
        checked_outcomes,
        normalized_campaign,
        checked_provenances,
    )
    eligibility = promotion_eligibility(
        hypothesis,
        evaluation,
        checked_experiments,
        checked_outcomes,
        policy_version=outcome_stat_policy.policy_version,
        policy_expires_at=outcome_stat_policy.expires_at,
        human_reviewer=evaluation.reviewer,
        now=issued,
        variant_provenances=checked_provenances,
        outcome_stat_policy=outcome_stat_policy,
    )
    if not eligibility.eligible:
        raise LearningAuthorityError("cannot issue authority for an ineligible promotion")
    unsigned = PromotionAuthorityEnvelope(
        schema_version=AUTHORITY_SCHEMA_VERSION,
        authority_id=authority_id,
        key_id=signer.key_id,
        tenant_id=tenant_id,
        campaign_id=normalized_campaign,
        hypothesis=hypothesis,
        evaluation=evaluation,
        evaluation_review_digest=evaluation_review.canonical_digest,
        experiments=checked_experiments,
        outcomes=checked_outcomes,
        outcome_stat_policy=outcome_stat_policy,
        outcome_stat_policy_digest=outcome_stat_policy.canonical_digest,
        eligibility=eligibility,
        issued_at=issued_text,
        expires_at=normalized_expiry,
        signature="0" * 64,
        variant_provenances=checked_provenances,
    )
    return PromotionAuthorityEnvelope(
        schema_version=unsigned.schema_version,
        authority_id=unsigned.authority_id,
        key_id=unsigned.key_id,
        tenant_id=unsigned.tenant_id,
        campaign_id=unsigned.campaign_id,
        hypothesis=unsigned.hypothesis,
        evaluation=unsigned.evaluation,
        evaluation_review_digest=unsigned.evaluation_review_digest,
        experiments=unsigned.experiments,
        outcomes=unsigned.outcomes,
        outcome_stat_policy=unsigned.outcome_stat_policy,
        outcome_stat_policy_digest=unsigned.outcome_stat_policy_digest,
        eligibility=unsigned.eligibility,
        issued_at=unsigned.issued_at,
        expires_at=unsigned.expires_at,
        signature=signer.sign(unsigned.signing_bytes),
        variant_provenances=unsigned.variant_provenances,
    )


def verify_promotion_authority(
    envelope: PromotionAuthorityEnvelope,
    verifier: AuthorityVerifier,
    *,
    tenant_id: str,
    campaign_id: str,
    now: datetime,
) -> PromotionAuthorityEnvelope:
    """Verify the signature, full artifact set, current gate, and request scope."""

    if not isinstance(envelope, PromotionAuthorityEnvelope):
        raise LearningAuthorityError("envelope must be a PromotionAuthorityEnvelope")
    if not isinstance(verifier, AuthorityVerifier):
        raise LearningAuthorityError("verifier must implement AuthorityVerifier")
    current = _now(now)
    if verifier.key_id != envelope.key_id:
        raise LearningAuthorityError("authority verifier key_id does not match envelope")
    if _opaque_id(tenant_id, "tenant_id") != envelope.tenant_id:
        raise LearningAuthorityError("authority tenant does not match")
    if _opaque_id(campaign_id, "campaign_id") != envelope.campaign_id:
        raise LearningAuthorityError("authority campaign does not match")
    if current < _datetime(envelope.issued_at):
        raise LearningAuthorityError("authority has not reached its issuance time")
    if current >= _datetime(envelope.expires_at):
        raise LearningAuthorityError("authority has expired")
    if not verifier.verify(envelope.signing_bytes, envelope.signature):
        raise LearningAuthorityError("authority signature is invalid")
    _validate_artifact_set(
        envelope.hypothesis,
        envelope.evaluation,
        envelope.experiments,
        envelope.outcomes,
        envelope.campaign_id,
        envelope.variant_provenances,
    )
    recomputed = promotion_eligibility(
        envelope.hypothesis,
        envelope.evaluation,
        envelope.experiments,
        envelope.outcomes,
        policy_version=envelope.eligibility.policy_version,
        policy_expires_at=envelope.eligibility.policy_expires_at,
        human_reviewer=envelope.eligibility.human_reviewer,
        now=current,
        variant_provenances=envelope.variant_provenances,
        outcome_stat_policy=envelope.outcome_stat_policy,
    )
    if recomputed.to_dict() != envelope.eligibility.to_dict() or not recomputed.eligible:
        raise LearningAuthorityError(
            "authority eligibility does not match a current promotion gate"
        )
    return envelope


def verified_promotion_eligibility(
    envelope: PromotionAuthorityEnvelope,
    verifier: AuthorityVerifier,
    *,
    tenant_id: str,
    campaign_id: str,
    now: datetime,
) -> PromotionEligibility:
    """Return an eligibility view after complete verification.

    This convenience adapter deliberately does *not* carry the signed proof,
    so it is suitable for display or diagnostics only.  Governance consumers
    must receive the envelope, verifier, tenant, and transition time and call
    :func:`verify_promotion_authority` at their own trust boundary.
    """

    return verify_promotion_authority(
        envelope,
        verifier,
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        now=now,
    ).eligibility
