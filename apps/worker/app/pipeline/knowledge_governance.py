"""Append-only governance for data-derived editorial knowledge.

The vault stores useful notes; this module governs what those notes are allowed
to become.  It deliberately keeps epistemic kind, human review, and lifecycle
on separate axes.  No transition mutates an existing state, and an outcome can
never promote knowledge without a reviewed learning evaluation and the
fail-closed promotion result from :mod:`decision_outcomes`.

This first contract governs campaign/source learnings.  Manually curated global
editing principles use a separate editorial-review workflow and must not be
misrepresented as performance-derived policies here.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, TypeAlias

from .decision_outcomes import LearningEvaluation, PromotionEligibility
from .learning_authority import (
    AuthorityVerifier,
    LearningAuthorityError,
    PromotionAuthorityEnvelope,
    verify_promotion_authority,
)

GOVERNANCE_SCHEMA_VERSION = "1.0"

EpistemicKind: TypeAlias = Literal["raw_source", "observation", "hypothesis", "learning", "policy"]
ReviewState: TypeAlias = Literal["unreviewed", "approved", "rejected"]
LifecycleState: TypeAlias = Literal["active", "superseded", "deprecated"]
GovernanceScope: TypeAlias = Literal["global", "campaign", "source"]
TransitionKind: TypeAlias = Literal[
    "capture_observation",
    "propose_hypothesis",
    "validate_learning",
    "promote_policy",
    "deprecate",
    "supersede",
]

_EPISTEMIC_KINDS = frozenset({"raw_source", "observation", "hypothesis", "learning", "policy"})
_REVIEW_STATES = frozenset({"unreviewed", "approved", "rejected"})
_LIFECYCLE_STATES = frozenset({"active", "superseded", "deprecated"})
_SCOPES = frozenset({"global", "campaign", "source"})
_TRANSITIONS = frozenset(
    {
        "capture_observation",
        "propose_hypothesis",
        "validate_learning",
        "promote_policy",
        "deprecate",
        "supersede",
    }
)
_NEXT_KIND: dict[str, tuple[str, str]] = {
    "capture_observation": ("raw_source", "observation"),
    "propose_hypothesis": ("observation", "hypothesis"),
    "validate_learning": ("hypothesis", "learning"),
    "promote_policy": ("learning", "policy"),
}
_NOTE_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_DIGEST_RE = re.compile(r"^[a-f0-9]{64}$")
_MAX_NOTE_ID = 80
_MAX_RATIONALE = 800
_MAX_REFS = 64


class KnowledgeGovernanceError(ValueError):
    """A requested knowledge transition is unsafe or internally incoherent."""


def _text(value: object, label: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise KnowledgeGovernanceError(f"{label} must be a string")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        raise KnowledgeGovernanceError(f"{label} cannot be empty")
    if len(normalized) > maximum:
        raise KnowledgeGovernanceError(f"{label} exceeds {maximum} characters")
    return normalized


def _note_id(value: object, label: str = "note_id") -> str:
    value = _text(value, label, maximum=_MAX_NOTE_ID)
    if not _NOTE_ID_RE.fullmatch(value):
        raise KnowledgeGovernanceError(f"{label} must be a safe snake_case note ID")
    return value


def _opaque_id(value: object, label: str) -> str:
    value = _text(value, label, maximum=128)
    if not _OPAQUE_ID_RE.fullmatch(value):
        raise KnowledgeGovernanceError(f"{label} must be a bounded opaque ID")
    return value


def _version(value: object, label: str) -> str:
    value = _text(value, label, maximum=64)
    if not _VERSION_RE.fullmatch(value):
        raise KnowledgeGovernanceError(f"{label} is invalid")
    return value


def _digest(value: object, label: str) -> str:
    value = _text(value, label, maximum=64).lower()
    if not _DIGEST_RE.fullmatch(value):
        raise KnowledgeGovernanceError(f"{label} must be a SHA-256 hex digest")
    return value


def _instant(value: object, label: str) -> str:
    value = _text(value, label, maximum=40)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise KnowledgeGovernanceError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise KnowledgeGovernanceError(f"{label} must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _digests(values: object, label: str, *, required: bool = False) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise KnowledgeGovernanceError(f"{label} must be a tuple")
    if len(values) > _MAX_REFS:
        raise KnowledgeGovernanceError(f"{label} exceeds {_MAX_REFS} references")
    normalized = tuple(sorted(_digest(value, label) for value in values))
    if len(normalized) != len(set(normalized)):
        raise KnowledgeGovernanceError(f"{label} cannot repeat a digest")
    if required and not normalized:
        raise KnowledgeGovernanceError(f"{label} cannot be empty")
    return normalized


def _canonical_json(payload: dict[str, object]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _canonical_digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class KnowledgeVersionRef:
    note_id: str
    version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "note_id", _note_id(self.note_id))
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise KnowledgeGovernanceError("version must be a positive integer")

    def to_payload(self) -> dict[str, object]:
        return {"note_id": self.note_id, "version": self.version}


@dataclass(frozen=True)
class KnowledgeGovernanceState:
    """One immutable governance snapshot for one exact note version."""

    schema_version: Literal["1.0"]
    note: KnowledgeVersionRef
    epistemic_kind: EpistemicKind
    review_state: ReviewState
    reviewed_by: str | None
    lifecycle: LifecycleState
    scope: GovernanceScope
    owner_id: str
    campaign_id: str | None
    source_id: str | None
    evidence_digests: tuple[str, ...]
    counterexample_digests: tuple[str, ...]
    evaluation_digest: str | None
    policy_version: str | None
    created_at: str
    expires_at: str | None = None
    superseded_by: KnowledgeVersionRef | None = None

    def __post_init__(self) -> None:
        if self.schema_version != GOVERNANCE_SCHEMA_VERSION:
            raise KnowledgeGovernanceError("unsupported governance schema version")
        if not isinstance(self.note, KnowledgeVersionRef):
            raise KnowledgeGovernanceError("note must be a KnowledgeVersionRef")
        if self.epistemic_kind not in _EPISTEMIC_KINDS:
            raise KnowledgeGovernanceError("unsupported epistemic kind")
        if self.review_state not in _REVIEW_STATES:
            raise KnowledgeGovernanceError("unsupported review state")
        if self.reviewed_by is not None:
            object.__setattr__(self, "reviewed_by", _opaque_id(self.reviewed_by, "reviewed_by"))
        if self.review_state in {"approved", "rejected"} and self.reviewed_by is None:
            raise KnowledgeGovernanceError(f"{self.review_state} review requires reviewed_by")
        if self.review_state == "unreviewed" and self.reviewed_by is not None:
            raise KnowledgeGovernanceError("unreviewed state cannot carry reviewed_by")
        if self.lifecycle not in _LIFECYCLE_STATES:
            raise KnowledgeGovernanceError("unsupported lifecycle state")
        if self.scope not in _SCOPES:
            raise KnowledgeGovernanceError("unsupported governance scope")
        object.__setattr__(self, "owner_id", _opaque_id(self.owner_id, "owner_id"))
        self._validate_scope()
        object.__setattr__(
            self,
            "evidence_digests",
            _digests(self.evidence_digests, "evidence_digests"),
        )
        object.__setattr__(
            self,
            "counterexample_digests",
            _digests(self.counterexample_digests, "counterexample_digests"),
        )
        if set(self.evidence_digests) & set(self.counterexample_digests):
            raise KnowledgeGovernanceError("evidence and counterexample namespaces cannot overlap")
        if self.evaluation_digest is not None:
            object.__setattr__(
                self,
                "evaluation_digest",
                _digest(self.evaluation_digest, "evaluation_digest"),
            )
        if self.policy_version is not None:
            object.__setattr__(
                self,
                "policy_version",
                _version(self.policy_version, "policy_version"),
            )
        object.__setattr__(self, "created_at", _instant(self.created_at, "created_at"))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", _instant(self.expires_at, "expires_at"))
            if self.lifecycle == "active" and _as_datetime(self.expires_at) <= _as_datetime(
                self.created_at
            ):
                raise KnowledgeGovernanceError("expires_at must be after created_at")
        self._validate_lifecycle()
        self._validate_epistemic_contract()

    def _validate_scope(self) -> None:
        if self.scope == "global":
            if self.campaign_id is not None or self.source_id is not None:
                raise KnowledgeGovernanceError("global governance cannot carry campaign/source IDs")
            return
        if self.campaign_id is None:
            raise KnowledgeGovernanceError(f"{self.scope} governance requires campaign_id")
        object.__setattr__(self, "campaign_id", _opaque_id(self.campaign_id, "campaign_id"))
        if self.scope == "campaign":
            if self.source_id is not None:
                raise KnowledgeGovernanceError("campaign governance cannot carry source_id")
            return
        if self.source_id is None:
            raise KnowledgeGovernanceError("source governance requires source_id")
        object.__setattr__(self, "source_id", _opaque_id(self.source_id, "source_id"))

    def _validate_lifecycle(self) -> None:
        if self.lifecycle == "active" and self.superseded_by is not None:
            raise KnowledgeGovernanceError("active state cannot have superseded_by")
        if self.lifecycle == "superseded":
            if not isinstance(self.superseded_by, KnowledgeVersionRef):
                raise KnowledgeGovernanceError("superseded state requires superseded_by")
            if self.superseded_by.note_id != self.note.note_id:
                raise KnowledgeGovernanceError("supersession must remain on the same note ID")
            if self.superseded_by.version <= self.note.version:
                raise KnowledgeGovernanceError("superseded_by must reference a newer version")
        elif self.superseded_by is not None:
            raise KnowledgeGovernanceError("only a superseded state can carry superseded_by")

    def _validate_epistemic_contract(self) -> None:
        if self.lifecycle != "active":
            return
        if self.epistemic_kind in {"hypothesis", "learning", "policy"}:
            if self.review_state != "approved" or self.reviewed_by is None:
                raise KnowledgeGovernanceError(
                    f"active {self.epistemic_kind} requires an approved human review"
                )
            if not self.evidence_digests:
                raise KnowledgeGovernanceError(
                    f"active {self.epistemic_kind} requires supporting evidence"
                )
            if self.expires_at is None:
                raise KnowledgeGovernanceError(f"active {self.epistemic_kind} requires expires_at")
        if (
            self.epistemic_kind in {"hypothesis", "learning", "policy"}
            and not self.counterexample_digests
        ):
            raise KnowledgeGovernanceError(
                f"active {self.epistemic_kind} requires counterexample evidence"
            )
        if self.epistemic_kind in {"learning", "policy"}:
            if self.evaluation_digest is None:
                raise KnowledgeGovernanceError(
                    f"active {self.epistemic_kind} requires approved evaluation"
                )
        if self.epistemic_kind == "policy":
            if self.policy_version is None or len(self.evidence_digests) < 2:
                raise KnowledgeGovernanceError(
                    "active policy requires policy_version and at least two evidence digests"
                )
        elif self.policy_version is not None:
            raise KnowledgeGovernanceError("only policy knowledge can have policy_version")

    def to_payload(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "counterexample_digests": list(self.counterexample_digests),
            "created_at": self.created_at,
            "epistemic_kind": self.epistemic_kind,
            "evaluation_digest": self.evaluation_digest,
            "evidence_digests": list(self.evidence_digests),
            "expires_at": self.expires_at,
            "lifecycle": self.lifecycle,
            "note": self.note.to_payload(),
            "owner_id": self.owner_id,
            "policy_version": self.policy_version,
            "review_state": self.review_state,
            "reviewed_by": self.reviewed_by,
            "schema_version": self.schema_version,
            "scope": self.scope,
            "source_id": self.source_id,
            "superseded_by": self.superseded_by.to_payload() if self.superseded_by else None,
        }

    @property
    def canonical_digest(self) -> str:
        return _canonical_digest(self.to_payload())


@dataclass(frozen=True)
class GovernanceTransitionRequest:
    transition_id: str
    transition: TransitionKind
    requested_by: str
    rationale: str
    evidence_digests: tuple[str, ...] = ()
    counterexample_digests: tuple[str, ...] = ()
    expires_at: str | None = None
    policy_version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "transition_id", _opaque_id(self.transition_id, "transition_id"))
        if self.transition not in _TRANSITIONS:
            raise KnowledgeGovernanceError("unsupported transition")
        object.__setattr__(self, "requested_by", _opaque_id(self.requested_by, "requested_by"))
        object.__setattr__(
            self,
            "rationale",
            _text(self.rationale, "rationale", maximum=_MAX_RATIONALE),
        )
        object.__setattr__(
            self,
            "evidence_digests",
            _digests(self.evidence_digests, "transition evidence_digests"),
        )
        object.__setattr__(
            self,
            "counterexample_digests",
            _digests(
                self.counterexample_digests,
                "transition counterexample_digests",
            ),
        )
        if set(self.evidence_digests) & set(self.counterexample_digests):
            raise KnowledgeGovernanceError("transition evidence and counterexamples cannot overlap")
        if self.expires_at is not None:
            object.__setattr__(
                self, "expires_at", _instant(self.expires_at, "transition expires_at")
            )
        if self.policy_version is not None:
            object.__setattr__(
                self,
                "policy_version",
                _version(self.policy_version, "transition policy_version"),
            )


@dataclass(frozen=True)
class GovernanceTransitionEvent:
    transition_id: str
    transition: TransitionKind
    from_state_digest: str
    to_state_digest: str
    note_id: str
    from_version: int
    to_version: int
    requested_by: str
    reviewed_by: str | None
    occurred_at: str
    rationale: str
    authority_digest: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "transition_id", _opaque_id(self.transition_id, "transition_id"))
        if self.transition not in _TRANSITIONS:
            raise KnowledgeGovernanceError("unsupported event transition")
        object.__setattr__(
            self,
            "from_state_digest",
            _digest(self.from_state_digest, "from_state_digest"),
        )
        object.__setattr__(
            self, "to_state_digest", _digest(self.to_state_digest, "to_state_digest")
        )
        object.__setattr__(self, "note_id", _note_id(self.note_id))
        if (
            isinstance(self.from_version, bool)
            or not isinstance(self.from_version, int)
            or isinstance(self.to_version, bool)
            or not isinstance(self.to_version, int)
            or self.from_version < 1
            or self.to_version <= self.from_version
        ):
            raise KnowledgeGovernanceError("event versions must advance monotonically")
        object.__setattr__(self, "requested_by", _opaque_id(self.requested_by, "requested_by"))
        if self.reviewed_by is not None:
            object.__setattr__(self, "reviewed_by", _opaque_id(self.reviewed_by, "reviewed_by"))
        object.__setattr__(self, "occurred_at", _instant(self.occurred_at, "occurred_at"))
        object.__setattr__(
            self,
            "rationale",
            _text(self.rationale, "rationale", maximum=_MAX_RATIONALE),
        )
        if self.transition == "promote_policy":
            if self.authority_digest is None:
                raise KnowledgeGovernanceError(
                    "policy promotion event requires an authority digest"
                )
            object.__setattr__(
                self,
                "authority_digest",
                _digest(self.authority_digest, "authority_digest"),
            )
        elif self.authority_digest is not None:
            raise KnowledgeGovernanceError(
                "only a policy promotion event can carry an authority digest"
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "authority_digest": self.authority_digest,
            "from_state_digest": self.from_state_digest,
            "from_version": self.from_version,
            "note_id": self.note_id,
            "occurred_at": self.occurred_at,
            "rationale": self.rationale,
            "requested_by": self.requested_by,
            "reviewed_by": self.reviewed_by,
            "to_state_digest": self.to_state_digest,
            "to_version": self.to_version,
            "transition": self.transition,
            "transition_id": self.transition_id,
        }

    @property
    def canonical_digest(self) -> str:
        return _canonical_digest(self.to_payload())


@dataclass(frozen=True)
class GovernanceTransitionResult:
    previous: KnowledgeGovernanceState
    current: KnowledgeGovernanceState
    event: GovernanceTransitionEvent
    replacement: KnowledgeGovernanceState | None = None


def _reviewer(value: str | None, label: str = "reviewed_by") -> str:
    if value is None:
        raise KnowledgeGovernanceError(f"{label} is required")
    return _opaque_id(value, label)


def _merged_digests(current: tuple[str, ...], additions: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(current) | set(additions)))


def _verified_policy_promotion(
    current: KnowledgeGovernanceState,
    *,
    authority: PromotionAuthorityEnvelope | None,
    verifier: AuthorityVerifier | None,
    tenant_id: str | None,
    occurred_at: str,
) -> PromotionEligibility:
    """Return promotion eligibility only after verifying its signed authority.

    ``PromotionEligibility`` is deliberately a public value object, so it is
    never authority on its own.  Governance verifies the complete signed
    envelope at the exact transition time and binds it to this learning note's
    campaign and reviewed evaluation.  ``learning_authority`` depends only on
    outcome contracts, keeping this one-way import free of a governance cycle.
    """

    if not isinstance(authority, PromotionAuthorityEnvelope):
        raise KnowledgeGovernanceError(
            "policy promotion requires a verified PromotionAuthorityEnvelope"
        )
    if not isinstance(verifier, AuthorityVerifier):
        raise KnowledgeGovernanceError("policy promotion requires an AuthorityVerifier")
    if tenant_id is None:
        raise KnowledgeGovernanceError("policy promotion requires tenant_id for authority scope")
    if current.campaign_id is None:
        # The global case is rejected by the caller first; this is a defensive
        # invariant so a future scope cannot accidentally verify unbound proof.
        raise KnowledgeGovernanceError("policy promotion requires a campaign-scoped learning")
    try:
        verified = verify_promotion_authority(
            authority,
            verifier,
            tenant_id=tenant_id,
            campaign_id=current.campaign_id,
            now=_as_datetime(occurred_at),
        )
    except LearningAuthorityError as exc:
        raise KnowledgeGovernanceError("policy promotion authority is invalid") from exc
    if verified.hypothesis.hypothesis_id != current.note.note_id:
        raise KnowledgeGovernanceError("policy authority does not target this learning note")
    if verified.evaluation.canonical_digest != current.evaluation_digest:
        raise KnowledgeGovernanceError("policy authority evaluation does not match this learning")
    return verified.eligibility


def apply_governance_transition(
    current: KnowledgeGovernanceState,
    request: GovernanceTransitionRequest,
    *,
    occurred_at: str,
    reviewed_by: str | None = None,
    evaluation: LearningEvaluation | None = None,
    promotion: PromotionEligibility | None = None,
    promotion_authority: PromotionAuthorityEnvelope | None = None,
    authority_verifier: AuthorityVerifier | None = None,
    tenant_id: str | None = None,
) -> GovernanceTransitionResult:
    """Apply one legal append-only transition and return a new version plus event.

    A ``promote_policy`` request must carry a signed authority envelope plus a
    trusted verifier and tenant scope.  The legacy ``promotion`` value remains
    accepted only as an optional consistency assertion; it can never authorize
    a policy transition by itself.
    """

    if not isinstance(current, KnowledgeGovernanceState):
        raise KnowledgeGovernanceError("current must be a KnowledgeGovernanceState")
    if not isinstance(request, GovernanceTransitionRequest):
        raise KnowledgeGovernanceError("request must be a GovernanceTransitionRequest")
    if current.lifecycle != "active":
        raise KnowledgeGovernanceError("only active knowledge can transition")
    occurred_at = _instant(occurred_at, "occurred_at")
    if _as_datetime(occurred_at) < _as_datetime(current.created_at):
        raise KnowledgeGovernanceError("transition cannot precede current state")

    if request.transition in {"deprecate", "supersede"}:
        raise KnowledgeGovernanceError(
            f"use the dedicated {request.transition}_governance_state function"
        )
    if current.expires_at is not None and _as_datetime(occurred_at) >= _as_datetime(
        current.expires_at
    ):
        raise KnowledgeGovernanceError("expired knowledge cannot be promoted or advanced")
    expected = _NEXT_KIND.get(request.transition)
    if expected is None or expected[0] != current.epistemic_kind:
        raise KnowledgeGovernanceError(
            f"illegal transition {current.epistemic_kind} -> {request.transition}"
        )
    reviewer = None
    if request.transition != "capture_observation":
        reviewer = _reviewer(reviewed_by)

    evidence = _merged_digests(current.evidence_digests, request.evidence_digests)
    counterexamples = _merged_digests(
        current.counterexample_digests, request.counterexample_digests
    )
    target_kind = expected[1]
    evaluation_digest = current.evaluation_digest
    policy_version = None

    if target_kind == "hypothesis":
        if not evidence or not counterexamples or request.expires_at is None:
            raise KnowledgeGovernanceError(
                "hypothesis requires evidence, counterexample, and expiry"
            )
    elif target_kind == "learning":
        if not isinstance(evaluation, LearningEvaluation):
            raise KnowledgeGovernanceError("learning requires a LearningEvaluation")
        if evaluation.hypothesis_id != current.note.note_id:
            raise KnowledgeGovernanceError("evaluation does not target this hypothesis note")
        if evaluation.verdict != "supported" or evaluation.confounders:
            raise KnowledgeGovernanceError(
                "learning evaluation must be supported and free of declared confounders"
            )
        if reviewer != evaluation.reviewer:
            raise KnowledgeGovernanceError("learning reviewer must match evaluation reviewer")
        if _as_datetime(evaluation.evaluated_at) > _as_datetime(occurred_at):
            raise KnowledgeGovernanceError("evaluation cannot occur after transition")
        evaluation_digest = evaluation.canonical_digest
        if request.expires_at is None:
            raise KnowledgeGovernanceError("learning requires expiry")
    elif target_kind == "policy":
        if current.scope == "global":
            raise KnowledgeGovernanceError(
                "data-derived knowledge cannot be promoted into global policy"
            )
        verified_promotion = _verified_policy_promotion(
            current,
            authority=promotion_authority,
            verifier=authority_verifier,
            tenant_id=tenant_id,
            occurred_at=occurred_at,
        )
        if promotion is not None and (
            not isinstance(promotion, PromotionEligibility)
            or promotion.to_dict() != verified_promotion.to_dict()
        ):
            raise KnowledgeGovernanceError(
                "caller-supplied PromotionEligibility does not match verified authority"
            )
        if not verified_promotion.eligible:
            # ``verify_promotion_authority`` already enforces this, but retain
            # the invariant at the policy boundary.
            raise KnowledgeGovernanceError("verified policy promotion is not eligible")
        if reviewer != verified_promotion.human_reviewer:
            raise KnowledgeGovernanceError("policy reviewer must match promotion reviewer")
        if (
            request.policy_version is None
            or request.policy_version != verified_promotion.policy_version
            or request.expires_at is None
            or request.expires_at != verified_promotion.policy_expires_at
        ):
            raise KnowledgeGovernanceError(
                "policy version/expiry must match the reviewed promotion"
            )
        if len(evidence) < 2 or not counterexamples:
            raise KnowledgeGovernanceError(
                "policy requires two evidence digests and a counterexample"
            )
        policy_version = request.policy_version

    next_state = KnowledgeGovernanceState(
        schema_version=GOVERNANCE_SCHEMA_VERSION,
        note=KnowledgeVersionRef(current.note.note_id, current.note.version + 1),
        epistemic_kind=target_kind,  # type: ignore[arg-type]
        review_state="approved" if reviewer else "unreviewed",
        reviewed_by=reviewer,
        lifecycle="active",
        scope=current.scope,
        owner_id=current.owner_id,
        campaign_id=current.campaign_id,
        source_id=current.source_id,
        evidence_digests=evidence,
        counterexample_digests=counterexamples,
        evaluation_digest=evaluation_digest,
        policy_version=policy_version,
        created_at=occurred_at,
        expires_at=request.expires_at,
    )
    event = GovernanceTransitionEvent(
        transition_id=request.transition_id,
        transition=request.transition,
        from_state_digest=current.canonical_digest,
        to_state_digest=next_state.canonical_digest,
        note_id=current.note.note_id,
        from_version=current.note.version,
        to_version=next_state.note.version,
        requested_by=request.requested_by,
        reviewed_by=reviewer,
        occurred_at=occurred_at,
        rationale=request.rationale,
        authority_digest=(
            _canonical_digest(promotion_authority.to_dict())
            if request.transition == "promote_policy" and promotion_authority is not None
            else None
        ),
    )
    return GovernanceTransitionResult(current, next_state, event)


def deprecate_governance_state(
    current: KnowledgeGovernanceState,
    *,
    transition_id: str,
    requested_by: str,
    reviewed_by: str,
    rationale: str,
    occurred_at: str,
) -> GovernanceTransitionResult:
    """Append a deprecated version without deleting historical knowledge."""

    if current.lifecycle != "active":
        raise KnowledgeGovernanceError("only active knowledge can be deprecated")
    occurred_at = _instant(occurred_at, "occurred_at")
    reviewer = _reviewer(reviewed_by)
    next_state = KnowledgeGovernanceState(
        schema_version=GOVERNANCE_SCHEMA_VERSION,
        note=KnowledgeVersionRef(current.note.note_id, current.note.version + 1),
        epistemic_kind=current.epistemic_kind,
        review_state="approved",
        reviewed_by=reviewer,
        lifecycle="deprecated",
        scope=current.scope,
        owner_id=current.owner_id,
        campaign_id=current.campaign_id,
        source_id=current.source_id,
        evidence_digests=current.evidence_digests,
        counterexample_digests=current.counterexample_digests,
        evaluation_digest=current.evaluation_digest,
        policy_version=current.policy_version,
        created_at=occurred_at,
        expires_at=current.expires_at,
    )
    request = GovernanceTransitionRequest(
        transition_id=transition_id,
        transition="deprecate",
        requested_by=requested_by,
        rationale=rationale,
    )
    event = GovernanceTransitionEvent(
        transition_id=request.transition_id,
        transition="deprecate",
        from_state_digest=current.canonical_digest,
        to_state_digest=next_state.canonical_digest,
        note_id=current.note.note_id,
        from_version=current.note.version,
        to_version=next_state.note.version,
        requested_by=request.requested_by,
        reviewed_by=reviewer,
        occurred_at=occurred_at,
        rationale=request.rationale,
    )
    return GovernanceTransitionResult(current, next_state, event)


def supersede_governance_state(
    current: KnowledgeGovernanceState,
    replacement: KnowledgeGovernanceState,
    *,
    transition_id: str,
    requested_by: str,
    reviewed_by: str,
    rationale: str,
    occurred_at: str,
) -> GovernanceTransitionResult:
    """Close one version in favour of an already-built newer active version."""

    if current.lifecycle != "active" or replacement.lifecycle != "active":
        raise KnowledgeGovernanceError("supersession requires active current/replacement states")
    if (
        replacement.note.note_id != current.note.note_id
        or replacement.note.version != current.note.version + 1
        or replacement.scope != current.scope
        or replacement.owner_id != current.owner_id
        or replacement.campaign_id != current.campaign_id
        or replacement.source_id != current.source_id
    ):
        raise KnowledgeGovernanceError("replacement is not a newer state in the same scope")
    occurred_at = _instant(occurred_at, "occurred_at")
    if replacement.created_at != occurred_at:
        raise KnowledgeGovernanceError("replacement created_at must equal supersession occurred_at")
    reviewer = _reviewer(reviewed_by)
    closed = KnowledgeGovernanceState(
        schema_version=GOVERNANCE_SCHEMA_VERSION,
        note=current.note,
        epistemic_kind=current.epistemic_kind,
        review_state=current.review_state,
        reviewed_by=current.reviewed_by,
        lifecycle="superseded",
        scope=current.scope,
        owner_id=current.owner_id,
        campaign_id=current.campaign_id,
        source_id=current.source_id,
        evidence_digests=current.evidence_digests,
        counterexample_digests=current.counterexample_digests,
        evaluation_digest=current.evaluation_digest,
        policy_version=current.policy_version,
        created_at=current.created_at,
        expires_at=current.expires_at,
        superseded_by=replacement.note,
    )
    request = GovernanceTransitionRequest(
        transition_id=transition_id,
        transition="supersede",
        requested_by=requested_by,
        rationale=rationale,
    )
    event = GovernanceTransitionEvent(
        transition_id=request.transition_id,
        transition="supersede",
        from_state_digest=current.canonical_digest,
        to_state_digest=replacement.canonical_digest,
        note_id=current.note.note_id,
        from_version=current.note.version,
        to_version=replacement.note.version,
        requested_by=request.requested_by,
        reviewed_by=reviewer,
        occurred_at=occurred_at,
        rationale=request.rationale,
    )
    return GovernanceTransitionResult(current, closed, event, replacement)
