"""Local, deterministic editorial knowledge vault primitives.

This module intentionally has no provider, database, renderer, or pipeline
dependency.  It is a small trust boundary: notes may inform an editorial
decision, but they cannot carry edit timings, render paths, or executable
instructions.  The public read API is bounded and campaign/source scoped.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal


class KnowledgeVaultError(ValueError):
    """A vault value violates the local, provider-independent contract."""


class KnowledgeVaultAccessError(KnowledgeVaultError):
    """A caller attempted to read a note outside its campaign/source scope."""


NoteType = Literal[
    "principle",
    "technique",
    "pattern",
    "problem",
    "example",
    "counterexample",
    "case_study",
    "audience",
    "objection",
    "offer",
    "claim",
    "proof",
    "asset",
    "source_moment",
    "clip",
    "decision",
    "observation",
    "hypothesis",
    "learning",
    "policy",
]
VaultKind = Literal["global", "campaign", "source"]
KnowledgeStatus = Literal[
    "raw_source", "observation", "hypothesis", "validated", "curated", "deprecated"
]
Confidence = Literal["low", "medium", "high"]
RelationType = Literal[
    "proves",
    "answers",
    "contradicts",
    "causes",
    "supports",
    "repairs",
    "risks",
    "requires",
    "used_in",
    "derived_from",
    "targets",
    "performs_for",
]
RefRole = Literal["source", "evidence", "derived_from", "related"]
GraphEvidenceKind = Literal["source_moment", "visual_beat", "audio_beat"]

NOTE_TYPES = frozenset(NoteType.__args__)
VAULT_KINDS = frozenset(VaultKind.__args__)
KNOWLEDGE_STATUSES = frozenset(KnowledgeStatus.__args__)
CONFIDENCES = frozenset(Confidence.__args__)
RELATION_TYPES = frozenset(RelationType.__args__)
REF_ROLES = frozenset(RefRole.__args__)
GRAPH_EVIDENCE_KINDS = frozenset(GraphEvidenceKind.__args__)

_SAFE_ID = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_SAFE_SCOPE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_TOKEN = re.compile(r"[a-z0-9]{2,}")
_MAX_ID_LENGTH = 80
_MAX_SCOPE_ID_LENGTH = 128
_MAX_QUERY_LIMIT = 25
_MAX_DEPTH = 3
_MAX_CONTENT_CHARS = 1_500
_MAX_QUESTION_CHARS = 320
_MAX_CONTEXT_JSON_CHARS = 4_800


def _require_safe_id(value: str, label: str) -> None:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value) or len(value) > _MAX_ID_LENGTH:
        raise KnowledgeVaultError(
            f"{label} must be a lowercase snake_case identifier up to {_MAX_ID_LENGTH} characters"
        )


def _require_safe_scope_id(value: str, label: str) -> None:
    """Accept opaque database IDs (including UUIDs) without accepting paths/control text."""
    if (
        not isinstance(value, str)
        or len(value) > _MAX_SCOPE_ID_LENGTH
        or not _SAFE_SCOPE_ID.fullmatch(value)
    ):
        raise KnowledgeVaultError(
            f"{label} must be a bounded opaque ID containing only letters, digits, "
            "underscores, or hyphens"
        )


def _validate_question(question: str) -> None:
    if not isinstance(question, str) or not question.strip() or len(question) > _MAX_QUESTION_CHARS:
        raise KnowledgeVaultError(
            f"question must be a non-empty string up to {_MAX_QUESTION_CHARS} characters"
        )


def _require_version(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise KnowledgeVaultError(f"{label} must be an integer greater than or equal to 1")


def _require_member(value: str, allowed: frozenset[str], label: str) -> None:
    if value not in allowed:
        raise KnowledgeVaultError(f"unsupported {label}: {value!r}")


def _require_limit(value: int, label: str, maximum: int = _MAX_QUERY_LIMIT) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise KnowledgeVaultError(f"{label} must be an integer between 1 and {maximum}")


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(value.casefold()))


@dataclass(frozen=True)
class KnowledgeRef:
    """A traceable reference to another note, used for provenance/evidence."""

    note_id: str
    role: RefRole = "source"

    def __post_init__(self) -> None:
        _require_safe_id(self.note_id, "KnowledgeRef.note_id")
        _require_member(self.role, REF_ROLES, "KnowledgeRef.role")


@dataclass(frozen=True)
class GraphEvidenceRef:
    """A graph-owned source evidence ID; graph existence is checked by a later layer."""

    kind: GraphEvidenceKind
    evidence_id: str

    def __post_init__(self) -> None:
        _require_member(self.kind, GRAPH_EVIDENCE_KINDS, "GraphEvidenceRef.kind")
        _require_safe_id(self.evidence_id, "GraphEvidenceRef.evidence_id")


@dataclass(frozen=True)
class KnowledgeNote:
    """An immutable atomic note in the global, campaign, or source vault."""

    id: str
    type: NoteType
    vault: VaultKind
    status: KnowledgeStatus
    confidence: Confidence
    title: str
    content: str
    version: int = 1
    tags: tuple[str, ...] = ()
    source_refs: tuple[KnowledgeRef, ...] = ()
    graph_refs: tuple[GraphEvidenceRef, ...] = ()
    campaign_id: str | None = None
    source_id: str | None = None
    created_at: str = "2026-08-09"
    updated_at: str = "2026-08-09"

    def __post_init__(self) -> None:
        _require_safe_id(self.id, "KnowledgeNote.id")
        _require_member(self.type, NOTE_TYPES, "KnowledgeNote.type")
        _require_member(self.vault, VAULT_KINDS, "KnowledgeNote.vault")
        _require_member(self.status, KNOWLEDGE_STATUSES, "KnowledgeNote.status")
        _require_member(self.confidence, CONFIDENCES, "KnowledgeNote.confidence")
        _require_version(self.version, "KnowledgeNote.version")
        if not isinstance(self.title, str) or not self.title.strip():
            raise KnowledgeVaultError("KnowledgeNote.title must be a non-empty string")
        if not isinstance(self.content, str) or len(self.content) > _MAX_CONTENT_CHARS:
            raise KnowledgeVaultError(
                f"KnowledgeNote.content must be at most {_MAX_CONTENT_CHARS} characters"
            )
        if not isinstance(self.tags, tuple) or any(
            not isinstance(tag, str) or not tag.strip() for tag in self.tags
        ):
            raise KnowledgeVaultError("KnowledgeNote.tags must be a tuple of non-empty strings")
        if tuple(sorted(set(self.tags))) != self.tags:
            raise KnowledgeVaultError("KnowledgeNote.tags must be unique and sorted")
        if not isinstance(self.source_refs, tuple) or not all(
            isinstance(ref, KnowledgeRef) for ref in self.source_refs
        ):
            raise KnowledgeVaultError(
                "KnowledgeNote.source_refs must be a tuple of KnowledgeRef values"
            )
        if len({ref.note_id for ref in self.source_refs}) != len(self.source_refs):
            raise KnowledgeVaultError("KnowledgeNote.source_refs cannot repeat a note")
        if not isinstance(self.graph_refs, tuple) or not all(
            isinstance(ref, GraphEvidenceRef) for ref in self.graph_refs
        ):
            raise KnowledgeVaultError(
                "KnowledgeNote.graph_refs must be a tuple of GraphEvidenceRef values"
            )
        if len({(ref.kind, ref.evidence_id) for ref in self.graph_refs}) != len(self.graph_refs):
            raise KnowledgeVaultError("KnowledgeNote.graph_refs cannot repeat graph evidence")
        self._validate_scope()
        if self.vault != "source" and self.graph_refs:
            raise KnowledgeVaultError("only source-vault notes can have graph_refs")
        if self.type == "source_moment" and not any(
            ref.kind == "source_moment" for ref in self.graph_refs
        ):
            raise KnowledgeVaultError("source_moment notes require a source_moment graph_ref")
        self._validate_epistemic_state()
        try:
            created, updated = date.fromisoformat(self.created_at), date.fromisoformat(
                self.updated_at
            )
        except (TypeError, ValueError) as exc:
            raise KnowledgeVaultError("note dates must use ISO YYYY-MM-DD") from exc
        if updated < created:
            raise KnowledgeVaultError("KnowledgeNote.updated_at cannot precede created_at")

    def _validate_scope(self) -> None:
        if self.vault == "global":
            if self.campaign_id is not None or self.source_id is not None:
                raise KnowledgeVaultError("global notes cannot have campaign_id or source_id")
            return
        if not isinstance(self.campaign_id, str):
            raise KnowledgeVaultError(f"{self.vault} notes require campaign_id")
        _require_safe_scope_id(self.campaign_id, "KnowledgeNote.campaign_id")
        if self.vault == "campaign":
            if self.source_id is not None:
                raise KnowledgeVaultError("campaign notes cannot have source_id")
            return
        if not isinstance(self.source_id, str):
            raise KnowledgeVaultError("source notes require source_id")
        _require_safe_scope_id(self.source_id, "KnowledgeNote.source_id")

    def _validate_epistemic_state(self) -> None:
        """Keep recorded evidence, inferences, learnings, and policies distinct.

        In particular a single observation/hypothesis cannot be represented as
        a policy: policy promotion needs two independent in-vault provenance
        references and an explicit curated/high-confidence review state.

        This is a local citation guard only.  Two references do not establish
        independent experimental evidence, nor does this module promote a
        learning into a product policy.
        """
        allowed_statuses: dict[str, frozenset[str]] = {
            "observation": frozenset({"observation", "validated", "deprecated"}),
            "hypothesis": frozenset({"hypothesis", "validated", "deprecated"}),
            "learning": frozenset({"validated", "curated", "deprecated"}),
            "policy": frozenset({"curated", "deprecated"}),
        }
        permitted = allowed_statuses.get(self.type)
        if permitted is not None and self.status not in permitted:
            raise KnowledgeVaultError(f"{self.type} cannot use status {self.status!r}")
        if self.type == "learning" and not self.source_refs:
            raise KnowledgeVaultError("learning requires at least one provenance reference")
        if self.type == "policy" and self.status != "deprecated":
            if self.confidence != "high" or len(self.source_refs) < 2:
                raise KnowledgeVaultError(
                    "a live policy requires high confidence and at least two provenance references"
                )


@dataclass(frozen=True)
class KnowledgeRelation:
    """An explicit typed edge; target existence is verified by KnowledgeVault."""

    source_id: str
    target_id: str
    relation: RelationType
    provenance: tuple[KnowledgeRef, ...] = ()

    def __post_init__(self) -> None:
        _require_safe_id(self.source_id, "KnowledgeRelation.source_id")
        _require_safe_id(self.target_id, "KnowledgeRelation.target_id")
        if self.source_id == self.target_id:
            raise KnowledgeVaultError("KnowledgeRelation cannot self-reference")
        _require_member(self.relation, RELATION_TYPES, "KnowledgeRelation.relation")
        if not isinstance(self.provenance, tuple) or not all(
            isinstance(ref, KnowledgeRef) for ref in self.provenance
        ):
            raise KnowledgeVaultError(
                "KnowledgeRelation.provenance must be a tuple of KnowledgeRef values"
            )


@dataclass(frozen=True)
class EditorialDecision:
    """Provider-neutral decision references, deliberately without edit timings."""

    decision_id: str
    decision: str
    knowledge_refs: tuple[KnowledgeRef, ...]
    source_refs: tuple[KnowledgeRef, ...]
    campaign_refs: tuple[KnowledgeRef, ...]

    def __post_init__(self) -> None:
        _require_safe_id(self.decision_id, "EditorialDecision.decision_id")
        if not isinstance(self.decision, str) or not self.decision.strip():
            raise KnowledgeVaultError("EditorialDecision.decision must be a non-empty string")
        for label, refs in (
            ("knowledge_refs", self.knowledge_refs),
            ("source_refs", self.source_refs),
            ("campaign_refs", self.campaign_refs),
        ):
            if not isinstance(refs, tuple) or not all(
                isinstance(ref, KnowledgeRef) for ref in refs
            ):
                raise KnowledgeVaultError(
                    f"EditorialDecision.{label} must be a tuple of KnowledgeRef values"
                )
            if len({ref.note_id for ref in refs}) != len(refs):
                raise KnowledgeVaultError(f"EditorialDecision.{label} cannot repeat a note")
        all_ref_ids = [
            ref.note_id
            for refs in (self.knowledge_refs, self.source_refs, self.campaign_refs)
            for ref in refs
        ]
        if len(set(all_ref_ids)) != len(all_ref_ids):
            raise KnowledgeVaultError(
                "EditorialDecision cannot repeat a note across reference classes"
            )


@dataclass(frozen=True)
class DecisionReferencePolicy:
    """Local citation guardrail, not proof of independent experimental evidence."""

    require_source_evidence: bool = True
    require_campaign_objective: bool = True


@dataclass(frozen=True)
class ContextNote:
    """A compact note representation for a JSON-only editorial prompt boundary."""

    note_id: str
    version: int
    type: NoteType
    vault: VaultKind
    status: KnowledgeStatus
    confidence: Confidence
    title: str
    content: str
    provenance: tuple[KnowledgeRef, ...]
    graph_refs: tuple[GraphEvidenceRef, ...]

    def __post_init__(self) -> None:
        _require_safe_id(self.note_id, "ContextNote.note_id")
        _require_version(self.version, "ContextNote.version")
        _require_member(self.type, NOTE_TYPES, "ContextNote.type")
        _require_member(self.vault, VAULT_KINDS, "ContextNote.vault")
        _require_member(self.status, KNOWLEDGE_STATUSES, "ContextNote.status")
        _require_member(self.confidence, CONFIDENCES, "ContextNote.confidence")
        if not isinstance(self.title, str) or not self.title.strip():
            raise KnowledgeVaultError("ContextNote.title must be a non-empty string")
        if not isinstance(self.content, str) or len(self.content) > _MAX_CONTENT_CHARS:
            raise KnowledgeVaultError("ContextNote.content must be a bounded string")
        if not isinstance(self.provenance, tuple) or not all(
            isinstance(ref, KnowledgeRef) for ref in self.provenance
        ):
            raise KnowledgeVaultError(
                "ContextNote.provenance must be a tuple of KnowledgeRef values"
            )
        if len({ref.note_id for ref in self.provenance}) != len(self.provenance):
            raise KnowledgeVaultError("ContextNote.provenance cannot repeat a note")
        if not isinstance(self.graph_refs, tuple) or not all(
            isinstance(ref, GraphEvidenceRef) for ref in self.graph_refs
        ):
            raise KnowledgeVaultError(
                "ContextNote.graph_refs must be a tuple of GraphEvidenceRef values"
            )
        if len({(ref.kind, ref.evidence_id) for ref in self.graph_refs}) != len(self.graph_refs):
            raise KnowledgeVaultError("ContextNote.graph_refs cannot repeat graph evidence")
        if self.vault != "source" and self.graph_refs:
            raise KnowledgeVaultError("only source ContextNotes can have graph_refs")
        if self.type == "source_moment" and not any(
            ref.kind == "source_moment" for ref in self.graph_refs
        ):
            raise KnowledgeVaultError(
                "source_moment ContextNotes require a source_moment graph_ref"
            )

    @classmethod
    def from_note(cls, note: KnowledgeNote, content_limit: int) -> ContextNote:
        _require_limit(content_limit, "content_limit", _MAX_CONTENT_CHARS)
        return cls(
            note_id=note.id,
            version=note.version,
            type=note.type,
            vault=note.vault,
            status=note.status,
            confidence=note.confidence,
            title=note.title,
            content=note.content[:content_limit],
            provenance=note.source_refs,
            graph_refs=note.graph_refs,
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "content": self.content,
            "confidence": self.confidence,
            "id": self.note_id,
            "graph_refs": [
                {"evidence_id": ref.evidence_id, "kind": ref.kind} for ref in self.graph_refs
            ],
            "provenance": [{"id": ref.note_id, "role": ref.role} for ref in self.provenance],
            "status": self.status,
            "title": self.title,
            "type": self.type,
            "vault": self.vault,
            "version": self.version,
        }


@dataclass(frozen=True)
class EditorialContextPack:
    """Stable, bounded, JSON-serialized context; note text is always data, never instructions."""

    question: str
    campaign_id: str
    source_id: str
    note_budget: int
    notes: tuple[ContextNote, ...]

    def __post_init__(self) -> None:
        _validate_question(self.question)
        _require_safe_scope_id(self.campaign_id, "EditorialContextPack.campaign_id")
        _require_safe_scope_id(self.source_id, "EditorialContextPack.source_id")
        _require_limit(self.note_budget, "note_budget")
        if len(self.notes) > self.note_budget:
            raise KnowledgeVaultError("EditorialContextPack exceeds note_budget")
        if len({note.note_id for note in self.notes}) != len(self.notes):
            raise KnowledgeVaultError("EditorialContextPack cannot repeat notes")
        if len(self.to_prompt_json()) > _MAX_CONTEXT_JSON_CHARS:
            raise KnowledgeVaultError(
                f"EditorialContextPack JSON exceeds {_MAX_CONTEXT_JSON_CHARS} characters"
            )

    @property
    def note_ids(self) -> tuple[str, ...]:
        return tuple(note.note_id for note in self.notes)

    def to_prompt_json(self) -> str:
        """Return canonical JSON so note content cannot break the prompt envelope."""
        payload = {
            "campaign_id": self.campaign_id,
            "notes": [note.to_payload() for note in self.notes],
            "question": self.question,
            "source_id": self.source_id,
        }
        encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        if len(encoded) > _MAX_CONTEXT_JSON_CHARS:
            raise KnowledgeVaultError(
                f"EditorialContextPack JSON exceeds {_MAX_CONTEXT_JSON_CHARS} characters"
            )
        return encoded


@dataclass(frozen=True)
class KnowledgeVault:
    """Validated immutable note graph with a bounded read-only navigation API."""

    notes: tuple[KnowledgeNote, ...]
    relations: tuple[KnowledgeRelation, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.notes, tuple) or not all(
            isinstance(note, KnowledgeNote) for note in self.notes
        ):
            raise KnowledgeVaultError(
                "KnowledgeVault.notes must be a tuple of KnowledgeNote values"
            )
        if not isinstance(self.relations, tuple) or not all(
            isinstance(relation, KnowledgeRelation) for relation in self.relations
        ):
            raise KnowledgeVaultError(
                "KnowledgeVault.relations must be a tuple of KnowledgeRelation values"
            )
        note_ids = {note.id for note in self.notes}
        if len(note_ids) != len(self.notes):
            raise KnowledgeVaultError("KnowledgeVault contains duplicate note IDs")
        by_id = self._by_id()
        for note in self.notes:
            self._validate_refs(note.source_refs, note_ids, f"note {note.id}")
            self._validate_refs_in_scope(note, note.source_refs, by_id, f"note {note.id}")
        seen_edges: set[tuple[str, str, str]] = set()
        for relation in self.relations:
            if relation.source_id not in note_ids or relation.target_id not in note_ids:
                raise KnowledgeVaultError("KnowledgeRelation references an unknown note")
            self._validate_refs(relation.provenance, note_ids, "relation provenance")
            self._validate_refs_in_scope(
                by_id[relation.source_id],
                relation.provenance,
                by_id,
                f"relation provenance for {relation.source_id}",
            )
            key = (relation.source_id, relation.target_id, relation.relation)
            if key in seen_edges:
                raise KnowledgeVaultError("KnowledgeVault contains a duplicate typed relation")
            seen_edges.add(key)
            self._validate_relation_scopes(by_id[relation.source_id], by_id[relation.target_id])
        counterexamples = {note.id for note in self.notes if note.type == "counterexample"}
        contradicted = {
            relation.source_id for relation in self.relations if relation.relation == "contradicts"
        }
        orphaned = sorted(counterexamples - contradicted)
        if orphaned:
            raise KnowledgeVaultError(
                "counterexample notes require an outbound contradicts relation: "
                + ", ".join(orphaned)
            )

    def _by_id(self) -> dict[str, KnowledgeNote]:
        return {note.id: note for note in self.notes}

    @staticmethod
    def _validate_refs(refs: tuple[KnowledgeRef, ...], note_ids: set[str], label: str) -> None:
        unknown = sorted({ref.note_id for ref in refs} - note_ids)
        if unknown:
            raise KnowledgeVaultError(f"{label} references unknown note(s): {', '.join(unknown)}")

    @staticmethod
    def _validate_relation_scopes(source: KnowledgeNote, target: KnowledgeNote) -> None:
        if source.campaign_id and target.campaign_id and source.campaign_id != target.campaign_id:
            raise KnowledgeVaultError("relations cannot cross campaigns")
        if source.source_id and target.source_id and source.source_id != target.source_id:
            raise KnowledgeVaultError("relations cannot cross source vaults")

    @staticmethod
    def _validate_refs_in_scope(
        owner: KnowledgeNote,
        refs: tuple[KnowledgeRef, ...],
        by_id: Mapping[str, KnowledgeNote],
        label: str,
    ) -> None:
        """Ensure persisted provenance cannot reveal a narrower tenant/source scope."""
        for ref in refs:
            target = by_id[ref.note_id]
            if target.vault == "global":
                continue
            if owner.vault == "global" or target.campaign_id != owner.campaign_id:
                raise KnowledgeVaultError(f"{label} cannot cross campaign scope")
            if target.vault == "source" and owner.source_id != target.source_id:
                raise KnowledgeVaultError(f"{label} cannot cross source scope")

    @staticmethod
    def _validate_scope_request(
        vaults: Sequence[VaultKind] | None, campaign_id: str | None, source_id: str | None
    ) -> tuple[VaultKind, ...]:
        requested = tuple(vaults) if vaults is not None else ("global", "campaign", "source")
        if not requested or len(set(requested)) != len(requested):
            raise KnowledgeVaultError("vaults must be a non-empty sequence without duplicates")
        for vault in requested:
            _require_member(vault, VAULT_KINDS, "vault")
        if campaign_id is not None:
            _require_safe_scope_id(campaign_id, "campaign_id")
        if source_id is not None:
            _require_safe_scope_id(source_id, "source_id")
        if "campaign" in requested or "source" in requested:
            if campaign_id is None:
                raise KnowledgeVaultAccessError(
                    "campaign_id is required to read campaign or source notes"
                )
        if "source" in requested:
            if source_id is None:
                raise KnowledgeVaultAccessError("source_id is required to read source notes")
        return requested

    @staticmethod
    def _visible(note: KnowledgeNote, campaign_id: str | None, source_id: str | None) -> bool:
        if note.vault == "global":
            return True
        if campaign_id != note.campaign_id:
            return False
        return note.vault == "campaign" or source_id == note.source_id

    def _open_visible(
        self, note_id: str, campaign_id: str | None, source_id: str | None
    ) -> KnowledgeNote:
        _require_safe_id(note_id, "note_id")
        if campaign_id is not None:
            _require_safe_scope_id(campaign_id, "campaign_id")
        if source_id is not None:
            _require_safe_scope_id(source_id, "source_id")
        note = self._by_id().get(note_id)
        if note is None:
            raise KnowledgeVaultError(f"unknown note_id: {note_id}")
        if not self._visible(note, campaign_id, source_id):
            raise KnowledgeVaultAccessError(f"note_id is outside the requested scope: {note_id}")
        return note

    def search_notes(
        self,
        query: str,
        *,
        vaults: Sequence[VaultKind] | None = None,
        types: Sequence[NoteType] | None = None,
        statuses: Sequence[KnowledgeStatus] | None = None,
        limit: int = 8,
        campaign_id: str | None = None,
        source_id: str | None = None,
        include_deprecated: bool = False,
    ) -> tuple[KnowledgeNote, ...]:
        """Lexically rank visible notes, using stable ID ordering as the tiebreaker."""
        _validate_question(query)
        _require_limit(limit, "limit")
        requested = self._validate_scope_request(vaults, campaign_id, source_id)
        type_filter = self._filter_values(types, NOTE_TYPES, "type")
        status_filter = self._filter_values(statuses, KNOWLEDGE_STATUSES, "status")
        query_tokens = _tokens(query)
        if not query_tokens:
            raise KnowledgeVaultError("query must contain at least one alphanumeric token")
        ranked: list[tuple[int, str, KnowledgeNote]] = []
        for note in self.notes:
            if note.vault not in requested or not self._visible(note, campaign_id, source_id):
                continue
            if note.status == "deprecated" and not include_deprecated:
                continue
            if type_filter and note.type not in type_filter:
                continue
            if status_filter and note.status not in status_filter:
                continue
            score = self._lexical_score(note, query_tokens)
            if score:
                ranked.append((-score, note.id, note))
        ranked.sort(key=lambda item: (item[0], item[1]))
        return tuple(item[2] for item in ranked[:limit])

    search = search_notes

    @staticmethod
    def _filter_values(
        values: Sequence[str] | None, allowed: frozenset[str], label: str
    ) -> frozenset[str]:
        if values is None:
            return frozenset()
        checked = tuple(values)
        if not checked:
            raise KnowledgeVaultError(f"{label}s cannot be empty when supplied")
        for value in checked:
            _require_member(value, allowed, label)
        return frozenset(checked)

    @staticmethod
    def _lexical_score(note: KnowledgeNote, query_tokens: tuple[str, ...]) -> int:
        title_tokens = set(_tokens(note.title))
        tag_tokens = {token for tag in note.tags for token in _tokens(tag)}
        content_tokens = set(_tokens(note.content))
        score = 0
        for token in query_tokens:
            if token in title_tokens:
                score += 6
            if token in tag_tokens:
                score += 4
            if token in content_tokens:
                score += 1
        return score

    def open_note(
        self, note_id: str, *, campaign_id: str | None = None, source_id: str | None = None
    ) -> KnowledgeNote:
        """Open an explicit visible note; deprecated is allowed only by explicit ID."""
        return self._open_visible(note_id, campaign_id, source_id)

    open = open_note

    def get_neighbors(
        self,
        note_id: str,
        *,
        relations: Sequence[RelationType] | None = None,
        depth: int = 1,
        limit: int = 8,
        campaign_id: str | None = None,
        source_id: str | None = None,
        include_deprecated: bool = False,
    ) -> tuple[KnowledgeNote, ...]:
        """Breadth-first, outbound graph traversal with hard depth/result bounds."""
        _require_limit(limit, "limit")
        _require_limit(depth, "depth", _MAX_DEPTH)
        start = self._open_visible(note_id, campaign_id, source_id)
        if start.status == "deprecated" and not include_deprecated:
            return ()
        relation_filter = self._filter_values(relations, RELATION_TYPES, "relation")
        by_id = self._by_id()
        frontier = (start.id,)
        visited = {start.id}
        result: list[KnowledgeNote] = []
        for _ in range(depth):
            candidates: list[tuple[str, str]] = []
            for current_id in frontier:
                for edge in self.relations:
                    if edge.source_id == current_id and (
                        not relation_filter or edge.relation in relation_filter
                    ):
                        candidates.append((edge.target_id, edge.relation))
            next_frontier: list[str] = []
            for target_id, _relation in sorted(candidates):
                if target_id in visited:
                    continue
                target = by_id[target_id]
                if not self._visible(target, campaign_id, source_id):
                    continue
                visited.add(target_id)
                if target.status == "deprecated" and not include_deprecated:
                    continue
                next_frontier.append(target_id)
                result.append(target)
                if len(result) == limit:
                    return tuple(result)
            frontier = tuple(next_frontier)
            if not frontier:
                break
        return tuple(result)

    neighbors = get_neighbors

    def get_backlinks(
        self,
        note_id: str,
        *,
        relation: RelationType | None = None,
        limit: int = 8,
        campaign_id: str | None = None,
        source_id: str | None = None,
        include_deprecated: bool = False,
    ) -> tuple[KnowledgeNote, ...]:
        """Return visible inbound linked notes in stable relation/ID order."""
        _require_limit(limit, "limit")
        self._open_visible(note_id, campaign_id, source_id)
        if relation is not None:
            _require_member(relation, RELATION_TYPES, "relation")
        by_id = self._by_id()
        candidates = sorted(
            (edge.relation, edge.source_id)
            for edge in self.relations
            if edge.target_id == note_id and (relation is None or edge.relation == relation)
        )
        found: list[KnowledgeNote] = []
        for _relation, source_note_id in candidates:
            note = by_id[source_note_id]
            if self._visible(note, campaign_id, source_id) and (
                note.status != "deprecated" or include_deprecated
            ):
                found.append(note)
                if len(found) == limit:
                    break
        return tuple(found)

    backlinks = get_backlinks

    def validate_decision(
        self,
        decision: EditorialDecision,
        *,
        campaign_id: str,
        source_id: str,
        policy: DecisionReferencePolicy | None = None,
    ) -> None:
        """Require real, in-scope knowledge/source/campaign citations for a decision."""
        policy = policy or DecisionReferencePolicy()
        _require_safe_scope_id(campaign_id, "campaign_id")
        _require_safe_scope_id(source_id, "source_id")
        if policy.require_source_evidence and not decision.source_refs:
            raise KnowledgeVaultError("decision requires at least one source reference")
        if policy.require_campaign_objective and not decision.campaign_refs:
            raise KnowledgeVaultError("decision requires at least one campaign reference")
        for ref in decision.knowledge_refs:
            note = self._open_visible(ref.note_id, campaign_id, source_id)
            self._validate_decision_ref(note, "global", "knowledge_refs")
        for ref in decision.source_refs:
            note = self._open_visible(ref.note_id, campaign_id, source_id)
            self._validate_decision_ref(note, "source", "source_refs")
        for ref in decision.campaign_refs:
            note = self._open_visible(ref.note_id, campaign_id, source_id)
            self._validate_decision_ref(note, "campaign", "campaign_refs")

    @staticmethod
    def _validate_decision_ref(note: KnowledgeNote, expected_vault: VaultKind, label: str) -> None:
        if note.status == "deprecated":
            raise KnowledgeVaultError(f"decision {label} cannot cite deprecated notes")
        if note.vault != expected_vault:
            raise KnowledgeVaultError(f"decision {label} must cite {expected_vault}-vault notes")

    def build_context_pack(
        self,
        question: str,
        *,
        campaign_id: str,
        source_id: str,
        note_budget: int = 8,
        content_limit: int = 420,
    ) -> EditorialContextPack:
        """Build an ordered compact pack from only visible non-deprecated notes."""
        _validate_question(question)
        _require_limit(note_budget, "note_budget")
        _require_limit(content_limit, "content_limit", _MAX_CONTENT_CHARS)
        notes = self.search_notes(
            question,
            campaign_id=campaign_id,
            source_id=source_id,
            limit=note_budget,
        )
        context_notes: list[ContextNote] = []
        visible_ids = {
            note.id for note in self.notes if self._visible(note, campaign_id, source_id)
        }
        for note in notes:
            context_note = ContextNote.from_note(note, content_limit)
            if context_note.note_id not in visible_ids or any(
                ref.note_id not in visible_ids for ref in context_note.provenance
            ):
                raise KnowledgeVaultError(
                    "context pack contains an invalid or out-of-scope reference"
                )
            try:
                candidate = EditorialContextPack(
                    question,
                    campaign_id,
                    source_id,
                    note_budget,
                    tuple((*context_notes, context_note)),
                )
            except KnowledgeVaultError as exc:
                if "JSON exceeds" not in str(exc):
                    raise
                continue
            # Stable pruning: ranking order is preserved and an oversized note
            # is skipped while later compact notes can still fit the same pack.
            if len(candidate.to_prompt_json()) <= _MAX_CONTEXT_JSON_CHARS:
                context_notes.append(context_note)
        return EditorialContextPack(
            question, campaign_id, source_id, note_budget, tuple(context_notes)
        )


def vault_from_dict(payload: Mapping[str, Any]) -> KnowledgeVault:
    """Parse a strict JSON fixture/persistence payload without accepting unknown fields."""
    _require_exact_keys(payload, {"notes", "relations"}, "vault")
    notes_value, relations_value = payload["notes"], payload["relations"]
    if not isinstance(notes_value, list) or not isinstance(relations_value, list):
        raise KnowledgeVaultError("vault notes and relations must be arrays")
    return KnowledgeVault(
        tuple(_note_from_dict(item) for item in notes_value),
        tuple(_relation_from_dict(item) for item in relations_value),
    )


def load_vault_fixture(path: Path) -> KnowledgeVault:
    """Load a local JSON fixture; this helper performs no network or stateful work."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KnowledgeVaultError(f"cannot load vault fixture: {path}") from exc
    if not isinstance(payload, dict):
        raise KnowledgeVaultError("vault fixture root must be an object")
    return vault_from_dict(payload)


def _note_from_dict(value: Any) -> KnowledgeNote:
    if not isinstance(value, dict):
        raise KnowledgeVaultError("note must be an object")
    expected_fields = {
        "id",
        "type",
        "vault",
        "status",
        "confidence",
        "title",
        "content",
        "version",
        "tags",
        "source_refs",
        "graph_refs",
        "campaign_id",
        "source_id",
        "created_at",
        "updated_at",
    }
    _require_exact_keys(value, expected_fields, "note")
    return KnowledgeNote(
        id=value["id"],
        type=value["type"],
        vault=value["vault"],
        status=value["status"],
        confidence=value["confidence"],
        title=value["title"],
        content=value["content"],
        version=value["version"],
        tags=tuple(value["tags"]),
        source_refs=tuple(_ref_from_dict(ref) for ref in value["source_refs"]),
        graph_refs=tuple(_graph_ref_from_dict(ref) for ref in value["graph_refs"]),
        campaign_id=value["campaign_id"],
        source_id=value["source_id"],
        created_at=value["created_at"],
        updated_at=value["updated_at"],
    )


def _relation_from_dict(value: Any) -> KnowledgeRelation:
    if not isinstance(value, dict):
        raise KnowledgeVaultError("relation must be an object")
    _require_exact_keys(value, {"source_id", "target_id", "relation", "provenance"}, "relation")
    return KnowledgeRelation(
        source_id=value["source_id"],
        target_id=value["target_id"],
        relation=value["relation"],
        provenance=tuple(_ref_from_dict(ref) for ref in value["provenance"]),
    )


def _ref_from_dict(value: Any) -> KnowledgeRef:
    if not isinstance(value, dict):
        raise KnowledgeVaultError("reference must be an object")
    _require_exact_keys(value, {"note_id", "role"}, "reference")
    return KnowledgeRef(note_id=value["note_id"], role=value["role"])


def _graph_ref_from_dict(value: Any) -> GraphEvidenceRef:
    if not isinstance(value, dict):
        raise KnowledgeVaultError("graph reference must be an object")
    _require_exact_keys(value, {"kind", "evidence_id"}, "graph reference")
    return GraphEvidenceRef(kind=value["kind"], evidence_id=value["evidence_id"])


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing, unknown = sorted(expected - actual), sorted(actual - expected)
        pieces = []
        if missing:
            pieces.append(f"missing: {', '.join(missing)}")
        if unknown:
            pieces.append(f"unsupported: {', '.join(unknown)}")
        raise KnowledgeVaultError(f"{label} fields invalid ({'; '.join(pieces)})")
