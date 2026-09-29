"""Deterministic, content-blind trust audit for campaign research packs.

This module deliberately does not inspect finding prose, source titles,
publishers, URLs or synthesis-provided source labels.  It consumes a separate
human/adapter attestation bound to a URL digest, then emits only opaque IDs,
aggregate counts and explicit policy codes.  It has no network, model, runner
or persistence dependency.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from .campaign_research import CampaignResearchPack, CampaignResearchSource, research_content_digest

QUALITY_SCHEMA_VERSION = "1.0"
MAX_SOURCE_AGE = timedelta(days=30)
CRITICAL_SECTIONS = frozenset({"audience_vocabulary", "audience_objections", "expected_proof"})
MAX_LARGEST_GROUP_FRACTION = 0.50
MIN_INDEPENDENT_GROUPS = 3

QualityStatus = Literal["trusted_complete", "limited", "blocked"]
SourceAuthority = Literal["verified_official", "established", "unverified"]

_SOURCE_TYPES = frozenset({"official", "competitor", "industry", "community", "platform"})
_EVIDENCE_TIERS = frozenset({"primary", "secondary", "community"})
_AUTHORITIES = frozenset({"verified_official", "established", "unverified"})
_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_GROUP = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class CampaignResearchQualityError(ValueError):
    """The quality-audit input or policy contract is malformed."""


def source_url_digest(source: CampaignResearchSource) -> str:
    """Opaque provenance binding for an attestation; never prompt the URL."""
    if not isinstance(source, CampaignResearchSource):
        raise CampaignResearchQualityError("source_url_digest requires CampaignResearchSource")
    return hashlib.sha256(source.url.encode("utf-8")).hexdigest()


def _instant(value: str, label: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise CampaignResearchQualityError(f"{label} must be a bounded ISO-8601 instant")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CampaignResearchQualityError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CampaignResearchQualityError(f"{label} must include a timezone")
    return parsed.astimezone(UTC)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class SourceClassificationAttestation:
    """Independent source classification, supplied by a trusted adapter/human.

    The pack's own ``source_type`` and ``evidence_tier`` are not used to grant
    trust.  A disagreement is auditable policy input, not a reason to silently
    fall back to the synthesis's self-declared labels.
    """

    schema_version: str
    source_id: str
    url_digest: str
    source_type: str
    evidence_tier: str
    authority: SourceAuthority
    editor_group: str
    domain_group: str

    def __post_init__(self) -> None:
        if self.schema_version != QUALITY_SCHEMA_VERSION:
            raise CampaignResearchQualityError("attestation schema_version is unsupported")
        if not isinstance(self.source_id, str) or not _ID.fullmatch(self.source_id):
            raise CampaignResearchQualityError("attestation source_id is invalid")
        if not isinstance(self.url_digest, str) or not _DIGEST.fullmatch(self.url_digest):
            raise CampaignResearchQualityError("attestation url_digest must be SHA-256")
        if self.source_type not in _SOURCE_TYPES or self.evidence_tier not in _EVIDENCE_TIERS:
            raise CampaignResearchQualityError("attestation source classification is unsupported")
        if self.authority not in _AUTHORITIES:
            raise CampaignResearchQualityError("attestation authority is unsupported")
        for label, value in (
            ("editor_group", self.editor_group),
            ("domain_group", self.domain_group),
        ):
            if not isinstance(value, str) or not _GROUP.fullmatch(value):
                raise CampaignResearchQualityError(f"attestation {label} is invalid")

    @property
    def is_attested_official_primary(self) -> bool:
        return (
            self.source_type == "official"
            and self.evidence_tier == "primary"
            and self.authority == "verified_official"
        )

    def to_audit_dict(self) -> dict[str, str]:
        """Safe audit projection: no URL/title/publisher/finding text."""
        return {
            "authority": self.authority,
            "domain_group": self.domain_group,
            "editor_group": self.editor_group,
            "evidence_tier": self.evidence_tier,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "url_digest": self.url_digest,
        }


@dataclass(frozen=True)
class CampaignResearchQuality:
    """Frozen, replayable audit result containing no source or finding prose."""

    schema_version: str
    research_digest: str
    as_of: str
    status: QualityStatus
    attested_source_ids: tuple[str, ...]
    missing_attestation_source_ids: tuple[str, ...]
    invalid_attestation_source_ids: tuple[str, ...]
    independent_group_count: int
    distinct_editor_group_count: int
    distinct_domain_group_count: int
    largest_group_fraction: float
    covered_critical_sections: tuple[str, ...]
    triangulated_finding_ids: tuple[str, ...]
    official_primary_finding_ids: tuple[str, ...]
    contrary_evidence_present: bool
    codes: tuple[str, ...]
    audit_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != QUALITY_SCHEMA_VERSION or not _DIGEST.fullmatch(
            self.research_digest
        ):
            raise CampaignResearchQualityError("quality schema or research digest is invalid")
        _instant(self.as_of, "quality.as_of")
        if self.status not in {"trusted_complete", "limited", "blocked"}:
            raise CampaignResearchQualityError("quality status is invalid")
        for label, values in (
            ("attested_source_ids", self.attested_source_ids),
            ("missing_attestation_source_ids", self.missing_attestation_source_ids),
            ("invalid_attestation_source_ids", self.invalid_attestation_source_ids),
            ("triangulated_finding_ids", self.triangulated_finding_ids),
            ("official_primary_finding_ids", self.official_primary_finding_ids),
            ("codes", self.codes),
        ):
            if tuple(sorted(set(values))) != values or not all(
                isinstance(value, str) for value in values
            ):
                raise CampaignResearchQualityError(f"quality {label} must be sorted and unique")
        if self.covered_critical_sections != tuple(
            sorted(set(self.covered_critical_sections))
        ) or not set(self.covered_critical_sections).issubset(CRITICAL_SECTIONS):
            raise CampaignResearchQualityError("quality critical sections are invalid")
        if (
            min(
                self.independent_group_count,
                self.distinct_editor_group_count,
                self.distinct_domain_group_count,
            )
            < 0
            or not math.isfinite(self.largest_group_fraction)
            or not 0 <= self.largest_group_fraction <= 1
        ):
            raise CampaignResearchQualityError("quality aggregate metrics are invalid")
        expected = _digest(self.to_audit_dict())
        object.__setattr__(self, "audit_digest", expected)

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of,
            "attested_source_ids": list(self.attested_source_ids),
            "codes": list(self.codes),
            "contrary_evidence_present": self.contrary_evidence_present,
            "covered_critical_sections": list(self.covered_critical_sections),
            "distinct_domain_group_count": self.distinct_domain_group_count,
            "distinct_editor_group_count": self.distinct_editor_group_count,
            "independent_group_count": self.independent_group_count,
            "invalid_attestation_source_ids": list(self.invalid_attestation_source_ids),
            "largest_group_fraction": self.largest_group_fraction,
            "missing_attestation_source_ids": list(self.missing_attestation_source_ids),
            "official_primary_finding_ids": list(self.official_primary_finding_ids),
            "research_digest": self.research_digest,
            "schema_version": self.schema_version,
            "status": self.status,
            "triangulated_finding_ids": list(self.triangulated_finding_ids),
        }


def _attestation_map(
    pack: CampaignResearchPack, attestations: Sequence[SourceClassificationAttestation]
) -> tuple[dict[str, SourceClassificationAttestation], set[str], set[str]]:
    """Return valid bindings plus missing/invalid IDs without trusting labels in pack."""
    if not isinstance(attestations, tuple) or not all(
        isinstance(item, SourceClassificationAttestation) for item in attestations
    ):
        raise CampaignResearchQualityError("attestations must be a tuple of attestations")
    sources = {source.source_id: source for source in pack.sources}
    grouped: dict[str, list[SourceClassificationAttestation]] = defaultdict(list)
    for item in attestations:
        grouped[item.source_id].append(item)
    valid: dict[str, SourceClassificationAttestation] = {}
    invalid: set[str] = set()
    for source_id, items in grouped.items():
        source = sources.get(source_id)
        if source is None or len(items) != 1 or items[0].url_digest != source_url_digest(source):
            invalid.add(source_id)
            continue
        valid[source_id] = items[0]
    return valid, set(sources) - set(valid), invalid


def _components(attestations: dict[str, SourceClassificationAttestation]) -> list[tuple[str, ...]]:
    """Groups are connected on shared editor OR shared registered-domain identity."""
    ids = sorted(attestations)
    parent = {source_id: source_id for source_id in ids}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            left_attestation, right_attestation = attestations[left], attestations[right]
            if (
                left_attestation.editor_group == right_attestation.editor_group
                or left_attestation.domain_group == right_attestation.domain_group
            ):
                union(left, right)
    groups: dict[str, list[str]] = defaultdict(list)
    for source_id in ids:
        groups[find(source_id)].append(source_id)
    return sorted(tuple(sorted(values)) for values in groups.values())


def evaluate_campaign_research_quality(
    pack: CampaignResearchPack,
    attestations: tuple[SourceClassificationAttestation, ...],
    as_of: datetime,
) -> CampaignResearchQuality:
    """Evaluate a closed trust policy without inspecting provider text or URLs.

    ``trusted_complete`` requires all valid bindings, fresh sources, independent
    groups, critical-section coverage, per-fact triangulation (or one verified
    official primary source), and one supported negative-evidence record.
    Everything else is ``limited``; unavailable research is ``blocked``.
    """
    if not isinstance(pack, CampaignResearchPack):
        raise CampaignResearchQualityError("pack must be CampaignResearchPack")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise CampaignResearchQualityError("as_of must be timezone-aware")
    as_of_utc = as_of.astimezone(UTC)
    generated = _instant(pack.generated_at, "pack.generated_at")
    if as_of_utc < generated:
        raise CampaignResearchQualityError("as_of cannot precede pack generation")
    research_digest = research_content_digest(pack)
    if pack.status == "unavailable":
        if attestations:
            # Validating type here preserves a closed caller contract even
            # though unavailable evidence cannot earn any quality state.
            _attestation_map(pack, attestations)
        return CampaignResearchQuality(
            QUALITY_SCHEMA_VERSION,
            research_digest,
            as_of_utc.isoformat(),
            "blocked",
            (),
            (),
            (),
            0,
            0,
            0,
            0.0,
            (),
            (),
            (),
            False,
            ("UNAVAILABLE_RESEARCH",),
        )

    valid, missing, invalid = _attestation_map(pack, attestations)
    components = _components(valid)
    largest_fraction = round(
        max((len(group) for group in components), default=0) / max(len(valid), 1), 6
    )
    editor_count = len({item.editor_group for item in valid.values()})
    domain_count = len({item.domain_group for item in valid.values()})
    source_by_id = {source.source_id: source for source in pack.sources}
    stale = {
        source_id
        for source_id in valid
        if as_of_utc - _instant(source_by_id[source_id].accessed_at, "source.accessed_at")
        > MAX_SOURCE_AGE
    }
    component_by_source = {
        source_id: index for index, component in enumerate(components) for source_id in component
    }
    covered: set[str] = set()
    triangulated: set[str] = set()
    official_primary: set[str] = set()
    contrary = False
    untriangulated = False
    findings_with_sections = (
        [(None, pack.market_summary)] if pack.market_summary is not None else []
    )
    findings_with_sections.extend(
        (section.name, finding) for section in pack.sections for finding in section.findings
    )
    for section_name, finding in findings_with_sections:
        assert finding is not None
        cited = [valid[source_id] for source_id in finding.source_ids if source_id in valid]
        groups = {component_by_source[item.source_id] for item in cited}
        official = any(item.is_attested_official_primary for item in cited)
        supported = len(groups) >= 2 or official
        if section_name in CRITICAL_SECTIONS and supported:
            covered.add(section_name)
        if finding.kind in {"fact", "negative_evidence"}:
            if len(groups) >= 2:
                triangulated.add(finding.finding_id)
            if official:
                official_primary.add(finding.finding_id)
            if not supported:
                untriangulated = True
        if finding.kind == "negative_evidence" and supported:
            contrary = True
    codes: set[str] = set()
    if pack.status != "complete":
        codes.add("PACK_NOT_COMPLETE")
    if missing:
        codes.add("ATTESTATIONS_MISSING")
    if invalid:
        codes.add("ATTESTATIONS_INVALID")
    if stale:
        codes.add("SOURCES_STALE")
    if set(CRITICAL_SECTIONS) - covered:
        codes.add("CRITICAL_SECTION_UNCOVERED")
    if untriangulated:
        codes.add("FINDING_UNTRIANGULATED")
    if not contrary:
        codes.add("NO_CONTRARY_EVIDENCE")
    if len(components) < MIN_INDEPENDENT_GROUPS:
        codes.add("INSUFFICIENT_INDEPENDENCE")
    if largest_fraction > MAX_LARGEST_GROUP_FRACTION:
        codes.add("SOURCE_CONCENTRATION_HIGH")
    trusted = not codes
    return CampaignResearchQuality(
        QUALITY_SCHEMA_VERSION,
        research_digest,
        as_of_utc.isoformat(),
        "trusted_complete" if trusted else "limited",
        tuple(sorted(valid)),
        tuple(sorted(missing)),
        tuple(sorted(invalid)),
        len(components),
        editor_count,
        domain_count,
        largest_fraction,
        tuple(sorted(covered)),
        tuple(sorted(triangulated)),
        tuple(sorted(official_primary)),
        contrary,
        tuple(sorted(codes)),
    )
