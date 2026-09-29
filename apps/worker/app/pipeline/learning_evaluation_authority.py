"""Short-lived, signed human review for a registered learning evaluation.

``LearningEvaluation`` is a deliberately public immutable value object.  It
describes a review, but it cannot establish who reviewed it or which signed
experiment and outcome import were considered.  This module provides that
small authority boundary without persistence, a runner dependency, or network
I/O.  A trusted reviewer service signs the exact review and every consumer
rechecks the registration and platform import before it may use the review.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

from .decision_outcomes import LearningEvaluation, canonical_json, stable_digest
from .learning_registration import (
    ImportedOutcomeEnvelope,
    LearningRegistrationEnvelope,
    OutcomeAdapterVerifier,
    RegistrationVerifier,
    verify_imported_outcomes,
    verify_learning_registration,
)

LEARNING_EVALUATION_REVIEW_SCHEMA_VERSION = "1.0"
MAX_REVIEW_TTL = timedelta(hours=24)
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_DIGEST_RE = re.compile(r"^[a-f0-9]{64}$")


class LearningEvaluationAuthorityError(ValueError):
    """A review envelope is incomplete, stale, forged, or out of scope."""


@runtime_checkable
class LearningEvaluationReviewSigner(Protocol):
    @property
    def key_id(self) -> str: ...

    def sign(self, payload: bytes) -> str: ...


@runtime_checkable
class LearningEvaluationReviewVerifier(Protocol):
    @property
    def key_id(self) -> str: ...

    def verify(self, payload: bytes, signature: str) -> bool: ...


class HmacSha256LearningEvaluationAuthority:
    """Worker-local HMAC signer/verifier; key material never enters an envelope."""

    def __init__(self, *, key_id: str, secret: bytes) -> None:
        self._key_id = _key_id(key_id, "key_id")
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise LearningEvaluationAuthorityError("HMAC secret must contain at least 32 bytes")
        self._secret = secret

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, payload: bytes) -> str:
        if not isinstance(payload, bytes):
            raise LearningEvaluationAuthorityError("review signature payload must be bytes")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return (
            isinstance(payload, bytes)
            and isinstance(signature, str)
            and hmac.compare_digest(self.sign(payload), signature)
        )


def _text(value: object, label: str, maximum: int = 128) -> str:
    if not isinstance(value, str):
        raise LearningEvaluationAuthorityError(f"{label} must be a string")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized or len(normalized) > maximum:
        raise LearningEvaluationAuthorityError(f"{label} is invalid")
    return normalized


def _id(value: object, label: str) -> str:
    value = _text(value, label)
    if not _ID_RE.fullmatch(value):
        raise LearningEvaluationAuthorityError(f"{label} must be a bounded opaque identifier")
    return value


def _key_id(value: object, label: str) -> str:
    value = _text(value, label, 64)
    if not _KEY_ID_RE.fullmatch(value):
        raise LearningEvaluationAuthorityError(f"{label} is invalid")
    return value


def _digest(value: object, label: str) -> str:
    value = _text(value, label, 64).lower()
    if not _DIGEST_RE.fullmatch(value):
        raise LearningEvaluationAuthorityError(f"{label} must be a SHA-256 digest")
    return value


def _instant(value: object, label: str) -> str:
    value = _text(value, label, 40)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LearningEvaluationAuthorityError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LearningEvaluationAuthorityError(f"{label} must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _now(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LearningEvaluationAuthorityError("now must be a timezone-aware datetime")
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_authority(value: object, label: str, method: str) -> None:
    if not isinstance(value, (LearningEvaluationReviewSigner, LearningEvaluationReviewVerifier)):
        raise LearningEvaluationAuthorityError(f"{label} must implement review authority")
    if not callable(getattr(value, method, None)):
        raise LearningEvaluationAuthorityError(f"{label} must implement {method}")


def _import_digest(imported: ImportedOutcomeEnvelope) -> str:
    """Mirror the registration envelope digest without making it a capability."""
    return stable_digest({"payload": imported.signature_payload, "signature": imported.signature})


def _validate_exact_review(
    evaluation: LearningEvaluation,
    registration: LearningRegistrationEnvelope,
    imported: ImportedOutcomeEnvelope,
    *,
    reviewer_id: str,
    issued_at: str,
) -> None:
    if not isinstance(evaluation, LearningEvaluation):
        raise LearningEvaluationAuthorityError("evaluation is invalid")
    if evaluation.reviewer != reviewer_id:
        raise LearningEvaluationAuthorityError("reviewer_id must exactly match evaluation.reviewer")
    if evaluation.hypothesis_id != registration.hypothesis.hypothesis_id:
        raise LearningEvaluationAuthorityError(
            "evaluation hypothesis is not the registered hypothesis"
        )
    experiment_ids = tuple(item.experiment_id for item in registration.experiments)
    outcome_ids = tuple(item.outcome_id for item in imported.outcomes)
    if evaluation.experiment_ids != experiment_ids:
        raise LearningEvaluationAuthorityError(
            "evaluation must exactly cover registered experiment IDs"
        )
    if evaluation.outcome_ids != outcome_ids:
        raise LearningEvaluationAuthorityError("evaluation must exactly cover imported outcome IDs")
    if evaluation.effect.metric_name != registration.hypothesis.target_metric:
        raise LearningEvaluationAuthorityError(
            "evaluation effect metric is not the registered hypothesis metric"
        )
    if not (
        _datetime(imported.imported_at)
        <= _datetime(evaluation.evaluated_at)
        <= _datetime(issued_at)
    ):
        raise LearningEvaluationAuthorityError(
            "evaluation time must follow import and not follow review issuance"
        )


@dataclass(frozen=True)
class IssuedLearningEvaluationReview:
    """Immutable signed review bound to exact registration and imported outcomes."""

    schema_version: str
    review_id: str
    key_id: str
    tenant_id: str
    campaign_id: str
    registration_digest: str
    imported_outcome_digest: str
    evaluation: LearningEvaluation
    reviewer_id: str
    issued_at: str
    expires_at: str
    signature: str

    def __post_init__(self) -> None:
        if self.schema_version != LEARNING_EVALUATION_REVIEW_SCHEMA_VERSION:
            raise LearningEvaluationAuthorityError("unsupported learning evaluation review schema")
        for field in ("review_id", "tenant_id", "campaign_id", "reviewer_id"):
            object.__setattr__(self, field, _id(getattr(self, field), field))
        object.__setattr__(self, "key_id", _key_id(self.key_id, "key_id"))
        object.__setattr__(
            self,
            "registration_digest",
            _digest(self.registration_digest, "registration_digest"),
        )
        object.__setattr__(
            self,
            "imported_outcome_digest",
            _digest(self.imported_outcome_digest, "imported_outcome_digest"),
        )
        if not isinstance(self.evaluation, LearningEvaluation):
            raise LearningEvaluationAuthorityError("evaluation is invalid")
        object.__setattr__(self, "issued_at", _instant(self.issued_at, "issued_at"))
        object.__setattr__(self, "expires_at", _instant(self.expires_at, "expires_at"))
        if _datetime(self.expires_at) <= _datetime(self.issued_at):
            raise LearningEvaluationAuthorityError("review expiry must be after issuance")
        if _datetime(self.expires_at) - _datetime(self.issued_at) > MAX_REVIEW_TTL:
            raise LearningEvaluationAuthorityError("review TTL exceeds 24 hours")
        object.__setattr__(self, "signature", _digest(self.signature, "signature"))

    @property
    def signature_payload(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "evaluation": self.evaluation.to_dict(),
            "evaluation_digest": self.evaluation.canonical_digest,
            "expires_at": self.expires_at,
            "imported_outcome_digest": self.imported_outcome_digest,
            "issued_at": self.issued_at,
            "key_id": self.key_id,
            "registration_digest": self.registration_digest,
            "review_id": self.review_id,
            "reviewer_id": self.reviewer_id,
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
        }

    @property
    def signing_bytes(self) -> bytes:
        return canonical_json(self.signature_payload).encode("utf-8")

    @property
    def canonical_digest(self) -> str:
        return stable_digest({"payload": self.signature_payload, "signature": self.signature})


def issue_learning_evaluation_review(
    signer: LearningEvaluationReviewSigner,
    *,
    review_id: str,
    tenant_id: str,
    campaign_id: str,
    registration: LearningRegistrationEnvelope,
    registration_verifier: RegistrationVerifier,
    imported_outcomes: ImportedOutcomeEnvelope,
    outcome_adapter_verifier: OutcomeAdapterVerifier,
    evaluation: LearningEvaluation,
    reviewer_id: str,
    issued_at: datetime,
    expires_at: str,
) -> IssuedLearningEvaluationReview:
    """Verify source authority, recompute exact bindings, then sign the review."""
    _require_authority(signer, "signer", "sign")
    current = _now(issued_at)
    tenant = _id(tenant_id, "tenant_id")
    campaign = _id(campaign_id, "campaign_id")
    reviewer = _id(reviewer_id, "reviewer_id")
    verified_registration = verify_learning_registration(
        registration, registration_verifier, tenant_id=tenant, campaign_id=campaign
    )
    verified_outcomes = verify_imported_outcomes(
        imported_outcomes,
        outcome_adapter_verifier,
        verified_registration,
        registration_verifier,
        tenant_id=tenant,
        campaign_id=campaign,
    )
    # The imported tuple is verified above.  Keep the envelope object for its
    # signed digest, not a caller-supplied tuple that could omit an outcome.
    del verified_outcomes
    _validate_exact_review(
        evaluation,
        verified_registration,
        imported_outcomes,
        reviewer_id=reviewer,
        issued_at=current,
    )
    unsigned = IssuedLearningEvaluationReview(
        LEARNING_EVALUATION_REVIEW_SCHEMA_VERSION,
        _id(review_id, "review_id"),
        _key_id(signer.key_id, "signer.key_id"),
        tenant,
        campaign,
        verified_registration.canonical_digest,
        _import_digest(imported_outcomes),
        evaluation,
        reviewer,
        current,
        expires_at,
        "0" * 64,
    )
    return replace(unsigned, signature=signer.sign(unsigned.signing_bytes))


def verify_learning_evaluation_review(
    review: IssuedLearningEvaluationReview,
    verifier: LearningEvaluationReviewVerifier,
    *,
    registration: LearningRegistrationEnvelope,
    registration_verifier: RegistrationVerifier,
    imported_outcomes: ImportedOutcomeEnvelope,
    outcome_adapter_verifier: OutcomeAdapterVerifier,
    tenant_id: str,
    campaign_id: str,
    now: datetime,
) -> LearningEvaluation:
    """Verify the HMAC, scope, TTL, digests, and exact source bindings on use."""
    if not isinstance(review, IssuedLearningEvaluationReview):
        raise LearningEvaluationAuthorityError("review must be an IssuedLearningEvaluationReview")
    _require_authority(verifier, "verifier", "verify")
    tenant = _id(tenant_id, "tenant_id")
    campaign = _id(campaign_id, "campaign_id")
    current = _now(now)
    if (review.tenant_id, review.campaign_id) != (tenant, campaign):
        raise LearningEvaluationAuthorityError("review tenant or campaign does not match")
    if _key_id(verifier.key_id, "verifier.key_id") != review.key_id:
        raise LearningEvaluationAuthorityError("review verifier key_id does not match")
    if not verifier.verify(review.signing_bytes, review.signature):
        raise LearningEvaluationAuthorityError("review signature is invalid")
    if not (_datetime(review.issued_at) <= _datetime(current) < _datetime(review.expires_at)):
        raise LearningEvaluationAuthorityError("review has expired or is not yet valid")
    verified_registration = verify_learning_registration(
        registration, registration_verifier, tenant_id=tenant, campaign_id=campaign
    )
    verify_imported_outcomes(
        imported_outcomes,
        outcome_adapter_verifier,
        verified_registration,
        registration_verifier,
        tenant_id=tenant,
        campaign_id=campaign,
    )
    if review.registration_digest != verified_registration.canonical_digest:
        raise LearningEvaluationAuthorityError("review registration digest does not match")
    if review.imported_outcome_digest != _import_digest(imported_outcomes):
        raise LearningEvaluationAuthorityError("review imported outcome digest does not match")
    _validate_exact_review(
        review.evaluation,
        verified_registration,
        imported_outcomes,
        reviewer_id=review.reviewer_id,
        issued_at=review.issued_at,
    )
    return review.evaluation


# Short aliases keep the boundary discoverable beside the existing authority APIs.
issue_evaluation_review = issue_learning_evaluation_review
verify_evaluation_review = verify_learning_evaluation_review
