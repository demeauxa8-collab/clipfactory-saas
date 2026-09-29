"""Question-specific, deterministic retrieval for the local editorial Second Brain.

This module deliberately sits *before* ``build_editorial_context_pack``.  It
does not replace that guardrail and it has no model, embedding, database,
network, transcript, or rendering dependency.  Its job is narrower: given a
frozen snapshot and one validated editorial question, make a bounded and
auditable recommendation of complementary evidence roles.

The selector treats note text as untrusted data.  Scope is checked before any
title/content/tag is inspected, source evidence is bound to the exact question
graph evidence, and a contradictory pair of live hard constraints blocks the
result instead of letting a later prompt improvise a choice.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from .editorial_beats import EditorialBeatGraph, validate_editorial_beat_graph
from .editorial_context import EditorialQuestion, graph_digest, project_context_note
from .knowledge_ingestion import KnowledgeVaultSnapshot
from .knowledge_vault import ContextNote, KnowledgeNote, KnowledgeRelation


class EditorialRetrievalError(ValueError):
    """A retrieval input/result crosses an editorial trust boundary."""


RETRIEVAL_SCHEMA_VERSION = "1.0"
MAX_RETRIEVAL_JSON_CHARS = 4_800
MAX_SELECTION_REASON_CHARS = 180
MAX_RELATION_PATH_STEPS = 3
MAX_NOTE_CONTENT_CHARS = 180

EvidenceRole = Literal[
    "hard_constraint",
    "source_evidence",
    "campaign_goal",
    "campaign_objection_or_proof",
    "global_principle",
    "counterexample_or_risk",
]
RetrievalStatus = Literal["ready", "blocked"]
FindingKind = Literal["contradictory_hard_constraints"]

_ROLES = frozenset(EvidenceRole.__args__)
_ROLE_QUOTAS: tuple[tuple[EvidenceRole, int], ...] = (
    ("hard_constraint", 2),
    ("source_evidence", 3),
    ("campaign_goal", 1),
    ("campaign_objection_or_proof", 2),
    ("global_principle", 1),
    ("counterexample_or_risk", 1),
)
_MAX_TOTAL = sum(quota for _, quota in _ROLE_QUOTAS)
_TOKEN = re.compile(r"[a-z0-9]{2,}")
_URL = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_TIMING_OR_TRANSCRIPT = re.compile(
    r"(?:transcript|word_?id|source_(?:in|out)(?:_ms)?|\b\d{1,2}:\d{2}(?::\d{2})?\b)",
    re.IGNORECASE,
)
_RESEARCH_AUDIT_TAG = "research_source_audit"
_RESEARCH_FINDING_TAG = "research_finding"
_RESEARCH_CLAIM_REVIEW_TAG = "claim_requires_verification"
_SAFE_POLICY_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}$")
_HEX = re.compile(r"^[a-f0-9]{64}$")


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _tokens(value: str) -> frozenset[str]:
    return frozenset(_TOKEN.findall(value.casefold()))


def _safe_note_text(note: KnowledgeNote) -> bool:
    """Reject prompt-unsafe note text rather than trying to repair it silently."""
    values = (note.title, note.content, *note.tags)
    rendered = " ".join(values)
    return not (
        _URL.search(rendered) or _CONTROL.search(rendered) or _TIMING_OR_TRANSCRIPT.search(rendered)
    )


@dataclass(frozen=True)
class RetrievalPolicy:
    """Closed, versioned retrieval rules; quotas cannot be changed by a caller."""

    schema_version: str = RETRIEVAL_SCHEMA_VERSION
    role_quotas: tuple[tuple[EvidenceRole, int], ...] = _ROLE_QUOTAS
    max_total: int = _MAX_TOTAL

    def __post_init__(self) -> None:
        if self.schema_version != RETRIEVAL_SCHEMA_VERSION or not _SAFE_POLICY_VERSION.fullmatch(
            self.schema_version
        ):
            raise EditorialRetrievalError("retrieval policy schema_version is unsupported")
        if self.role_quotas != _ROLE_QUOTAS or self.max_total != _MAX_TOTAL:
            raise EditorialRetrievalError(
                "retrieval policy quotas are closed for this schema version"
            )

    @property
    def digest(self) -> str:
        return _digest(
            {
                "max_total": self.max_total,
                "role_quotas": list(self.role_quotas),
                "schema_version": self.schema_version,
            }
        )

    def quota_for(self, role: EvidenceRole) -> int:
        if role not in _ROLES:
            raise EditorialRetrievalError("unsupported retrieval role")
        return dict(self.role_quotas)[role]


@dataclass(frozen=True)
class RetrievalSelection:
    """A compact, prompt-safe recommendation plus its reproducible explanation."""

    role: EvidenceRole
    note: ContextNote
    score: int
    selection_reason: str
    relation_path: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.role not in _ROLES:
            raise EditorialRetrievalError("selection role is unsupported")
        if not isinstance(self.note, ContextNote):
            raise EditorialRetrievalError("selection note must be a ContextNote")
        rendered_note = " ".join((self.note.title, self.note.content))
        if (
            _URL.search(rendered_note)
            or _CONTROL.search(rendered_note)
            or _TIMING_OR_TRANSCRIPT.search(rendered_note)
        ):
            raise EditorialRetrievalError("selection note contains prompt-unsafe text")
        if isinstance(self.score, bool) or not isinstance(self.score, int) or self.score < 0:
            raise EditorialRetrievalError("selection score must be a non-negative integer")
        if (
            not isinstance(self.selection_reason, str)
            or not self.selection_reason.strip()
            or len(self.selection_reason) > MAX_SELECTION_REASON_CHARS
            or _URL.search(self.selection_reason)
            or _CONTROL.search(self.selection_reason)
        ):
            raise EditorialRetrievalError("selection_reason is invalid")
        if (
            not isinstance(self.relation_path, tuple)
            or len(self.relation_path) > MAX_RELATION_PATH_STEPS
            or any(
                not isinstance(step, str) or not step or _URL.search(step) or _CONTROL.search(step)
                for step in self.relation_path
            )
        ):
            raise EditorialRetrievalError("selection relation_path is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "note": self.note.to_payload(),
            "relation_path": list(self.relation_path),
            "role": self.role,
            "score": self.score,
            "selection_reason": self.selection_reason,
        }


@dataclass(frozen=True)
class RetrievalFinding:
    kind: FindingKind
    note_ids: tuple[str, str]
    relation_path: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        if self.kind != "contradictory_hard_constraints":
            raise EditorialRetrievalError("finding kind is unsupported")
        if (
            not isinstance(self.note_ids, tuple)
            or len(self.note_ids) != 2
            or len(set(self.note_ids)) != 2
            or any(not isinstance(item, str) or not item for item in self.note_ids)
        ):
            raise EditorialRetrievalError("finding must identify two different notes")
        if (
            not self.relation_path
            or len(self.relation_path) > MAX_RELATION_PATH_STEPS
            or any(_URL.search(step) or _CONTROL.search(step) for step in self.relation_path)
        ):
            raise EditorialRetrievalError("finding requires a bounded relation path")
        if (
            not isinstance(self.message, str)
            or not self.message.strip()
            or _URL.search(self.message)
            or _CONTROL.search(self.message)
        ):
            raise EditorialRetrievalError("finding message is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "message": self.message,
            "note_ids": list(self.note_ids),
            "relation_path": list(self.relation_path),
        }


@dataclass(frozen=True)
class RetrievalResult:
    """Bounded retrieval output. ``blocked`` outputs no candidate selections."""

    schema_version: str
    status: RetrievalStatus
    question_digest: str
    snapshot_digest: str
    graph_digest: str
    policy_digest: str
    selections: tuple[RetrievalSelection, ...]
    findings: tuple[RetrievalFinding, ...]
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != RETRIEVAL_SCHEMA_VERSION:
            raise EditorialRetrievalError("result schema_version is unsupported")
        if self.status not in {"ready", "blocked"}:
            raise EditorialRetrievalError("result status is unsupported")
        for label, value in (
            ("question_digest", self.question_digest),
            ("snapshot_digest", self.snapshot_digest),
            ("graph_digest", self.graph_digest),
            ("policy_digest", self.policy_digest),
        ):
            if not isinstance(value, str) or not _HEX.fullmatch(value):
                raise EditorialRetrievalError(f"{label} must be a SHA-256 digest")
        if not isinstance(self.selections, tuple) or not all(
            isinstance(item, RetrievalSelection) for item in self.selections
        ):
            raise EditorialRetrievalError("result selections are invalid")
        if not isinstance(self.findings, tuple) or not all(
            isinstance(item, RetrievalFinding) for item in self.findings
        ):
            raise EditorialRetrievalError("result findings are invalid")
        ids = tuple(item.note.note_id for item in self.selections)
        if len(ids) != len(set(ids)) or len(ids) > _MAX_TOTAL:
            raise EditorialRetrievalError("result cannot repeat or exceed evidence selections")
        counts = defaultdict(int)
        for item in self.selections:
            counts[item.role] += 1
        if any(counts[role] > quota for role, quota in _ROLE_QUOTAS):
            raise EditorialRetrievalError("result exceeded a closed role quota")
        if self.status == "blocked":
            if self.selections or not self.findings:
                raise EditorialRetrievalError(
                    "blocked result must contain findings and no selections"
                )
        elif self.findings:
            raise EditorialRetrievalError("ready result cannot contain unresolved findings")
        if self.status == "ready":
            roles = {item.role for item in self.selections}
            if "source_evidence" not in roles:
                raise EditorialRetrievalError("ready result requires source evidence")
            if not roles & {
                "hard_constraint",
                "campaign_goal",
                "campaign_objection_or_proof",
            }:
                raise EditorialRetrievalError("ready result requires campaign evidence")
            has_principle = "global_principle" in roles
            has_counter = "counterexample_or_risk" in roles
            if has_principle != has_counter:
                raise EditorialRetrievalError("global advice must be an atomic paired selection")
            if has_principle:
                pair_paths = [
                    item.relation_path
                    for item in self.selections
                    if item.role in {"global_principle", "counterexample_or_risk"}
                ]
                if len(pair_paths) != 2 or not pair_paths[0] or pair_paths[0] != pair_paths[1]:
                    raise EditorialRetrievalError(
                        "global advice requires one shared direct relation path"
                    )
        object.__setattr__(self, "result_digest", _digest(self._payload(include_digest=False)))
        if len(self.to_json()) > MAX_RETRIEVAL_JSON_CHARS:
            raise EditorialRetrievalError("retrieval JSON exceeds the hard limit")

    def _payload(self, *, include_digest: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "findings": [item.to_payload() for item in self.findings],
            "graph_digest": self.graph_digest,
            "policy_digest": self.policy_digest,
            "question_digest": self.question_digest,
            "schema_version": self.schema_version,
            "selections": [item.to_payload() for item in self.selections],
            "snapshot_digest": self.snapshot_digest,
            "status": self.status,
        }
        if include_digest:
            payload["result_digest"] = self.result_digest
        return payload

    def to_json(self) -> str:
        return json.dumps(
            self._payload(include_digest=True),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )


def editorial_question_digest(question: EditorialQuestion) -> str:
    """Return the canonical identity used to bind retrieval to one question."""
    if not isinstance(question, EditorialQuestion):
        raise EditorialRetrievalError("question must be an EditorialQuestion")
    return _digest(
        {
            "beat_ids": list(question.beat_ids),
            "campaign_id": question.campaign_id,
            "goal": question.goal,
            "hypothesis": question.hypothesis,
            "kind": question.kind,
            "source_id": question.source_id,
            "source_moment_ids": list(question.source_moment_ids),
        }
    )


def _validate_question_graph(
    question: EditorialQuestion, graph: EditorialBeatGraph
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    validate_editorial_beat_graph(graph)
    beats = {item.beat_id: item for item in graph.editorial_beats}
    moments = {item.moment_id for item in graph.source_moments}
    if not set(question.beat_ids).issubset(beats) or not set(question.source_moment_ids).issubset(
        moments
    ):
        raise EditorialRetrievalError("question references unknown graph evidence")
    if {beats[item].source_moment_id for item in question.beat_ids} != set(
        question.source_moment_ids
    ):
        raise EditorialRetrievalError("question beats and source moments must bind exactly")
    all_evidence = {
        "source_moment": moments,
        "visual_beat": {item.visual_id for item in graph.visual_beats},
        "audio_beat": {item.audio_id for item in graph.audio_beats},
    }
    selected = [beats[item] for item in question.beat_ids]
    relevant = {
        "source_moment": set(question.source_moment_ids),
        "visual_beat": {item for beat in selected for item in beat.visual_ids},
        "audio_beat": {item for beat in selected for item in beat.audio_ids},
    }
    return all_evidence, relevant


def _scope_visible(note: KnowledgeNote, question: EditorialQuestion) -> bool:
    """Only metadata is read here; must run before text scoring/filtering."""
    if note.vault == "global":
        return True
    if note.campaign_id != question.campaign_id:
        return False
    return note.vault == "campaign" or note.source_id == question.source_id


def _is_live(note: KnowledgeNote) -> bool:
    return note.status not in {"raw_source", "deprecated"}


def _is_active_research_finding(note: KnowledgeNote, snapshot: KnowledgeVaultSnapshot) -> bool:
    """Only the research component bound to this snapshot may reach retrieval.

    Historical research remains in the durable vault for audit and learning,
    but it cannot silently become current campaign evidence after the pack
    expires, is replaced, or was not requested for this context build.
    """
    return (
        _RESEARCH_FINDING_TAG in note.tags
        and note.id in snapshot.active_research_note_ids
        and snapshot.research_digest is not None
    )


def _is_hard_constraint(note: KnowledgeNote) -> bool:
    return note.vault == "campaign" and (
        "hard_constraint" in note.tags
        or "avoid" in note.tags
        or (note.type == "policy" and note.status in {"curated", "validated"})
    )


def _role_for(note: KnowledgeNote) -> EvidenceRole | None:
    if _is_hard_constraint(note):
        return "hard_constraint"
    if note.vault == "source":
        return "source_evidence"
    if note.vault == "campaign":
        if note.type in {"offer", "audience"} or "goal" in note.tags:
            return "campaign_goal"
        if note.type in {"objection", "proof", "claim", "observation", "hypothesis"}:
            return "campaign_objection_or_proof"
    return None


def _relation_paths(
    relations: Sequence[KnowledgeRelation], allowed_note_ids: frozenset[str]
) -> Mapping[str, tuple[str, ...]]:
    paths: dict[str, list[str]] = defaultdict(list)
    for edge in sorted(relations, key=lambda item: (item.source_id, item.target_id, item.relation)):
        if edge.source_id not in allowed_note_ids or edge.target_id not in allowed_note_ids:
            continue
        descriptor = f"{edge.source_id}--{edge.relation}-->{edge.target_id}"
        paths[edge.source_id].append(descriptor)
        paths[edge.target_id].append(descriptor)
    return {key: tuple(value[:MAX_RELATION_PATH_STEPS]) for key, value in paths.items()}


def _score(
    note: KnowledgeNote, query_tokens: frozenset[str], relation_count: int
) -> tuple[int, int, int, int]:
    title = _tokens(note.title)
    tags = frozenset(token for tag in note.tags for token in _tokens(tag))
    content = _tokens(note.content)
    title_score = 6 * len(query_tokens & title)
    tag_score = 4 * len(query_tokens & tags)
    content_score = len(query_tokens & content)
    relation_score = min(relation_count, MAX_RELATION_PATH_STEPS)
    return (
        title_score + tag_score + content_score + relation_score,
        title_score,
        tag_score,
        relation_score,
    )


def _global_pair(
    notes: Sequence[KnowledgeNote],
    relations: Sequence[KnowledgeRelation],
    query_tokens: frozenset[str],
) -> tuple[tuple[KnowledgeNote, KnowledgeNote, str], ...]:
    by_id = {note.id: note for note in notes}
    pairs: list[tuple[int, str, str, KnowledgeNote, KnowledgeNote, str]] = []
    for edge in relations:
        if edge.relation not in {"contradicts", "risks"}:
            continue
        left, right = by_id.get(edge.source_id), by_id.get(edge.target_id)
        if left is None or right is None:
            continue
        # The counterexample/problem must explicitly point at the principle.
        # Treating the reverse edge as equivalent would manufacture a positive
        # pair from an unrelated principle that merely happens to mention risk.
        counter, principle = left, right
        if (
            counter.vault == principle.vault == "global"
            and counter.type in {"counterexample", "problem"}
            and principle.type in {"principle", "pattern"}
            and counter.status in {"validated", "curated"}
            and principle.status in {"validated", "curated"}
        ):
            score = _score(principle, query_tokens, 1)[0] + _score(counter, query_tokens, 1)[0]
            path = f"{edge.source_id}--{edge.relation}-->{edge.target_id}"
            pairs.append((score, principle.id, counter.id, principle, counter, path))
    pairs.sort(key=lambda item: (-item[0], item[1], item[2]))
    return tuple((item[3], item[4], item[5]) for item in pairs)


def _contradictions(
    constraints: Sequence[KnowledgeNote], relations: Sequence[KnowledgeRelation]
) -> tuple[RetrievalFinding, ...]:
    ids = {note.id for note in constraints}
    findings = []
    for edge in sorted(relations, key=lambda item: (item.source_id, item.target_id, item.relation)):
        # ``risks`` is directional caution, not proof that two policies are
        # logically incompatible.  Only an explicit contradiction may stop
        # the whole retrieval result.
        if edge.relation == "contradicts" and {edge.source_id, edge.target_id} <= ids:
            pair = tuple(sorted((edge.source_id, edge.target_id)))
            findings.append(
                RetrievalFinding(
                    "contradictory_hard_constraints",
                    pair,  # type: ignore[arg-type]
                    (f"{edge.source_id}--{edge.relation}-->{edge.target_id}",),
                    "Live campaign hard constraints conflict; editorial retrieval is blocked.",
                )
            )
    return tuple(findings)


def retrieve_editorial_evidence(
    question: EditorialQuestion,
    graph: EditorialBeatGraph,
    snapshot: KnowledgeVaultSnapshot,
    policy: RetrievalPolicy,
) -> RetrievalResult:
    """Retrieve scoped, explainable evidence without constructing a Director context.

    ``snapshot`` makes retrieval replayable: if it is graph-bound, a changed
    graph is rejected before notes are examined.  The result is a candidate
    list for a later context builder, not a permission to make an edit.
    """
    if not isinstance(question, EditorialQuestion):
        raise EditorialRetrievalError("question must be an EditorialQuestion")
    if not isinstance(snapshot, KnowledgeVaultSnapshot):
        raise EditorialRetrievalError("snapshot must be a KnowledgeVaultSnapshot")
    if not isinstance(policy, RetrievalPolicy):
        raise EditorialRetrievalError("policy must be a RetrievalPolicy")
    all_evidence, relevant_evidence = _validate_question_graph(question, graph)
    actual_graph_digest = graph_digest(graph)
    if snapshot.campaign_id != question.campaign_id or snapshot.source_id != question.source_id:
        raise EditorialRetrievalError("question scope does not match frozen snapshot")
    if snapshot.graph_digest is not None and snapshot.graph_digest != actual_graph_digest:
        raise EditorialRetrievalError("snapshot graph digest is stale for this question")

    # Scope is authorised before any caller-controlled title/content/tag is read.
    visible = [note for note in snapshot.vault.notes if _scope_visible(note, question)]
    active = [note for note in visible if _is_live(note)]
    for note in active:
        if note.vault != "source":
            continue
        for ref in note.graph_refs:
            if ref.evidence_id not in all_evidence[ref.kind]:
                raise EditorialRetrievalError("active source note contains stale graph evidence")

    safe_active_ids = frozenset(
        note.id
        for note in active
        if _RESEARCH_AUDIT_TAG not in note.tags
        and (_RESEARCH_FINDING_TAG not in note.tags or _is_active_research_finding(note, snapshot))
        and _safe_note_text(note)
    )
    relation_paths = _relation_paths(snapshot.vault.relations, safe_active_ids)
    query_tokens = _tokens(" ".join((question.kind, question.goal, question.hypothesis or "")))
    if not query_tokens:
        raise EditorialRetrievalError("question contains no lexical retrieval tokens")

    # A malformed hard constraint is not eligible for a prompt, but it must
    # still participate in a contradiction check: a hostile note cannot be a
    # route around the fail-closed editorial policy.
    hard_constraints = [
        note
        for note in active
        if _is_hard_constraint(note)
        and _RESEARCH_AUDIT_TAG not in note.tags
        and (_RESEARCH_FINDING_TAG not in note.tags or _is_active_research_finding(note, snapshot))
    ]
    findings = _contradictions(hard_constraints, snapshot.vault.relations)
    question_hash = editorial_question_digest(question)
    if findings:
        return RetrievalResult(
            RETRIEVAL_SCHEMA_VERSION,
            "blocked",
            question_hash,
            snapshot.digest,
            actual_graph_digest,
            policy.digest,
            (),
            findings,
        )

    candidates: dict[EvidenceRole, list[KnowledgeNote]] = defaultdict(list)
    for note in active:
        # The audit source material proves research provenance but must not be a director input.
        if (
            _RESEARCH_AUDIT_TAG in note.tags
            or _RESEARCH_CLAIM_REVIEW_TAG in note.tags
            or (
                _RESEARCH_FINDING_TAG in note.tags
                and not _is_active_research_finding(note, snapshot)
            )
            or not _safe_note_text(note)
        ):
            continue
        if note.vault == "source":
            if not note.graph_refs or not all(
                ref.evidence_id in relevant_evidence[ref.kind] for ref in note.graph_refs
            ):
                continue
        role = _role_for(note)
        if role is not None:
            candidates[role].append(note)

    selections: list[RetrievalSelection] = []
    selected_ids: set[str] = set()

    def choose(role: EvidenceRole, notes: Sequence[KnowledgeNote]) -> None:
        quota = policy.quota_for(role)
        ranked = []
        for note in notes:
            if note.id in selected_ids:
                continue
            score, lexical, tags, relation_score = _score(
                note, query_tokens, len(relation_paths.get(note.id, ()))
            )
            ranked.append((-score, note.id, note, lexical, tags, relation_score))
        for negated, _note_id, note, lexical, tags, relation_score in sorted(ranked)[:quota]:
            score = -negated
            reason = (
                f"role={role}; lexical={lexical}; tag_match={tags}; "
                f"relation_bonus={relation_score}; deterministic_id_tiebreak"
            )
            selections.append(
                RetrievalSelection(
                    role,
                    project_context_note(note),
                    score,
                    reason,
                    relation_paths.get(note.id, ()),
                )
            )
            selected_ids.add(note.id)

    choose("hard_constraint", candidates["hard_constraint"])
    choose("source_evidence", candidates["source_evidence"])
    choose("campaign_goal", candidates["campaign_goal"])
    choose("campaign_objection_or_proof", candidates["campaign_objection_or_proof"])

    # Global advice is atomic.  No disconnected positive/counterexample is ever selected.
    for principle, counter, path in _global_pair(active, snapshot.vault.relations, query_tokens):
        if principle.id in selected_ids or counter.id in selected_ids:
            continue
        p_score = _score(principle, query_tokens, 1)[0]
        c_score = _score(counter, query_tokens, 1)[0]
        selections.extend(
            (
                RetrievalSelection(
                    "global_principle",
                    project_context_note(principle),
                    p_score,
                    "role=global_principle; validated paired advice; direct risk relation",
                    (path,),
                ),
                RetrievalSelection(
                    "counterexample_or_risk",
                    project_context_note(counter),
                    c_score,
                    "role=counterexample_or_risk; validated paired advice; direct risk relation",
                    (path,),
                ),
            )
        )
        selected_ids.update((principle.id, counter.id))
        break

    if not any(item.role == "source_evidence" for item in selections):
        raise EditorialRetrievalError(
            "no authorised source evidence matches the exact question graph"
        )
    if not any(
        item.role in {"hard_constraint", "campaign_goal", "campaign_objection_or_proof"}
        for item in selections
    ):
        raise EditorialRetrievalError("no authorised campaign evidence matches the question")
    return RetrievalResult(
        RETRIEVAL_SCHEMA_VERSION,
        "ready",
        question_hash,
        snapshot.digest,
        actual_graph_digest,
        policy.digest,
        tuple(selections),
        (),
    )
