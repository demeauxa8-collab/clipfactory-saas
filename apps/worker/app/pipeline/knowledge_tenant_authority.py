"""Signed tenant authority for non-global Second Brain material.

``KnowledgeVault`` deliberately models editorial scope (global, campaign and
source), but it is not an authentication object.  This module adds the small
missing boundary: before campaign/source material is composed into a snapshot
or used for a signed editorial context, a server-side authority must bind the
*exact* input vault to one owner/campaign/source tuple for a short lifetime.

The capability is intentionally local and pure.  It does not know about a
database, HTTP, a renderer, or a job runner.  An application is expected to
make its own authorization decision before issuing an envelope.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from .knowledge_vault import KnowledgeVault

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_HEX = re.compile(r"^[a-f0-9]{64}$")
_MAX_TTL = timedelta(hours=24)
_VERIFIED_TENANT_VAULT_TOKEN = object()


class KnowledgeTenantAuthorityError(ValueError):
    """A tenant-vault capability is missing, invalid, stale, or mismatched."""


class Signer(Protocol):
    key_id: str

    def sign(self, payload: bytes) -> str: ...


class Verifier(Protocol):
    key_id: str

    def verify(self, payload: bytes, signature: str) -> bool: ...


@dataclass(frozen=True)
class HMACSHA256TenantAuthority:
    """A local HMAC signer; its secret is deliberately excluded from ``repr``."""

    key_id: str
    secret: bytes = field(repr=False)

    def __post_init__(self) -> None:
        _identifier(self.key_id, "authority key_id")
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise KnowledgeTenantAuthorityError("authority secret must be at least 32 bytes")

    def sign(self, payload: bytes) -> str:
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return isinstance(signature, str) and hmac.compare_digest(self.sign(payload), signature)


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise KnowledgeTenantAuthorityError(f"{label} is invalid")
    return value


def _instant(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise KnowledgeTenantAuthorityError(f"{label} must be a timezone-aware datetime")
    return value.astimezone(UTC).replace(microsecond=0)


def _instant_text(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_instant(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise KnowledgeTenantAuthorityError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise KnowledgeTenantAuthorityError(f"{label} must include a timezone")
    return parsed.astimezone(UTC).replace(microsecond=0)


def _canonical(value: dict[str, Any]) -> bytes:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return encoded.encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical({"value": value})).hexdigest()


def _note_payload(note: Any) -> dict[str, object]:
    """Keep the authority digest explicit, versioned and independent of repr()."""
    return {
        "campaign_id": note.campaign_id,
        "confidence": note.confidence,
        "content": note.content,
        "created_at": note.created_at,
        "graph_refs": [
            {"evidence_id": ref.evidence_id, "kind": ref.kind} for ref in note.graph_refs
        ],
        "id": note.id,
        "source_id": note.source_id,
        "source_refs": [{"note_id": ref.note_id, "role": ref.role} for ref in note.source_refs],
        "status": note.status,
        "tags": list(note.tags),
        "title": note.title,
        "type": note.type,
        "updated_at": note.updated_at,
        "vault": note.vault,
        "version": note.version,
    }


def vault_content_digest(vault: KnowledgeVault) -> str:
    """Digest every note, relation, and note version in canonical order."""
    if not isinstance(vault, KnowledgeVault):
        raise KnowledgeTenantAuthorityError("vault must be a KnowledgeVault")
    return _digest(
        {
            "schema_version": "1.0",
            "notes": [
                _note_payload(note) for note in sorted(vault.notes, key=lambda item: item.id)
            ],
            "relations": [
                {
                    "provenance": [
                        {"note_id": ref.note_id, "role": ref.role} for ref in relation.provenance
                    ],
                    "relation": relation.relation,
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                }
                for relation in sorted(
                    vault.relations,
                    key=lambda item: (item.source_id, item.target_id, item.relation),
                )
            ],
        }
    )


def vault_requires_tenant_authority(vault: KnowledgeVault) -> bool:
    if not isinstance(vault, KnowledgeVault):
        raise KnowledgeTenantAuthorityError("vault must be a KnowledgeVault")
    return any(note.vault != "global" for note in vault.notes)


@dataclass(frozen=True)
class IssuedTenantVaultAuthority:
    """Portable signed record; it is not itself a usable capability."""

    owner_id: str
    campaign_id: str
    source_id: str
    vault_digest: str
    issued_at: str
    expires_at: str
    authority_key_id: str
    authority_id: str
    signature: str

    def __post_init__(self) -> None:
        for label in ("owner_id", "campaign_id", "source_id", "authority_key_id", "authority_id"):
            object.__setattr__(self, label, _identifier(getattr(self, label), label))
        if not isinstance(self.vault_digest, str) or not _HEX.fullmatch(self.vault_digest):
            raise KnowledgeTenantAuthorityError("vault_digest must be a SHA-256 digest")
        issued, expires = _parse_instant(self.issued_at, "issued_at"), _parse_instant(
            self.expires_at, "expires_at"
        )
        if expires <= issued:
            raise KnowledgeTenantAuthorityError("expires_at must be after issued_at")
        if expires - issued > _MAX_TTL:
            raise KnowledgeTenantAuthorityError(
                "tenant vault authority lifetime exceeds the hard limit"
            )
        object.__setattr__(self, "issued_at", _instant_text(issued))
        object.__setattr__(self, "expires_at", _instant_text(expires))
        if not isinstance(self.signature, str) or not _HEX.fullmatch(self.signature):
            raise KnowledgeTenantAuthorityError("signature must be a SHA-256 hexadecimal value")

    def unsigned_payload(self) -> dict[str, str]:
        return {
            "authority_id": self.authority_id,
            "authority_key_id": self.authority_key_id,
            "campaign_id": self.campaign_id,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "owner_id": self.owner_id,
            "source_id": self.source_id,
            "vault_digest": self.vault_digest,
        }

    def canonical_payload(self) -> bytes:
        return _canonical(self.unsigned_payload())

    @property
    def authority_digest(self) -> str:
        return _digest({"payload": self.unsigned_payload(), "signature": self.signature})


@dataclass(frozen=True, init=False)
class VerifiedTenantVaultAuthority:
    """Private-constructor capability returned only after HMAC verification."""

    issued: IssuedTenantVaultAuthority

    def __init__(self, issued: IssuedTenantVaultAuthority, *, _token: object) -> None:
        if _token is not _VERIFIED_TENANT_VAULT_TOKEN:
            raise KnowledgeTenantAuthorityError(
                "VerifiedTenantVaultAuthority must be created by signature verification"
            )
        object.__setattr__(self, "issued", issued)

    @property
    def authority_digest(self) -> str:
        return self.issued.authority_digest

    @property
    def vault_digest(self) -> str:
        return self.issued.vault_digest

    def require_current_scope(
        self,
        vault: KnowledgeVault,
        *,
        owner_id: str,
        campaign_id: str,
        source_id: str,
        now: datetime,
    ) -> None:
        current = _instant(now, "now")
        expected_scope = (
            _identifier(owner_id, "owner_id"),
            _identifier(campaign_id, "campaign_id"),
            _identifier(source_id, "source_id"),
        )
        if (self.issued.owner_id, self.issued.campaign_id, self.issued.source_id) != expected_scope:
            raise KnowledgeTenantAuthorityError("tenant vault authority scope mismatch")
        if vault_content_digest(vault) != self.issued.vault_digest:
            raise KnowledgeTenantAuthorityError(
                "tenant vault authority does not bind this exact vault"
            )
        issued, expires = _parse_instant(self.issued.issued_at, "issued_at"), _parse_instant(
            self.issued.expires_at, "expires_at"
        )
        if current < issued:
            raise KnowledgeTenantAuthorityError("tenant vault authority is not yet valid")
        if current >= expires:
            raise KnowledgeTenantAuthorityError("tenant vault authority is expired")

    def require_snapshot_binding(
        self,
        *,
        owner_id: str,
        campaign_id: str,
        source_id: str,
        base_vault_digest: str | None,
        tenant_authority_digest: str | None,
        now: datetime,
    ) -> None:
        """Validate the immutable composition binding before a later signature."""
        expected_scope = (
            _identifier(owner_id, "owner_id"),
            _identifier(campaign_id, "campaign_id"),
            _identifier(source_id, "source_id"),
        )
        if (self.issued.owner_id, self.issued.campaign_id, self.issued.source_id) != expected_scope:
            raise KnowledgeTenantAuthorityError("tenant vault authority scope mismatch")
        if base_vault_digest != self.issued.vault_digest:
            raise KnowledgeTenantAuthorityError("snapshot does not bind the authorised base vault")
        if tenant_authority_digest != self.authority_digest:
            raise KnowledgeTenantAuthorityError(
                "snapshot does not bind the verified tenant authority"
            )
        # Reuse the time checks without requiring the original vault again.
        current = _instant(now, "now")
        issued, expires = _parse_instant(self.issued.issued_at, "issued_at"), _parse_instant(
            self.issued.expires_at, "expires_at"
        )
        if current < issued:
            raise KnowledgeTenantAuthorityError("tenant vault authority is not yet valid")
        if current >= expires:
            raise KnowledgeTenantAuthorityError("tenant vault authority is expired")


def issue_tenant_vault_authority(
    vault: KnowledgeVault,
    *,
    owner_id: str,
    campaign_id: str,
    source_id: str,
    signer: Signer,
    issued_at: datetime,
    expires_at: datetime,
    authority_id: str,
) -> IssuedTenantVaultAuthority:
    """Issue a short-lived envelope after the caller made its access decision."""
    issued, expires = _instant(issued_at, "issued_at"), _instant(expires_at, "expires_at")
    unsigned = {
        "owner_id": _identifier(owner_id, "owner_id"),
        "campaign_id": _identifier(campaign_id, "campaign_id"),
        "source_id": _identifier(source_id, "source_id"),
        "vault_digest": vault_content_digest(vault),
        "issued_at": _instant_text(issued),
        "expires_at": _instant_text(expires),
        "authority_key_id": _identifier(signer.key_id, "signer.key_id"),
        "authority_id": _identifier(authority_id, "authority_id"),
    }
    return IssuedTenantVaultAuthority(**unsigned, signature=signer.sign(_canonical(unsigned)))


def verify_tenant_vault_authority(
    issued: IssuedTenantVaultAuthority,
    vault: KnowledgeVault,
    *,
    verifier: Verifier,
    owner_id: str,
    campaign_id: str,
    source_id: str,
    now: datetime,
) -> VerifiedTenantVaultAuthority:
    """Verify HMAC, exact vault digest, scope, and current validity at once."""
    if not isinstance(issued, IssuedTenantVaultAuthority):
        raise KnowledgeTenantAuthorityError("issued must be an IssuedTenantVaultAuthority")
    if issued.authority_key_id != _identifier(verifier.key_id, "verifier.key_id"):
        raise KnowledgeTenantAuthorityError("tenant vault authority key rotation mismatch")
    if not verifier.verify(issued.canonical_payload(), issued.signature):
        raise KnowledgeTenantAuthorityError("tenant vault authority signature is invalid")
    verified = VerifiedTenantVaultAuthority(issued, _token=_VERIFIED_TENANT_VAULT_TOKEN)
    verified.require_current_scope(
        vault,
        owner_id=owner_id,
        campaign_id=campaign_id,
        source_id=source_id,
        now=now,
    )
    return verified


def verify_tenant_vault_snapshot_authority(
    issued: IssuedTenantVaultAuthority,
    *,
    verifier: Verifier,
    owner_id: str,
    campaign_id: str,
    source_id: str,
    base_vault_digest: str | None,
    tenant_authority_digest: str | None,
    now: datetime,
) -> VerifiedTenantVaultAuthority:
    """Re-verify a signed authority before a later snapshot-signing boundary.

    ``VerifiedTenantVaultAuthority`` is ergonomic within one call chain, not a
    bearer credential: Python module internals are inspectable.  Consumers
    therefore receive the signed envelope and a verifier, and validate it
    again at each authority boundary.
    """
    if not isinstance(issued, IssuedTenantVaultAuthority):
        raise KnowledgeTenantAuthorityError("issued must be an IssuedTenantVaultAuthority")
    if issued.authority_key_id != _identifier(verifier.key_id, "verifier.key_id"):
        raise KnowledgeTenantAuthorityError("tenant vault authority key rotation mismatch")
    if not verifier.verify(issued.canonical_payload(), issued.signature):
        raise KnowledgeTenantAuthorityError("tenant vault authority signature is invalid")
    verified = VerifiedTenantVaultAuthority(issued, _token=_VERIFIED_TENANT_VAULT_TOKEN)
    verified.require_snapshot_binding(
        owner_id=owner_id,
        campaign_id=campaign_id,
        source_id=source_id,
        base_vault_digest=base_vault_digest,
        tenant_authority_digest=tenant_authority_digest,
        now=now,
    )
    return verified
