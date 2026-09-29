"""Pure, deterministic adaptive planning for campaign research.

This module decides *which evidence class to look for next*.  It is not a
search client and deliberately cannot fetch, call a model, persist data, or
accept a pre-computed quality object.  That last restriction is important:
the repair decision is always derived afresh from a pack plus independently
bound source attestations.

The output is safe to hand to an injected provider boundary such as
``campaign_research_runtime``.  It contains compact, scrubbed query text and
opaque policy codes only; it never includes URLs, fetched content, source
titles, or raw campaign fields.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from ..safety import sanitize_campaign, sanitize_text
from .campaign_research import (
    CampaignResearchPack,
    campaign_fingerprint,
    research_content_digest,
)
from .campaign_research_quality import (
    CRITICAL_SECTIONS,
    CampaignResearchQualityError,
    evaluate_campaign_research_quality,
)
from .research_attestation_authority import (
    IssuedResearchAttestations,
    ResearchAttestationAuthorityError,
    Verifier as ResearchAttestationVerifier,
    verify_research_attestations,
)

STRATEGY_VERSION = "1.0"
INITIAL_QUERY_COUNT = 4
MAX_FOLLOW_UP_QUERIES = 2
MAX_TOTAL_QUERIES = 6

SourceClass = Literal["official", "competitor", "industry", "community", "platform"]
GapKind = Literal["critical_section", "independence", "contrary_evidence", "claim_verification"]
StopReason = Literal[
    "initial_research_planned",
    "research_unavailable",
    "no_research_gaps",
    "repair_queries_planned",
    "repair_budget_exhausted",
]

_SOURCE_CLASSES = frozenset({"official", "competitor", "industry", "community", "platform"})
_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,95}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_URL = re.compile(r"(?:https?://|www\.)[^\s<>()\[\]{}]+", re.IGNORECASE)
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_LONG_TOKEN = re.compile(r"\b(?:[a-f0-9]{32,}|[a-z0-9_-]{24,})\b", re.IGNORECASE)
_SECRET_ASSIGNMENT = re.compile(
    r"\b(?:api[_ -]?key|access[_ -]?token|bearer|password|secret|sk)[\s:=_-]+[^\s,;]{4,}",
    re.IGNORECASE,
)


class CampaignResearchStrategyError(ValueError):
    """The strategy caller or its closed planning data violated the contract."""


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _safe_query_fragment(value: object, *, maximum: int = 100) -> str:
    """Retain only bounded topical prose; never copy addresses or secret-shaped input."""
    cleaned = sanitize_text(value, max_len=maximum * 3)
    cleaned = _URL.sub(" ", cleaned)
    cleaned = _EMAIL.sub(" ", cleaned)
    cleaned = _SECRET_ASSIGNMENT.sub(" ", cleaned)
    cleaned = _LONG_TOKEN.sub(" ", cleaned)
    return sanitize_text(cleaned, max_len=maximum)


def _query_context(campaign: Mapping[str, object]) -> str:
    sanitized = sanitize_campaign(dict(campaign))
    # Campaign name is intentionally omitted: it can be a customer/company
    # identifier and is unnecessary for a market-level evidence query.
    fields = (
        _safe_query_fragment(sanitized["niche"]),
        _safe_query_fragment(sanitized["audience"]),
        _safe_query_fragment(sanitized["goal"]),
    )
    parts = [value for value in fields if value]
    # Avoid topics and example hooks influence the evidence requirements, but
    # their verbatim copy may be proprietary campaign material.  Presence is
    # enough to request the right public evidence class without leaking the
    # customer's exact forbidden promises or creative examples to search.
    if sanitized["avoid_topics"]:
        parts.append("claim safety prohibited promise patterns")
    if sanitized["example_hooks"]:
        parts.append("short video hook pattern alternatives")
    return sanitize_text(" ".join(parts) or "market audience", max_len=180)


def _require_targets(value: tuple[str, ...], label: str) -> tuple[SourceClass, ...]:
    if (
        not isinstance(value, tuple)
        or not value
        or tuple(sorted(set(value))) != value
        or not all(item in _SOURCE_CLASSES for item in value)
    ):
        raise CampaignResearchStrategyError(
            f"{label} must be a sorted non-empty source-class tuple"
        )
    return value  # type: ignore[return-value]


@dataclass(frozen=True)
class ResearchRequirement:
    """An initial evidence need and its explicit target source classes."""

    requirement_id: str
    query: str
    source_class_targets: tuple[SourceClass, ...]
    section_targets: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.requirement_id, str) or not _ID.fullmatch(self.requirement_id):
            raise CampaignResearchStrategyError("requirement_id is invalid")
        query = _safe_query_fragment(self.query, maximum=240)
        if not query:
            raise CampaignResearchStrategyError("requirement query is empty or unsafe")
        if _URL.search(query) or _EMAIL.search(query) or _SECRET_ASSIGNMENT.search(query):
            raise CampaignResearchStrategyError("requirement query includes sensitive routing data")
        object.__setattr__(self, "query", query)
        _require_targets(self.source_class_targets, "requirement source_class_targets")
        if (
            not isinstance(self.section_targets, tuple)
            or not self.section_targets
            or tuple(sorted(set(self.section_targets))) != self.section_targets
            or not all(
                isinstance(item, str) and _ID.fullmatch(item) for item in self.section_targets
            )
        ):
            raise CampaignResearchStrategyError("requirement section_targets are invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "requirement_id": self.requirement_id,
            "query": self.query,
            "section_targets": list(self.section_targets),
            "source_class_targets": list(self.source_class_targets),
        }


@dataclass(frozen=True)
class ResearchGap:
    """A deterministic repairable deficit inferred from raw pack evidence."""

    gap_id: str
    kind: GapKind
    codes: tuple[str, ...]
    section_targets: tuple[str, ...]
    source_class_targets: tuple[SourceClass, ...]
    priority: int

    def __post_init__(self) -> None:
        if not isinstance(self.gap_id, str) or not _ID.fullmatch(self.gap_id):
            raise CampaignResearchStrategyError("gap_id is invalid")
        if self.kind not in {
            "critical_section",
            "independence",
            "contrary_evidence",
            "claim_verification",
        }:
            raise CampaignResearchStrategyError("gap kind is invalid")
        if (
            not isinstance(self.codes, tuple)
            or not self.codes
            or tuple(sorted(set(self.codes))) != self.codes
            or not all(isinstance(item, str) and _CODE.fullmatch(item) for item in self.codes)
        ):
            raise CampaignResearchStrategyError("gap codes are invalid")
        if (
            not isinstance(self.section_targets, tuple)
            or tuple(sorted(set(self.section_targets))) != self.section_targets
            or not all(
                isinstance(item, str) and _ID.fullmatch(item) for item in self.section_targets
            )
        ):
            raise CampaignResearchStrategyError("gap section targets are invalid")
        _require_targets(self.source_class_targets, "gap source_class_targets")
        if (
            isinstance(self.priority, bool)
            or not isinstance(self.priority, int)
            or not 0 <= self.priority <= 99
        ):
            raise CampaignResearchStrategyError("gap priority is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "codes": list(self.codes),
            "gap_id": self.gap_id,
            "kind": self.kind,
            "priority": self.priority,
            "section_targets": list(self.section_targets),
            "source_class_targets": list(self.source_class_targets),
        }


@dataclass(frozen=True)
class FollowUpQuery:
    """One bounded repair query, explicitly bound to the gaps it can repair."""

    query_id: str
    query: str
    source_class_targets: tuple[SourceClass, ...]
    addresses_gap_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.query_id, str) or not _ID.fullmatch(self.query_id):
            raise CampaignResearchStrategyError("follow-up query_id is invalid")
        query = _safe_query_fragment(self.query, maximum=240)
        if not query:
            raise CampaignResearchStrategyError("follow-up query is empty or unsafe")
        if _URL.search(query) or _EMAIL.search(query) or _SECRET_ASSIGNMENT.search(query):
            raise CampaignResearchStrategyError("follow-up query includes sensitive routing data")
        object.__setattr__(self, "query", query)
        _require_targets(self.source_class_targets, "follow-up source_class_targets")
        if (
            not isinstance(self.addresses_gap_ids, tuple)
            or not self.addresses_gap_ids
            or tuple(sorted(set(self.addresses_gap_ids))) != self.addresses_gap_ids
            or not all(
                isinstance(item, str) and _ID.fullmatch(item) for item in self.addresses_gap_ids
            )
        ):
            raise CampaignResearchStrategyError("follow-up addresses_gap_ids are invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "addresses_gap_ids": list(self.addresses_gap_ids),
            "query": self.query,
            "query_id": self.query_id,
            "source_class_targets": list(self.source_class_targets),
        }


@dataclass(frozen=True)
class AdaptiveResearchPlan:
    """Closed initial + repair plan with a content-addressed audit digest."""

    strategy_version: str
    campaign_fingerprint: str
    initial_requirements: tuple[ResearchRequirement, ...]
    gaps: tuple[ResearchGap, ...]
    follow_up_queries: tuple[FollowUpQuery, ...]
    total_query_budget: int
    stop_reason: StopReason
    research_digest: str | None
    quality_status: str | None
    quality_audit_digest: str | None
    digest: str = ""

    def __post_init__(self) -> None:
        if self.strategy_version != STRATEGY_VERSION or not _DIGEST.fullmatch(
            self.campaign_fingerprint
        ):
            raise CampaignResearchStrategyError(
                "strategy version or campaign fingerprint is invalid"
            )
        if (
            not isinstance(self.initial_requirements, tuple)
            or len(self.initial_requirements) != INITIAL_QUERY_COUNT
            or any(not isinstance(item, ResearchRequirement) for item in self.initial_requirements)
            or len({item.requirement_id for item in self.initial_requirements})
            != len(self.initial_requirements)
        ):
            raise CampaignResearchStrategyError("initial requirements are invalid")
        if (
            not isinstance(self.gaps, tuple)
            or any(not isinstance(item, ResearchGap) for item in self.gaps)
            or tuple(sorted(self.gaps, key=lambda item: (item.priority, item.gap_id))) != self.gaps
            or len({item.gap_id for item in self.gaps}) != len(self.gaps)
        ):
            raise CampaignResearchStrategyError("gaps must be unique and priority ordered")
        if (
            not isinstance(self.follow_up_queries, tuple)
            or len(self.follow_up_queries) > MAX_FOLLOW_UP_QUERIES
            or any(not isinstance(item, FollowUpQuery) for item in self.follow_up_queries)
            or len({item.query_id for item in self.follow_up_queries})
            != len(self.follow_up_queries)
            or len(self.initial_requirements) + len(self.follow_up_queries) > MAX_TOTAL_QUERIES
        ):
            raise CampaignResearchStrategyError("follow-up query budget is invalid")
        known_gap_ids = {gap.gap_id for gap in self.gaps}
        if any(
            not set(item.addresses_gap_ids).issubset(known_gap_ids)
            for item in self.follow_up_queries
        ):
            raise CampaignResearchStrategyError("follow-up references an unknown gap")
        if self.total_query_budget != MAX_TOTAL_QUERIES:
            raise CampaignResearchStrategyError("total query budget is fixed")
        if self.stop_reason not in {
            "initial_research_planned",
            "research_unavailable",
            "no_research_gaps",
            "repair_queries_planned",
            "repair_budget_exhausted",
        }:
            raise CampaignResearchStrategyError("stop reason is invalid")
        if (self.research_digest is None) != (self.quality_status is None):
            raise CampaignResearchStrategyError("research and quality state must be paired")
        if self.research_digest is not None and not _DIGEST.fullmatch(self.research_digest):
            raise CampaignResearchStrategyError("research digest is invalid")
        if self.quality_status not in {None, "trusted_complete", "limited", "blocked"}:
            raise CampaignResearchStrategyError("quality status is invalid")
        if self.quality_audit_digest is not None and not _DIGEST.fullmatch(
            self.quality_audit_digest
        ):
            raise CampaignResearchStrategyError("quality audit digest is invalid")
        if self.research_digest is None and self.quality_audit_digest is not None:
            raise CampaignResearchStrategyError("quality digest requires research")
        if self.research_digest is not None and self.quality_audit_digest is None:
            raise CampaignResearchStrategyError("research requires a recomputed quality digest")
        all_queries = tuple(item.query for item in self.initial_requirements) + tuple(
            item.query for item in self.follow_up_queries
        )
        if len(all_queries) != len(set(all_queries)):
            raise CampaignResearchStrategyError("adaptive plan cannot repeat query text")
        payload_digest = _digest(self.to_dict(include_digest=False))
        if self.digest and self.digest != payload_digest:
            raise CampaignResearchStrategyError("adaptive plan digest does not match its content")
        object.__setattr__(self, "digest", payload_digest)

    def to_dict(self, *, include_digest: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "campaign_fingerprint": self.campaign_fingerprint,
            "follow_up_queries": [item.to_dict() for item in self.follow_up_queries],
            "gaps": [item.to_dict() for item in self.gaps],
            "initial_requirements": [item.to_dict() for item in self.initial_requirements],
            "quality_audit_digest": self.quality_audit_digest,
            "quality_status": self.quality_status,
            "research_digest": self.research_digest,
            "stop_reason": self.stop_reason,
            "strategy_version": self.strategy_version,
            "total_query_budget": self.total_query_budget,
        }
        if include_digest:
            value["digest"] = self.digest
        return value


def _initial_requirements(campaign: Mapping[str, object]) -> tuple[ResearchRequirement, ...]:
    context = _query_context(campaign)
    return (
        ResearchRequirement(
            "audience_language",
            f"{context} audience vocabulary pains objections firsthand language",
            ("community", "industry"),
            ("audience_objections", "audience_pains", "audience_vocabulary"),
        ),
        ResearchRequirement(
            "proof_expectations",
            f"{context} expected proof evidence benchmarks buyer objections",
            ("industry", "official"),
            ("claims_requiring_verification", "expected_proof"),
        ),
        ResearchRequirement(
            "competitor_market",
            f"{context} competitor positioning saturated claims differentiation",
            ("competitor", "industry"),
            ("competitor_angles", "saturated_claims"),
        ),
        ResearchRequirement(
            "platform_hook_context",
            f"{context} platform short video hook patterns audience safety constraints",
            ("official", "platform"),
            ("avoid_topics", "hook_patterns", "platform_notes"),
        ),
    )


def build_initial_adaptive_research_plan(campaign: Mapping[str, object]) -> AdaptiveResearchPlan:
    """Return the four safe initial evidence requirements; no I/O is performed."""
    if not isinstance(campaign, Mapping):
        raise CampaignResearchStrategyError("campaign must be an object")
    sanitized = sanitize_campaign(dict(campaign))
    return AdaptiveResearchPlan(
        STRATEGY_VERSION,
        campaign_fingerprint(sanitized),
        _initial_requirements(sanitized),
        (),
        (),
        MAX_TOTAL_QUERIES,
        "initial_research_planned",
        None,
        None,
        None,
    )


def _gaps_for_quality(
    pack: CampaignResearchPack, codes: frozenset[str], covered: frozenset[str], contrary: bool
) -> tuple[ResearchGap, ...]:
    gaps: list[ResearchGap] = []
    for section in sorted(CRITICAL_SECTIONS - covered):
        targets: tuple[SourceClass, ...] = ("industry", "official")
        gaps.append(
            ResearchGap(
                f"critical-{section.replace('_', '-')}",
                "critical_section",
                ("CRITICAL_SECTION_UNCOVERED",),
                (section,),
                targets,
                10,
            )
        )
    if {"INSUFFICIENT_INDEPENDENCE", "SOURCE_CONCENTRATION_HIGH"} & codes:
        gaps.append(
            ResearchGap(
                "independent-source-coverage",
                "independence",
                tuple(sorted({"INSUFFICIENT_INDEPENDENCE", "SOURCE_CONCENTRATION_HIGH"} & codes)),
                (),
                ("industry", "official", "platform"),
                20,
            )
        )
    if not contrary or "NO_CONTRARY_EVIDENCE" in codes:
        gaps.append(
            ResearchGap(
                "contrary-evidence",
                "contrary_evidence",
                ("NO_CONTRARY_EVIDENCE",),
                ("avoid_topics",),
                ("competitor", "official"),
                30,
            )
        )
    if not pack.section("claims_requiring_verification") or "FINDING_UNTRIANGULATED" in codes:
        claim_codes = {"CLAIMS_REQUIRING_VERIFICATION"}
        if "FINDING_UNTRIANGULATED" in codes:
            claim_codes.add("FINDING_UNTRIANGULATED")
        gaps.append(
            ResearchGap(
                "claim-verification",
                "claim_verification",
                tuple(sorted(claim_codes)),
                ("claims_requiring_verification",),
                ("industry", "official"),
                40,
            )
        )
    return tuple(sorted(gaps, key=lambda item: (item.priority, item.gap_id)))


def _follow_up_query(
    context: str,
    gaps: tuple[ResearchGap, ...],
    index: int,
) -> FollowUpQuery:
    kinds = {gap.kind for gap in gaps}
    sections = tuple(sorted({item for gap in gaps for item in gap.section_targets}))
    suffixes: list[str] = []
    if "critical_section" in kinds:
        rendered = " ".join(sections).replace("_", " ")
        suffixes.append(f"independent evidence for {rendered}")
    if "independence" in kinds:
        suffixes.append("independent publishers alternative evidence")
    if "contrary_evidence" in kinds:
        suffixes.append("limitations failures counterexamples avoid claims")
    if "claim_verification" in kinds:
        suffixes.append("claims requiring verification authoritative supporting evidence")
    label = "critical-coverage" if kinds == {"critical_section"} else "systemic-evidence"
    return FollowUpQuery(
        f"repair-{index}-{label}",
        f"{context} {' '.join(suffixes)}",
        tuple(sorted({item for gap in gaps for item in gap.source_class_targets})),
        tuple(sorted(gap.gap_id for gap in gaps)),
    )


def _repair_groups(gaps: tuple[ResearchGap, ...]) -> tuple[tuple[ResearchGap, ...], ...]:
    """Use one query for missing content and one for systemic trust deficits.

    Selecting the first two granular gaps would spend the entire budget on two
    alphabetically adjacent sections while ignoring independence or contrary
    evidence.  Grouping preserves every audit finding in the query provenance
    and gives the fixed two-query repair budget complementary jobs.
    """
    critical = tuple(gap for gap in gaps if gap.kind == "critical_section")
    systemic = tuple(gap for gap in gaps if gap.kind != "critical_section")
    return tuple(group for group in (critical, systemic) if group)


def plan_adaptive_campaign_research(
    campaign: Mapping[str, object],
    pack: CampaignResearchPack,
    attestations: IssuedResearchAttestations | None,
    as_of: datetime,
    *,
    owner_id: str | None = None,
    campaign_id: str | None = None,
    attestation_verifier: ResearchAttestationVerifier | None = None,
) -> AdaptiveResearchPlan:
    """Recompute quality and create no more than two deterministic repairs.

    A :class:`CampaignResearchQuality` value is intentionally absent from this
    API.  Accepting one would let a caller turn a forged public dataclass into
    a search decision.  The evaluator is called for every non-initial plan.
    """
    if not isinstance(campaign, Mapping):
        raise CampaignResearchStrategyError("campaign must be an object")
    if not isinstance(pack, CampaignResearchPack):
        raise CampaignResearchStrategyError("pack must be CampaignResearchPack")
    if attestations is not None and not isinstance(attestations, IssuedResearchAttestations):
        raise CampaignResearchStrategyError(
            "source classifications require a signed research attestation authority"
        )
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise CampaignResearchStrategyError("as_of must be timezone-aware")
    sanitized = sanitize_campaign(dict(campaign))
    fingerprint = campaign_fingerprint(sanitized)
    if pack.campaign_fingerprint != fingerprint:
        raise CampaignResearchStrategyError("pack does not belong to this campaign fingerprint")
    try:
        attestation_items = ()
        if attestations is not None:
            if owner_id is None or campaign_id is None or attestation_verifier is None:
                raise CampaignResearchStrategyError(
                    "research source classifications require scope and an authority verifier"
                )
            verified_attestations = verify_research_attestations(
                attestations,
                pack,
                verifier=attestation_verifier,
                owner_id=owner_id,
                campaign_id=campaign_id,
                now=as_of.astimezone(UTC),
            )
            attestation_items = verified_attestations.attestations
        quality = evaluate_campaign_research_quality(pack, attestation_items, as_of.astimezone(UTC))
    except (CampaignResearchQualityError, ResearchAttestationAuthorityError) as exc:
        raise CampaignResearchStrategyError(
            "campaign research quality could not be evaluated"
        ) from exc
    initial = _initial_requirements(sanitized)
    research_digest = research_content_digest(pack)
    if quality.status == "blocked":
        return AdaptiveResearchPlan(
            STRATEGY_VERSION,
            fingerprint,
            initial,
            (),
            (),
            MAX_TOTAL_QUERIES,
            "research_unavailable",
            research_digest,
            quality.status,
            quality.audit_digest,
        )
    gaps = _gaps_for_quality(
        pack,
        frozenset(quality.codes),
        frozenset(quality.covered_critical_sections),
        quality.contrary_evidence_present,
    )
    if not gaps:
        return AdaptiveResearchPlan(
            STRATEGY_VERSION,
            fingerprint,
            initial,
            (),
            (),
            MAX_TOTAL_QUERIES,
            "no_research_gaps",
            research_digest,
            quality.status,
            quality.audit_digest,
        )
    capacity = min(MAX_FOLLOW_UP_QUERIES, MAX_TOTAL_QUERIES - len(initial))
    if capacity <= 0:
        return AdaptiveResearchPlan(
            STRATEGY_VERSION,
            fingerprint,
            initial,
            gaps,
            (),
            MAX_TOTAL_QUERIES,
            "repair_budget_exhausted",
            research_digest,
            quality.status,
            quality.audit_digest,
        )
    context = _query_context(sanitized)
    repair_groups = _repair_groups(gaps)[:capacity]
    repairs = tuple(
        _follow_up_query(context, group, index + 1) for index, group in enumerate(repair_groups)
    )
    return AdaptiveResearchPlan(
        STRATEGY_VERSION,
        fingerprint,
        initial,
        gaps,
        repairs,
        MAX_TOTAL_QUERIES,
        "repair_queries_planned",
        research_digest,
        quality.status,
        quality.audit_digest,
    )
