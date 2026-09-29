"""Signed local authority for a unified editorial context and vault snapshot."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from ..models import Transcript
from .campaign_research import (
    CampaignResearchPack,
    is_reusable_research_pack,
    research_content_digest,
)
from .campaign_research_quality import (
    CampaignResearchQuality,
    CampaignResearchQualityError,
    evaluate_campaign_research_quality,
)
from .editorial_beats import EditorialBeatGraph
from .editorial_context import (
    UnifiedEditorialContextPack,
    graph_digest,
    materialize_campaign_research,
    project_context_note,
)
from .editorial_director_v22 import (
    EditorialDirectorPlanV22,
    _compile_editorial_director_plan_v22_unverified,
    _editorial_director_user_prompt_v22_unverified,
    _parse_editorial_director_plan_v22_unverified,
    _validate_editorial_director_plan_v22_unverified,
)
from .editorial_retrieval import (
    EditorialRetrievalError,
    RetrievalPolicy,
    RetrievalResult,
    retrieve_editorial_evidence,
)
from .knowledge_ingestion import KnowledgeVaultSnapshot
from .knowledge_tenant_authority import (
    IssuedTenantVaultAuthority,
    KnowledgeTenantAuthorityError,
    verify_tenant_vault_snapshot_authority,
)
from .knowledge_tenant_authority import (
    Verifier as TenantVerifier,
)
from .research_attestation_authority import (
    IssuedResearchAttestations,
    ResearchAttestationAuthorityError,
    verify_research_attestations,
)
from .research_attestation_authority import (
    Verifier as ResearchAttestationVerifier,
)
from .vision_evidence_authority import (
    VerifiedVisionEvidenceSet,
    VisionEvidenceAuthorityError,
    VisionEvidenceVerifier,
    graph_requires_vision_evidence,
)

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_HEX = re.compile(r"^[a-f0-9]{64}$")
_MAX_ISSUANCE_SECONDS = 24 * 60 * 60
_VERIFIED_CONTEXT_TOKEN = object()


class EditorialContextAuthorityError(ValueError):
    pass


def _tenant_vault_binding(
    snapshot: KnowledgeVaultSnapshot,
    tenant_authority: IssuedTenantVaultAuthority | None,
    tenant_authority_verifier: TenantVerifier | None,
    *,
    now: datetime,
    issuance_expires_at: datetime | None = None,
) -> str | None:
    """Require the separate tenant capability before signing non-global notes.

    The snapshot records the capability and exact raw-base digest established
    during composition.  Requiring the still-current capability here prevents
    a caller from manufacturing a ``KnowledgeVaultSnapshot`` with a relabelled
    ``owner_id`` and asking the editorial signer to bless it.
    """
    has_non_global_notes = any(note.vault != "global" for note in snapshot.vault.notes)
    if not has_non_global_notes:
        if tenant_authority is not None or tenant_authority_verifier is not None:
            raise EditorialContextAuthorityError(
                "global-only snapshot must not carry tenant vault authority"
            )
        if snapshot.tenant_authority_digest is not None or snapshot.base_vault_digest is not None:
            raise EditorialContextAuthorityError(
                "global-only snapshot cannot carry a tenant vault binding"
            )
        return None
    if not isinstance(tenant_authority, IssuedTenantVaultAuthority):
        raise EditorialContextAuthorityError(
            "non-global snapshot requires a signed tenant vault authority"
        )
    if tenant_authority_verifier is None:
        raise EditorialContextAuthorityError("non-global snapshot requires a tenant vault verifier")
    try:
        verified_tenant_authority = verify_tenant_vault_snapshot_authority(
            tenant_authority,
            verifier=tenant_authority_verifier,
            owner_id=snapshot.owner_id,
            campaign_id=snapshot.campaign_id,
            source_id=snapshot.source_id,
            base_vault_digest=snapshot.base_vault_digest,
            tenant_authority_digest=snapshot.tenant_authority_digest,
            now=now,
        )
    except KnowledgeTenantAuthorityError as exc:
        raise EditorialContextAuthorityError("tenant vault authority rejected snapshot") from exc
    if issuance_expires_at is not None:
        tenant_expires = datetime.fromisoformat(
            verified_tenant_authority.issued.expires_at.replace("Z", "+00:00")
        )
        if issuance_expires_at > tenant_expires:
            raise EditorialContextAuthorityError(
                "editorial context cannot outlive tenant vault authority"
            )
    return verified_tenant_authority.authority_digest


class Signer(Protocol):
    key_id: str

    def sign(self, payload: bytes) -> str: ...


class Verifier(Protocol):
    key_id: str

    def verify(self, payload: bytes, signature: str) -> bool: ...


@dataclass(frozen=True)
class HMACSHA256Authority:
    key_id: str
    secret: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.key_id, str) or not _ID.fullmatch(self.key_id):
            raise EditorialContextAuthorityError("authority key_id is invalid")
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise EditorialContextAuthorityError("authority secret must be at least 32 bytes")

    def sign(self, payload: bytes) -> str:
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return isinstance(signature, str) and hmac.compare_digest(self.sign(payload), signature)


def _instant(value: str, label: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise EditorialContextAuthorityError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EditorialContextAuthorityError(f"{label} must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise EditorialContextAuthorityError(f"{label} is invalid")
    return value


def _digest(value: str, label: str) -> str:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise EditorialContextAuthorityError(f"{label} must be a SHA-256 digest")
    return value


def _context_integrity(context: UnifiedEditorialContextPack) -> None:
    expected = UnifiedEditorialContextPack.compute_digest(
        schema_version=context.schema_version,
        question=context.question,
        campaign_fingerprint=context.campaign_fingerprint,
        research_digest=context.research_digest,
        graph_digest=context.graph_digest,
        editorial_policy_version=context.editorial_policy_version,
        selected_notes=context.selected_notes,
        allowed_ref_ids=context.allowed_ref_ids,
    )
    if expected != context.context_digest:
        raise EditorialContextAuthorityError("context digest integrity failed")


def _bind(
    snapshot: KnowledgeVaultSnapshot,
    context: UnifiedEditorialContextPack,
    graph: EditorialBeatGraph,
) -> RetrievalResult:
    _context_integrity(context)
    if (snapshot.campaign_id, snapshot.source_id) != (
        context.question.campaign_id,
        context.question.source_id,
    ):
        raise EditorialContextAuthorityError("snapshot scope does not match context")
    if snapshot.graph_digest != graph_digest(graph) or context.graph_digest != graph_digest(graph):
        raise EditorialContextAuthorityError("snapshot/context graph digest does not match graph")
    if (
        snapshot.campaign_fingerprint != context.campaign_fingerprint
        or snapshot.research_digest != context.research_digest
    ):
        raise EditorialContextAuthorityError(
            "snapshot campaign or research binding does not match context"
        )
    notes = {note.id: note for note in snapshot.vault.notes}
    selected = {item.note.note_id: item.note for item in context.selected_notes}
    if set(selected) != set(context.allowed_ref_ids) or set(selected) - set(notes):
        raise EditorialContextAuthorityError("snapshot does not cover selected context notes")
    for note_id, note in selected.items():
        current = notes[note_id]
        if current.version != note.version:
            raise EditorialContextAuthorityError("snapshot note version does not match context")
        if note != project_context_note(current):
            raise EditorialContextAuthorityError(
                "selected context note is not the canonical snapshot projection"
            )
    try:
        retrieval = retrieve_editorial_evidence(
            context.question,
            graph,
            snapshot,
            RetrievalPolicy(),
        )
    except EditorialRetrievalError as exc:
        raise EditorialContextAuthorityError(
            "authorised retrieval could not be reproduced for context issuance"
        ) from exc
    if retrieval.status != "ready":
        raise EditorialContextAuthorityError(
            "blocked editorial retrieval cannot receive context authority"
        )
    retrieved_notes = {item.note.note_id: item.note for item in retrieval.selections}
    if retrieved_notes != selected:
        raise EditorialContextAuthorityError(
            "context selections do not exactly match authorised retrieval"
        )
    return retrieval


def _research_quality_binding(
    snapshot: KnowledgeVaultSnapshot,
    context: UnifiedEditorialContextPack,
    research_pack: CampaignResearchPack | None,
    research_attestations: IssuedResearchAttestations | None,
    research_attestation_verifier: ResearchAttestationVerifier | None,
    *,
    as_of: datetime,
    require_current_reusability: bool,
) -> CampaignResearchQuality | None:
    """Recompute, rather than accept, the research trust result being signed.

    A ``CampaignResearchQuality`` value is a useful public audit record, but it
    is not an authority capability: callers can instantiate one.  The signing
    boundary therefore takes only the immutable research pack and independent
    source attestations, recomputes the closed audit, and binds its result.
    """
    if context.research_digest is None:
        if research_pack is not None or research_attestations is not None:
            raise EditorialContextAuthorityError(
                "speech-only context cannot carry research quality inputs"
            )
        return None
    if not isinstance(research_pack, CampaignResearchPack):
        raise EditorialContextAuthorityError(
            "research-bound context requires the immutable research pack"
        )
    if research_pack.status not in {"complete", "partial"}:
        raise EditorialContextAuthorityError(
            "research-bound context requires an available research pack"
        )
    if research_content_digest(research_pack) != context.research_digest:
        raise EditorialContextAuthorityError("research pack digest does not match context")
    materialized = materialize_campaign_research(
        research_pack,
        context.question.campaign_id,
    )
    expected_notes = {note.id: note for note in materialized.notes}
    if set(snapshot.active_research_note_ids) != set(expected_notes):
        raise EditorialContextAuthorityError(
            "snapshot active research lineage does not match the research pack"
        )
    snapshot_notes = {note.id: note for note in snapshot.vault.notes}
    if any(snapshot_notes.get(note_id) != note for note_id, note in expected_notes.items()):
        raise EditorialContextAuthorityError(
            "snapshot active research notes do not match the research pack"
        )
    if require_current_reusability and not is_reusable_research_pack(
        research_pack,
        campaign_fingerprint_value=research_pack.campaign_fingerprint,
        now=as_of,
        research_policy_version=research_pack.research_policy_version,
    ):
        raise EditorialContextAuthorityError("research pack is stale or incompatible")
    if research_attestations is not None and not isinstance(
        research_attestations, IssuedResearchAttestations
    ):
        raise EditorialContextAuthorityError(
            "research source classifications require a signed authority envelope"
        )
    try:
        attestation_items = ()
        if research_attestations is not None:
            if research_attestation_verifier is None:
                raise EditorialContextAuthorityError(
                    "research source classifications require an authority verifier"
                )
            verified_attestations = verify_research_attestations(
                research_attestations,
                research_pack,
                verifier=research_attestation_verifier,
                owner_id=snapshot.owner_id,
                campaign_id=snapshot.campaign_id,
                now=as_of,
            )
            attestation_items = verified_attestations.attestations
        quality = evaluate_campaign_research_quality(
            research_pack,
            attestation_items,
            as_of,
        )
    except (CampaignResearchQualityError, ResearchAttestationAuthorityError) as exc:
        raise EditorialContextAuthorityError("research quality evaluation failed") from exc
    if quality.status == "blocked":
        raise EditorialContextAuthorityError(
            "available research cannot have a blocked quality audit"
        )
    if research_pack.status == "complete" and quality.status != "trusted_complete":
        raise EditorialContextAuthorityError(
            "complete research requires a trusted_complete quality audit"
        )
    return quality


@dataclass(frozen=True)
class IssuedEditorialContext:
    owner_id: str
    campaign_id: str
    source_id: str
    snapshot_digest: str
    context_digest: str
    graph_digest: str
    retrieval_result_digest: str
    retrieval_policy_digest: str
    issued_at: str
    expires_at: str
    authority_key_id: str
    issuance_id: str
    signature: str
    research_status: str | None = None
    research_quality_status: str | None = None
    research_quality_digest: str | None = None
    research_attestation_authority_digest: str | None = None
    tenant_authority_digest: str | None = None
    vision_evidence_audit_digest: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "campaign_id",
            "source_id",
            "authority_key_id",
            "issuance_id",
        ):
            object.__setattr__(self, name, _id(getattr(self, name), name))
        for name in (
            "snapshot_digest",
            "context_digest",
            "graph_digest",
            "retrieval_result_digest",
            "retrieval_policy_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name))
        object.__setattr__(self, "issued_at", _instant(self.issued_at, "issued_at"))
        object.__setattr__(self, "expires_at", _instant(self.expires_at, "expires_at"))
        issued = datetime.fromisoformat(self.issued_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        lifetime = (expires - issued).total_seconds()
        if lifetime <= 0:
            raise EditorialContextAuthorityError("expires_at must be after issued_at")
        if lifetime > _MAX_ISSUANCE_SECONDS:
            raise EditorialContextAuthorityError("issued context lifetime exceeds the hard limit")
        if not isinstance(self.signature, str) or not _HEX.fullmatch(self.signature):
            raise EditorialContextAuthorityError("signature must be a SHA-256 hexadecimal value")
        if self.research_status is None:
            if (
                self.research_quality_status is not None
                or self.research_quality_digest is not None
                or self.research_attestation_authority_digest is not None
            ):
                raise EditorialContextAuthorityError(
                    "speech-only issuance cannot contain research quality bindings"
                )
        else:
            if self.research_status not in {"complete", "partial"}:
                raise EditorialContextAuthorityError("research_status is invalid")
            if self.research_quality_status not in {"trusted_complete", "limited"}:
                raise EditorialContextAuthorityError("research_quality_status is invalid")
            object.__setattr__(
                self,
                "research_quality_digest",
                _digest(self.research_quality_digest, "research_quality_digest"),
            )
            if self.research_quality_status == "trusted_complete":
                object.__setattr__(
                    self,
                    "research_attestation_authority_digest",
                    _digest(
                        self.research_attestation_authority_digest,
                        "research_attestation_authority_digest",
                    ),
                )
            elif self.research_attestation_authority_digest is not None:
                object.__setattr__(
                    self,
                    "research_attestation_authority_digest",
                    _digest(
                        self.research_attestation_authority_digest,
                        "research_attestation_authority_digest",
                    ),
                )
        if self.tenant_authority_digest is not None:
            object.__setattr__(
                self,
                "tenant_authority_digest",
                _digest(self.tenant_authority_digest, "tenant_authority_digest"),
            )
        if self.vision_evidence_audit_digest is not None:
            object.__setattr__(
                self,
                "vision_evidence_audit_digest",
                _digest(self.vision_evidence_audit_digest, "vision_evidence_audit_digest"),
            )

    def unsigned_payload(self) -> dict[str, str | None]:
        return {
            key: getattr(self, key)
            for key in (
                "owner_id",
                "campaign_id",
                "source_id",
                "snapshot_digest",
                "context_digest",
                "graph_digest",
                "retrieval_result_digest",
                "retrieval_policy_digest",
                "issued_at",
                "expires_at",
                "authority_key_id",
                "issuance_id",
                "research_status",
                "research_quality_status",
                "research_quality_digest",
                "research_attestation_authority_digest",
                "tenant_authority_digest",
                "vision_evidence_audit_digest",
            )
        }

    def canonical_payload(self) -> bytes:
        return _canonical(self.unsigned_payload())


def _vision_evidence_binding(
    snapshot: KnowledgeVaultSnapshot,
    graph: EditorialBeatGraph,
    vision_evidence: VerifiedVisionEvidenceSet | None,
    vision_evidence_verifier: VisionEvidenceVerifier | None,
    *,
    now: str,
) -> str | None:
    """Require a sealed visual authority before a graph unlocks visual privilege."""
    if not graph_requires_vision_evidence(graph):
        if vision_evidence is not None:
            raise EditorialContextAuthorityError(
                "speech-only graph cannot carry vision evidence authority"
            )
        return None
    if not isinstance(vision_evidence, VerifiedVisionEvidenceSet):
        raise EditorialContextAuthorityError(
            "candidate visual graph requires a VerifiedVisionEvidenceSet"
        )
    if vision_evidence_verifier is None:
        raise EditorialContextAuthorityError(
            "candidate visual graph requires a vision evidence verifier"
        )
    try:
        vision_evidence.validate_graph(
            graph,
            verifier=vision_evidence_verifier,
            owner_id=snapshot.owner_id,
            campaign_id=snapshot.campaign_id,
            source_id=snapshot.source_id,
            now=now,
        )
    except VisionEvidenceAuthorityError as exc:
        raise EditorialContextAuthorityError(
            "vision evidence does not bind this editorial context"
        ) from exc
    return vision_evidence.audit_digest


@dataclass(frozen=True, init=False)
class VerifiedEditorialContext:
    """A short-lived capability for one signed editorial context projection.

    Construction is intentionally private to this module.  The only supported
    public factory is :func:`verify_editorial_context_capability`, which binds
    the signed issuance to the exact snapshot, question scope, graph, and
    expiry before this value can expose a Director prompt, parse, validation or
    compilation operation.  Each operation receives ``now`` again, preventing
    a capability verified before expiry from being replayed afterwards.
    """

    issued: IssuedEditorialContext
    snapshot: KnowledgeVaultSnapshot
    context: UnifiedEditorialContextPack
    graph: EditorialBeatGraph
    vision_evidence: VerifiedVisionEvidenceSet | None
    vision_evidence_verifier: VisionEvidenceVerifier | None

    def __init__(
        self,
        issued: IssuedEditorialContext,
        snapshot: KnowledgeVaultSnapshot,
        context: UnifiedEditorialContextPack,
        graph: EditorialBeatGraph,
        *,
        vision_evidence: VerifiedVisionEvidenceSet | None = None,
        vision_evidence_verifier: VisionEvidenceVerifier | None = None,
        _token: object,
    ) -> None:
        if _token is not _VERIFIED_CONTEXT_TOKEN:
            raise EditorialContextAuthorityError(
                "VerifiedEditorialContext must be created by signature verification"
            )
        object.__setattr__(self, "issued", issued)
        object.__setattr__(self, "snapshot", snapshot)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "graph", graph)
        object.__setattr__(self, "vision_evidence", vision_evidence)
        object.__setattr__(self, "vision_evidence_verifier", vision_evidence_verifier)

    def _require_current(self, now: str) -> None:
        current = _instant(now, "now")
        instant = datetime.fromisoformat(current.replace("Z", "+00:00"))
        issued_at = datetime.fromisoformat(self.issued.issued_at.replace("Z", "+00:00"))
        expires_at = datetime.fromisoformat(self.issued.expires_at.replace("Z", "+00:00"))
        if instant < issued_at:
            raise EditorialContextAuthorityError("verified context is not yet valid")
        if instant >= expires_at:
            raise EditorialContextAuthorityError("verified context is expired")

    def prompt(
        self,
        *,
        transcript: Transcript,
        target_duration_seconds: int,
        now: str,
        music_asset_ids: tuple[str, ...] = (),
        sfx_asset_ids: tuple[str, ...] = (),
    ) -> str:
        self._require_current(now)
        return _editorial_director_user_prompt_v22_unverified(
            graph=self.graph,
            transcript=transcript,
            context=self.context,
            target_duration_seconds=target_duration_seconds,
            music_asset_ids=music_asset_ids,
            sfx_asset_ids=sfx_asset_ids,
        )

    def parse(self, payload: Any, *, now: str) -> EditorialDirectorPlanV22:
        self._require_current(now)
        return _parse_editorial_director_plan_v22_unverified(
            payload,
            context=self.context,
            graph=self.graph,
        )

    def validate(
        self,
        plan: EditorialDirectorPlanV22,
        *,
        now: str,
        claim_authority: Any | None = None,
        claim_authority_verifier: Any | None = None,
    ) -> None:
        self._require_current(now)
        _validate_editorial_director_plan_v22_unverified(
            plan,
            context=self.context,
            graph=self.graph,
        )
        self._validate_plan_vision(plan, now=now)
        if claim_authority is not None:
            # Local import avoids making the signed context module depend on a
            # claim registry at import time.  A claim capability is optional
            # for legacy speech-only edits, but if supplied it is fail-closed.
            from .claim_authority import validate_claim_authority

            validate_claim_authority(
                claim_authority,
                verified_context=self,
                plan=plan,
                now=now,
                verifier=claim_authority_verifier,
            )

    def _validate_plan_vision(self, plan: EditorialDirectorPlanV22, *, now: str) -> None:
        """Recheck exact candidate IDs when a plan invokes a visual privilege."""
        if not graph_requires_vision_evidence(self.graph):
            if self.vision_evidence is not None:
                raise EditorialContextAuthorityError(
                    "speech-only context cannot carry a vision evidence capability"
                )
            return
        if not isinstance(self.vision_evidence, VerifiedVisionEvidenceSet):
            raise EditorialContextAuthorityError(
                "candidate visual graph requires a VerifiedVisionEvidenceSet"
            )
        visuals = {item.visual_id: item for item in self.graph.visual_beats}
        beats = {item.beat_id: item for item in self.graph.editorial_beats}
        for shot in plan.controls.shots:
            if shot.framing.mode not in {"locked_face", "screen_focus"}:
                continue
            beat = beats.get(shot.beat_id)
            if beat is None:
                raise EditorialContextAuthorityError("vision plan references an unknown graph beat")
            if shot.framing.mode == "locked_face":
                selected = tuple(
                    visual_id
                    for visual_id in beat.visual_ids
                    if visuals[visual_id].provenance == "verified_candidate"
                    and visuals[visual_id].face_state == "primary"
                )
            else:
                selected = tuple(
                    visual_id
                    for visual_id in beat.visual_ids
                    if visuals[visual_id].provenance == "verified_candidate"
                    and visuals[visual_id].kind == "screen_proof"
                    and visuals[visual_id].screen_readability == "readable"
                    and visuals[visual_id].focus_region is not None
                )
            try:
                self.vision_evidence.validate_visual_ids(
                    selected,
                    verifier=self.vision_evidence_verifier,
                    graph=self.graph,
                    owner_id=self.issued.owner_id,
                    campaign_id=self.issued.campaign_id,
                    source_id=self.issued.source_id,
                    now=now,
                )
            except VisionEvidenceAuthorityError as exc:
                raise EditorialContextAuthorityError(
                    "plan visual framing is not covered by verified vision evidence"
                ) from exc

    def compile(
        self,
        plan: EditorialDirectorPlanV22,
        transcript: Transcript,
        *,
        now: str,
        source_duration_ms: int,
        claim_authority: Any | None = None,
        claim_authority_verifier: Any | None = None,
        **kwargs: Any,
    ):
        self.validate(
            plan,
            now=now,
            claim_authority=claim_authority,
            claim_authority_verifier=claim_authority_verifier,
        )
        return _compile_editorial_director_plan_v22_unverified(
            plan,
            self.graph,
            transcript,
            context=self.context,
            source_duration_ms=source_duration_ms,
            **kwargs,
        )


def issue_editorial_context(
    snapshot: KnowledgeVaultSnapshot,
    context: UnifiedEditorialContextPack,
    graph: EditorialBeatGraph,
    *,
    signer: Signer,
    issued_at: str,
    expires_at: str,
    issuance_id: str,
    research_pack: CampaignResearchPack | None = None,
    research_attestations: IssuedResearchAttestations | None = None,
    research_attestation_verifier: ResearchAttestationVerifier | None = None,
    tenant_authority: IssuedTenantVaultAuthority | None = None,
    tenant_authority_verifier: TenantVerifier | None = None,
    vision_evidence: VerifiedVisionEvidenceSet | None = None,
    vision_evidence_verifier: VisionEvidenceVerifier | None = None,
) -> IssuedEditorialContext:
    retrieval = _bind(snapshot, context, graph)
    issued_at, expires_at = _instant(issued_at, "issued_at"), _instant(expires_at, "expires_at")
    issued_instant = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
    expires_instant = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    tenant_authority_digest = _tenant_vault_binding(
        snapshot,
        tenant_authority,
        tenant_authority_verifier,
        now=issued_instant,
        issuance_expires_at=expires_instant,
    )
    quality = _research_quality_binding(
        snapshot,
        context,
        research_pack,
        research_attestations,
        research_attestation_verifier,
        as_of=issued_instant,
        require_current_reusability=True,
    )
    vision_evidence_audit_digest = _vision_evidence_binding(
        snapshot,
        graph,
        vision_evidence,
        vision_evidence_verifier,
        now=issued_at,
    )
    authority_key_id = _id(signer.key_id, "signer.key_id")
    issuance_id = _id(issuance_id, "issuance_id")
    unsigned_payload = {
        "owner_id": snapshot.owner_id,
        "campaign_id": snapshot.campaign_id,
        "source_id": snapshot.source_id,
        "snapshot_digest": snapshot.digest,
        "context_digest": context.context_digest,
        "graph_digest": context.graph_digest,
        "retrieval_result_digest": retrieval.result_digest,
        "retrieval_policy_digest": retrieval.policy_digest,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "authority_key_id": authority_key_id,
        "issuance_id": issuance_id,
        "research_status": research_pack.status if research_pack is not None else None,
        "research_quality_status": quality.status if quality is not None else None,
        "research_quality_digest": quality.audit_digest if quality is not None else None,
        "research_attestation_authority_digest": (
            research_attestations.authority_digest if research_attestations is not None else None
        ),
        "tenant_authority_digest": tenant_authority_digest,
        "vision_evidence_audit_digest": vision_evidence_audit_digest,
    }
    signature = signer.sign(_canonical(unsigned_payload))
    return IssuedEditorialContext(
        **unsigned_payload,
        signature=signature,
    )


def verify_issued_editorial_context(
    issued: IssuedEditorialContext,
    snapshot: KnowledgeVaultSnapshot,
    context: UnifiedEditorialContextPack,
    graph: EditorialBeatGraph,
    *,
    verifier: Verifier,
    now: str,
    expected_owner_id: str,
    expected_campaign_id: str,
    expected_source_id: str,
    research_pack: CampaignResearchPack | None = None,
    research_attestations: IssuedResearchAttestations | None = None,
    research_attestation_verifier: ResearchAttestationVerifier | None = None,
    vision_evidence: VerifiedVisionEvidenceSet | None = None,
    vision_evidence_verifier: VisionEvidenceVerifier | None = None,
) -> None:
    if not isinstance(issued, IssuedEditorialContext):
        raise EditorialContextAuthorityError("issued must be an IssuedEditorialContext")
    expected_owner_id = _id(expected_owner_id, "expected_owner_id")
    expected_campaign_id = _id(expected_campaign_id, "expected_campaign_id")
    expected_source_id = _id(expected_source_id, "expected_source_id")
    if issued.authority_key_id != verifier.key_id:
        raise EditorialContextAuthorityError("authority key rotation mismatch")
    if not verifier.verify(issued.canonical_payload(), issued.signature):
        raise EditorialContextAuthorityError("issued context signature is invalid")
    now = _instant(now, "now")
    if datetime.fromisoformat(now.replace("Z", "+00:00")) < datetime.fromisoformat(
        issued.issued_at.replace("Z", "+00:00")
    ):
        raise EditorialContextAuthorityError("issued context is not yet valid")
    if datetime.fromisoformat(now.replace("Z", "+00:00")) >= datetime.fromisoformat(
        issued.expires_at.replace("Z", "+00:00")
    ):
        raise EditorialContextAuthorityError("issued context is expired")
    if (issued.owner_id, issued.campaign_id, issued.source_id) != (
        expected_owner_id,
        expected_campaign_id,
        expected_source_id,
    ):
        raise EditorialContextAuthorityError("issued context tenant scope mismatch")
    issued_instant = datetime.fromisoformat(issued.issued_at.replace("Z", "+00:00"))
    quality = _research_quality_binding(
        snapshot,
        context,
        research_pack,
        research_attestations,
        research_attestation_verifier,
        as_of=issued_instant,
        require_current_reusability=False,
    )
    if (
        issued.research_status,
        issued.research_quality_status,
        issued.research_quality_digest,
        issued.research_attestation_authority_digest,
    ) != (
        research_pack.status if research_pack is not None else None,
        quality.status if quality is not None else None,
        quality.audit_digest if quality is not None else None,
        research_attestations.authority_digest if research_attestations is not None else None,
    ):
        raise EditorialContextAuthorityError("issued context research quality binding mismatch")
    expected_tenant_authority_digest = snapshot.tenant_authority_digest
    has_non_global_notes = any(note.vault != "global" for note in snapshot.vault.notes)
    if has_non_global_notes and expected_tenant_authority_digest is None:
        raise EditorialContextAuthorityError(
            "non-global snapshot lacks a tenant vault authority binding"
        )
    if issued.tenant_authority_digest != expected_tenant_authority_digest:
        raise EditorialContextAuthorityError("issued context tenant vault binding mismatch")
    vision_evidence_audit_digest = _vision_evidence_binding(
        snapshot,
        graph,
        vision_evidence,
        vision_evidence_verifier,
        now=now,
    )
    if issued.vision_evidence_audit_digest != vision_evidence_audit_digest:
        raise EditorialContextAuthorityError("issued context vision evidence binding mismatch")
    if research_pack is not None and not is_reusable_research_pack(
        research_pack,
        campaign_fingerprint_value=research_pack.campaign_fingerprint,
        now=datetime.fromisoformat(now.replace("Z", "+00:00")),
        research_policy_version=research_pack.research_policy_version,
    ):
        raise EditorialContextAuthorityError("research pack is stale or incompatible")
    retrieval = _bind(snapshot, context, graph)
    if (issued.owner_id, issued.campaign_id, issued.source_id) != (
        snapshot.owner_id,
        snapshot.campaign_id,
        snapshot.source_id,
    ):
        raise EditorialContextAuthorityError("issued context does not bind the current snapshot")
    if (
        issued.snapshot_digest,
        issued.context_digest,
        issued.graph_digest,
        issued.retrieval_result_digest,
        issued.retrieval_policy_digest,
    ) != (
        snapshot.digest,
        context.context_digest,
        context.graph_digest,
        retrieval.result_digest,
        retrieval.policy_digest,
    ):
        raise EditorialContextAuthorityError("issued context digest binding mismatch")


def verify_editorial_context_capability(
    issued: IssuedEditorialContext,
    snapshot: KnowledgeVaultSnapshot,
    context: UnifiedEditorialContextPack,
    graph: EditorialBeatGraph,
    *,
    verifier: Verifier,
    now: str,
    expected_owner_id: str,
    expected_campaign_id: str,
    expected_source_id: str,
    research_pack: CampaignResearchPack | None = None,
    research_attestations: IssuedResearchAttestations | None = None,
    research_attestation_verifier: ResearchAttestationVerifier | None = None,
    vision_evidence: VerifiedVisionEvidenceSet | None = None,
    vision_evidence_verifier: VisionEvidenceVerifier | None = None,
) -> VerifiedEditorialContext:
    """Return the sole normal Director 2.2 authority capability.

    The legacy verifier remains available for audit-only checks.  Code that
    asks the Director for a prompt, parses its answer, validates citations, or
    compiles EDL must use the returned capability rather than raw V2.2 helpers.
    """

    verify_issued_editorial_context(
        issued,
        snapshot,
        context,
        graph,
        verifier=verifier,
        now=now,
        expected_owner_id=expected_owner_id,
        expected_campaign_id=expected_campaign_id,
        expected_source_id=expected_source_id,
        research_pack=research_pack,
        research_attestations=research_attestations,
        research_attestation_verifier=research_attestation_verifier,
        vision_evidence=vision_evidence,
        vision_evidence_verifier=vision_evidence_verifier,
    )
    return VerifiedEditorialContext(
        issued,
        snapshot,
        context,
        graph,
        vision_evidence=vision_evidence,
        vision_evidence_verifier=vision_evidence_verifier,
        _token=_VERIFIED_CONTEXT_TOKEN,
    )


def parse_issued_editorial_director_plan_v22(
    payload: Any,
    *,
    issued: IssuedEditorialContext,
    snapshot: KnowledgeVaultSnapshot,
    context: UnifiedEditorialContextPack,
    graph: EditorialBeatGraph,
    verifier: Verifier,
    now: str,
    expected_owner_id: str,
    expected_campaign_id: str,
    expected_source_id: str,
    research_pack: CampaignResearchPack | None = None,
    research_attestations: IssuedResearchAttestations | None = None,
    research_attestation_verifier: ResearchAttestationVerifier | None = None,
    vision_evidence: VerifiedVisionEvidenceSet | None = None,
    vision_evidence_verifier: VisionEvidenceVerifier | None = None,
) -> EditorialDirectorPlanV22:
    verified = verify_editorial_context_capability(
        issued,
        snapshot,
        context,
        graph,
        verifier=verifier,
        now=now,
        expected_owner_id=expected_owner_id,
        expected_campaign_id=expected_campaign_id,
        expected_source_id=expected_source_id,
        research_pack=research_pack,
        research_attestations=research_attestations,
        research_attestation_verifier=research_attestation_verifier,
        vision_evidence=vision_evidence,
        vision_evidence_verifier=vision_evidence_verifier,
    )
    return verified.parse(payload, now=now)


def compile_issued_editorial_director_plan_v22(
    plan: EditorialDirectorPlanV22,
    graph: EditorialBeatGraph,
    transcript: Transcript,
    *,
    issued: IssuedEditorialContext,
    snapshot: KnowledgeVaultSnapshot,
    context: UnifiedEditorialContextPack,
    verifier: Verifier,
    now: str,
    expected_owner_id: str,
    expected_campaign_id: str,
    expected_source_id: str,
    source_duration_ms: int,
    research_pack: CampaignResearchPack | None = None,
    research_attestations: IssuedResearchAttestations | None = None,
    research_attestation_verifier: ResearchAttestationVerifier | None = None,
    vision_evidence: VerifiedVisionEvidenceSet | None = None,
    vision_evidence_verifier: VisionEvidenceVerifier | None = None,
    **kwargs: Any,
):
    verified = verify_editorial_context_capability(
        issued,
        snapshot,
        context,
        graph,
        verifier=verifier,
        now=now,
        expected_owner_id=expected_owner_id,
        expected_campaign_id=expected_campaign_id,
        expected_source_id=expected_source_id,
        research_pack=research_pack,
        research_attestations=research_attestations,
        research_attestation_verifier=research_attestation_verifier,
        vision_evidence=vision_evidence,
        vision_evidence_verifier=vision_evidence_verifier,
    )
    return verified.compile(
        plan,
        transcript,
        now=now,
        source_duration_ms=source_duration_ms,
        **kwargs,
    )


def editorial_director_user_prompt_issued_v22(
    transcript: Transcript,
    *,
    issued: IssuedEditorialContext,
    snapshot: KnowledgeVaultSnapshot,
    context: UnifiedEditorialContextPack,
    graph: EditorialBeatGraph,
    verifier: Verifier,
    now: str,
    expected_owner_id: str,
    expected_campaign_id: str,
    expected_source_id: str,
    target_duration_seconds: int,
    music_asset_ids: tuple[str, ...] = (),
    sfx_asset_ids: tuple[str, ...] = (),
    research_pack: CampaignResearchPack | None = None,
    research_attestations: IssuedResearchAttestations | None = None,
    research_attestation_verifier: ResearchAttestationVerifier | None = None,
    vision_evidence: VerifiedVisionEvidenceSet | None = None,
    vision_evidence_verifier: VisionEvidenceVerifier | None = None,
) -> str:
    """Build a Director prompt only after the context issuance is verified."""

    verified = verify_editorial_context_capability(
        issued,
        snapshot,
        context,
        graph,
        verifier=verifier,
        now=now,
        expected_owner_id=expected_owner_id,
        expected_campaign_id=expected_campaign_id,
        expected_source_id=expected_source_id,
        research_pack=research_pack,
        research_attestations=research_attestations,
        research_attestation_verifier=research_attestation_verifier,
        vision_evidence=vision_evidence,
        vision_evidence_verifier=vision_evidence_verifier,
    )
    return verified.prompt(
        transcript=transcript,
        target_duration_seconds=target_duration_seconds,
        now=now,
        music_asset_ids=music_asset_ids,
        sfx_asset_ids=sfx_asset_ids,
    )
