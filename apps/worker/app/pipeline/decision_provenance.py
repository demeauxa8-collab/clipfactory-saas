"""Materialize cited Director decisions into immutable outcome-ready provenance.

The Director cites versioned note IDs because they are useful to humans.  The
outcome layer stores canonical digests because a later note version must never
rewrite the evidence behind an old edit.  This module is the explicit bridge
between those two representations and requires a verified context issuance.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from .decision_outcomes import (
    DecisionEvidenceRefs,
    EditorialDecisionRecord,
    VariantProvenance,
    stable_digest,
)
from .editorial_beats import EditorialBeatGraph
from .editorial_context_authority import (
    IssuedEditorialContext,
    VerifiedEditorialContext,
    verify_editorial_context_capability,
)
from .editorial_context_authority import Verifier as EditorialContextVerifier
from .editorial_director_v22 import (
    DirectorDecisionEvidence,
    EditorialDirectorPlanV22,
)
from .knowledge_vault import ContextNote

DECISION_PROVENANCE_SCHEMA_VERSION = "1.0"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_DIGEST_RE = re.compile(r"^[a-f0-9]{64}$")
_VERIFIED_VARIANT_PROVENANCE_TOKEN = object()
_MAX_VARIANT_ISSUANCE_TTL = timedelta(hours=24)


class DecisionProvenanceError(ValueError):
    """A decision audit cannot be bound to its issued context and exact notes."""


class VariantProvenanceSigner(Protocol):
    """Signs a variant authority manifest without exposing key bytes."""

    key_id: str

    def sign(self, payload: bytes) -> str: ...


class VariantProvenanceVerifier(Protocol):
    """Verifies a variant authority manifest at the promotion boundary."""

    key_id: str

    def verify(self, payload: bytes, signature: str) -> bool: ...


@dataclass(frozen=True)
class HmacSha256VariantAuthority:
    """Local HMAC issuer/verifier for the sealed variant manifest.

    This deliberately remains worker-local.  A production adapter can replace
    it with a KMS-backed signer while keeping the manifest contract unchanged.
    """

    key_id: str
    secret: bytes = field(repr=False)

    def __post_init__(self) -> None:
        _id(self.key_id, "variant authority key_id")
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise DecisionProvenanceError("variant authority secret must be at least 32 bytes")

    def sign(self, payload: bytes) -> str:
        if not isinstance(payload, bytes):
            raise DecisionProvenanceError("variant authority payload must be bytes")
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        if not isinstance(payload, bytes) or not isinstance(signature, str):
            return False
        return hmac.compare_digest(self.sign(payload), signature)


@dataclass(frozen=True, init=False)
class VerifiedVariantProvenance:
    """Capability proving a rendered variant was rebuilt from signed context.

    ``VariantProvenance`` is intentionally a public, serializable outcome
    artifact.  It is therefore not authority to promote a learning policy.
    This capability is the sole input the promotion issuer accepts; its private
    constructor can only be reached after re-materialising the complete cited
    decision audit through a live :class:`VerifiedEditorialContext`.
    """

    provenance: VariantProvenance

    def __init__(self, provenance: VariantProvenance, *, _token: object) -> None:
        if _token is not _VERIFIED_VARIANT_PROVENANCE_TOKEN:
            raise DecisionProvenanceError(
                "VerifiedVariantProvenance must be created by provenance attestation"
            )
        if not isinstance(provenance, VariantProvenance):
            raise DecisionProvenanceError("provenance must be a VariantProvenance")
        if (
            provenance.snapshot_digest is None
            or provenance.context_issuance_id is None
            or provenance.decision_audit_digest is None
        ):
            raise DecisionProvenanceError("verified provenance requires a complete audit chain")
        object.__setattr__(self, "provenance", provenance)


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise DecisionProvenanceError(f"{label} must be a bounded opaque ID")
    return value


def _digest(value: str, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise DecisionProvenanceError(f"{label} must be a SHA-256 digest")
    return value


def _note_digests(context_digest: str, note: ContextNote) -> tuple[str, str]:
    payload_digest = stable_digest(note.to_payload())
    note_digest = stable_digest(
        {
            "context_digest": context_digest,
            "note_id": note.note_id,
            "payload_digest": payload_digest,
            "vault": note.vault,
            "version": note.version,
        }
    )
    return payload_digest, note_digest


def _ordered_evidence(plan: EditorialDirectorPlanV22) -> tuple[DirectorDecisionEvidence, ...]:
    by_id = {item.decision_id: item for item in plan.decision_evidence}
    return (by_id["plan"], *(by_id[shot.shot_id] for shot in plan.controls.shots))


def director_plan_digest(plan: EditorialDirectorPlanV22) -> str:
    """Hash controls and citations in semantic plan/shot order, not JSON input order."""
    if not isinstance(plan, EditorialDirectorPlanV22):
        raise DecisionProvenanceError("plan must be an EditorialDirectorPlanV22")
    return stable_digest(
        {
            "schema_version": plan.schema_version,
            "context_digest": plan.context_digest,
            "graph_digest": plan.graph_digest,
            "controls": asdict(plan.controls),
            "decision_evidence": [item.to_dict() for item in _ordered_evidence(plan)],
        }
    )


@dataclass(frozen=True)
class ResolvedDecisionReference:
    """One exact prompt note resolved to a content-and-context digest."""

    note_id: str
    version: int
    vault: Literal["global", "campaign", "source"]
    context_digest: str
    payload_digest: str
    note_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "note_id", _id(self.note_id, "note_id"))
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise DecisionProvenanceError("reference version must be a positive integer")
        if self.vault not in {"global", "campaign", "source"}:
            raise DecisionProvenanceError("reference vault is invalid")
        for name in ("context_digest", "payload_digest", "note_digest"):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        expected = stable_digest(
            {
                "context_digest": self.context_digest,
                "note_id": self.note_id,
                "payload_digest": self.payload_digest,
                "vault": self.vault,
                "version": self.version,
            }
        )
        if self.note_digest != expected:
            raise DecisionProvenanceError("note_digest does not match the resolved note identity")

    def to_payload(self) -> dict[str, object]:
        return {
            "context_digest": self.context_digest,
            "note_digest": self.note_digest,
            "note_id": self.note_id,
            "payload_digest": self.payload_digest,
            "vault": self.vault,
            "version": self.version,
        }


@dataclass(frozen=True)
class DecisionProvenanceBundle:
    schema_version: Literal["1.0"]
    variant_id: str
    issuance_id: str
    snapshot_digest: str
    context_digest: str
    graph_digest: str
    director_plan_digest: str
    records: tuple[EditorialDecisionRecord, ...]
    resolved_references: tuple[ResolvedDecisionReference, ...]
    audit_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != DECISION_PROVENANCE_SCHEMA_VERSION:
            raise DecisionProvenanceError("unsupported decision provenance schema")
        object.__setattr__(self, "variant_id", _id(self.variant_id, "variant_id"))
        object.__setattr__(self, "issuance_id", _id(self.issuance_id, "issuance_id"))
        for name in (
            "snapshot_digest",
            "context_digest",
            "graph_digest",
            "director_plan_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.records, tuple) or not self.records:
            raise DecisionProvenanceError("records must be a non-empty tuple")
        if not all(isinstance(item, EditorialDecisionRecord) for item in self.records):
            raise DecisionProvenanceError("records contains an invalid decision")
        if len({item.decision_id for item in self.records}) != len(self.records):
            raise DecisionProvenanceError("records cannot repeat decision IDs")
        if not isinstance(self.resolved_references, tuple) or not all(
            isinstance(item, ResolvedDecisionReference) for item in self.resolved_references
        ):
            raise DecisionProvenanceError("resolved_references is invalid")
        reference_digests = {item.note_digest for item in self.resolved_references}
        if len(reference_digests) != len(self.resolved_references):
            raise DecisionProvenanceError("resolved references cannot repeat digests")
        if any(item.context_digest != self.context_digest for item in self.resolved_references):
            raise DecisionProvenanceError("resolved references must belong to the audited context")
        used = {
            digest
            for record in self.records
            for digest in (
                *record.evidence_refs.knowledge_ref_digests,
                *record.evidence_refs.campaign_ref_digests,
                *record.evidence_refs.source_ref_digests,
            )
        }
        if used != reference_digests:
            raise DecisionProvenanceError(
                "resolved references must exactly cover cited decision evidence"
            )
        object.__setattr__(self, "audit_digest", stable_digest(self.to_payload()))

    def to_payload(self) -> dict[str, object]:
        return {
            "context_digest": self.context_digest,
            "director_plan_digest": self.director_plan_digest,
            "graph_digest": self.graph_digest,
            "issuance_id": self.issuance_id,
            "records": [item.to_dict() for item in self.records],
            "resolved_references": [item.to_payload() for item in self.resolved_references],
            "schema_version": self.schema_version,
            "snapshot_digest": self.snapshot_digest,
            "variant_id": self.variant_id,
        }


def _instant(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise DecisionProvenanceError(f"{label} must be ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionProvenanceError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DecisionProvenanceError(f"{label} must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _signature(value: str) -> str:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise DecisionProvenanceError("variant authority signature must be an HMAC-SHA256 digest")
    return value


@dataclass(frozen=True)
class IssuedVariantProvenance:
    """Short-lived signed authority for exactly one rendered variant.

    The public dataclasses in this module remain useful audit objects.  This
    envelope is the only promotion input: it signs the full cross-boundary
    identity (tenant/scope, context issuance, reconstructed audit, semantic
    Director plan and render) so importing a private Python capability token
    cannot manufacture an admissible learning artifact.
    """

    schema_version: Literal["1.0"]
    authority_id: str
    authority_key_id: str
    owner_id: str
    campaign_id: str
    source_id: str
    context_issuance_id: str
    context_issuance_digest: str
    snapshot_digest: str
    context_digest: str
    graph_digest: str
    director_plan_digest: str
    decision_audit_digest: str
    bundle_digest: str
    render_artifact_digest: str
    provenance: VariantProvenance
    issued_at: str
    expires_at: str
    signature: str

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise DecisionProvenanceError("unsupported variant authority schema")
        for name in (
            "authority_id",
            "authority_key_id",
            "owner_id",
            "campaign_id",
            "source_id",
            "context_issuance_id",
        ):
            object.__setattr__(self, name, _id(getattr(self, name), name))
        for name in (
            "context_issuance_digest",
            "snapshot_digest",
            "context_digest",
            "graph_digest",
            "director_plan_digest",
            "decision_audit_digest",
            "bundle_digest",
            "render_artifact_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        if not isinstance(self.provenance, VariantProvenance):
            raise DecisionProvenanceError("issued variant provenance is invalid")
        if (
            self.provenance.campaign_id,
            self.provenance.source_id,
            self.provenance.context_issuance_id,
            self.provenance.snapshot_digest,
            self.provenance.editorial_context_digest,
            self.provenance.graph_digest,
            self.provenance.director_plan_digest,
            self.provenance.decision_audit_digest,
            self.provenance.render_artifact_digest,
        ) != (
            self.campaign_id,
            self.source_id,
            self.context_issuance_id,
            self.snapshot_digest,
            self.context_digest,
            self.graph_digest,
            self.director_plan_digest,
            self.decision_audit_digest,
            self.render_artifact_digest,
        ):
            raise DecisionProvenanceError("issued variant provenance binding mismatch")
        object.__setattr__(self, "issued_at", _instant(self.issued_at, "issued_at"))
        object.__setattr__(self, "expires_at", _instant(self.expires_at, "expires_at"))
        if _datetime(self.expires_at) <= _datetime(self.issued_at):
            raise DecisionProvenanceError("variant authority expiry must follow issuance")
        if _datetime(self.expires_at) - _datetime(self.issued_at) > _MAX_VARIANT_ISSUANCE_TTL:
            raise DecisionProvenanceError("variant authority TTL must not exceed 24 hours")
        object.__setattr__(self, "signature", _signature(self.signature))

    @property
    def signature_payload(self) -> dict[str, object]:
        return {
            "authority_id": self.authority_id,
            "authority_key_id": self.authority_key_id,
            "bundle_digest": self.bundle_digest,
            "campaign_id": self.campaign_id,
            "context_digest": self.context_digest,
            "context_issuance_digest": self.context_issuance_digest,
            "context_issuance_id": self.context_issuance_id,
            "decision_audit_digest": self.decision_audit_digest,
            "director_plan_digest": self.director_plan_digest,
            "expires_at": self.expires_at,
            "graph_digest": self.graph_digest,
            "issued_at": self.issued_at,
            "owner_id": self.owner_id,
            "provenance_digest": self.provenance.canonical_digest,
            "render_artifact_digest": self.render_artifact_digest,
            "schema_version": self.schema_version,
            "snapshot_digest": self.snapshot_digest,
            "source_id": self.source_id,
            "variant_id": self.provenance.variant_id,
        }

    @property
    def signing_bytes(self) -> bytes:
        # The shared stable encoder is canonical and avoids transport-specific
        # JSON formatting from becoming part of the authorization surface.
        from .decision_outcomes import canonical_json

        return canonical_json(self.signature_payload).encode("utf-8")


def _decision_record_id(variant_id: str, subject_id: str) -> str:
    material = f"{variant_id}\x1f{subject_id}".encode()
    return f"decision_{hashlib.sha256(material).hexdigest()[:24]}"


def _refs(
    evidence: DirectorDecisionEvidence,
    reference_by_id: dict[str, ResolvedDecisionReference],
) -> DecisionEvidenceRefs:
    return DecisionEvidenceRefs(
        knowledge_ref_digests=tuple(
            reference_by_id[item].note_digest for item in evidence.knowledge_refs
        ),
        campaign_ref_digests=tuple(
            reference_by_id[item].note_digest for item in evidence.campaign_refs
        ),
        source_ref_digests=tuple(
            reference_by_id[item].note_digest for item in evidence.source_refs
        ),
    )


def materialize_director_decision_provenance(
    plan: EditorialDirectorPlanV22,
    *,
    verified: VerifiedEditorialContext,
    now: str,
    variant_id: str,
    created_at: str,
) -> DecisionProvenanceBundle:
    """Resolve citations through an already verified, short-lived capability."""
    variant_id = _id(variant_id, "variant_id")
    if not isinstance(verified, VerifiedEditorialContext):
        raise DecisionProvenanceError("verified must be a VerifiedEditorialContext")
    verified.validate(plan, now=now)
    issued = verified.issued
    snapshot = verified.snapshot
    context = verified.context
    notes = {item.note.note_id: item.note for item in context.selected_notes}
    cited_ids = {
        note_id
        for evidence in plan.decision_evidence
        for note_id in (
            *evidence.knowledge_refs,
            *evidence.campaign_refs,
            *evidence.source_refs,
        )
    }
    references_list: list[ResolvedDecisionReference] = []
    for note_id in sorted(cited_ids):
        payload_digest, note_digest = _note_digests(
            context.context_digest,
            notes[note_id],
        )
        references_list.append(
            ResolvedDecisionReference(
                note_id,
                notes[note_id].version,
                notes[note_id].vault,
                context.context_digest,
                payload_digest,
                note_digest,
            )
        )
    references = tuple(references_list)
    reference_by_id = {item.note_id: item for item in references}
    evidence_by_id = {item.decision_id: item for item in plan.decision_evidence}
    records: list[EditorialDecisionRecord] = []
    plan_evidence = evidence_by_id["plan"]
    records.append(
        EditorialDecisionRecord(
            decision_id=_decision_record_id(variant_id, "plan"),
            campaign_id=context.question.campaign_id,
            subject_id="plan",
            created_at=created_at,
            decision_type="plan_hypothesis",
            decision={
                "campaign_hypothesis": plan.controls.campaign_hypothesis,
                "editorial_thesis": plan.controls.editorial_thesis,
                "shot_ids": [shot.shot_id for shot in plan.controls.shots],
            },
            rationale=plan.controls.editorial_thesis,
            evidence_refs=_refs(plan_evidence, reference_by_id),
            policy_version=context.editorial_policy_version,
        )
    )
    for shot in plan.controls.shots:
        evidence = evidence_by_id[shot.shot_id]
        records.append(
            EditorialDecisionRecord(
                decision_id=_decision_record_id(variant_id, shot.shot_id),
                campaign_id=context.question.campaign_id,
                subject_id=shot.shot_id,
                created_at=created_at,
                decision_type="shot_selection",
                decision=asdict(shot),
                rationale=(
                    f"{shot.entry_motivation} -> {shot.exit_motivation}; "
                    f"{shot.joint_motivation} via {shot.continuity_strategy}"
                ),
                evidence_refs=_refs(evidence, reference_by_id),
                policy_version=context.editorial_policy_version,
            )
        )
    return DecisionProvenanceBundle(
        DECISION_PROVENANCE_SCHEMA_VERSION,
        variant_id,
        issued.issuance_id,
        snapshot.digest,
        context.context_digest,
        context.graph_digest,
        director_plan_digest(plan),
        tuple(records),
        references,
    )


def attest_variant_provenance(
    bundle: DecisionProvenanceBundle,
    plan: EditorialDirectorPlanV22,
    *,
    verified: VerifiedEditorialContext,
    now: str,
    render_artifact_digest: str,
    created_at: str,
) -> VerifiedVariantProvenance:
    """Attest one render against a re-materialised signed decision audit.

    The supplied bundle is never trusted simply because it is an immutable
    dataclass: this function rebuilds it from the current verified capability,
    plan and creation time, then requires exact equality before exposing an
    outcome provenance capability.  Callers may still read raw
    ``VariantProvenance`` values for diagnostics, but only this return value
    can enter :func:`learning_authority.issue_promotion_authority`.
    """
    if not isinstance(bundle, DecisionProvenanceBundle):
        raise DecisionProvenanceError("bundle must be a DecisionProvenanceBundle")
    if not isinstance(verified, VerifiedEditorialContext):
        raise DecisionProvenanceError("verified must be a VerifiedEditorialContext")
    try:
        rebuilt = materialize_director_decision_provenance(
            plan,
            verified=verified,
            now=now,
            variant_id=bundle.variant_id,
            created_at=created_at,
        )
    except ValueError as exc:
        raise DecisionProvenanceError(
            "decision audit does not exactly match the verified context and plan"
        ) from exc
    if rebuilt != bundle:
        raise DecisionProvenanceError(
            "decision audit does not exactly match the verified context and plan"
        )
    context = verified.context
    plan_record = next((item for item in rebuilt.records if item.subject_id == "plan"), None)
    if plan_record is None:
        raise DecisionProvenanceError("decision audit is missing the plan record")
    provenance = VariantProvenance(
        variant_id=rebuilt.variant_id,
        decision_id=plan_record.decision_id,
        campaign_id=context.question.campaign_id,
        source_id=context.question.source_id,
        campaign_fingerprint=context.campaign_fingerprint,
        research_content_digest=context.research_digest,
        editorial_context_digest=context.context_digest,
        graph_digest=context.graph_digest,
        director_plan_digest=rebuilt.director_plan_digest,
        editorial_policy_version=context.editorial_policy_version,
        director_schema_version=plan.schema_version,
        campaign_hypothesis=plan.controls.campaign_hypothesis,
        render_artifact_digest=render_artifact_digest,
        created_at=created_at,
        snapshot_digest=rebuilt.snapshot_digest,
        context_issuance_id=rebuilt.issuance_id,
        decision_audit_digest=rebuilt.audit_digest,
    )
    return VerifiedVariantProvenance(
        provenance,
        _token=_VERIFIED_VARIANT_PROVENANCE_TOKEN,
    )


def issue_variant_provenance(
    signer: VariantProvenanceSigner,
    bundle: DecisionProvenanceBundle,
    plan: EditorialDirectorPlanV22,
    *,
    issued_context: IssuedEditorialContext,
    snapshot: object,
    context: object,
    graph: EditorialBeatGraph,
    context_verifier: EditorialContextVerifier,
    expected_owner_id: str,
    expected_campaign_id: str,
    expected_source_id: str,
    now: str,
    authority_id: str,
    expires_at: str,
    render_artifact_digest: str,
    created_at: str,
    research_pack: object | None = None,
    research_attestations: object | None = None,
    vision_evidence: object | None = None,
    vision_evidence_verifier: object | None = None,
) -> IssuedVariantProvenance:
    """Re-verify context and issue the sole promotion-admissible variant proof.

    ``VerifiedEditorialContext`` and ``VerifiedVariantProvenance`` are useful
    in-process ergonomics but Python module attributes are not a security
    boundary.  The issuer therefore receives the signed context envelope plus
    its verifier and re-runs the complete context check before signing this
    independent, short-lived artifact.
    """
    if not hasattr(signer, "key_id") or not callable(getattr(signer, "sign", None)):
        raise DecisionProvenanceError("signer must implement VariantProvenanceSigner")
    authority_key_id = _id(signer.key_id, "variant authority key_id")
    current = _instant(now, "now")
    expiry = _instant(expires_at, "expires_at")
    if _datetime(expiry) <= _datetime(current):
        raise DecisionProvenanceError("variant authority expiry must follow issuance")
    if _datetime(expiry) - _datetime(current) > _MAX_VARIANT_ISSUANCE_TTL:
        raise DecisionProvenanceError("variant authority TTL must not exceed 24 hours")
    try:
        # Narrow typing is intentional here: the authority module remains the
        # canonical validator for every context attachment.  Runtime types are
        # checked there, rather than duplicated and allowed to drift here.
        verified = verify_editorial_context_capability(
            issued_context,
            snapshot,  # type: ignore[arg-type]
            context,  # type: ignore[arg-type]
            graph,
            verifier=context_verifier,
            now=current,
            expected_owner_id=expected_owner_id,
            expected_campaign_id=expected_campaign_id,
            expected_source_id=expected_source_id,
            research_pack=research_pack,  # type: ignore[arg-type]
            research_attestations=research_attestations,  # type: ignore[arg-type]
            vision_evidence=vision_evidence,  # type: ignore[arg-type]
            vision_evidence_verifier=vision_evidence_verifier,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        raise DecisionProvenanceError("signed editorial context is invalid") from exc
    capability = attest_variant_provenance(
        bundle,
        plan,
        verified=verified,
        now=current,
        render_artifact_digest=render_artifact_digest,
        created_at=created_at,
    )
    provenance = capability.provenance
    unsigned = IssuedVariantProvenance(
        schema_version="1.0",
        authority_id=authority_id,
        authority_key_id=authority_key_id,
        owner_id=verified.snapshot.owner_id,
        campaign_id=provenance.campaign_id,
        source_id=provenance.source_id,
        context_issuance_id=verified.issued.issuance_id,
        context_issuance_digest=stable_digest(verified.issued.unsigned_payload()),
        snapshot_digest=verified.snapshot.digest,
        context_digest=verified.context.context_digest,
        graph_digest=verified.context.graph_digest,
        director_plan_digest=director_plan_digest(plan),
        decision_audit_digest=bundle.audit_digest,
        bundle_digest=stable_digest(bundle.to_payload()),
        render_artifact_digest=provenance.render_artifact_digest,
        provenance=provenance,
        issued_at=current,
        expires_at=expiry,
        signature="0" * 64,
    )
    return IssuedVariantProvenance(
        schema_version=unsigned.schema_version,
        authority_id=unsigned.authority_id,
        authority_key_id=unsigned.authority_key_id,
        owner_id=unsigned.owner_id,
        campaign_id=unsigned.campaign_id,
        source_id=unsigned.source_id,
        context_issuance_id=unsigned.context_issuance_id,
        context_issuance_digest=unsigned.context_issuance_digest,
        snapshot_digest=unsigned.snapshot_digest,
        context_digest=unsigned.context_digest,
        graph_digest=unsigned.graph_digest,
        director_plan_digest=unsigned.director_plan_digest,
        decision_audit_digest=unsigned.decision_audit_digest,
        bundle_digest=unsigned.bundle_digest,
        render_artifact_digest=unsigned.render_artifact_digest,
        provenance=unsigned.provenance,
        issued_at=unsigned.issued_at,
        expires_at=unsigned.expires_at,
        signature=signer.sign(unsigned.signing_bytes),
    )


def verify_issued_variant_provenance(
    issued: IssuedVariantProvenance,
    verifier: VariantProvenanceVerifier,
    *,
    owner_id: str,
    campaign_id: str,
    source_id: str | None = None,
    now: str,
    require_current: bool = True,
) -> VariantProvenance:
    """Verify a sealed variant proof immediately before its sensitive use.

    ``require_current`` is true for online hand-offs such as experiment
    registration.  Historical learning may set it to false: the envelope then
    proves what was attested at render time without pretending that a
    short-lived bearer credential must still be live days later.  Signature,
    tenant scope and the complete immutable provenance binding are always
    checked.
    """
    if not isinstance(issued, IssuedVariantProvenance):
        raise DecisionProvenanceError("issued must be an IssuedVariantProvenance")
    if not hasattr(verifier, "key_id") or not callable(getattr(verifier, "verify", None)):
        raise DecisionProvenanceError("verifier must implement VariantProvenanceVerifier")
    if _id(verifier.key_id, "variant verifier key_id") != issued.authority_key_id:
        raise DecisionProvenanceError("variant authority key rotation mismatch")
    expected = (_id(owner_id, "owner_id"), _id(campaign_id, "campaign_id"))
    if (issued.owner_id, issued.campaign_id) != expected:
        raise DecisionProvenanceError("issued variant tenant scope mismatch")
    if source_id is not None and issued.source_id != _id(source_id, "source_id"):
        raise DecisionProvenanceError("issued variant source scope mismatch")
    current = _instant(now, "now")
    if not isinstance(require_current, bool):
        raise DecisionProvenanceError("require_current must be a boolean")
    if _datetime(current) < _datetime(issued.issued_at):
        raise DecisionProvenanceError("issued variant is not yet valid")
    if require_current and _datetime(current) >= _datetime(issued.expires_at):
        raise DecisionProvenanceError("issued variant is expired")
    if not verifier.verify(issued.signing_bytes, issued.signature):
        raise DecisionProvenanceError("issued variant signature is invalid")
    return issued.provenance


def build_variant_provenance(*args: object, **kwargs: object) -> None:
    """Disabled raw constructor retained only to make unsafe callers fail closed.

    Use :func:`attest_variant_provenance`; it requires the verified editorial
    context capability and returns the non-forgeable promotion input.
    """
    del args, kwargs
    raise DecisionProvenanceError(
        "raw variant provenance is disabled; use attest_variant_provenance"
    )
