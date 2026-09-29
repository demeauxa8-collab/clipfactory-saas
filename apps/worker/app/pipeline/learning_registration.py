"""Signed local boundary for pre-registered learning experiments and outcomes.

This is deliberately an in-memory contract.  It gives a future persistence or
platform adapter one narrow place to attach its own signing implementation,
without treating a public immutable outcome dataclass as authority.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from .decision_outcomes import (
    EditorialExperiment,
    LearningHypothesis,
    OutcomeObservation,
    OutcomeStatPolicy,
    canonical_json,
    stable_digest,
)
from .decision_provenance import (
    IssuedVariantProvenance,
    VariantProvenanceVerifier,
    verify_issued_variant_provenance,
)

LEARNING_REGISTRATION_SCHEMA_VERSION = "1.0"
MAX_REGISTERED_EXPERIMENTS = 32
MAX_REGISTERED_VARIANTS = 64
MAX_IMPORTED_OUTCOMES = 64
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SIGNATURE_RE = re.compile(r"^[a-f0-9]{64}$")


class LearningRegistrationError(ValueError):
    """A registration or platform-import proof is incomplete or untrusted."""


@runtime_checkable
class RegistrationSigner(Protocol):
    @property
    def key_id(self) -> str: ...

    def sign(self, payload: bytes) -> str: ...


@runtime_checkable
class RegistrationVerifier(Protocol):
    @property
    def key_id(self) -> str: ...

    def verify(self, payload: bytes, signature: str) -> bool: ...


@runtime_checkable
class OutcomeAdapterSigner(Protocol):
    @property
    def key_id(self) -> str: ...

    def sign(self, payload: bytes) -> str: ...


@runtime_checkable
class OutcomeAdapterVerifier(Protocol):
    @property
    def key_id(self) -> str: ...

    def verify(self, payload: bytes, signature: str) -> bool: ...


class HmacSha256LearningRegistrationAuthority:
    """Worker-local HMAC signer/verifier; key bytes never enter envelopes."""

    def __init__(self, *, key_id: str, secret: bytes) -> None:
        self._key_id = _key_id(key_id)
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise LearningRegistrationError("HMAC secret must contain at least 32 bytes")
        self._secret = secret

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, payload: bytes) -> str:
        if not isinstance(payload, bytes):
            raise LearningRegistrationError("signature payload must be bytes")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return (
            isinstance(payload, bytes)
            and isinstance(signature, str)
            and hmac.compare_digest(self.sign(payload), signature)
        )


# The same non-exporting adapter implementation is useful in local tests.  A
# real platform adapter has a separate key and must be passed as its verifier
# at the consumer boundary.
HmacSha256OutcomeAdapter = HmacSha256LearningRegistrationAuthority


def _text(value: object, label: str, maximum: int = 128) -> str:
    if not isinstance(value, str):
        raise LearningRegistrationError(f"{label} must be a string")
    value = unicodedata.normalize("NFC", value).strip()
    if not value or len(value) > maximum:
        raise LearningRegistrationError(f"{label} is invalid")
    return value


def _id(value: object, label: str) -> str:
    value = _text(value, label)
    if not _ID_RE.fullmatch(value):
        raise LearningRegistrationError(f"{label} must be a bounded opaque identifier")
    return value


def _key_id(value: object) -> str:
    value = _text(value, "key_id", 64)
    if not _KEY_ID_RE.fullmatch(value):
        raise LearningRegistrationError("key_id is invalid")
    return value


def _signature(value: object) -> str:
    value = _text(value, "signature", 64).lower()
    if not _SIGNATURE_RE.fullmatch(value):
        raise LearningRegistrationError("signature must be an HMAC-SHA256 digest")
    return value


def _instant(value: object, label: str) -> str:
    value = _text(value, label, 40)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LearningRegistrationError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LearningRegistrationError(f"{label} must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _now(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LearningRegistrationError("now must be a timezone-aware datetime")
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _signer(value: object, label: str) -> None:
    if not isinstance(value, (RegistrationSigner, OutcomeAdapterSigner)):
        raise LearningRegistrationError(f"{label} must implement a signing authority")


def _verifier(value: object, label: str) -> None:
    if not isinstance(value, (RegistrationVerifier, OutcomeAdapterVerifier)):
        raise LearningRegistrationError(f"{label} must implement a verification authority")


def _experiments(values: object) -> tuple[EditorialExperiment, ...]:
    if not isinstance(values, tuple) or not values:
        raise LearningRegistrationError("experiments must be a nonempty tuple")
    if len(values) > MAX_REGISTERED_EXPERIMENTS:
        raise LearningRegistrationError("experiments exceed the registration hard cap")
    if not all(isinstance(item, EditorialExperiment) for item in values):
        raise LearningRegistrationError("experiments contains an invalid artifact")
    ids = tuple(item.experiment_id for item in values)
    if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
        raise LearningRegistrationError("experiments must have unique canonical IDs")
    return values


def _issued_variants(values: object) -> tuple[IssuedVariantProvenance, ...]:
    if not isinstance(values, tuple) or not values:
        raise LearningRegistrationError("issued_variant_provenances must be a nonempty tuple")
    if len(values) > MAX_REGISTERED_VARIANTS:
        raise LearningRegistrationError(
            "issued variant provenances exceed the registration hard cap"
        )
    if not all(isinstance(item, IssuedVariantProvenance) for item in values):
        raise LearningRegistrationError("issued_variant_provenances must be signed envelopes")
    ids = tuple(item.provenance.variant_id for item in values)
    if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
        raise LearningRegistrationError(
            "issued_variant_provenances must have unique canonical variants"
        )
    return values


def _registered_variant_ids(experiments: tuple[EditorialExperiment, ...]) -> set[str]:
    return {variant_id for experiment in experiments for variant_id in experiment.variants}


def _require_exact_variant_cover(
    experiments: tuple[EditorialExperiment, ...],
    issued_variant_provenances: tuple[IssuedVariantProvenance, ...],
) -> None:
    registered = _registered_variant_ids(experiments)
    issued = {item.provenance.variant_id for item in issued_variant_provenances}
    if len(registered) > MAX_REGISTERED_VARIANTS or registered != issued:
        raise LearningRegistrationError(
            "issued variant provenances must exactly cover registered experiment variants"
        )


def _validate_registration_contents(
    *,
    campaign_id: str,
    hypothesis: LearningHypothesis,
    experiments: tuple[EditorialExperiment, ...],
    issued_variant_provenances: tuple[IssuedVariantProvenance, ...],
    outcome_stat_policy: OutcomeStatPolicy,
    registered_at: str,
) -> None:
    """Keep server-stamped preregistration invariants true after deserialization."""
    registered = _datetime(registered_at)
    if hypothesis.scope.get("campaign_id") != campaign_id:
        raise LearningRegistrationError("hypothesis campaign scope does not match registration")
    if hypothesis.created_at != registered_at:
        raise LearningRegistrationError("hypothesis must be server-stamped at registration time")
    if _datetime(hypothesis.expires_at) <= registered:
        raise LearningRegistrationError("hypothesis expired before server registration")
    if _datetime(outcome_stat_policy.expires_at) <= registered:
        raise LearningRegistrationError("outcome policy expired before server registration")
    if hypothesis.target_metric not in outcome_stat_policy.preregistered_metrics:
        raise LearningRegistrationError("policy does not preregister the hypothesis metric")

    by_variant = {
        item.provenance.variant_id: item.provenance.canonical_digest
        for item in issued_variant_provenances
    }
    _require_exact_variant_cover(experiments, issued_variant_provenances)
    for experiment in experiments:
        if (
            experiment.campaign_id != campaign_id
            or experiment.primary_metric != hypothesis.target_metric
        ):
            raise LearningRegistrationError(
                "experiment does not match registered campaign or metric"
            )
        expected_bindings = {
            variant_id: by_variant[variant_id] for variant_id in experiment.variants
        }
        if dict(experiment.variant_provenance_digests) != expected_bindings:
            raise LearningRegistrationError(
                "experiment provenance bindings do not match signed variants"
            )
        if experiment.registered_at != registered_at:
            raise LearningRegistrationError(
                "experiments must be server-stamped at registration time"
            )
        if registered >= _datetime(experiment.posting_window_start):
            raise LearningRegistrationError(
                "registration must strictly predate every experiment posting window"
            )


def _outcomes(values: object) -> tuple[OutcomeObservation, ...]:
    if not isinstance(values, tuple) or not values:
        raise LearningRegistrationError("outcomes must be a nonempty tuple")
    if len(values) > MAX_IMPORTED_OUTCOMES:
        raise LearningRegistrationError("outcomes exceed the import hard cap")
    if not all(isinstance(item, OutcomeObservation) for item in values):
        raise LearningRegistrationError("outcomes contains an invalid artifact")
    ids = tuple(item.outcome_id for item in values)
    if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
        raise LearningRegistrationError("outcomes must have unique canonical IDs")
    return values


@dataclass(frozen=True)
class LearningRegistrationEnvelope:
    """A server-stamped, signed preregistration for one exact campaign set."""

    schema_version: str
    registration_id: str
    key_id: str
    tenant_id: str
    campaign_id: str
    hypothesis: LearningHypothesis
    experiments: tuple[EditorialExperiment, ...]
    issued_variant_provenances: tuple[IssuedVariantProvenance, ...]
    outcome_stat_policy: OutcomeStatPolicy
    registered_at: str
    signature: str

    def __post_init__(self) -> None:
        if self.schema_version != LEARNING_REGISTRATION_SCHEMA_VERSION:
            raise LearningRegistrationError("unsupported learning registration schema")
        for field in ("registration_id", "tenant_id", "campaign_id"):
            object.__setattr__(self, field, _id(getattr(self, field), field))
        object.__setattr__(self, "key_id", _key_id(self.key_id))
        if not isinstance(self.hypothesis, LearningHypothesis):
            raise LearningRegistrationError("hypothesis is invalid")
        object.__setattr__(self, "experiments", _experiments(self.experiments))
        object.__setattr__(
            self, "issued_variant_provenances", _issued_variants(self.issued_variant_provenances)
        )
        _require_exact_variant_cover(self.experiments, self.issued_variant_provenances)
        if not isinstance(self.outcome_stat_policy, OutcomeStatPolicy):
            raise LearningRegistrationError("outcome_stat_policy must be signed with registration")
        object.__setattr__(self, "registered_at", _instant(self.registered_at, "registered_at"))
        _validate_registration_contents(
            campaign_id=self.campaign_id,
            hypothesis=self.hypothesis,
            experiments=self.experiments,
            issued_variant_provenances=self.issued_variant_provenances,
            outcome_stat_policy=self.outcome_stat_policy,
            registered_at=self.registered_at,
        )
        object.__setattr__(self, "signature", _signature(self.signature))

    @property
    def signature_payload(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "experiment_digests": [item.canonical_digest for item in self.experiments],
            "hypothesis_digest": self.hypothesis.canonical_digest,
            "issued_variant_provenance_digests": [
                stable_digest({"payload": item.signature_payload, "signature": item.signature})
                for item in self.issued_variant_provenances
            ],
            "key_id": self.key_id,
            "outcome_stat_policy_digest": self.outcome_stat_policy.canonical_digest,
            "registered_at": self.registered_at,
            "registration_id": self.registration_id,
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
        }

    @property
    def signing_bytes(self) -> bytes:
        return canonical_json(self.signature_payload).encode("utf-8")

    @property
    def canonical_digest(self) -> str:
        return stable_digest({"payload": self.signature_payload, "signature": self.signature})


@dataclass(frozen=True)
class ImportedOutcomeEnvelope:
    """Platform-adapter signed outcomes tied to one signed registration."""

    schema_version: str
    import_id: str
    adapter_key_id: str
    registration_id: str
    registration_digest: str
    tenant_id: str
    campaign_id: str
    outcomes: tuple[OutcomeObservation, ...]
    imported_at: str
    signature: str

    def __post_init__(self) -> None:
        if self.schema_version != LEARNING_REGISTRATION_SCHEMA_VERSION:
            raise LearningRegistrationError("unsupported outcome import schema")
        for field in ("import_id", "registration_id", "tenant_id", "campaign_id"):
            object.__setattr__(self, field, _id(getattr(self, field), field))
        object.__setattr__(self, "adapter_key_id", _key_id(self.adapter_key_id))
        if not isinstance(self.registration_digest, str) or not re.fullmatch(
            r"[a-f0-9]{64}", self.registration_digest
        ):
            raise LearningRegistrationError("registration_digest must be a SHA-256 digest")
        object.__setattr__(self, "outcomes", _outcomes(self.outcomes))
        object.__setattr__(self, "imported_at", _instant(self.imported_at, "imported_at"))
        for outcome in self.outcomes:
            if (
                outcome.observed_at != self.imported_at
                or outcome.trust != "verified"
                or outcome.is_historical
            ):
                raise LearningRegistrationError(
                    "outcomes must be server-stamped verified import results"
                )
        object.__setattr__(self, "signature", _signature(self.signature))

    @property
    def signature_payload(self) -> dict[str, object]:
        return {
            "adapter_key_id": self.adapter_key_id,
            "campaign_id": self.campaign_id,
            "import_id": self.import_id,
            "imported_at": self.imported_at,
            "outcome_digests": [item.canonical_digest for item in self.outcomes],
            "registration_digest": self.registration_digest,
            "registration_id": self.registration_id,
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
        }

    @property
    def signing_bytes(self) -> bytes:
        return canonical_json(self.signature_payload).encode("utf-8")


def issue_learning_registration(
    signer: RegistrationSigner,
    *,
    registration_id: str,
    tenant_id: str,
    campaign_id: str,
    hypothesis: LearningHypothesis,
    experiments: tuple[EditorialExperiment, ...],
    outcome_stat_policy: OutcomeStatPolicy,
    issued_variant_provenances: tuple[IssuedVariantProvenance, ...],
    variant_provenance_verifier: VariantProvenanceVerifier,
    variant_owner_id: str,
    now: datetime,
) -> LearningRegistrationEnvelope:
    """Server-stamp and sign a complete hypothesis, experiment and policy set."""
    _signer(signer, "signer")
    current = _now(now)
    campaign = _id(campaign_id, "campaign_id")
    tenant = _id(tenant_id, "tenant_id")
    owner = _id(variant_owner_id, "variant_owner_id")
    if not isinstance(hypothesis, LearningHypothesis):
        raise LearningRegistrationError("hypothesis is invalid")
    if hypothesis.scope.get("campaign_id") != campaign:
        raise LearningRegistrationError("hypothesis campaign scope does not match registration")
    stamped_hypothesis = replace(hypothesis, created_at=current)
    if _datetime(stamped_hypothesis.expires_at) <= _datetime(current):
        raise LearningRegistrationError("hypothesis has expired before server registration")
    if not isinstance(outcome_stat_policy, OutcomeStatPolicy):
        raise LearningRegistrationError("outcome_stat_policy is invalid")
    if _datetime(outcome_stat_policy.expires_at) <= _datetime(current):
        raise LearningRegistrationError("outcome_stat_policy has expired before registration")
    supplied = _experiments(experiments)
    sealed = _issued_variants(issued_variant_provenances)
    _require_exact_variant_cover(supplied, sealed)
    if not hasattr(variant_provenance_verifier, "key_id") or not callable(
        getattr(variant_provenance_verifier, "verify", None)
    ):
        raise LearningRegistrationError("variant_provenance_verifier is invalid")
    try:
        provenances = tuple(
            verify_issued_variant_provenance(
                envelope,
                variant_provenance_verifier,
                owner_id=owner,
                campaign_id=campaign,
                now=current,
            )
            for envelope in sealed
        )
    except ValueError as exc:
        raise LearningRegistrationError("issued variant provenance verification failed") from exc
    by_variant = {item.variant_id: item for item in provenances}
    stamped: list[EditorialExperiment] = []
    for experiment in supplied:
        if (
            experiment.campaign_id != campaign
            or experiment.primary_metric != stamped_hypothesis.target_metric
        ):
            raise LearningRegistrationError(
                "experiment does not match registered campaign or metric"
            )
        if not all(variant in by_variant for variant in experiment.variants):
            raise LearningRegistrationError(
                "experiment variants are not exactly backed by issued provenance"
            )
        bindings = {
            variant: by_variant[variant].canonical_digest for variant in experiment.variants
        }
        if (
            experiment.variant_provenance_digests
            and dict(experiment.variant_provenance_digests) != bindings
        ):
            raise LearningRegistrationError(
                "experiment provenance bindings do not match signed variants"
            )
        if _datetime(current) >= _datetime(experiment.posting_window_start):
            raise LearningRegistrationError(
                "registration must strictly predate every experiment posting window"
            )
        try:
            stamped.append(
                replace(experiment, registered_at=current, variant_provenance_digests=bindings)
            )
        except ValueError as exc:
            raise LearningRegistrationError(
                "experiment cannot be server-registered before posting"
            ) from exc
    if tuple(item.experiment_id for item in stamped) != tuple(
        sorted(item.experiment_id for item in stamped)
    ):
        raise LearningRegistrationError("experiments must remain in canonical order")
    if stamped_hypothesis.target_metric not in outcome_stat_policy.preregistered_metrics:
        raise LearningRegistrationError("policy does not preregister the hypothesis metric")
    unsigned = LearningRegistrationEnvelope(
        LEARNING_REGISTRATION_SCHEMA_VERSION,
        registration_id,
        signer.key_id,
        tenant,
        campaign,
        stamped_hypothesis,
        tuple(stamped),
        sealed,
        outcome_stat_policy,
        current,
        "0" * 64,
    )
    return replace(unsigned, signature=signer.sign(unsigned.signing_bytes))


def verify_learning_registration(
    registration: LearningRegistrationEnvelope,
    verifier: RegistrationVerifier,
    *,
    tenant_id: str,
    campaign_id: str,
) -> LearningRegistrationEnvelope:
    """Verify a registration at every consumer; no private capability is trusted."""
    if not isinstance(registration, LearningRegistrationEnvelope):
        raise LearningRegistrationError("registration must be a LearningRegistrationEnvelope")
    _verifier(verifier, "registration_verifier")
    if _key_id(verifier.key_id) != registration.key_id:
        raise LearningRegistrationError("registration verifier key_id does not match")
    if (registration.tenant_id, registration.campaign_id) != (
        _id(tenant_id, "tenant_id"),
        _id(campaign_id, "campaign_id"),
    ):
        raise LearningRegistrationError("registration tenant or campaign does not match")
    if not verifier.verify(registration.signing_bytes, registration.signature):
        raise LearningRegistrationError("registration signature is invalid")
    return registration


def import_registered_outcomes(
    adapter_signer: OutcomeAdapterSigner,
    registration: LearningRegistrationEnvelope,
    registration_verifier: RegistrationVerifier,
    *,
    import_id: str,
    tenant_id: str,
    campaign_id: str,
    outcomes: tuple[OutcomeObservation, ...],
    now: datetime,
) -> ImportedOutcomeEnvelope:
    """Bind adapter data to its preregistration and server-stamp observation time."""
    _signer(adapter_signer, "adapter_signer")
    verified = verify_learning_registration(
        registration, registration_verifier, tenant_id=tenant_id, campaign_id=campaign_id
    )
    current = _now(now)
    supplied_outcomes = _outcomes(outcomes)
    by_experiment = {item.experiment_id: item for item in verified.experiments}
    expected = {
        (item.experiment_id, variant) for item in verified.experiments for variant in item.variants
    }
    supplied = {(item.experiment_id, item.variant_id) for item in supplied_outcomes}
    if supplied != expected or len(supplied) != len(supplied_outcomes):
        raise LearningRegistrationError(
            "outcomes must exactly cover registered experiment variants"
        )
    stamped: list[OutcomeObservation] = []
    for outcome in supplied_outcomes:
        experiment = by_experiment.get(outcome.experiment_id)
        if experiment is None or (
            outcome.metric_name != experiment.primary_metric
            or outcome.platform != experiment.platform
            or outcome.account_id != experiment.account_id
            or outcome.window_start != experiment.posting_window_start
            or outcome.window_end != experiment.posting_window_end
            or outcome.variant_provenance_digest
            != experiment.variant_provenance_digests[outcome.variant_id]
        ):
            raise LearningRegistrationError(
                "outcome does not exactly match registered metric, scope, variant, or window"
            )
        try:
            stamped.append(
                replace(outcome, observed_at=current, trust="verified", is_historical=False)
            )
        except ValueError as exc:
            raise LearningRegistrationError("outcome cannot be server-stamped") from exc
    stamped.sort(key=lambda item: item.outcome_id)
    unsigned = ImportedOutcomeEnvelope(
        LEARNING_REGISTRATION_SCHEMA_VERSION,
        import_id,
        adapter_signer.key_id,
        verified.registration_id,
        verified.canonical_digest,
        verified.tenant_id,
        verified.campaign_id,
        tuple(stamped),
        current,
        "0" * 64,
    )
    return replace(unsigned, signature=adapter_signer.sign(unsigned.signing_bytes))


def verify_imported_outcomes(
    imported: ImportedOutcomeEnvelope,
    adapter_verifier: OutcomeAdapterVerifier,
    registration: LearningRegistrationEnvelope,
    registration_verifier: RegistrationVerifier,
    *,
    tenant_id: str,
    campaign_id: str,
) -> tuple[OutcomeObservation, ...]:
    """Verify both issuer signatures and re-check exact registration bindings."""
    verified = verify_learning_registration(
        registration, registration_verifier, tenant_id=tenant_id, campaign_id=campaign_id
    )
    if not isinstance(imported, ImportedOutcomeEnvelope):
        raise LearningRegistrationError("imported must be an ImportedOutcomeEnvelope")
    _verifier(adapter_verifier, "adapter_verifier")
    if _key_id(adapter_verifier.key_id) != imported.adapter_key_id:
        raise LearningRegistrationError("outcome adapter key_id does not match")
    if (
        imported.registration_id,
        imported.registration_digest,
        imported.tenant_id,
        imported.campaign_id,
    ) != (
        verified.registration_id,
        verified.canonical_digest,
        verified.tenant_id,
        verified.campaign_id,
    ):
        raise LearningRegistrationError("outcome import is not bound to this registration scope")
    if not adapter_verifier.verify(imported.signing_bytes, imported.signature):
        raise LearningRegistrationError("outcome import signature is invalid")
    # Re-use the importer validation with a temporary signer would be wrong: it
    # would re-stamp a historical import.  Its immutable checks are repeated
    # here so signature verification remains the actual consumer boundary.
    by_experiment = {item.experiment_id: item for item in verified.experiments}
    expected = {
        (item.experiment_id, variant) for item in verified.experiments for variant in item.variants
    }
    actual = {(item.experiment_id, item.variant_id) for item in imported.outcomes}
    if actual != expected or len(actual) != len(imported.outcomes):
        raise LearningRegistrationError("outcome import does not exactly cover registered variants")
    for outcome in imported.outcomes:
        experiment = by_experiment[outcome.experiment_id]
        if (
            outcome.observed_at != imported.imported_at
            or _datetime(imported.imported_at) < _datetime(experiment.posting_window_end)
            or outcome.trust != "verified"
            or outcome.is_historical
            or outcome.metric_name != experiment.primary_metric
            or outcome.platform != experiment.platform
            or outcome.account_id != experiment.account_id
            or outcome.window_start != experiment.posting_window_start
            or outcome.window_end != experiment.posting_window_end
            or outcome.variant_provenance_digest
            != experiment.variant_provenance_digests[outcome.variant_id]
        ):
            raise LearningRegistrationError(
                "outcome import is not an exact verified registration result"
            )
    return imported.outcomes


# Names that read naturally at the call site; both maintain the same strict
# contract and make the boundary discoverable beside existing `issue_*` APIs.
register_learning_experiment = issue_learning_registration
verify_registered_learning = verify_learning_registration
