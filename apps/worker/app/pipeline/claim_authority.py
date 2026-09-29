"""Closed claim-to-evidence authority for the local editorial path.

This module deliberately stores a claim's *digest*, not its wording.  It can
therefore audit an assertion without creating a second channel through which a
web finding could become a caption or an overlay.  Transcript word IDs and the
validated beat graph remain the sole timing/source authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, Protocol

from .editorial_beats import EditorialBeatGraph, validate_editorial_beat_graph
from .editorial_context import graph_digest
from .editorial_director_v22 import EditorialDirectorPlanV22
from .knowledge_vault import GraphEvidenceRef
from .vision_evidence_authority import (
    VerifiedVisionEvidenceSet,
    VisionEvidenceAuthorityError,
    VisionEvidenceVerifier,
)

if TYPE_CHECKING:
    from .editorial_context_authority import VerifiedEditorialContext


CLAIM_AUTHORITY_SCHEMA_VERSION = "1.0"
ClaimOrigin = Literal["source_transcript", "research_finding", "operator"]
ClaimState = Literal["unresolved", "verified", "approved"]
ClaimEvidenceKind = Literal["source_words", "verified_visual", "approved_overlay"]
ClaimUsage = Literal["spoken_source", "caption", "overlay", "decision_rationale"]

_ID = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_HEX = re.compile(r"^[a-f0-9]{64}$")
_ORIGINS = frozenset(ClaimOrigin.__args__)
_STATES = frozenset(ClaimState.__args__)
_EVIDENCE_KINDS = frozenset(ClaimEvidenceKind.__args__)
_USAGES = frozenset(ClaimUsage.__args__)
_MAX_AUTHORITY_TTL = timedelta(hours=24)


class ClaimAuthorityError(ValueError):
    """A claim is not authorised for this exact editorial decision."""


class ClaimAuthoritySigner(Protocol):
    """Authenticated reviewer/service key used to seal an exact claim batch."""

    key_id: str

    def sign(self, payload: bytes) -> str: ...


class ClaimAuthorityVerifier(Protocol):
    key_id: str

    def verify(self, payload: bytes, signature: str) -> bool: ...


@dataclass(frozen=True)
class HMACSHA256ClaimAuthority:
    """Local signing primitive; production key custody stays outside this module."""

    key_id: str
    secret: bytes = field(repr=False)

    def __post_init__(self) -> None:
        _id(self.key_id, "authority key_id", opaque=True)
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise ClaimAuthorityError("authority secret must be at least 32 bytes")

    def sign(self, payload: bytes) -> str:
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return isinstance(signature, str) and hmac.compare_digest(self.sign(payload), signature)


def _id(value: object, label: str, *, opaque: bool = False) -> str:
    pattern = _OPAQUE_ID if opaque else _ID
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ClaimAuthorityError(f"{label} is invalid")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise ClaimAuthorityError(f"{label} must be a SHA-256 digest")
    return value


def _instant(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ClaimAuthorityError(f"{label} must be ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ClaimAuthorityError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ClaimAuthorityError(f"{label} must include a timezone")
    return parsed.astimezone(UTC)


def _canonical_instant(value: object, label: str) -> str:
    return _instant(value, label).isoformat(timespec="seconds").replace("+00:00", "Z")


def claim_content_digest(statement: str) -> str:
    """Return an audit-only digest without retaining or exposing claim text."""
    if not isinstance(statement, str) or not statement.strip() or len(statement) > 500:
        raise ClaimAuthorityError("claim statement must be a bounded non-empty string")
    return hashlib.sha256(statement.strip().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ClaimAtom:
    """A scoped assertion whose words are intentionally outside the prompt API."""

    schema_version: Literal["1.0"]
    claim_id: str
    origin: ClaimOrigin
    state: ClaimState
    content_digest: str
    campaign_id: str
    source_id: str
    valid_from: str
    valid_until: str
    research_section: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != CLAIM_AUTHORITY_SCHEMA_VERSION:
            raise ClaimAuthorityError("unsupported claim schema")
        _id(self.claim_id, "claim_id")
        if self.origin not in _ORIGINS or self.state not in _STATES:
            raise ClaimAuthorityError("claim origin or state is unsupported")
        _digest(self.content_digest, "claim.content_digest")
        _id(self.campaign_id, "claim.campaign_id", opaque=True)
        _id(self.source_id, "claim.source_id", opaque=True)
        valid_from = _canonical_instant(self.valid_from, "claim.valid_from")
        valid_until = _canonical_instant(self.valid_until, "claim.valid_until")
        if _instant(valid_until, "claim.valid_until") <= _instant(valid_from, "claim.valid_from"):
            raise ClaimAuthorityError("claim.valid_until must be after claim.valid_from")
        object.__setattr__(self, "valid_from", valid_from)
        object.__setattr__(self, "valid_until", valid_until)
        if self.origin == "research_finding":
            if self.research_section != "claims_requiring_verification":
                raise ClaimAuthorityError(
                    "research claims must declare claims_requiring_verification"
                )
        elif self.research_section is not None:
            raise ClaimAuthorityError("only research claims may declare research_section")

    def is_current(self, now: str) -> bool:
        instant = _instant(now, "now")
        return (
            _instant(self.valid_from, "claim.valid_from")
            <= instant
            < _instant(self.valid_until, "claim.valid_until")
        )


@dataclass(frozen=True)
class ClaimEvidence:
    """One verifier-attested proof binding a claim to graph-owned evidence."""

    schema_version: Literal["1.0"]
    evidence_id: str
    claim_id: str
    kind: ClaimEvidenceKind
    graph_refs: tuple[GraphEvidenceRef, ...]
    graph_digest: str
    verifier: str
    valid_from: str
    valid_until: str

    def __post_init__(self) -> None:
        if self.schema_version != CLAIM_AUTHORITY_SCHEMA_VERSION:
            raise ClaimAuthorityError("unsupported claim evidence schema")
        _id(self.evidence_id, "evidence_id")
        _id(self.claim_id, "evidence.claim_id")
        if self.kind not in _EVIDENCE_KINDS:
            raise ClaimAuthorityError("claim evidence kind is unsupported")
        if not isinstance(self.graph_refs, tuple) or not self.graph_refs:
            raise ClaimAuthorityError("claim evidence needs graph references")
        if not all(isinstance(item, GraphEvidenceRef) for item in self.graph_refs):
            raise ClaimAuthorityError("claim evidence graph_refs are invalid")
        if len({(item.kind, item.evidence_id) for item in self.graph_refs}) != len(self.graph_refs):
            raise ClaimAuthorityError("claim evidence graph_refs cannot repeat")
        _digest(self.graph_digest, "evidence.graph_digest")
        _id(self.verifier, "evidence.verifier", opaque=True)
        valid_from = _canonical_instant(self.valid_from, "evidence.valid_from")
        valid_until = _canonical_instant(self.valid_until, "evidence.valid_until")
        if _instant(valid_until, "evidence.valid_until") <= _instant(
            valid_from, "evidence.valid_from"
        ):
            raise ClaimAuthorityError("evidence.valid_until must be after evidence.valid_from")
        object.__setattr__(self, "valid_from", valid_from)
        object.__setattr__(self, "valid_until", valid_until)

    def is_current(self, now: str) -> bool:
        instant = _instant(now, "now")
        return (
            _instant(self.valid_from, "evidence.valid_from")
            <= instant
            < _instant(self.valid_until, "evidence.valid_until")
        )


@dataclass(frozen=True)
class ClaimUse:
    """A claim's one requested use in one Director shot, never its text."""

    schema_version: Literal["1.0"]
    claim_id: str
    decision_id: str
    beat_id: str
    source_moment_id: str
    usage: ClaimUsage
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != CLAIM_AUTHORITY_SCHEMA_VERSION:
            raise ClaimAuthorityError("unsupported claim use schema")
        for name in ("claim_id", "decision_id", "beat_id", "source_moment_id"):
            _id(getattr(self, name), name)
        if self.usage not in _USAGES:
            raise ClaimAuthorityError("claim usage is unsupported")
        if not isinstance(self.evidence_ids, tuple) or not self.evidence_ids:
            raise ClaimAuthorityError("claim use needs evidence_ids")
        checked = tuple(_id(item, "claim use evidence_id") for item in self.evidence_ids)
        if len(checked) != len(set(checked)):
            raise ClaimAuthorityError("claim use evidence_ids cannot repeat")
        object.__setattr__(self, "evidence_ids", checked)


def _plan_digest(plan: EditorialDirectorPlanV22) -> str:
    """Small stable binding; the V22 controls keep ownership of word IDs."""
    if not isinstance(plan, EditorialDirectorPlanV22):
        raise ClaimAuthorityError("plan must be an EditorialDirectorPlanV22")
    payload = {
        "context_digest": plan.context_digest,
        "graph_digest": plan.graph_digest,
        "shots": [
            {
                "beat_id": shot.beat_id,
                "from_word_id": shot.from_word_id,
                "shot_id": shot.shot_id,
                "to_word_id": shot.to_word_id,
            }
            for shot in plan.controls.shots
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _graph_targets(graph: EditorialBeatGraph, beat_id: str) -> tuple[str, set[tuple[str, str]]]:
    beats = {item.beat_id: item for item in graph.editorial_beats}
    moments = {item.moment_id: item for item in graph.source_moments}
    beat = beats.get(beat_id)
    if beat is None or beat.source_moment_id not in moments:
        raise ClaimAuthorityError("claim use references an unknown graph beat")
    targets = {("source_moment", beat.source_moment_id)}
    targets.update(("visual_beat", item) for item in beat.visual_ids)
    return beat.source_moment_id, targets


def _validate_evidence_for_use(
    claim: ClaimAtom,
    evidence: ClaimEvidence,
    use: ClaimUse,
    *,
    graph: EditorialBeatGraph,
    now: str,
    vision_evidence: VerifiedVisionEvidenceSet | None,
    vision_evidence_verifier: VisionEvidenceVerifier | None,
    owner_id: str,
    campaign_id: str,
    source_id: str,
) -> None:
    if evidence.claim_id != claim.claim_id:
        raise ClaimAuthorityError("claim evidence belongs to a different claim")
    if not evidence.is_current(now):
        raise ClaimAuthorityError("claim evidence is expired or not yet valid")
    if evidence.graph_digest != graph_digest(graph):
        raise ClaimAuthorityError("claim evidence graph digest does not match current graph")
    source_moment_id, allowed = _graph_targets(graph, use.beat_id)
    if use.source_moment_id != source_moment_id:
        raise ClaimAuthorityError("claim use source moment does not match its exact beat")
    refs = {(item.kind, item.evidence_id) for item in evidence.graph_refs}
    if not refs.issubset(allowed):
        raise ClaimAuthorityError("claim evidence does not bind the exact decision beat")
    if evidence.kind == "source_words":
        if refs != {("source_moment", source_moment_id)}:
            raise ClaimAuthorityError("source_words evidence must bind the exact source moment")
    elif evidence.kind == "verified_visual":
        if not refs or any(kind != "visual_beat" for kind, _ in refs):
            raise ClaimAuthorityError("verified_visual evidence must bind a visual beat")
        visuals = {item.visual_id: item for item in graph.visual_beats}
        visual_ids: list[str] = []
        for _, visual_id in refs:
            visual = visuals[visual_id]
            if visual.provenance != "verified_candidate":
                raise ClaimAuthorityError("visual claim evidence is not candidate verified")
            visual_ids.append(visual_id)
        if not isinstance(vision_evidence, VerifiedVisionEvidenceSet):
            raise ClaimAuthorityError(
                "verified_visual evidence requires a VerifiedVisionEvidenceSet"
            )
        try:
            vision_evidence.validate_visual_ids(
                tuple(visual_ids),
                verifier=vision_evidence_verifier,
                graph=graph,
                owner_id=owner_id,
                campaign_id=campaign_id,
                source_id=source_id,
                now=now,
            )
        except VisionEvidenceAuthorityError as exc:
            raise ClaimAuthorityError(
                "verified_visual evidence is not covered by the vision authority"
            ) from exc
    elif evidence.kind == "approved_overlay":
        if refs != {("source_moment", source_moment_id)}:
            raise ClaimAuthorityError("approved overlay must bind the exact source moment")


def _validate_usage(claim: ClaimAtom, use: ClaimUse, evidences: tuple[ClaimEvidence, ...]) -> None:
    kinds = {item.kind for item in evidences}
    if claim.state == "unresolved":
        raise ClaimAuthorityError("unresolved claim cannot influence an editorial decision")
    if claim.origin == "research_finding":
        # A finding from the web-research verification bucket may narrow a
        # decision once independently proved, but can never supply copy.
        if use.usage != "decision_rationale":
            raise ClaimAuthorityError(
                "research findings can never become spoken copy, caption, or overlay"
            )
        if claim.state != "verified":
            raise ClaimAuthorityError("research finding must be independently verified")
    if use.usage == "spoken_source":
        if claim.origin != "source_transcript" or kinds != {"source_words"}:
            raise ClaimAuthorityError("spoken claim requires exact source_words evidence")
    elif use.usage == "caption":
        if claim.origin != "source_transcript" or kinds != {"source_words"}:
            raise ClaimAuthorityError("caption claim requires exact source transcript words")
    elif use.usage == "overlay":
        if claim.origin != "operator" or claim.state != "approved" or kinds != {"approved_overlay"}:
            raise ClaimAuthorityError("overlay claims require an explicit approved_overlay")


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _claim_payload(claim: ClaimAtom) -> dict[str, object]:
    return {
        "schema_version": claim.schema_version,
        "claim_id": claim.claim_id,
        "origin": claim.origin,
        "state": claim.state,
        "content_digest": claim.content_digest,
        "campaign_id": claim.campaign_id,
        "source_id": claim.source_id,
        "valid_from": claim.valid_from,
        "valid_until": claim.valid_until,
        "research_section": claim.research_section,
    }


def _evidence_payload(evidence: ClaimEvidence) -> dict[str, object]:
    return {
        "schema_version": evidence.schema_version,
        "evidence_id": evidence.evidence_id,
        "claim_id": evidence.claim_id,
        "kind": evidence.kind,
        "graph_refs": [
            {"kind": item.kind, "evidence_id": item.evidence_id} for item in evidence.graph_refs
        ],
        "graph_digest": evidence.graph_digest,
        "verifier": evidence.verifier,
        "valid_from": evidence.valid_from,
        "valid_until": evidence.valid_until,
    }


def _use_payload(use: ClaimUse) -> dict[str, object]:
    return {
        "schema_version": use.schema_version,
        "claim_id": use.claim_id,
        "decision_id": use.decision_id,
        "beat_id": use.beat_id,
        "source_moment_id": use.source_moment_id,
        "usage": use.usage,
        "evidence_ids": list(use.evidence_ids),
    }


@dataclass(frozen=True)
class ClaimUseEnvelope:
    """Exact, portable request approved by an authenticated claim reviewer.

    This deliberately includes projections rather than only their digests: the
    verifier replays every editorial and evidence constraint after it verifies
    the HMAC.  A caller cannot replace a signed digest with different public
    ``ClaimAtom`` objects and keep a valid decision.
    """

    schema_version: str
    owner_id: str
    campaign_id: str
    source_id: str
    context_issuance_id: str
    context_digest: str
    graph_digest: str
    plan_digest: str
    vision_evidence_audit_digest: str | None
    claims: tuple[ClaimAtom, ...]
    evidences: tuple[ClaimEvidence, ...]
    uses: tuple[ClaimUse, ...]
    issuer_id: str
    reviewer_id: str
    issued_at: str
    expires_at: str

    def __post_init__(self) -> None:
        if self.schema_version != CLAIM_AUTHORITY_SCHEMA_VERSION:
            raise ClaimAuthorityError("unsupported claim authority schema")
        for name in (
            "owner_id",
            "campaign_id",
            "source_id",
            "context_issuance_id",
            "issuer_id",
            "reviewer_id",
        ):
            _id(getattr(self, name), name, opaque=True)
        for name in ("context_digest", "graph_digest", "plan_digest"):
            _digest(getattr(self, name), name)
        if self.vision_evidence_audit_digest is not None:
            _digest(self.vision_evidence_audit_digest, "vision_evidence_audit_digest")
        for name, cls in (("claims", ClaimAtom), ("evidences", ClaimEvidence), ("uses", ClaimUse)):
            items = getattr(self, name)
            if (
                not isinstance(items, tuple)
                or not items
                or not all(isinstance(item, cls) for item in items)
            ):
                raise ClaimAuthorityError(f"{name} must be a non-empty immutable tuple")
        if len({item.claim_id for item in self.claims}) != len(self.claims):
            raise ClaimAuthorityError("claims cannot repeat IDs")
        if len({item.evidence_id for item in self.evidences}) != len(self.evidences):
            raise ClaimAuthorityError("evidences cannot repeat IDs")
        if len({(item.claim_id, item.decision_id, item.usage) for item in self.uses}) != len(
            self.uses
        ):
            raise ClaimAuthorityError("claim uses cannot repeat one claim decision usage")
        issued_at = _canonical_instant(self.issued_at, "issued_at")
        expires_at = _canonical_instant(self.expires_at, "expires_at")
        issued, expires = _instant(issued_at, "issued_at"), _instant(expires_at, "expires_at")
        if expires <= issued:
            raise ClaimAuthorityError("expires_at must be after issued_at")
        if expires - issued > _MAX_AUTHORITY_TTL:
            raise ClaimAuthorityError("claim authority lifetime exceeds the hard limit")
        object.__setattr__(self, "issued_at", issued_at)
        object.__setattr__(self, "expires_at", expires_at)

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "owner_id": self.owner_id,
            "campaign_id": self.campaign_id,
            "source_id": self.source_id,
            "context_issuance_id": self.context_issuance_id,
            "context_digest": self.context_digest,
            "graph_digest": self.graph_digest,
            "plan_digest": self.plan_digest,
            "vision_evidence_audit_digest": self.vision_evidence_audit_digest,
            "claims": [_claim_payload(item) for item in self.claims],
            "evidences": [_evidence_payload(item) for item in self.evidences],
            "uses": [_use_payload(item) for item in self.uses],
            "issuer_id": self.issuer_id,
            "reviewer_id": self.reviewer_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }

    def canonical_payload(self) -> bytes:
        return _canonical(self.unsigned_payload())


@dataclass(frozen=True)
class IssuedClaimAuthority:
    """HMAC-sealed authority that compile/validate must verify every use."""

    envelope: ClaimUseEnvelope
    authority_key_id: str
    authority_id: str
    signature: str

    def __post_init__(self) -> None:
        if not isinstance(self.envelope, ClaimUseEnvelope):
            raise ClaimAuthorityError("envelope must be a ClaimUseEnvelope")
        _id(self.authority_key_id, "authority_key_id", opaque=True)
        _id(self.authority_id, "authority_id", opaque=True)
        if not isinstance(self.signature, str) or not _HEX.fullmatch(self.signature):
            raise ClaimAuthorityError("signature must be a SHA-256 hexadecimal value")

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "envelope": self.envelope.unsigned_payload(),
            "authority_key_id": self.authority_key_id,
            "authority_id": self.authority_id,
        }

    def canonical_payload(self) -> bytes:
        return _canonical(self.unsigned_payload())

    @property
    def audit_digest(self) -> str:
        return hashlib.sha256(
            _canonical({"payload": self.unsigned_payload(), "signature": self.signature})
        ).hexdigest()


# Kept as a source-compatible name for callers that import it.  It is no
# longer accepted by the compiler: only an ``IssuedClaimAuthority`` reverified
# with a key may influence the edit.
VerifiedClaimUses = IssuedClaimAuthority


def _validate_envelope_content(
    envelope: ClaimUseEnvelope,
    *,
    verified_context: VerifiedEditorialContext,
    plan: EditorialDirectorPlanV22,
    now: str,
) -> None:
    verified_context.validate(plan, now=now)
    graph = verified_context.graph
    validate_editorial_beat_graph(graph)
    expected = (
        verified_context.issued.owner_id,
        verified_context.issued.campaign_id,
        verified_context.issued.source_id,
        verified_context.issued.issuance_id,
        verified_context.context.context_digest,
        graph_digest(graph),
        _plan_digest(plan),
        verified_context.issued.vision_evidence_audit_digest,
    )
    actual = (
        envelope.owner_id,
        envelope.campaign_id,
        envelope.source_id,
        envelope.context_issuance_id,
        envelope.context_digest,
        envelope.graph_digest,
        envelope.plan_digest,
        envelope.vision_evidence_audit_digest,
    )
    if actual != expected:
        raise ClaimAuthorityError("claim authority is not bound to this exact tenant context plan")
    instant = _instant(now, "now")
    if instant < _instant(envelope.issued_at, "issued_at"):
        raise ClaimAuthorityError("claim authority is not yet valid")
    if instant >= _instant(envelope.expires_at, "expires_at"):
        raise ClaimAuthorityError("claim authority is expired")
    context_expiry = _instant(verified_context.issued.expires_at, "context.expires_at")
    if _instant(envelope.expires_at, "expires_at") > context_expiry:
        raise ClaimAuthorityError("claim authority cannot outlive its editorial context")
    claims_by_id = {item.claim_id: item for item in envelope.claims}
    evidence_by_id = {item.evidence_id: item for item in envelope.evidences}
    shots = {item.shot_id: item for item in plan.controls.shots}
    for use in envelope.uses:
        claim = claims_by_id.get(use.claim_id)
        shot = shots.get(use.decision_id)
        if claim is None or shot is None:
            raise ClaimAuthorityError("claim use references an unknown claim or decision")
        if (claim.campaign_id, claim.source_id) != (envelope.campaign_id, envelope.source_id):
            raise ClaimAuthorityError("claim scope does not match the signed authority")
        if not claim.is_current(now):
            raise ClaimAuthorityError("claim is expired or not yet valid")
        if use.beat_id != shot.beat_id:
            raise ClaimAuthorityError("claim use beat does not match the exact decision beat")
        selected = tuple(
            evidence_by_id[item] for item in use.evidence_ids if item in evidence_by_id
        )
        if len(selected) != len(use.evidence_ids):
            raise ClaimAuthorityError("claim use references unknown evidence")
        for evidence in selected:
            _validate_evidence_for_use(
                claim,
                evidence,
                use,
                graph=graph,
                now=now,
                vision_evidence=verified_context.vision_evidence,
                vision_evidence_verifier=verified_context.vision_evidence_verifier,
                owner_id=envelope.owner_id,
                campaign_id=envelope.campaign_id,
                source_id=envelope.source_id,
            )
        _validate_usage(claim, use, selected)
        if claim.origin == "operator":
            if claim.state != "approved" or any(
                item.kind != "approved_overlay" for item in selected
            ):
                raise ClaimAuthorityError("operator claim requires an approved overlay review")
            if any(item.verifier != envelope.reviewer_id for item in selected):
                raise ClaimAuthorityError("approved overlay must name the signed reviewer")


def issue_claim_authority(
    verified_context: VerifiedEditorialContext,
    plan: EditorialDirectorPlanV22,
    *,
    claims: tuple[ClaimAtom, ...],
    evidences: tuple[ClaimEvidence, ...],
    uses: tuple[ClaimUse, ...],
    signer: ClaimAuthoritySigner,
    issuer_id: str,
    reviewer_id: str,
    issued_at: str,
    expires_at: str,
    authority_id: str,
) -> IssuedClaimAuthority:
    """Seal an exact reviewer-approved batch after replaying all constraints."""
    envelope = ClaimUseEnvelope(
        CLAIM_AUTHORITY_SCHEMA_VERSION,
        verified_context.issued.owner_id,
        verified_context.issued.campaign_id,
        verified_context.issued.source_id,
        verified_context.issued.issuance_id,
        verified_context.context.context_digest,
        graph_digest(verified_context.graph),
        _plan_digest(plan),
        verified_context.issued.vision_evidence_audit_digest,
        claims,
        evidences,
        uses,
        _id(issuer_id, "issuer_id", opaque=True),
        _id(reviewer_id, "reviewer_id", opaque=True),
        issued_at,
        expires_at,
    )
    _validate_envelope_content(
        envelope, verified_context=verified_context, plan=plan, now=issued_at
    )
    key_id = _id(signer.key_id, "signer.key_id", opaque=True)
    unsigned = {
        "envelope": envelope.unsigned_payload(),
        "authority_key_id": key_id,
        "authority_id": _id(authority_id, "authority_id", opaque=True),
    }
    return IssuedClaimAuthority(
        envelope=envelope,
        authority_key_id=key_id,
        authority_id=unsigned["authority_id"],  # type: ignore[arg-type]
        signature=signer.sign(_canonical(unsigned)),
    )


def authorize_claim_uses(
    verified_context: VerifiedEditorialContext,
    plan: EditorialDirectorPlanV22,
    *,
    claims: tuple[ClaimAtom, ...],
    evidences: tuple[ClaimEvidence, ...],
    uses: tuple[ClaimUse, ...],
    signer: ClaimAuthoritySigner,
    issuer_id: str,
    reviewer_id: str,
    issued_at: str,
    expires_at: str,
    authority_id: str,
) -> IssuedClaimAuthority:
    """Compatibility name for :func:`issue_claim_authority`; unsigned uses are gone."""
    return issue_claim_authority(
        verified_context,
        plan,
        claims=claims,
        evidences=evidences,
        uses=uses,
        signer=signer,
        issuer_id=issuer_id,
        reviewer_id=reviewer_id,
        issued_at=issued_at,
        expires_at=expires_at,
        authority_id=authority_id,
    )


def validate_claim_authority(
    authority: IssuedClaimAuthority,
    *,
    verified_context: VerifiedEditorialContext,
    plan: EditorialDirectorPlanV22,
    now: str,
    verifier: ClaimAuthorityVerifier | None,
) -> None:
    """Verify HMAC, TTL, scope and the full evidence graph at point of use."""
    if not isinstance(authority, IssuedClaimAuthority):
        raise ClaimAuthorityError("claim authority must be an IssuedClaimAuthority")
    if verifier is None:
        raise ClaimAuthorityError("claim authority requires a verifier at point of use")
    if authority.authority_key_id != _id(verifier.key_id, "verifier.key_id", opaque=True):
        raise ClaimAuthorityError("claim authority key rotation mismatch")
    if not verifier.verify(authority.canonical_payload(), authority.signature):
        raise ClaimAuthorityError("claim authority signature is invalid")
    _validate_envelope_content(
        authority.envelope, verified_context=verified_context, plan=plan, now=now
    )


def verify_claim_authority(
    authority: IssuedClaimAuthority,
    *,
    verified_context: VerifiedEditorialContext,
    plan: EditorialDirectorPlanV22,
    verifier: ClaimAuthorityVerifier,
    now: str,
) -> IssuedClaimAuthority:
    """Convenience verification API; returns the same signed envelope, never a token."""
    validate_claim_authority(
        authority,
        verified_context=verified_context,
        plan=plan,
        verifier=verifier,
        now=now,
    )
    return authority
