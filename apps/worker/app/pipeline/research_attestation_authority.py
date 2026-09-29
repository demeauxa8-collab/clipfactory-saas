"""Signed authority for source classifications used by campaign research.

``SourceClassificationAttestation`` is deliberately a public, serialisable
projection.  It is useful for audit and for a trusted adapter to *request* a
classification, but it is not proof that an adapter or human actually made
that classification.  This module turns one exact set of those projections
into a short-lived, HMAC-signed capability bound to a tenant, campaign and
immutable research pack.

The module is pure and local: it neither fetches pages nor knows about a
database, a provider, the runner, or rendering.  The caller which issues an
envelope remains responsible for authenticating its reviewer/adapter.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from .campaign_research import CampaignResearchPack, research_content_digest
from .campaign_research_quality import SourceClassificationAttestation, source_url_digest

RESEARCH_ATTESTATION_AUTHORITY_SCHEMA_VERSION = "1.0"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_HEX = re.compile(r"^[a-f0-9]{64}$")
_MAX_TTL = timedelta(hours=24)
_VERIFIED_RESEARCH_ATTESTATIONS_TOKEN = object()


class ResearchAttestationAuthorityError(ValueError):
    """Research classifications are unsigned, stale, or outside their scope."""


class Signer(Protocol):
    key_id: str

    def sign(self, payload: bytes) -> str: ...


class Verifier(Protocol):
    key_id: str

    def verify(self, payload: bytes, signature: str) -> bool: ...


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ResearchAttestationAuthorityError(f"{label} is invalid")
    return value


def _instant(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ResearchAttestationAuthorityError(f"{label} must be a timezone-aware datetime")
    return value.astimezone(UTC).replace(microsecond=0)


def _instant_text(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_instant(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ResearchAttestationAuthorityError(f"{label} must be ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchAttestationAuthorityError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResearchAttestationAuthorityError(f"{label} must include a timezone")
    return parsed.astimezone(UTC).replace(microsecond=0)


def _canonical(value: dict[str, Any]) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return encoded.encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical({"value": value})).hexdigest()


def _canonical_attestations(
    attestations: tuple[SourceClassificationAttestation, ...],
) -> tuple[SourceClassificationAttestation, ...]:
    if not isinstance(attestations, tuple) or not all(
        isinstance(item, SourceClassificationAttestation) for item in attestations
    ):
        raise ResearchAttestationAuthorityError(
            "attestations must be a tuple of source classification attestations"
        )
    ordered = tuple(sorted(attestations, key=lambda item: item.source_id))
    if tuple(item.source_id for item in ordered) != tuple(
        sorted({item.source_id for item in ordered})
    ):
        raise ResearchAttestationAuthorityError("attestations cannot contain duplicate source IDs")
    return ordered


def _attestation_payload(
    attestations: tuple[SourceClassificationAttestation, ...],
) -> list[dict[str, str]]:
    return [item.to_audit_dict() for item in _canonical_attestations(attestations)]


def _require_exact_pack_bindings(
    pack: CampaignResearchPack,
    attestations: tuple[SourceClassificationAttestation, ...],
) -> tuple[SourceClassificationAttestation, ...]:
    if not isinstance(pack, CampaignResearchPack):
        raise ResearchAttestationAuthorityError("pack must be a CampaignResearchPack")
    canonical = _canonical_attestations(attestations)
    sources = {source.source_id: source for source in pack.sources}
    if set(item.source_id for item in canonical) != set(sources):
        raise ResearchAttestationAuthorityError(
            "attestations must bind every and only the research pack sources"
        )
    for item in canonical:
        if item.url_digest != source_url_digest(sources[item.source_id]):
            raise ResearchAttestationAuthorityError(
                "attestation URL digest does not match the research pack source"
            )
    return canonical


@dataclass(frozen=True)
class HMACSHA256ResearchAttestationAuthority:
    """Local signer/verifier whose secret is deliberately excluded from repr."""

    key_id: str
    secret: bytes = field(repr=False)

    def __post_init__(self) -> None:
        _identifier(self.key_id, "authority key_id")
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise ResearchAttestationAuthorityError("authority secret must be at least 32 bytes")

    def sign(self, payload: bytes) -> str:
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return isinstance(signature, str) and hmac.compare_digest(self.sign(payload), signature)


@dataclass(frozen=True)
class IssuedResearchAttestations:
    """Portable signed classification record; not a usable capability itself."""

    schema_version: str
    owner_id: str
    campaign_id: str
    research_content_digest: str
    attestations: tuple[SourceClassificationAttestation, ...]
    issued_at: str
    expires_at: str
    authority_key_id: str
    authority_id: str
    signature: str

    def __post_init__(self) -> None:
        if self.schema_version != RESEARCH_ATTESTATION_AUTHORITY_SCHEMA_VERSION:
            raise ResearchAttestationAuthorityError(
                "unsupported research attestation authority schema"
            )
        for label in ("owner_id", "campaign_id", "authority_key_id", "authority_id"):
            object.__setattr__(self, label, _identifier(getattr(self, label), label))
        if not isinstance(self.research_content_digest, str) or not _HEX.fullmatch(
            self.research_content_digest
        ):
            raise ResearchAttestationAuthorityError(
                "research_content_digest must be a SHA-256 digest"
            )
        object.__setattr__(self, "attestations", _canonical_attestations(self.attestations))
        issued, expires = _parse_instant(self.issued_at, "issued_at"), _parse_instant(
            self.expires_at, "expires_at"
        )
        if expires <= issued:
            raise ResearchAttestationAuthorityError("expires_at must be after issued_at")
        if expires - issued > _MAX_TTL:
            raise ResearchAttestationAuthorityError(
                "research attestation authority lifetime exceeds the hard limit"
            )
        object.__setattr__(self, "issued_at", _instant_text(issued))
        object.__setattr__(self, "expires_at", _instant_text(expires))
        if not isinstance(self.signature, str) or not _HEX.fullmatch(self.signature):
            raise ResearchAttestationAuthorityError("signature must be a SHA-256 hexadecimal value")

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "owner_id": self.owner_id,
            "campaign_id": self.campaign_id,
            "research_content_digest": self.research_content_digest,
            "attestations": _attestation_payload(self.attestations),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "authority_key_id": self.authority_key_id,
            "authority_id": self.authority_id,
        }

    def canonical_payload(self) -> bytes:
        return _canonical(self.unsigned_payload())

    @property
    def authority_digest(self) -> str:
        return _digest({"payload": self.unsigned_payload(), "signature": self.signature})


@dataclass(frozen=True, init=False)
class VerifiedResearchAttestations:
    """Private-constructor capability returned only after signature verification."""

    issued: IssuedResearchAttestations

    def __init__(self, issued: IssuedResearchAttestations, *, _token: object) -> None:
        if _token is not _VERIFIED_RESEARCH_ATTESTATIONS_TOKEN:
            raise ResearchAttestationAuthorityError(
                "VerifiedResearchAttestations must be created by signature verification"
            )
        object.__setattr__(self, "issued", issued)

    @property
    def attestations(self) -> tuple[SourceClassificationAttestation, ...]:
        return self.issued.attestations

    @property
    def authority_digest(self) -> str:
        return self.issued.authority_digest

    def require_current_binding(
        self,
        pack: CampaignResearchPack,
        *,
        owner_id: str,
        campaign_id: str,
        now: datetime,
    ) -> None:
        if (self.issued.owner_id, self.issued.campaign_id) != (
            _identifier(owner_id, "owner_id"),
            _identifier(campaign_id, "campaign_id"),
        ):
            raise ResearchAttestationAuthorityError("research attestation tenant scope mismatch")
        self.require_pack_binding(pack, now=now)

    def require_pack_binding(self, pack: CampaignResearchPack, *, now: datetime) -> None:
        if research_content_digest(pack) != self.issued.research_content_digest:
            raise ResearchAttestationAuthorityError(
                "research attestation authority does not bind this exact research pack"
            )
        _require_exact_pack_bindings(pack, self.issued.attestations)
        current = _instant(now, "now")
        issued, expires = _parse_instant(self.issued.issued_at, "issued_at"), _parse_instant(
            self.issued.expires_at, "expires_at"
        )
        if current < issued:
            raise ResearchAttestationAuthorityError(
                "research attestation authority is not yet valid"
            )
        if current >= expires:
            raise ResearchAttestationAuthorityError("research attestation authority is expired")


def issue_research_attestations(
    pack: CampaignResearchPack,
    attestations: tuple[SourceClassificationAttestation, ...],
    *,
    owner_id: str,
    campaign_id: str,
    signer: Signer,
    issued_at: datetime,
    expires_at: datetime,
    authority_id: str,
) -> IssuedResearchAttestations:
    """Issue a capability after an authenticated adapter/human classified sources."""
    issued, expires = _instant(issued_at, "issued_at"), _instant(expires_at, "expires_at")
    canonical = _require_exact_pack_bindings(pack, attestations)
    unsigned: dict[str, object] = {
        "schema_version": RESEARCH_ATTESTATION_AUTHORITY_SCHEMA_VERSION,
        "owner_id": _identifier(owner_id, "owner_id"),
        "campaign_id": _identifier(campaign_id, "campaign_id"),
        "research_content_digest": research_content_digest(pack),
        "attestations": _attestation_payload(canonical),
        "issued_at": _instant_text(issued),
        "expires_at": _instant_text(expires),
        "authority_key_id": _identifier(signer.key_id, "signer.key_id"),
        "authority_id": _identifier(authority_id, "authority_id"),
    }
    return IssuedResearchAttestations(
        schema_version=RESEARCH_ATTESTATION_AUTHORITY_SCHEMA_VERSION,
        owner_id=unsigned["owner_id"],  # type: ignore[arg-type]
        campaign_id=unsigned["campaign_id"],  # type: ignore[arg-type]
        research_content_digest=unsigned["research_content_digest"],  # type: ignore[arg-type]
        attestations=canonical,
        issued_at=unsigned["issued_at"],  # type: ignore[arg-type]
        expires_at=unsigned["expires_at"],  # type: ignore[arg-type]
        authority_key_id=unsigned["authority_key_id"],  # type: ignore[arg-type]
        authority_id=unsigned["authority_id"],  # type: ignore[arg-type]
        signature=signer.sign(_canonical(unsigned)),
    )


def verify_research_attestations(
    issued: IssuedResearchAttestations,
    pack: CampaignResearchPack,
    *,
    verifier: Verifier,
    owner_id: str,
    campaign_id: str,
    now: datetime,
) -> VerifiedResearchAttestations:
    """Verify HMAC, exact source labels/URLs/pack digest, scope and TTL."""
    if not isinstance(issued, IssuedResearchAttestations):
        raise ResearchAttestationAuthorityError("issued must be an IssuedResearchAttestations")
    if issued.authority_key_id != _identifier(verifier.key_id, "verifier.key_id"):
        raise ResearchAttestationAuthorityError(
            "research attestation authority key rotation mismatch"
        )
    if not verifier.verify(issued.canonical_payload(), issued.signature):
        raise ResearchAttestationAuthorityError(
            "research attestation authority signature is invalid"
        )
    verified = VerifiedResearchAttestations(issued, _token=_VERIFIED_RESEARCH_ATTESTATIONS_TOKEN)
    verified.require_current_binding(
        pack,
        owner_id=owner_id,
        campaign_id=campaign_id,
        now=now,
    )
    return verified
