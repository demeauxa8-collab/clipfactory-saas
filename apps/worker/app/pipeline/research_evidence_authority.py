"""Seal campaign-research findings to exact spans of normalized documents.

Research packs intentionally retain concise, model-produced findings rather
than full source text.  A source URL alone, however, cannot prove that a
finding was grounded in that source.  This local authority turns explicit
character-span checks against ``NormalizedResearchDocument`` values into a
short-lived HMAC envelope.

The portable envelope contains only opaque IDs, digests and offsets.  It never
serializes a document URL, a finding's prose, or the cited excerpt.  Consumers
must receive the original pack and documents again and re-materialize every
bound span before accepting the envelope.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from .campaign_research import CampaignResearchPack, canonical_public_url, research_content_digest
from .campaign_research_runtime import NormalizedResearchDocument

RESEARCH_EVIDENCE_AUTHORITY_SCHEMA_VERSION = "1.0"
MAX_EVIDENCE_TTL = timedelta(hours=24)
MAX_EXCERPT_CHARS = 1_200
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_DIGEST_RE = re.compile(r"^[a-f0-9]{64}$")


class ResearchEvidenceAuthorityError(ValueError):
    """Evidence is malformed, ungrounded, forged, stale, or out of scope."""


class Signer(Protocol):
    key_id: str

    def sign(self, payload: bytes) -> str: ...


class Verifier(Protocol):
    key_id: str

    def verify(self, payload: bytes, signature: str) -> bool: ...


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ResearchEvidenceAuthorityError(f"{label} is invalid")
    return value


def _key_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not _KEY_ID_RE.fullmatch(value):
        raise ResearchEvidenceAuthorityError(f"{label} is invalid")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise ResearchEvidenceAuthorityError(f"{label} must be a SHA-256 digest")
    return value


def _instant(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ResearchEvidenceAuthorityError(f"{label} must be a timezone-aware datetime")
    return value.astimezone(UTC).replace(microsecond=0)


def _instant_text(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_instant(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ResearchEvidenceAuthorityError(f"{label} must be ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchEvidenceAuthorityError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResearchEvidenceAuthorityError(f"{label} must include a timezone")
    return parsed.astimezone(UTC).replace(microsecond=0)


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _authority_digest(payload: dict[str, object], signature: str) -> str:
    return hashlib.sha256(_canonical({"payload": payload, "signature": signature})).hexdigest()


@dataclass(frozen=True)
class HmacSha256ResearchEvidenceAuthority:
    """Pure local HMAC signer/verifier.  The key never enters an envelope."""

    key_id: str
    secret: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "key_id", _key_id(self.key_id, "key_id"))
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise ResearchEvidenceAuthorityError("authority secret must be at least 32 bytes")

    def sign(self, payload: bytes) -> str:
        if not isinstance(payload, bytes):
            raise ResearchEvidenceAuthorityError("authority payload must be bytes")
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return (
            isinstance(payload, bytes)
            and isinstance(signature, str)
            and hmac.compare_digest(self.sign(payload), signature)
        )


@dataclass(frozen=True)
class EvidenceSpanClaim:
    """Untrusted issuer input: a requested finding-to-document excerpt binding."""

    finding_id: str
    source_id: str
    document_content_digest: str
    excerpt: str
    char_start: int
    char_end: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "finding_id", _id(self.finding_id, "finding_id"))
        object.__setattr__(self, "source_id", _id(self.source_id, "source_id"))
        object.__setattr__(
            self,
            "document_content_digest",
            _digest(self.document_content_digest, "document_content_digest"),
        )
        if not isinstance(self.excerpt, str) or not self.excerpt or len(self.excerpt) > MAX_EXCERPT_CHARS:
            raise ResearchEvidenceAuthorityError("excerpt must be non-empty and bounded")
        if (
            isinstance(self.char_start, bool)
            or isinstance(self.char_end, bool)
            or not isinstance(self.char_start, int)
            or not isinstance(self.char_end, int)
            or self.char_start < 0
            or self.char_end <= self.char_start
        ):
            raise ResearchEvidenceAuthorityError("evidence character offsets are invalid")


@dataclass(frozen=True)
class FindingEvidenceBinding:
    """Portable evidence identity; deliberately excludes excerpt and source URL."""

    finding_id: str
    source_id: str
    document_content_digest: str
    excerpt_digest: str
    char_start: int
    char_end: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "finding_id", _id(self.finding_id, "finding_id"))
        object.__setattr__(self, "source_id", _id(self.source_id, "source_id"))
        for label in ("document_content_digest", "excerpt_digest"):
            object.__setattr__(self, label, _digest(getattr(self, label), label))
        if (
            isinstance(self.char_start, bool)
            or isinstance(self.char_end, bool)
            or not isinstance(self.char_start, int)
            or not isinstance(self.char_end, int)
            or self.char_start < 0
            or self.char_end <= self.char_start
        ):
            raise ResearchEvidenceAuthorityError("evidence character offsets are invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "char_end": self.char_end,
            "char_start": self.char_start,
            "document_content_digest": self.document_content_digest,
            "excerpt_digest": self.excerpt_digest,
            "finding_id": self.finding_id,
            "source_id": self.source_id,
        }


@dataclass(frozen=True)
class SourceDocumentBinding:
    """Opaque source-to-document identity; the URL is rechecked outside this value."""

    source_id: str
    document_content_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _id(self.source_id, "source_id"))
        object.__setattr__(
            self,
            "document_content_digest",
            _digest(self.document_content_digest, "document_content_digest"),
        )

    def to_payload(self) -> dict[str, str]:
        return {
            "document_content_digest": self.document_content_digest,
            "source_id": self.source_id,
        }


def _canonical_bindings(
    bindings: tuple[FindingEvidenceBinding, ...],
) -> tuple[FindingEvidenceBinding, ...]:
    if not isinstance(bindings, tuple) or not all(isinstance(item, FindingEvidenceBinding) for item in bindings):
        raise ResearchEvidenceAuthorityError("evidence_bindings must be a tuple of bindings")
    ordered = tuple(
        sorted(
            bindings,
            key=lambda item: (
                item.finding_id,
                item.source_id,
                item.document_content_digest,
                item.char_start,
                item.char_end,
                item.excerpt_digest,
            ),
        )
    )
    identities = tuple(item.to_payload() for item in ordered)
    if len(identities) != len({json.dumps(item, sort_keys=True) for item in identities}):
        raise ResearchEvidenceAuthorityError("evidence bindings cannot be duplicated")
    return ordered


def _canonical_documents(
    bindings: tuple[SourceDocumentBinding, ...],
) -> tuple[SourceDocumentBinding, ...]:
    if not isinstance(bindings, tuple) or not all(isinstance(item, SourceDocumentBinding) for item in bindings):
        raise ResearchEvidenceAuthorityError("document_bindings must be a tuple of bindings")
    ordered = tuple(sorted(bindings, key=lambda item: item.source_id))
    if len(ordered) != len({item.source_id for item in ordered}):
        raise ResearchEvidenceAuthorityError("document bindings cannot contain duplicate source IDs")
    return ordered


def _documents_by_source(
    pack: CampaignResearchPack,
    documents: tuple[NormalizedResearchDocument, ...],
) -> dict[str, NormalizedResearchDocument]:
    if not isinstance(pack, CampaignResearchPack):
        raise ResearchEvidenceAuthorityError("pack must be a CampaignResearchPack")
    if not isinstance(documents, tuple) or not all(
        isinstance(document, NormalizedResearchDocument) for document in documents
    ):
        raise ResearchEvidenceAuthorityError("documents must be a tuple of normalized documents")
    sources_by_url = {canonical_public_url(source.url): source for source in pack.sources}
    if len(sources_by_url) != len(pack.sources):
        raise ResearchEvidenceAuthorityError("research pack source URLs must be unique")
    docs_by_url = {canonical_public_url(document.url): document for document in documents}
    if len(docs_by_url) != len(documents):
        raise ResearchEvidenceAuthorityError("documents cannot contain duplicate URLs")
    if set(docs_by_url) != set(sources_by_url):
        raise ResearchEvidenceAuthorityError("documents must match every and only research pack source URL")
    by_source: dict[str, NormalizedResearchDocument] = {}
    for url, source in sources_by_url.items():
        document = docs_by_url[url]
        if _sha256(document.content) != document.content_digest:
            raise ResearchEvidenceAuthorityError("normalized document content digest is invalid")
        by_source[source.source_id] = document
    return by_source


def _validated_bindings(
    pack: CampaignResearchPack,
    documents: tuple[NormalizedResearchDocument, ...],
    span_claims: tuple[EvidenceSpanClaim, ...],
) -> tuple[tuple[SourceDocumentBinding, ...], tuple[FindingEvidenceBinding, ...]]:
    by_source = _documents_by_source(pack, documents)
    if not isinstance(span_claims, tuple) or not all(
        isinstance(claim, EvidenceSpanClaim) for claim in span_claims
    ):
        raise ResearchEvidenceAuthorityError("span_claims must be a tuple of evidence span claims")
    findings = {finding.finding_id: finding for finding in pack.iter_findings()}
    if not findings:
        raise ResearchEvidenceAuthorityError("research evidence requires at least one retained finding")
    bindings: list[FindingEvidenceBinding] = []
    for claim in span_claims:
        finding = findings.get(claim.finding_id)
        if finding is None:
            raise ResearchEvidenceAuthorityError("evidence claim references an unknown finding")
        if claim.source_id not in finding.source_ids:
            raise ResearchEvidenceAuthorityError("evidence claim source is not cited by finding")
        document = by_source.get(claim.source_id)
        if document is None:
            raise ResearchEvidenceAuthorityError("evidence claim source has no matching document")
        if document.content_digest != claim.document_content_digest:
            raise ResearchEvidenceAuthorityError("evidence claim document digest does not match source document")
        if claim.char_end > len(document.content):
            raise ResearchEvidenceAuthorityError("evidence claim offsets exceed normalized document")
        excerpt = document.content[claim.char_start : claim.char_end]
        if not excerpt or excerpt != claim.excerpt:
            raise ResearchEvidenceAuthorityError("evidence claim excerpt does not match normalized document span")
        bindings.append(
            FindingEvidenceBinding(
                finding_id=claim.finding_id,
                source_id=claim.source_id,
                document_content_digest=document.content_digest,
                excerpt_digest=_sha256(excerpt),
                char_start=claim.char_start,
                char_end=claim.char_end,
            )
        )
    canonical = _canonical_bindings(tuple(bindings))
    covered_findings = {binding.finding_id for binding in canonical}
    covered_sources = {binding.source_id for binding in canonical}
    cited_sources = {source_id for finding in findings.values() for source_id in finding.source_ids}
    if covered_findings != set(findings):
        raise ResearchEvidenceAuthorityError("every retained finding requires at least one evidence span")
    if covered_sources != cited_sources:
        raise ResearchEvidenceAuthorityError("every cited source requires at least one evidence span")
    documents_bound = _canonical_documents(
        tuple(
            SourceDocumentBinding(source_id=source_id, document_content_digest=document.content_digest)
            for source_id, document in by_source.items()
        )
    )
    return documents_bound, canonical


@dataclass(frozen=True)
class IssuedResearchEvidence:
    """Signed opaque manifest; cannot be used without fresh verification."""

    schema_version: str
    owner_id: str
    campaign_id: str
    research_content_digest: str
    document_bindings: tuple[SourceDocumentBinding, ...]
    evidence_bindings: tuple[FindingEvidenceBinding, ...]
    issued_at: str
    expires_at: str
    authority_key_id: str
    authority_id: str
    signature: str

    def __post_init__(self) -> None:
        if self.schema_version != RESEARCH_EVIDENCE_AUTHORITY_SCHEMA_VERSION:
            raise ResearchEvidenceAuthorityError("unsupported research evidence authority schema")
        for label in ("owner_id", "campaign_id", "authority_id"):
            object.__setattr__(self, label, _id(getattr(self, label), label))
        object.__setattr__(
            self, "authority_key_id", _key_id(self.authority_key_id, "authority_key_id")
        )
        object.__setattr__(
            self,
            "research_content_digest",
            _digest(self.research_content_digest, "research_content_digest"),
        )
        object.__setattr__(self, "document_bindings", _canonical_documents(self.document_bindings))
        object.__setattr__(self, "evidence_bindings", _canonical_bindings(self.evidence_bindings))
        issued, expires = _parse_instant(self.issued_at, "issued_at"), _parse_instant(
            self.expires_at, "expires_at"
        )
        if expires <= issued:
            raise ResearchEvidenceAuthorityError("expires_at must be after issued_at")
        if expires - issued > MAX_EVIDENCE_TTL:
            raise ResearchEvidenceAuthorityError("research evidence authority lifetime exceeds hard limit")
        object.__setattr__(self, "issued_at", _instant_text(issued))
        object.__setattr__(self, "expires_at", _instant_text(expires))
        object.__setattr__(self, "signature", _digest(self.signature, "signature"))

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "authority_id": self.authority_id,
            "authority_key_id": self.authority_key_id,
            "campaign_id": self.campaign_id,
            "document_bindings": [item.to_payload() for item in self.document_bindings],
            "evidence_bindings": [item.to_payload() for item in self.evidence_bindings],
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "owner_id": self.owner_id,
            "research_content_digest": self.research_content_digest,
            "schema_version": self.schema_version,
        }

    def canonical_payload(self) -> bytes:
        return _canonical(self.unsigned_payload())

    @property
    def authority_digest(self) -> str:
        return _authority_digest(self.unsigned_payload(), self.signature)


def issue_research_evidence(
    pack: CampaignResearchPack,
    documents: tuple[NormalizedResearchDocument, ...],
    span_claims: tuple[EvidenceSpanClaim, ...],
    *,
    owner_id: str,
    campaign_id: str,
    signer: Signer,
    issued_at: datetime,
    expires_at: datetime,
    authority_id: str,
) -> IssuedResearchEvidence:
    """Validate exact spans and sign their opaque, deterministic manifest."""
    issued, expires = _instant(issued_at, "issued_at"), _instant(expires_at, "expires_at")
    document_bindings, evidence_bindings = _validated_bindings(pack, documents, span_claims)
    unsigned: dict[str, object] = {
        "schema_version": RESEARCH_EVIDENCE_AUTHORITY_SCHEMA_VERSION,
        "owner_id": _id(owner_id, "owner_id"),
        "campaign_id": _id(campaign_id, "campaign_id"),
        "research_content_digest": research_content_digest(pack),
        "document_bindings": [item.to_payload() for item in document_bindings],
        "evidence_bindings": [item.to_payload() for item in evidence_bindings],
        "issued_at": _instant_text(issued),
        "expires_at": _instant_text(expires),
        "authority_key_id": _key_id(signer.key_id, "signer.key_id"),
        "authority_id": _id(authority_id, "authority_id"),
    }
    return IssuedResearchEvidence(
        schema_version=RESEARCH_EVIDENCE_AUTHORITY_SCHEMA_VERSION,
        owner_id=unsigned["owner_id"],  # type: ignore[arg-type]
        campaign_id=unsigned["campaign_id"],  # type: ignore[arg-type]
        research_content_digest=unsigned["research_content_digest"],  # type: ignore[arg-type]
        document_bindings=document_bindings,
        evidence_bindings=evidence_bindings,
        issued_at=unsigned["issued_at"],  # type: ignore[arg-type]
        expires_at=unsigned["expires_at"],  # type: ignore[arg-type]
        authority_key_id=unsigned["authority_key_id"],  # type: ignore[arg-type]
        authority_id=unsigned["authority_id"],  # type: ignore[arg-type]
        signature=signer.sign(_canonical(unsigned)),
    )


def verify_research_evidence(
    issued: IssuedResearchEvidence,
    pack: CampaignResearchPack,
    documents: tuple[NormalizedResearchDocument, ...],
    *,
    verifier: Verifier,
    owner_id: str,
    campaign_id: str,
    now: datetime,
) -> IssuedResearchEvidence:
    """Re-materialize exact spans and reject stale, forged or substituted evidence."""
    if not isinstance(issued, IssuedResearchEvidence):
        raise ResearchEvidenceAuthorityError("issued must be an IssuedResearchEvidence")
    if issued.authority_key_id != _key_id(verifier.key_id, "verifier.key_id"):
        raise ResearchEvidenceAuthorityError("research evidence authority key rotation mismatch")
    if not verifier.verify(issued.canonical_payload(), issued.signature):
        raise ResearchEvidenceAuthorityError("research evidence authority signature is invalid")
    if (issued.owner_id, issued.campaign_id) != (
        _id(owner_id, "owner_id"),
        _id(campaign_id, "campaign_id"),
    ):
        raise ResearchEvidenceAuthorityError("research evidence tenant scope mismatch")
    current = _instant(now, "now")
    if current < _parse_instant(issued.issued_at, "issued_at"):
        raise ResearchEvidenceAuthorityError("research evidence authority is not yet valid")
    if current >= _parse_instant(issued.expires_at, "expires_at"):
        raise ResearchEvidenceAuthorityError("research evidence authority is expired")
    if research_content_digest(pack) != issued.research_content_digest:
        raise ResearchEvidenceAuthorityError("research evidence does not bind this exact research pack")
    expected_documents, expected_evidence = _validated_bindings(pack, documents, tuple(
        EvidenceSpanClaim(
            finding_id=binding.finding_id,
            source_id=binding.source_id,
            document_content_digest=binding.document_content_digest,
            excerpt=_documents_by_source(pack, documents)[binding.source_id].content[
                binding.char_start : binding.char_end
            ],
            char_start=binding.char_start,
            char_end=binding.char_end,
        )
        for binding in issued.evidence_bindings
    ))
    if expected_documents != issued.document_bindings or expected_evidence != issued.evidence_bindings:
        raise ResearchEvidenceAuthorityError("research evidence bindings do not exactly match pack documents")
    return issued
