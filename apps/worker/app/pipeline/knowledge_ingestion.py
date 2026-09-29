"""Deterministic local materializers for the editorial Second Brain.

The module is deliberately one-way: it turns validated graph and campaign
brief artefacts into immutable vault records.  It never exposes transcript
words, timing, paths, URLs, or authority to make edit boundaries.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from ..safety import sanitize_campaign
from .editorial_beats import (
    EditorialBeatGraph,
    SourceMoment,
    VisualBeat,
    validate_editorial_beat_graph,
)
from .knowledge_tenant_authority import (
    IssuedTenantVaultAuthority,
    KnowledgeTenantAuthorityError,
    vault_content_digest,
    verify_tenant_vault_authority,
)
from .knowledge_tenant_authority import (
    Verifier as TenantVerifier,
)
from .knowledge_vault import (
    GraphEvidenceRef,
    KnowledgeNote,
    KnowledgeRef,
    KnowledgeRelation,
    KnowledgeVault,
    KnowledgeVaultError,
)


class KnowledgeIngestionError(ValueError):
    """An input cannot be safely materialized into a local vault snapshot."""


_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MAX_REVISION_LENGTH = 128
_MAX_BRIEF_CONTENT = 1_500
_RESEARCH_NOTE_TAGS = frozenset({"research_finding", "research_source_audit"})


def _opaque_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not _OPAQUE_ID.fullmatch(value):
        raise KnowledgeIngestionError(f"{label} must be a bounded opaque ID")
    return value


def _revision(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_REVISION_LENGTH:
        raise KnowledgeIngestionError("revision must be a bounded non-empty opaque value")
    if any(char.isspace() or ord(char) < 32 for char in value):
        raise KnowledgeIngestionError("revision cannot contain whitespace or control characters")
    return value


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(material).hexdigest()[:32]}"


def _tags(*values: str) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}))


def _overlaps(start: int, end: int, moment: SourceMoment) -> bool:
    return start < moment.source_out_ms and moment.source_in_ms < end


def _graph_digest(graph: EditorialBeatGraph) -> str:
    """Bind a snapshot to the full validated graph without serializing it into notes."""
    validate_editorial_beat_graph(graph)
    return _digest(asdict(graph))


def _visual_confidence(beat: VisualBeat) -> str:
    """Map vision confidence conservatively; coarse video-map observations stay low."""
    if beat.provenance != "verified_candidate":
        return "low"
    if beat.confidence >= 90:
        return "high"
    if beat.confidence >= 65:
        return "medium"
    return "low"


@dataclass(frozen=True)
class MaterializedEditorialGraph:
    graph_digest: str
    notes: tuple[KnowledgeNote, ...]
    relations: tuple[KnowledgeRelation, ...]
    moment_note_ids: Mapping[str, str]
    visual_note_ids: Mapping[str, str]
    audio_note_ids: Mapping[str, str]

    def __post_init__(self) -> None:
        if not _HEX_DIGEST.fullmatch(self.graph_digest):
            raise KnowledgeIngestionError("graph_digest must be a SHA-256 hexadecimal digest")
        for label, mapping in (
            ("moment_note_ids", self.moment_note_ids),
            ("visual_note_ids", self.visual_note_ids),
            ("audio_note_ids", self.audio_note_ids),
        ):
            if not isinstance(mapping, Mapping):
                raise KnowledgeIngestionError(f"{label} must be a mapping")
            for graph_id, note_id in mapping.items():
                if not isinstance(graph_id, str) or not isinstance(note_id, str):
                    raise KnowledgeIngestionError(f"{label} must map strings to strings")
            object.__setattr__(self, label, MappingProxyType(dict(sorted(mapping.items()))))


def materialize_editorial_graph(
    graph: EditorialBeatGraph, campaign_id: str, source_id: str
) -> MaterializedEditorialGraph:
    """Materialize graph observations without leaking transcript or source timing.

    Visual observations are intentionally observations, including a verified
    candidate window.  In particular this materializer never emits a ``proves``
    relation or a ``proof`` note from vision alone.
    """
    campaign_id, source_id = _opaque_id(campaign_id, "campaign_id"), _opaque_id(
        source_id, "source_id"
    )
    validate_editorial_beat_graph(graph)
    digest = _graph_digest(graph)
    moment_ids = {
        moment.moment_id: _stable_id("source_moment", campaign_id, source_id, moment.moment_id)
        for moment in graph.source_moments
    }
    visual_ids = {
        beat.visual_id: _stable_id("source_visual", campaign_id, source_id, beat.visual_id)
        for beat in graph.visual_beats
    }
    audio_ids = {
        beat.audio_id: _stable_id("source_audio", campaign_id, source_id, beat.audio_id)
        for beat in graph.audio_beats
    }
    notes: list[KnowledgeNote] = []
    for moment in sorted(graph.source_moments, key=lambda item: item.moment_id):
        notes.append(
            KnowledgeNote(
                id=moment_ids[moment.moment_id],
                type="source_moment",
                vault="source",
                # A SourceMoment is already a bounded, graph-derived
                # interpretation of transcript evidence.  It is therefore an
                # observation, not the raw media/transcript itself.  Keeping
                # it selectable also gives speech-only beats a citable source
                # binding without exposing words or timing to the vault.
                status="observation",
                confidence="high",
                title=f"Source moment: {moment.semantic_role}",
                content=(
                    f"Derived source moment with semantic role {moment.semantic_role}; "
                    f"graph provenance {moment.provenance}."
                ),
                tags=_tags("graph_source_moment", moment.provenance, moment.semantic_role),
                graph_refs=(GraphEvidenceRef("source_moment", moment.moment_id),),
                campaign_id=campaign_id,
                source_id=source_id,
            )
        )

    relations: list[KnowledgeRelation] = []
    for visual in sorted(graph.visual_beats, key=lambda item: item.visual_id):
        related = tuple(
            moment_ids[moment.moment_id]
            for moment in graph.source_moments
            if _overlaps(visual.source_in_ms, visual.source_out_ms, moment)
        )
        refs = tuple(KnowledgeRef(note_id, "source") for note_id in sorted(related))
        notes.append(
            KnowledgeNote(
                id=visual_ids[visual.visual_id],
                type="observation",
                vault="source",
                status="observation",
                confidence=_visual_confidence(visual),
                title=f"Visual observation: {visual.kind}",
                content=(
                    f"Visual observation kind {visual.kind}; face state {visual.face_state}; "
                    f"screen readability {visual.screen_readability}; motion {visual.motion}; "
                    f"vision provenance {visual.provenance}."
                ),
                tags=_tags(
                    "graph_visual",
                    visual.face_state,
                    visual.kind,
                    visual.motion,
                    visual.provenance,
                    visual.screen_readability,
                ),
                source_refs=refs,
                graph_refs=(GraphEvidenceRef("visual_beat", visual.visual_id),),
                campaign_id=campaign_id,
                source_id=source_id,
            )
        )
        relations.extend(
            KnowledgeRelation(visual_ids[visual.visual_id], note_id, "supports")
            for note_id in refs_id(refs)
        )

    for audio in sorted(graph.audio_beats, key=lambda item: item.audio_id):
        related = tuple(
            moment_ids[moment.moment_id]
            for moment in graph.source_moments
            if _overlaps(audio.source_in_ms, audio.source_out_ms, moment)
        )
        refs = tuple(KnowledgeRef(note_id, "source") for note_id in sorted(related))
        notes.append(
            KnowledgeNote(
                id=audio_ids[audio.audio_id],
                type="observation",
                vault="source",
                status="observation",
                confidence="medium",
                title=f"Audio observation: {audio.kind}",
                content=(
                    f"Measured audio observation kind {audio.kind}; "
                    f"provenance {audio.provenance}."
                ),
                tags=_tags("graph_audio", audio.kind, audio.provenance),
                source_refs=refs,
                graph_refs=(GraphEvidenceRef("audio_beat", audio.audio_id),),
                campaign_id=campaign_id,
                source_id=source_id,
            )
        )
        relations.extend(
            KnowledgeRelation(audio_ids[audio.audio_id], note_id, "supports")
            for note_id in refs_id(refs)
        )
    return MaterializedEditorialGraph(
        digest,
        tuple(notes),
        tuple(sorted(relations, key=lambda item: (item.source_id, item.target_id, item.relation))),
        moment_ids,
        visual_ids,
        audio_ids,
    )


def refs_id(refs: Sequence[KnowledgeRef]) -> tuple[str, ...]:
    return tuple(ref.note_id for ref in refs)


@dataclass(frozen=True)
class MaterializedCampaignBrief:
    campaign_fingerprint: str
    notes: tuple[KnowledgeNote, ...]
    relations: tuple[KnowledgeRelation, ...]

    def __post_init__(self) -> None:
        if not _HEX_DIGEST.fullmatch(self.campaign_fingerprint):
            raise KnowledgeIngestionError(
                "campaign_fingerprint must be a SHA-256 hexadecimal digest"
            )


def materialize_campaign_brief(
    campaign: Mapping[str, Any], campaign_id: str
) -> MaterializedCampaignBrief:
    """Convert only a sanitized campaign brief into campaign-local approved context."""
    campaign_id = _opaque_id(campaign_id, "campaign_id")
    if not isinstance(campaign, Mapping):
        raise KnowledgeIngestionError("campaign must be a mapping")
    brief = sanitize_campaign(dict(campaign))
    fingerprint = _digest(brief)
    notes: list[KnowledgeNote] = []

    def add(note_type: str, suffix: str, title: str, content: str, *tags: str) -> None:
        if not content:
            return
        notes.append(
            KnowledgeNote(
                id=_stable_id("campaign_brief", fingerprint, suffix),
                type=note_type,  # type: ignore[arg-type]
                vault="campaign",
                status="observation" if note_type == "observation" else "curated",
                confidence="high",
                title=title,
                content=content[:_MAX_BRIEF_CONTENT],
                tags=_tags("approved", "campaign_brief", *tags),
                campaign_id=campaign_id,
            )
        )

    audience = "; ".join(
        part for part in (brief["audience"], brief["niche"], brief["tone"]) if part
    )
    add("audience", "audience", "Approved campaign audience", audience, "audience")
    add("offer", "goal", "Approved campaign goal", brief["goal"], "goal")
    for index, item in enumerate(brief["avoid_topics"]):
        add("observation", f"avoid_{index}", "Approved topic restriction", item, "avoid")
    for index, item in enumerate(brief["example_hooks"]):
        # A brief example is campaign-local vocabulary, never a globally promoted policy.
        add("observation", f"hook_{index}", "Approved hook vocabulary", item, "hook_vocabulary")
    return MaterializedCampaignBrief(fingerprint, tuple(notes), ())


@runtime_checkable
class _Materialized(Protocol):
    notes: tuple[KnowledgeNote, ...]
    relations: tuple[KnowledgeRelation, ...]


@dataclass(frozen=True)
class KnowledgeVaultSnapshot:
    """Immutable, replayable local vault view without a wall-clock creation field."""

    version: int
    owner_id: str
    campaign_id: str
    source_id: str
    revision: str
    vault: KnowledgeVault
    campaign_fingerprint: str | None = None
    research_digest: str | None = None
    graph_digest: str | None = None
    active_research_note_ids: tuple[str, ...] = ()
    tenant_authority_digest: str | None = None
    base_vault_digest: str | None = None
    digest: str = field(init=False)
    note_versions: Mapping[str, int] = field(init=False)

    def __post_init__(self) -> None:
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise KnowledgeIngestionError(
                "snapshot version must be an integer greater than or equal to 1"
            )
        _opaque_id(self.owner_id, "owner_id")
        _opaque_id(self.campaign_id, "campaign_id")
        _opaque_id(self.source_id, "source_id")
        _revision(self.revision)
        if not isinstance(self.vault, KnowledgeVault):
            raise KnowledgeIngestionError("snapshot vault must be a KnowledgeVault")
        for label, value in (
            ("campaign_fingerprint", self.campaign_fingerprint),
            ("research_digest", self.research_digest),
            ("graph_digest", self.graph_digest),
            ("tenant_authority_digest", self.tenant_authority_digest),
            ("base_vault_digest", self.base_vault_digest),
        ):
            if value is not None and (
                not isinstance(value, str) or not _HEX_DIGEST.fullmatch(value)
            ):
                raise KnowledgeIngestionError(f"{label} must be a SHA-256 hexadecimal digest")
        if (self.tenant_authority_digest is None) != (self.base_vault_digest is None):
            raise KnowledgeIngestionError(
                "tenant_authority_digest and base_vault_digest must be supplied together"
            )
        for note in self.vault.notes:
            if note.vault == "campaign" and note.campaign_id != self.campaign_id:
                raise KnowledgeIngestionError("snapshot contains a note from another campaign")
            if note.vault == "source" and (
                note.campaign_id != self.campaign_id or note.source_id != self.source_id
            ):
                raise KnowledgeIngestionError("snapshot contains a note from another source scope")
        versions = {note.id: note.version for note in self.vault.notes}
        if len(versions) != len(self.vault.notes):
            raise KnowledgeIngestionError("snapshot contains duplicate note IDs")
        if (
            not isinstance(self.active_research_note_ids, tuple)
            or tuple(sorted(set(self.active_research_note_ids))) != self.active_research_note_ids
        ):
            raise KnowledgeIngestionError("active_research_note_ids must be a sorted unique tuple")
        active_research_notes = []
        for note_id in self.active_research_note_ids:
            note = next((item for item in self.vault.notes if item.id == note_id), None)
            if note is None or not (_RESEARCH_NOTE_TAGS & set(note.tags)):
                raise KnowledgeIngestionError(
                    "active research note is absent or lacks research provenance"
                )
            active_research_notes.append(note)
        if self.research_digest is None and active_research_notes:
            raise KnowledgeIngestionError("active research notes require a bound research_digest")
        if self.research_digest is not None and not active_research_notes:
            raise KnowledgeIngestionError("a bound research_digest requires active research notes")
        object.__setattr__(self, "note_versions", MappingProxyType(dict(sorted(versions.items()))))
        object.__setattr__(self, "digest", _digest(self._digest_payload()))

    def _digest_payload(self) -> dict[str, object]:
        def note_payload(note: KnowledgeNote) -> dict[str, object]:
            return {
                "id": note.id,
                "version": note.version,
                "type": note.type,
                "vault": note.vault,
                "status": note.status,
                "confidence": note.confidence,
                "title": note.title,
                "content": note.content,
                "tags": note.tags,
                "source_refs": tuple((ref.note_id, ref.role) for ref in note.source_refs),
                "graph_refs": tuple((ref.kind, ref.evidence_id) for ref in note.graph_refs),
                "campaign_id": note.campaign_id,
                "source_id": note.source_id,
            }

        return {
            "snapshot_version": self.version,
            "owner_id": self.owner_id,
            "campaign_id": self.campaign_id,
            "source_id": self.source_id,
            "revision": self.revision,
            "campaign_fingerprint": self.campaign_fingerprint,
            "research_digest": self.research_digest,
            "active_research_note_ids": self.active_research_note_ids,
            "graph_digest": self.graph_digest,
            "tenant_authority_digest": self.tenant_authority_digest,
            "base_vault_digest": self.base_vault_digest,
            "notes": [
                note_payload(note) for note in sorted(self.vault.notes, key=lambda item: item.id)
            ],
            "relations": [
                {
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                    "relation": relation.relation,
                    "provenance": tuple((ref.note_id, ref.role) for ref in relation.provenance),
                }
                for relation in sorted(
                    self.vault.relations,
                    key=lambda item: (item.source_id, item.target_id, item.relation),
                )
            ],
        }


def compose_vault_snapshot(
    base_vault: KnowledgeVault,
    brief: MaterializedCampaignBrief | None = None,
    research: _Materialized | None = None,
    graph: MaterializedEditorialGraph | None = None,
    *,
    owner_id: str,
    campaign_id: str,
    source_id: str,
    revision: str,
    tenant_authority: IssuedTenantVaultAuthority | None = None,
    tenant_authority_verifier: TenantVerifier | None = None,
    authority_now: datetime | None = None,
) -> KnowledgeVaultSnapshot:
    """Merge independently materialized local artefacts with collision fail-closed semantics."""
    if not isinstance(base_vault, KnowledgeVault):
        raise KnowledgeIngestionError("base_vault must be a KnowledgeVault")
    components: list[_Materialized | KnowledgeVault] = [base_vault]
    if brief is not None:
        components.append(brief)
    if research is not None:
        if not isinstance(research, _Materialized):
            raise KnowledgeIngestionError("research must expose immutable notes and relations")
        components.append(research)
    if graph is not None:
        components.append(graph)
    notes = tuple(note for component in components for note in component.notes)
    relations = tuple(relation for component in components for relation in component.relations)
    ids = [note.id for note in notes]
    if len(ids) != len(set(ids)):
        raise KnowledgeIngestionError("snapshot composition has note ID collisions")
    requires_tenant_authority = any(note.vault != "global" for note in notes)
    if requires_tenant_authority:
        if not isinstance(tenant_authority, IssuedTenantVaultAuthority):
            raise KnowledgeIngestionError(
                "non-global snapshot composition requires a signed tenant vault authority"
            )
        if tenant_authority_verifier is None:
            raise KnowledgeIngestionError(
                "non-global snapshot composition requires a tenant vault verifier"
            )
        if authority_now is None:
            raise KnowledgeIngestionError("non-global snapshot composition requires authority_now")
        try:
            verified_tenant_authority = verify_tenant_vault_authority(
                tenant_authority,
                base_vault,
                verifier=tenant_authority_verifier,
                owner_id=owner_id,
                campaign_id=campaign_id,
                source_id=source_id,
                now=authority_now,
            )
        except KnowledgeTenantAuthorityError as exc:
            raise KnowledgeIngestionError("tenant vault authority rejected composition") from exc
    elif (
        tenant_authority is not None
        or tenant_authority_verifier is not None
        or authority_now is not None
    ):
        raise KnowledgeIngestionError(
            "global-only snapshot composition must not carry tenant vault authority"
        )
    try:
        vault = KnowledgeVault(
            tuple(sorted(notes, key=lambda item: item.id)),
            tuple(
                sorted(relations, key=lambda item: (item.source_id, item.target_id, item.relation))
            ),
        )
    except KnowledgeVaultError as exc:
        raise KnowledgeIngestionError("snapshot composition produced an invalid vault") from exc
    research_digest = getattr(research, "research_digest", None) if research is not None else None
    active_research_note_ids = tuple(
        sorted(
            note.id
            for note in (research.notes if research is not None else ())
            if _RESEARCH_NOTE_TAGS & set(note.tags)
        )
    )
    return KnowledgeVaultSnapshot(
        1,
        owner_id,
        campaign_id,
        source_id,
        revision,
        vault,
        campaign_fingerprint=brief.campaign_fingerprint if brief is not None else None,
        research_digest=research_digest,
        graph_digest=graph.graph_digest if graph is not None else None,
        active_research_note_ids=active_research_note_ids,
        tenant_authority_digest=(
            verified_tenant_authority.authority_digest if tenant_authority is not None else None
        ),
        base_vault_digest=(
            vault_content_digest(base_vault) if tenant_authority is not None else None
        ),
    )
