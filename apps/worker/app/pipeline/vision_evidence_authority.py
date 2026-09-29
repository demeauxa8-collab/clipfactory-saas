"""Closed authority for candidate-window visual evidence.

The beat graph may describe a useful visual observation, but a graph label is
not proof that the observation was actually checked against the source asset.
This module turns a bounded, immutable verifier attestation into a short-lived
capability.  It never opens media or creates timing: graph-owned windows and
transcript word IDs remain the edit authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from .editorial_beats import EditorialBeatGraph, VisualFocusRegion, validate_editorial_beat_graph
from .editorial_context import graph_digest

VISION_EVIDENCE_SCHEMA_VERSION = "1.0"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_VISUAL_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_HEX = re.compile(r"^[a-f0-9]{64}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MAX_ISSUANCE_SECONDS = 24 * 60 * 60
_VERIFIED_VISION_EVIDENCE_TOKEN = object()


class VisionEvidenceAuthorityError(ValueError):
    """Candidate-window visual evidence is missing, stale, or mismatched."""


class VisionEvidenceSigner(Protocol):
    key_id: str

    def sign(self, payload: bytes) -> str: ...


class VisionEvidenceVerifier(Protocol):
    key_id: str

    def verify(self, payload: bytes, signature: str) -> bool: ...


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise VisionEvidenceAuthorityError(f"{label} is invalid")
    return value


def _visual_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not _VISUAL_ID.fullmatch(value):
        raise VisionEvidenceAuthorityError(f"{label} is invalid")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise VisionEvidenceAuthorityError(f"{label} must be a SHA-256 digest")
    return value


def _version(value: object, label: str) -> str:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise VisionEvidenceAuthorityError(f"{label} is invalid")
    return value


def _instant(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise VisionEvidenceAuthorityError(f"{label} must be ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VisionEvidenceAuthorityError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise VisionEvidenceAuthorityError(f"{label} must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_live(valid_from: str, valid_until: str, now: str, *, label: str) -> None:
    instant = datetime.fromisoformat(_instant(now, "now").replace("Z", "+00:00"))
    start = datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
    end = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
    if instant < start:
        raise VisionEvidenceAuthorityError(f"{label} is not yet valid")
    if instant >= end:
        raise VisionEvidenceAuthorityError(f"{label} is expired")


def _focus_payload(region: VisualFocusRegion | None) -> dict[str, float] | None:
    if region is None:
        return None
    return {
        "x": float(region.x),
        "y": float(region.y),
        "width": float(region.width),
        "height": float(region.height),
    }


@dataclass(frozen=True)
class HMACSHA256VisionEvidenceAuthority:
    """Local signer/verifier; secrets deliberately do not appear in repr."""

    key_id: str
    secret: bytes = field(repr=False)

    def __post_init__(self) -> None:
        _id(self.key_id, "authority key_id")
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise VisionEvidenceAuthorityError("authority secret must be at least 32 bytes")

    def sign(self, payload: bytes) -> str:
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return isinstance(signature, str) and hmac.compare_digest(self.sign(payload), signature)


@dataclass(frozen=True)
class VisualEvidenceAttestation:
    """One verifier result for one ``verified_candidate`` graph visual.

    The attestation carries digests only.  Source paths, frames and raw model
    output are intentionally outside both the prompt and the authority API.
    """

    schema_version: Literal["1.0"]
    attestation_id: str
    owner_id: str
    campaign_id: str
    source_id: str
    source_asset_digest: str
    graph_digest: str
    visual_id: str
    source_in_ms: int
    source_out_ms: int
    sampled_frame_digests: tuple[str, ...]
    focus_region: VisualFocusRegion | None
    verifier_policy_version: str
    verifier_model_version: str
    valid_from: str
    valid_until: str

    def __post_init__(self) -> None:
        if self.schema_version != VISION_EVIDENCE_SCHEMA_VERSION:
            raise VisionEvidenceAuthorityError("unsupported vision evidence schema")
        for name in ("attestation_id", "owner_id", "campaign_id", "source_id"):
            _id(getattr(self, name), name)
        for name in ("source_asset_digest", "graph_digest"):
            _digest(getattr(self, name), name)
        _visual_id(self.visual_id, "visual_id")
        if (
            not isinstance(self.source_in_ms, int)
            or isinstance(self.source_in_ms, bool)
            or not isinstance(self.source_out_ms, int)
            or isinstance(self.source_out_ms, bool)
            or self.source_in_ms < 0
            or self.source_out_ms <= self.source_in_ms
        ):
            raise VisionEvidenceAuthorityError("source window must be a positive millisecond range")
        if not isinstance(self.sampled_frame_digests, tuple) or not self.sampled_frame_digests:
            raise VisionEvidenceAuthorityError("sampled frame digests must be a non-empty tuple")
        frames = tuple(_digest(item, "sampled frame digest") for item in self.sampled_frame_digests)
        if len(frames) != len(set(frames)):
            raise VisionEvidenceAuthorityError("sampled frame digests cannot repeat")
        object.__setattr__(self, "sampled_frame_digests", frames)
        if self.focus_region is not None and not isinstance(self.focus_region, VisualFocusRegion):
            raise VisionEvidenceAuthorityError("focus_region must be a VisualFocusRegion or None")
        _version(self.verifier_policy_version, "verifier_policy_version")
        _version(self.verifier_model_version, "verifier_model_version")
        valid_from = _instant(self.valid_from, "valid_from")
        valid_until = _instant(self.valid_until, "valid_until")
        if datetime.fromisoformat(valid_until.replace("Z", "+00:00")) <= datetime.fromisoformat(
            valid_from.replace("Z", "+00:00")
        ):
            raise VisionEvidenceAuthorityError("valid_until must be after valid_from")
        object.__setattr__(self, "valid_from", valid_from)
        object.__setattr__(self, "valid_until", valid_until)

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "attestation_id": self.attestation_id,
            "owner_id": self.owner_id,
            "campaign_id": self.campaign_id,
            "source_id": self.source_id,
            "source_asset_digest": self.source_asset_digest,
            "graph_digest": self.graph_digest,
            "visual_id": self.visual_id,
            "source_in_ms": self.source_in_ms,
            "source_out_ms": self.source_out_ms,
            "sampled_frame_digests": list(self.sampled_frame_digests),
            "focus_region": _focus_payload(self.focus_region),
            "verifier_policy_version": self.verifier_policy_version,
            "verifier_model_version": self.verifier_model_version,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
        }

    @property
    def audit_digest(self) -> str:
        return hashlib.sha256(_canonical(self.payload())).hexdigest()


def graph_requires_vision_evidence(graph: EditorialBeatGraph) -> bool:
    """Return whether a graph exposes any candidate-verification privilege."""
    validate_editorial_beat_graph(graph)
    return any(item.provenance == "verified_candidate" for item in graph.visual_beats) or any(
        {"screen_focus", "locked_face"}.intersection(item.available_framings)
        for item in graph.editorial_beats
    )


def _validate_attestation_for_graph(
    attestation: VisualEvidenceAttestation,
    *,
    graph: EditorialBeatGraph,
    owner_id: str,
    campaign_id: str,
    source_id: str,
    now: str,
) -> None:
    actual_graph_digest = graph_digest(graph)
    if attestation.graph_digest != actual_graph_digest:
        raise VisionEvidenceAuthorityError("vision attestation graph digest does not match graph")
    if (attestation.owner_id, attestation.campaign_id, attestation.source_id) != (
        owner_id,
        campaign_id,
        source_id,
    ):
        raise VisionEvidenceAuthorityError("vision attestation tenant scope does not match context")
    visual = next(
        (item for item in graph.visual_beats if item.visual_id == attestation.visual_id),
        None,
    )
    if visual is None or visual.provenance != "verified_candidate":
        raise VisionEvidenceAuthorityError(
            "vision attestation must bind a verified_candidate visual"
        )
    if (attestation.source_in_ms, attestation.source_out_ms) != (
        visual.source_in_ms,
        visual.source_out_ms,
    ):
        raise VisionEvidenceAuthorityError(
            "vision attestation source window does not exactly match graph"
        )
    if visual.screen_readability == "readable":
        if visual.focus_region is None or attestation.focus_region != visual.focus_region:
            raise VisionEvidenceAuthorityError("readable screen requires the exact graph ROI")
    elif attestation.focus_region is not None:
        raise VisionEvidenceAuthorityError("non-readable visual attestation cannot carry an ROI")
    _require_live(attestation.valid_from, attestation.valid_until, now, label="vision attestation")


@dataclass(frozen=True)
class IssuedVisionEvidenceSet:
    """Signed envelope whose contents are independently rechecked on use."""

    owner_id: str
    campaign_id: str
    source_id: str
    source_asset_digest: str
    graph_digest: str
    issued_at: str
    expires_at: str
    authority_key_id: str
    evidence_set_id: str
    attestations: tuple[VisualEvidenceAttestation, ...]
    signature: str

    def __post_init__(self) -> None:
        for name in ("owner_id", "campaign_id", "source_id", "authority_key_id", "evidence_set_id"):
            _id(getattr(self, name), name)
        _digest(self.source_asset_digest, "source_asset_digest")
        _digest(self.graph_digest, "graph_digest")
        issued_at = _instant(self.issued_at, "issued_at")
        expires_at = _instant(self.expires_at, "expires_at")
        if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) <= datetime.fromisoformat(
            issued_at.replace("Z", "+00:00")
        ):
            raise VisionEvidenceAuthorityError("expires_at must be after issued_at")
        if (
            datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            - datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
        ).total_seconds() > _MAX_ISSUANCE_SECONDS:
            raise VisionEvidenceAuthorityError("vision evidence lifetime exceeds the hard limit")
        if (
            not isinstance(self.attestations, tuple)
            or not self.attestations
            or not all(isinstance(item, VisualEvidenceAttestation) for item in self.attestations)
        ):
            raise VisionEvidenceAuthorityError(
                "issued vision evidence requires immutable attestations"
            )
        if len({item.attestation_id for item in self.attestations}) != len(self.attestations):
            raise VisionEvidenceAuthorityError("vision evidence attestation IDs cannot repeat")
        if len({item.visual_id for item in self.attestations}) != len(self.attestations):
            raise VisionEvidenceAuthorityError("vision evidence visual IDs cannot repeat")
        if not isinstance(self.signature, str) or not _HEX.fullmatch(self.signature):
            raise VisionEvidenceAuthorityError("signature must be a SHA-256 hexadecimal value")
        object.__setattr__(self, "issued_at", issued_at)
        object.__setattr__(self, "expires_at", expires_at)

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "owner_id": self.owner_id,
            "campaign_id": self.campaign_id,
            "source_id": self.source_id,
            "source_asset_digest": self.source_asset_digest,
            "graph_digest": self.graph_digest,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "authority_key_id": self.authority_key_id,
            "evidence_set_id": self.evidence_set_id,
            "attestations": [item.payload() for item in self.attestations],
        }

    def canonical_payload(self) -> bytes:
        return _canonical(self.unsigned_payload())

    @property
    def audit_digest(self) -> str:
        return hashlib.sha256(self.canonical_payload()).hexdigest()


@dataclass(frozen=True, init=False)
class VerifiedVisionEvidenceSet:
    """Private capability for exact candidate IDs in one live graph instance."""

    issued: IssuedVisionEvidenceSet
    graph: EditorialBeatGraph

    def __init__(
        self,
        issued: IssuedVisionEvidenceSet,
        graph: EditorialBeatGraph,
        *,
        _token: object,
    ) -> None:
        if _token is not _VERIFIED_VISION_EVIDENCE_TOKEN:
            raise VisionEvidenceAuthorityError(
                "VerifiedVisionEvidenceSet must be created by signature verification"
            )
        object.__setattr__(self, "issued", issued)
        object.__setattr__(self, "graph", graph)

    @property
    def audit_digest(self) -> str:
        return self.issued.audit_digest

    def validate_graph(
        self,
        graph: EditorialBeatGraph,
        *,
        verifier: VisionEvidenceVerifier,
        owner_id: str,
        campaign_id: str,
        source_id: str,
        now: str,
    ) -> None:
        if verifier is None:
            raise VisionEvidenceAuthorityError("vision evidence requires a verifier")
        _verify_issued_set(
            self.issued,
            graph,
            now=now,
            expected_owner_id=owner_id,
            expected_campaign_id=campaign_id,
            expected_source_id=source_id,
            verifier=verifier,
        )
        if graph_digest(self.graph) != graph_digest(graph):
            raise VisionEvidenceAuthorityError("verified vision capability graph replay detected")

    def validate_visual_ids(
        self,
        visual_ids: tuple[str, ...],
        *,
        verifier: VisionEvidenceVerifier,
        graph: EditorialBeatGraph,
        owner_id: str,
        campaign_id: str,
        source_id: str,
        now: str,
    ) -> None:
        self.validate_graph(
            graph,
            verifier=verifier,
            owner_id=owner_id,
            campaign_id=campaign_id,
            source_id=source_id,
            now=now,
        )
        if not isinstance(visual_ids, tuple) or not visual_ids:
            raise VisionEvidenceAuthorityError("vision validation requires exact visual IDs")
        ids = tuple(_visual_id(item, "visual_id") for item in visual_ids)
        if len(ids) != len(set(ids)):
            raise VisionEvidenceAuthorityError("vision visual IDs cannot repeat")
        attested = {item.visual_id for item in self.issued.attestations}
        if not set(ids).issubset(attested):
            raise VisionEvidenceAuthorityError(
                "vision evidence does not attest the exact visual IDs"
            )


def _verify_issued_set(
    issued: IssuedVisionEvidenceSet,
    graph: EditorialBeatGraph,
    *,
    now: str,
    expected_owner_id: str,
    expected_campaign_id: str,
    expected_source_id: str,
    verifier: VisionEvidenceVerifier | None,
) -> None:
    if not isinstance(issued, IssuedVisionEvidenceSet):
        raise VisionEvidenceAuthorityError("issued must be an IssuedVisionEvidenceSet")
    for value, label in (
        (expected_owner_id, "expected_owner_id"),
        (expected_campaign_id, "expected_campaign_id"),
        (expected_source_id, "expected_source_id"),
    ):
        _id(value, label)
    if verifier is not None:
        if issued.authority_key_id != verifier.key_id:
            raise VisionEvidenceAuthorityError("vision evidence authority key rotation mismatch")
        if not verifier.verify(issued.canonical_payload(), issued.signature):
            raise VisionEvidenceAuthorityError("vision evidence signature is invalid")
    _require_live(issued.issued_at, issued.expires_at, now, label="vision evidence")
    if (issued.owner_id, issued.campaign_id, issued.source_id) != (
        expected_owner_id,
        expected_campaign_id,
        expected_source_id,
    ):
        raise VisionEvidenceAuthorityError("vision evidence tenant scope mismatch")
    actual_graph_digest = graph_digest(graph)
    if issued.graph_digest != actual_graph_digest:
        raise VisionEvidenceAuthorityError("vision evidence graph digest does not match graph")
    required_ids = {
        item.visual_id for item in graph.visual_beats if item.provenance == "verified_candidate"
    }
    actual_ids = {item.visual_id for item in issued.attestations}
    if actual_ids != required_ids:
        raise VisionEvidenceAuthorityError(
            "vision evidence does not exactly cover candidate visuals"
        )
    for attestation in issued.attestations:
        if attestation.source_asset_digest != issued.source_asset_digest:
            raise VisionEvidenceAuthorityError(
                "vision attestation source asset does not match evidence set"
            )
        _validate_attestation_for_graph(
            attestation,
            graph=graph,
            owner_id=expected_owner_id,
            campaign_id=expected_campaign_id,
            source_id=expected_source_id,
            now=now,
        )


def issue_vision_evidence_set(
    graph: EditorialBeatGraph,
    attestations: tuple[VisualEvidenceAttestation, ...],
    *,
    signer: VisionEvidenceSigner,
    owner_id: str,
    campaign_id: str,
    source_id: str,
    source_asset_digest: str,
    issued_at: str,
    expires_at: str,
    evidence_set_id: str,
) -> IssuedVisionEvidenceSet:
    """Sign a complete graph-attestation set; no partial candidate coverage."""
    validate_editorial_beat_graph(graph)
    if not graph_requires_vision_evidence(graph):
        raise VisionEvidenceAuthorityError("speech-only graph does not require vision evidence")
    if not isinstance(attestations, tuple) or not attestations:
        raise VisionEvidenceAuthorityError("candidate graph requires vision attestations")
    owner_id, campaign_id, source_id = (
        _id(owner_id, "owner_id"),
        _id(campaign_id, "campaign_id"),
        _id(source_id, "source_id"),
    )
    source_asset_digest = _digest(source_asset_digest, "source_asset_digest")
    issued_at, expires_at = _instant(issued_at, "issued_at"), _instant(expires_at, "expires_at")
    _require_live(issued_at, expires_at, issued_at, label="vision evidence")
    if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) <= datetime.fromisoformat(
        issued_at.replace("Z", "+00:00")
    ):
        raise VisionEvidenceAuthorityError("expires_at must be after issued_at")
    if len({item.attestation_id for item in attestations}) != len(attestations):
        raise VisionEvidenceAuthorityError("vision evidence attestation IDs cannot repeat")
    if len({item.visual_id for item in attestations}) != len(attestations):
        raise VisionEvidenceAuthorityError("vision evidence visual IDs cannot repeat")
    for attestation in attestations:
        if not isinstance(attestation, VisualEvidenceAttestation):
            raise VisionEvidenceAuthorityError("vision attestations must be immutable attestations")
        if attestation.source_asset_digest != source_asset_digest:
            raise VisionEvidenceAuthorityError(
                "vision attestation source asset does not match evidence set"
            )
        _validate_attestation_for_graph(
            attestation,
            graph=graph,
            owner_id=owner_id,
            campaign_id=campaign_id,
            source_id=source_id,
            now=issued_at,
        )
    required_ids = {
        item.visual_id for item in graph.visual_beats if item.provenance == "verified_candidate"
    }
    if {item.visual_id for item in attestations} != required_ids:
        raise VisionEvidenceAuthorityError(
            "vision attestations must exactly cover candidate visuals"
        )
    unsigned = {
        "owner_id": owner_id,
        "campaign_id": campaign_id,
        "source_id": source_id,
        "source_asset_digest": source_asset_digest,
        "graph_digest": graph_digest(graph),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "authority_key_id": _id(signer.key_id, "signer.key_id"),
        "evidence_set_id": _id(evidence_set_id, "evidence_set_id"),
        "attestations": [item.payload() for item in attestations],
    }
    return IssuedVisionEvidenceSet(
        owner_id=owner_id,
        campaign_id=campaign_id,
        source_id=source_id,
        source_asset_digest=source_asset_digest,
        graph_digest=graph_digest(graph),
        issued_at=issued_at,
        expires_at=expires_at,
        authority_key_id=_id(signer.key_id, "signer.key_id"),
        evidence_set_id=_id(evidence_set_id, "evidence_set_id"),
        attestations=attestations,
        signature=signer.sign(_canonical(unsigned)),
    )


def verify_vision_evidence_capability(
    issued: IssuedVisionEvidenceSet,
    graph: EditorialBeatGraph,
    *,
    verifier: VisionEvidenceVerifier,
    now: str,
    expected_owner_id: str,
    expected_campaign_id: str,
    expected_source_id: str,
) -> VerifiedVisionEvidenceSet:
    """Verify and return the only public path to candidate visual privileges."""
    _verify_issued_set(
        issued,
        graph,
        now=now,
        expected_owner_id=expected_owner_id,
        expected_campaign_id=expected_campaign_id,
        expected_source_id=expected_source_id,
        verifier=verifier,
    )
    return VerifiedVisionEvidenceSet(issued, graph, _token=_VERIFIED_VISION_EVIDENCE_TOKEN)
