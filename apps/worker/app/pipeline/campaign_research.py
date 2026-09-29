"""Pure, hostile-input-safe contract for cached campaign research.

This module intentionally has no HTTP client, database connection, or runner
integration.  Providers may implement :class:`CampaignResearchClient`, but the
only artefact accepted by the rest of the worker is the validated immutable
``CampaignResearchPack`` defined here.

Research is evidence, not instructions.  The compact serializer therefore
emits JSON data made from short synthesized findings and source identifiers;
it never emits a fetched page, HTML, or search snippet.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any, Literal, Protocol, TypeAlias
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..safety import sanitize_campaign, sanitize_text

SCHEMA_VERSION = "1.0"
RESEARCH_POLICY_VERSION = "1.0"

MAX_SOURCES = 15
MIN_SOURCES_FOR_COMPLETE = 3
MAX_FINDINGS_PER_SECTION = 12
MAX_FINDING_CHARS = 280
MAX_MARKET_SUMMARY_CHARS = 600
MAX_SOURCE_TITLE_CHARS = 180
MAX_PUBLISHER_CHARS = 120
MAX_EVIDENCE_SUMMARY_CHARS = 500
MAX_URL_CHARS = 2_048
MAX_PROMPT_CHARS = 3_200
MAX_PROMPT_SOURCES = 8
MAX_PROMPT_FINDINGS_PER_SECTION = 3

ResearchStatus: TypeAlias = Literal["complete", "partial", "unavailable"]
SourceType: TypeAlias = Literal["official", "competitor", "industry", "community", "platform"]
EvidenceTier: TypeAlias = Literal["primary", "secondary", "community"]
FindingKind: TypeAlias = Literal["fact", "vocabulary", "hypothesis", "negative_evidence"]
FindingScope: TypeAlias = Literal["market_context", "sampled_sources"]

_SOURCE_TYPES = frozenset({"official", "competitor", "industry", "community", "platform"})
_STATUSES = frozenset({"complete", "partial", "unavailable"})
_EVIDENCE_TIERS = frozenset({"primary", "secondary", "community"})
_FINDING_KINDS = frozenset({"fact", "vocabulary", "hypothesis", "negative_evidence"})
_FINDING_SCOPES = frozenset({"market_context", "sampled_sources"})
_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}$")
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_URL_IN_TEXT_RE = re.compile(r"(?:https?://|www\.)[^\s<>()\[\]{}]+", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>]{0,240}>")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]\n]{1,180})\]\([^\)\n]{0,2_048}\)")
_CODE_FENCE_RE = re.compile(r"`{3,}")
_SECTION_NAMES = (
    "audience_vocabulary",
    "audience_pains",
    "audience_desires",
    "audience_objections",
    "expected_proof",
    "hook_patterns",
    "saturated_claims",
    "competitor_angles",
    "platform_notes",
    "claims_requiring_verification",
    "avoid_topics",
)
_PRIORITY_SECTIONS = (
    "audience_vocabulary",
    "audience_objections",
    "expected_proof",
    "audience_pains",
    "competitor_angles",
    "saturated_claims",
    "hook_patterns",
    "audience_desires",
    "platform_notes",
    "claims_requiring_verification",
    "avoid_topics",
)


class CampaignResearchError(ValueError):
    """Raised when an untrusted research artefact violates the closed contract."""


def _require_exact_keys(value: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = set(value) - allowed
    missing = allowed - set(value)
    if unknown or missing:
        details = []
        if unknown:
            details.append(f"unknown={sorted(unknown)}")
        if missing:
            details.append(f"missing={sorted(missing)}")
        raise CampaignResearchError(f"{label} keys invalid ({', '.join(details)})")


def _require_text(value: Any, label: str, *, maximum: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise CampaignResearchError(f"{label} must be a string")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized and not allow_empty:
        raise CampaignResearchError(f"{label} cannot be empty")
    if len(normalized) > maximum:
        raise CampaignResearchError(f"{label} exceeds {maximum} characters")
    return normalized


def research_data_text(value: Any, *, label: str, maximum: int) -> str:
    """Canonicalise external research prose for data-only downstream use.

    Research providers can return arbitrary page-derived text.  This helper is
    deliberately *not* an instruction detector: semantic blacklists are both
    brittle and destructive to real audience vocabulary.  Instead, it removes
    the syntax by which a value can escape a structured data boundary (control
    characters, prompt fences, code fences, HTML/Markdown links and URLs), then
    leaves the bounded natural-language observation intact as a data value.

    ``CampaignResearchSource.url`` is intentionally excluded: it remains an
    audit-only provenance field and is never passed through this text channel.
    """
    raw = _require_text(value, label, maximum=maximum)
    # ``sanitize_text`` normalises Unicode/whitespace, removes controls and
    # zero-width characters, and defuses the worker's BEGIN/END fence grammar.
    cleaned = sanitize_text(raw, max_len=maximum)
    # Preserve a Markdown link's human label, never its destination.  Do this
    # before generic URL stripping so the useful vocabulary survives.
    cleaned = _MARKDOWN_LINK_RE.sub(r"\1", cleaned)
    cleaned = _HTML_TAG_RE.sub(" ", cleaned)
    cleaned = _CODE_FENCE_RE.sub(" ", cleaned)
    cleaned = _URL_IN_TEXT_RE.sub("[url omitted]", cleaned)
    cleaned = sanitize_text(cleaned, max_len=maximum)
    if not cleaned:
        raise CampaignResearchError(f"{label} has no usable data after neutralisation")
    # These are postconditions, not semantic detection.  A caller may rely on
    # them when embedding this value as a field in a context record.
    if (
        _URL_IN_TEXT_RE.search(cleaned)
        or _HTML_TAG_RE.search(cleaned)
        or _CODE_FENCE_RE.search(cleaned)
    ):
        raise CampaignResearchError(f"{label} contains unsafe markup")
    return cleaned


def _require_id(value: Any, label: str) -> str:
    identifier = _require_text(value, label, maximum=64)
    if not _ID_RE.fullmatch(identifier):
        raise CampaignResearchError(f"{label} must match {_ID_RE.pattern}")
    return identifier


def _parse_iso8601(value: Any, label: str) -> datetime:
    raw = _require_text(value, label, maximum=40)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CampaignResearchError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CampaignResearchError(f"{label} must include a timezone")
    return parsed.astimezone(UTC)


def _iso8601(value: str, label: str) -> str:
    """Validate an ISO instant but preserve the caller's auditable representation."""
    _parse_iso8601(value, label)
    return value


def _finite_confidence(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CampaignResearchError(f"{label} must be a finite number")
    confidence = float(value)
    if not math.isfinite(confidence):
        raise CampaignResearchError(f"{label} must be a finite number")
    if not 0.0 <= confidence <= 1.0:
        raise CampaignResearchError(f"{label} must be between 0 and 1")
    return confidence


def canonical_public_url(value: Any) -> str:
    """Return a canonical public HTTP(S) URL or reject an SSRF-shaped value.

    DNS resolution is deliberately not attempted in this pure local layer.  A
    future fetch adapter must additionally check every resolved address and
    every redirect.  Literal addresses are fully checked here, as are local
    hostnames, credential-bearing URLs and non-web schemes.
    """
    raw = _require_text(value, "source.url", maximum=MAX_URL_CHARS)
    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise CampaignResearchError("source.url is malformed") from exc
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise CampaignResearchError("source.url must use HTTP(S)")
    if not parts.netloc or parts.username is not None or parts.password is not None:
        raise CampaignResearchError("source.url must have a public host and no credentials")
    try:
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise CampaignResearchError("source.url has an invalid port") from exc
    if not host:
        raise CampaignResearchError("source.url must have a host")
    host = host.rstrip(".").lower()
    blocked_suffixes = (".localhost", ".local", ".internal", ".lan", ".home")
    if (
        not host
        or ("." not in host and ":" not in host)
        or host == "localhost"
        or host.endswith(blocked_suffixes)
    ):
        raise CampaignResearchError("source.url host is local")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        # is_global rejects private, loopback, link-local, multicast, reserved,
        # unspecified and documentation ranges on supported Python versions.
        if not literal.is_global:
            raise CampaignResearchError("source.url literal IP is not public")
        rendered_host = f"[{literal.compressed}]" if literal.version == 6 else literal.compressed
    else:
        try:
            rendered_host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise CampaignResearchError("source.url host is invalid") from exc
    if port is not None and not (1 <= port <= 65_535):
        raise CampaignResearchError("source.url port is invalid")
    rendered_port = "" if port in {None, 80 if scheme == "http" else 443} else f":{port}"
    path = parts.path or "/"
    # Fragments are never useful evidence identity.  Sorting query pairs makes
    # cosmetic parameter order deterministic without discarding an article ID.
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((scheme, f"{rendered_host}{rendered_port}", path, query, ""))


def _source_sort_key(source: CampaignResearchSource) -> tuple[str, str, str, str, str]:
    return (
        source.source_id,
        source.title.casefold(),
        source.publisher or "",
        source.accessed_at,
        source.url,
    )


@dataclass(frozen=True)
class CampaignResearchSource:
    schema_version: str
    source_id: str
    url: str
    title: str
    publisher: str | None
    published_at: str | None
    accessed_at: str
    source_type: SourceType
    evidence_tier: EvidenceTier
    evidence_summary: str

    def __post_init__(self) -> None:
        _require_text(self.schema_version, "source.schema_version", maximum=16)
        if self.schema_version != SCHEMA_VERSION:
            raise CampaignResearchError("source.schema_version is unsupported")
        _require_id(self.source_id, "source.source_id")
        canonical = canonical_public_url(self.url)
        object.__setattr__(self, "url", canonical)
        object.__setattr__(
            self,
            "title",
            research_data_text(self.title, label="source.title", maximum=MAX_SOURCE_TITLE_CHARS),
        )
        if self.publisher is not None:
            object.__setattr__(
                self,
                "publisher",
                research_data_text(
                    self.publisher, label="source.publisher", maximum=MAX_PUBLISHER_CHARS
                ),
            )
        if self.published_at is not None:
            published = _parse_iso8601(self.published_at, "source.published_at")
        else:
            published = None
        accessed = _parse_iso8601(self.accessed_at, "source.accessed_at")
        if published is not None and published > accessed:
            raise CampaignResearchError("source.published_at cannot be after source.accessed_at")
        if self.source_type not in _SOURCE_TYPES:
            raise CampaignResearchError("source.source_type is not allowed")
        if self.evidence_tier not in _EVIDENCE_TIERS:
            raise CampaignResearchError("source.evidence_tier is not allowed")
        if self.source_type == "community" and self.evidence_tier != "community":
            raise CampaignResearchError("community sources must be labelled community evidence")
        if self.evidence_tier == "community" and self.source_type != "community":
            raise CampaignResearchError("community evidence must use source_type=community")
        object.__setattr__(
            self,
            "evidence_summary",
            research_data_text(
                self.evidence_summary,
                label="source.evidence_summary",
                maximum=MAX_EVIDENCE_SUMMARY_CHARS,
            ),
        )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> CampaignResearchSource:
        if not isinstance(raw, Mapping):
            raise CampaignResearchError("source must be an object")
        _require_exact_keys(
            raw,
            frozenset(
                {
                    "schema_version",
                    "source_id",
                    "url",
                    "title",
                    "publisher",
                    "published_at",
                    "accessed_at",
                    "source_type",
                    "evidence_tier",
                    "evidence_summary",
                }
            ),
            "source",
        )
        return cls(**dict(raw))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "url": self.url,
            "title": self.title,
            "publisher": self.publisher,
            "published_at": self.published_at,
            "accessed_at": self.accessed_at,
            "source_type": self.source_type,
            "evidence_tier": self.evidence_tier,
            "evidence_summary": self.evidence_summary,
        }


@dataclass(frozen=True)
class CitedFinding:
    """A concise synthesized observation and the retained evidence that supports it."""

    schema_version: str
    finding_id: str
    kind: FindingKind
    scope: FindingScope
    text: str
    source_ids: tuple[str, ...]
    confidence: float
    valid_from: str
    valid_until: str

    def __post_init__(self) -> None:
        _require_text(self.schema_version, "finding.schema_version", maximum=16)
        if self.schema_version != SCHEMA_VERSION:
            raise CampaignResearchError("finding.schema_version is unsupported")
        _require_id(self.finding_id, "finding.finding_id")
        if self.kind not in _FINDING_KINDS:
            raise CampaignResearchError("finding.kind is not allowed")
        if self.scope not in _FINDING_SCOPES:
            raise CampaignResearchError("finding.scope is not allowed")
        object.__setattr__(
            self,
            "text",
            research_data_text(self.text, label="finding.text", maximum=MAX_FINDING_CHARS),
        )
        if not isinstance(self.source_ids, tuple) or not self.source_ids:
            raise CampaignResearchError("finding.source_ids must be a non-empty tuple")
        ids = tuple(_require_id(value, "finding.source_id") for value in self.source_ids)
        if len(ids) != len(set(ids)):
            raise CampaignResearchError("finding.source_ids must be unique")
        object.__setattr__(self, "source_ids", tuple(sorted(ids)))
        _finite_confidence(self.confidence, "finding.confidence")
        valid_from = _parse_iso8601(self.valid_from, "finding.valid_from")
        valid_until = _parse_iso8601(self.valid_until, "finding.valid_until")
        if valid_until <= valid_from:
            raise CampaignResearchError("finding.valid_until must be after finding.valid_from")
        if self.kind == "negative_evidence":
            if self.scope != "sampled_sources":
                raise CampaignResearchError("negative evidence must use the sampled_sources scope")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> CitedFinding:
        if not isinstance(raw, Mapping):
            raise CampaignResearchError("finding must be an object")
        _require_exact_keys(
            raw,
            frozenset(
                {
                    "schema_version",
                    "finding_id",
                    "kind",
                    "scope",
                    "text",
                    "source_ids",
                    "confidence",
                    "valid_from",
                    "valid_until",
                }
            ),
            "finding",
        )
        ids = raw["source_ids"]
        if not isinstance(ids, (list, tuple)) or isinstance(ids, str):
            raise CampaignResearchError("finding.source_ids must be an array")
        return cls(
            schema_version=raw["schema_version"],
            finding_id=raw["finding_id"],
            kind=raw["kind"],
            scope=raw["scope"],
            text=raw["text"],
            source_ids=tuple(ids),
            confidence=raw["confidence"],
            valid_from=raw["valid_from"],
            valid_until=raw["valid_until"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "finding_id": self.finding_id,
            "kind": self.kind,
            "scope": self.scope,
            "text": self.text,
            "source_ids": list(self.source_ids),
            "confidence": self.confidence,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
        }


@dataclass(frozen=True)
class CampaignResearchSection:
    """One closed research category.  Every entry is explicitly cited."""

    schema_version: str
    name: str
    findings: tuple[CitedFinding, ...]

    def __post_init__(self) -> None:
        _require_text(self.schema_version, "section.schema_version", maximum=16)
        if self.schema_version != SCHEMA_VERSION:
            raise CampaignResearchError("section.schema_version is unsupported")
        if self.name not in _SECTION_NAMES:
            raise CampaignResearchError("section.name is not allowed")
        if not isinstance(self.findings, tuple):
            raise CampaignResearchError("section.findings must be a tuple")
        if len(self.findings) > MAX_FINDINGS_PER_SECTION:
            raise CampaignResearchError("section has too many findings")
        if any(not isinstance(finding, CitedFinding) for finding in self.findings):
            raise CampaignResearchError("section.findings contains an invalid finding")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class CampaignResearchPack:
    schema_version: str
    research_policy_version: str
    campaign_fingerprint: str
    generated_at: str
    expires_at: str
    status: ResearchStatus
    market_summary: CitedFinding | None
    sections: tuple[CampaignResearchSection, ...]
    sources: tuple[CampaignResearchSource, ...]
    confidence: float

    def __post_init__(self) -> None:
        _require_text(self.schema_version, "pack.schema_version", maximum=16)
        _require_text(self.research_policy_version, "pack.research_policy_version", maximum=16)
        if self.schema_version != SCHEMA_VERSION:
            raise CampaignResearchError("pack.schema_version is unsupported")
        if not _VERSION_RE.fullmatch(self.research_policy_version):
            raise CampaignResearchError("pack.research_policy_version must be a numeric version")
        fingerprint = _require_text(
            self.campaign_fingerprint, "pack.campaign_fingerprint", maximum=64
        )
        if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
            raise CampaignResearchError("pack.campaign_fingerprint must be a SHA-256 hex digest")
        generated = _parse_iso8601(self.generated_at, "pack.generated_at")
        expires = _parse_iso8601(self.expires_at, "pack.expires_at")
        if expires <= generated:
            raise CampaignResearchError("pack.expires_at must be after pack.generated_at")
        if self.status not in _STATUSES:
            raise CampaignResearchError("pack.status is not allowed")
        _finite_confidence(self.confidence, "pack.confidence")
        if not isinstance(self.sources, tuple) or len(self.sources) > MAX_SOURCES:
            raise CampaignResearchError("pack.sources must be a bounded tuple")
        if any(not isinstance(source, CampaignResearchSource) for source in self.sources):
            raise CampaignResearchError("pack.sources contains an invalid source")
        ids = [source.source_id for source in self.sources]
        urls = [source.url for source in self.sources]
        if len(ids) != len(set(ids)) or len(urls) != len(set(urls)):
            raise CampaignResearchError("pack source IDs and URLs must be unique")
        for source in self.sources:
            accessed = _parse_iso8601(source.accessed_at, "source.accessed_at")
            if accessed > generated:
                raise CampaignResearchError("source.accessed_at cannot be after pack.generated_at")
        if not isinstance(self.sections, tuple) or len(self.sections) != len(_SECTION_NAMES):
            raise CampaignResearchError(
                "pack must contain each closed research section exactly once"
            )
        if any(not isinstance(section, CampaignResearchSection) for section in self.sections):
            raise CampaignResearchError("pack.sections contains an invalid section")
        names = [section.name for section in self.sections]
        if set(names) != set(_SECTION_NAMES) or len(names) != len(set(names)):
            raise CampaignResearchError("pack sections must be unique and closed")
        if self.market_summary is not None and not isinstance(self.market_summary, CitedFinding):
            raise CampaignResearchError("pack.market_summary is invalid")
        all_findings = list(self.iter_findings())
        finding_ids = [finding.finding_id for finding in all_findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise CampaignResearchError("finding IDs must be unique across the pack")
        source_ids = set(ids)
        referenced_ids = {source_id for finding in all_findings for source_id in finding.source_ids}
        if not referenced_ids.issubset(source_ids):
            raise CampaignResearchError("finding references an unknown source")
        if set(ids) != referenced_ids:
            raise CampaignResearchError("every retained source must support a finding")
        for finding in all_findings:
            valid_from = _parse_iso8601(finding.valid_from, "finding.valid_from")
            valid_until = _parse_iso8601(finding.valid_until, "finding.valid_until")
            if valid_from > generated or valid_until <= generated:
                raise CampaignResearchError("finding must be valid when the pack is generated")
            cited_sources = [
                source for source in self.sources if source.source_id in finding.source_ids
            ]
            if finding.kind == "fact" and any(
                source.evidence_tier == "community" for source in cited_sources
            ):
                raise CampaignResearchError("facts cannot rely on community evidence")
            if finding.kind == "negative_evidence" and any(
                source.evidence_tier == "community" for source in cited_sources
            ):
                raise CampaignResearchError("negative evidence cannot rely on community evidence")
        if self.status == "unavailable":
            if (
                self.sources
                or all_findings
                or self.market_summary is not None
                or self.confidence != 0
            ):
                raise CampaignResearchError(
                    "unavailable research must contain no evidence and zero confidence"
                )
        elif not self.sources or not all_findings:
            raise CampaignResearchError("available research requires sources and cited findings")
        elif self.status == "complete":
            critical_sections = {
                "audience_vocabulary",
                "audience_objections",
                "expected_proof",
            }
            populated = {section.name for section in self.sections if section.findings}
            if len(self.sources) < MIN_SOURCES_FOR_COMPLETE:
                raise CampaignResearchError(
                    "complete research requires at least "
                    f"{MIN_SOURCES_FOR_COMPLETE} retained sources"
                )
            if self.market_summary is None or not critical_sections.issubset(populated):
                raise CampaignResearchError(
                    "complete research requires market summary and critical sections"
                )

    def iter_findings(self) -> tuple[CitedFinding, ...]:
        entries: list[CitedFinding] = []
        if self.market_summary is not None:
            entries.append(self.market_summary)
        for section in self.sections:
            entries.extend(section.findings)
        return tuple(entries)

    def section(self, name: str) -> tuple[CitedFinding, ...]:
        for section in self.sections:
            if section.name == name:
                return section.findings
        raise CampaignResearchError("unknown research section")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "research_policy_version": self.research_policy_version,
            "campaign_fingerprint": self.campaign_fingerprint,
            "generated_at": self.generated_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "market_summary": self.market_summary.to_dict() if self.market_summary else None,
            "sections": [section.to_dict() for section in self.sections],
            "sources": [source.to_dict() for source in self.sources],
            "confidence": self.confidence,
        }


def research_content_digest(pack: CampaignResearchPack) -> str:
    """Canonical SHA-256 of normalized research content, excluding volatile audit times.

    ``generated_at``, ``expires_at`` and a source's ``accessed_at`` govern cache
    validity and audit trails, but do not alter the underlying retained research.
    The digest is useful for tracking editorial variants against exactly the same
    market context despite a cache refresh with new timestamps.
    """

    def finding_value(finding: CitedFinding) -> dict[str, Any]:
        return finding.to_dict()

    normalized = {
        "schema_version": pack.schema_version,
        "research_policy_version": pack.research_policy_version,
        "campaign_fingerprint": pack.campaign_fingerprint,
        "status": pack.status,
        "confidence": pack.confidence,
        "market_summary": finding_value(pack.market_summary) if pack.market_summary else None,
        "sections": [
            {
                "schema_version": section.schema_version,
                "name": section.name,
                "findings": [
                    finding_value(finding)
                    for finding in sorted(section.findings, key=lambda x: x.finding_id)
                ],
            }
            for section in sorted(pack.sections, key=lambda x: x.name)
        ],
        "sources": [
            {
                "schema_version": source.schema_version,
                "source_id": source.source_id,
                "url": source.url,
                "title": source.title,
                "publisher": source.publisher,
                "published_at": source.published_at,
                "source_type": source.source_type,
                "evidence_tier": source.evidence_tier,
                "evidence_summary": source.evidence_summary,
            }
            for source in sorted(pack.sources, key=lambda x: x.source_id)
        ],
    }
    encoded = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class CampaignResearchClient(Protocol):
    """Bounded adapter boundary; implementations own DNS/redirect safety and I/O."""

    async def research(
        self, *, campaign: Mapping[str, Any], policy_version: str
    ) -> Mapping[str, Any]: ...


def campaign_fingerprint(
    campaign: Mapping[str, Any], *, research_policy_version: str = RESEARCH_POLICY_VERSION
) -> str:
    """Hash only sanitized, campaign-relevant values plus the policy version."""
    if not isinstance(campaign, Mapping):
        raise CampaignResearchError("campaign must be an object")
    policy = _require_text(research_policy_version, "research_policy_version", maximum=16)
    if not _VERSION_RE.fullmatch(policy):
        raise CampaignResearchError("research_policy_version must be a numeric version")
    brief = sanitize_campaign(dict(campaign))
    # List ordering is a UI artefact, not a research semantic.  Stable de-duping
    # makes logically equivalent briefs reuse the same pack.
    canonical_brief = {
        key: sorted(set(value)) if isinstance(value, list) else value
        for key, value in brief.items()
    }
    payload = {"campaign": canonical_brief, "research_policy_version": policy}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _empty_sections() -> tuple[CampaignResearchSection, ...]:
    return tuple(
        CampaignResearchSection(schema_version=SCHEMA_VERSION, name=name, findings=())
        for name in _SECTION_NAMES
    )


def unavailable_research_pack(
    *,
    campaign_fingerprint_value: str,
    generated_at: str,
    expires_at: str,
    research_policy_version: str = RESEARCH_POLICY_VERSION,
) -> CampaignResearchPack:
    """Create the explicit no-research state; callers must use brief fallback."""
    return CampaignResearchPack(
        schema_version=SCHEMA_VERSION,
        research_policy_version=research_policy_version,
        campaign_fingerprint=campaign_fingerprint_value,
        generated_at=generated_at,
        expires_at=expires_at,
        status="unavailable",
        market_summary=None,
        sections=_empty_sections(),
        sources=(),
        confidence=0.0,
    )


def _finding_signature(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).casefold()
    return " ".join(_TOKEN_RE.findall(normalized))


def _same_finding(left: CitedFinding, right: CitedFinding) -> bool:
    if left.kind != right.kind or left.scope != right.scope:
        return False
    a, b = _finding_signature(left.text), _finding_signature(right.text)
    if a == b:
        return True
    if not a or not b or min(len(a), len(b)) < 20:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.85


def _deduplicate_findings(
    findings: Sequence[CitedFinding], source_id_map: Mapping[str, str]
) -> tuple[CitedFinding, ...]:
    """Merge exact/near duplicates deterministically, retaining all citations."""
    normalized = [
        CitedFinding(
            schema_version=finding.schema_version,
            finding_id=finding.finding_id,
            kind=finding.kind,
            scope=finding.scope,
            text=finding.text,
            source_ids=tuple(
                source_id_map.get(source_id, source_id) for source_id in finding.source_ids
            ),
            confidence=finding.confidence,
            valid_from=finding.valid_from,
            valid_until=finding.valid_until,
        )
        for finding in findings
    ]
    ordered = sorted(
        normalized, key=lambda finding: (_finding_signature(finding.text), finding.text)
    )
    merged: list[CitedFinding] = []
    for finding in ordered:
        for index, existing in enumerate(merged):
            if _same_finding(existing, finding):
                text = min(
                    existing.text, finding.text, key=lambda item: (_finding_signature(item), item)
                )
                merged[index] = CitedFinding(
                    schema_version=min(existing.schema_version, finding.schema_version),
                    finding_id=min(existing.finding_id, finding.finding_id),
                    kind=existing.kind,
                    scope=existing.scope,
                    text=text,
                    source_ids=tuple(sorted(set(existing.source_ids) | set(finding.source_ids))),
                    confidence=min(existing.confidence, finding.confidence),
                    valid_from=min(existing.valid_from, finding.valid_from),
                    valid_until=min(existing.valid_until, finding.valid_until),
                )
                break
        else:
            merged.append(finding)
    return tuple(merged)


def _deduplicate_sources(
    sources: Sequence[CampaignResearchSource],
) -> tuple[tuple[CampaignResearchSource, ...], dict[str, str]]:
    """Keep one source per canonical URL and map old IDs to its stable ID."""
    by_url: dict[str, list[CampaignResearchSource]] = defaultdict(list)
    for source in sources:
        by_url[source.url].append(source)
    kept: list[CampaignResearchSource] = []
    aliases: dict[str, str] = {}
    for url in sorted(by_url):
        winner = min(by_url[url], key=_source_sort_key)
        kept.append(winner)
        for source in by_url[url]:
            aliases[source.source_id] = winner.source_id
    return tuple(sorted(kept, key=lambda source: source.source_id)), aliases


def parse_campaign_research_pack(raw: Mapping[str, Any]) -> CampaignResearchPack:
    """Strictly parse provider-shaped data, canonicalising deterministic duplicates.

    Unknown keys are errors.  URL and near-finding duplicates are the limited
    exception: they are normalised before final cross-reference validation so a
    noisy provider cannot cause duplicate evidence to reach a prompt.
    """
    if not isinstance(raw, Mapping):
        raise CampaignResearchError("research pack must be an object")
    allowed = frozenset(
        {
            "schema_version",
            "research_policy_version",
            "campaign_fingerprint",
            "generated_at",
            "expires_at",
            "status",
            "market_summary",
            "sections",
            "sources",
            "confidence",
        }
    )
    _require_exact_keys(raw, allowed, "pack")
    raw_sources = raw["sources"]
    if not isinstance(raw_sources, list):
        raise CampaignResearchError("pack.sources must be an array")
    if len(raw_sources) > MAX_SOURCES * 2:
        raise CampaignResearchError("pack.sources exceeds duplicate intake limit")
    parsed_sources = tuple(CampaignResearchSource.from_mapping(item) for item in raw_sources)
    if len({source.source_id for source in parsed_sources}) != len(parsed_sources):
        raise CampaignResearchError("input source IDs must be unique")
    sources, aliases = _deduplicate_sources(parsed_sources)
    raw_sections = raw["sections"]
    if not isinstance(raw_sections, list) or len(raw_sections) != len(_SECTION_NAMES):
        raise CampaignResearchError("pack.sections must contain every section")
    parsed_sections: list[CampaignResearchSection] = []
    for item in raw_sections:
        if not isinstance(item, Mapping):
            raise CampaignResearchError("section must be an object")
        _require_exact_keys(item, frozenset({"schema_version", "name", "findings"}), "section")
        raw_findings = item["findings"]
        if not isinstance(raw_findings, list) or len(raw_findings) > MAX_FINDINGS_PER_SECTION * 2:
            raise CampaignResearchError("section.findings must be a bounded array")
        findings = tuple(CitedFinding.from_mapping(finding) for finding in raw_findings)
        parsed_sections.append(
            CampaignResearchSection(
                schema_version=item["schema_version"],
                name=item["name"],
                findings=_deduplicate_findings(findings, aliases),
            )
        )
    summary_raw = raw["market_summary"]
    summary = CitedFinding.from_mapping(summary_raw) if summary_raw is not None else None
    if summary is not None:
        summary = _deduplicate_findings((summary,), aliases)[0]
    return CampaignResearchPack(
        schema_version=raw["schema_version"],
        research_policy_version=raw["research_policy_version"],
        campaign_fingerprint=raw["campaign_fingerprint"],
        generated_at=raw["generated_at"],
        expires_at=raw["expires_at"],
        status=raw["status"],
        market_summary=summary,
        sections=tuple(parsed_sections),
        sources=sources,
        confidence=raw["confidence"],
    )


def is_reusable_research_pack(
    pack: CampaignResearchPack | None,
    *,
    campaign_fingerprint_value: str,
    now: datetime,
    research_policy_version: str = RESEARCH_POLICY_VERSION,
) -> bool:
    """Pure cache decision; unavailable results intentionally never suppress a retry."""
    if pack is None or now.tzinfo is None or now.utcoffset() is None:
        return False
    return (
        pack.status in {"complete", "partial"}
        and pack.campaign_fingerprint == campaign_fingerprint_value
        and pack.research_policy_version == research_policy_version
        and _parse_iso8601(pack.expires_at, "pack.expires_at") > now.astimezone(UTC)
        and all(
            _parse_iso8601(finding.valid_until, "finding.valid_until") > now.astimezone(UTC)
            for finding in pack.iter_findings()
        )
    )


def reusable_cached_pack(
    cached: Sequence[CampaignResearchPack],
    *,
    campaign_fingerprint_value: str,
    now: datetime,
    research_policy_version: str = RESEARCH_POLICY_VERSION,
) -> CampaignResearchPack | None:
    """Select the newest valid compatible item independently of cache storage."""
    candidates = [
        pack
        for pack in cached
        if is_reusable_research_pack(
            pack,
            campaign_fingerprint_value=campaign_fingerprint_value,
            now=now,
            research_policy_version=research_policy_version,
        )
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda pack: (
            _parse_iso8601(pack.generated_at, "pack.generated_at"),
            research_content_digest(pack),
        ),
    )


def _safe_prompt_text(text: str, maximum: int) -> str:
    # JSON encoding keeps this material data; sanitisation also neutralises our
    # known prompt fence forms should a caller put this JSON in a fenced prompt.
    return sanitize_text(text, max_len=maximum)


def _prompt_source(source: CampaignResearchSource) -> dict[str, str]:
    result = {
        "source_id": source.source_id,
        "title": _safe_prompt_text(source.title, 100),
        "source_type": source.source_type,
    }
    if source.publisher:
        result["publisher"] = _safe_prompt_text(source.publisher, 80)
    return result


def _prompt_finding(finding: CitedFinding) -> dict[str, Any]:
    return {
        "finding_id": finding.finding_id,
        "kind": finding.kind,
        "scope": finding.scope,
        "text": _safe_prompt_text(finding.text, 180),
        "source_ids": list(finding.source_ids),
        "confidence": finding.confidence,
        "valid_until": finding.valid_until,
    }


def _json_compact(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def serialize_research_for_prompt(
    pack: CampaignResearchPack,
    *,
    max_chars: int = MAX_PROMPT_CHARS,
    max_sources: int = MAX_PROMPT_SOURCES,
    max_findings_per_section: int = MAX_PROMPT_FINDINGS_PER_SECTION,
) -> str:
    """Serialize an available pack under strict source/finding/character budgets.

    Findings are selected in a fixed editorial priority.  A source is included
    only if one of the surviving findings cites it.  If the smallest valid
    representation cannot fit, fail closed instead of returning malformed JSON.
    """
    if pack.status not in {"complete", "partial"}:
        raise CampaignResearchError("unavailable research cannot be serialized as evidence")
    if (
        not 256 <= max_chars <= MAX_PROMPT_CHARS
        or not 1 <= max_sources <= MAX_PROMPT_SOURCES
        or not 1 <= max_findings_per_section <= MAX_PROMPT_FINDINGS_PER_SECTION
    ):
        raise CampaignResearchError("prompt budgets are too small")
    source_by_id = {source.source_id: source for source in pack.sources}
    sections: dict[str, list[dict[str, Any]]] = {}
    selected_ids: set[str] = set()
    base: dict[str, Any] = {
        "research": {
            "schema_version": pack.schema_version,
            "policy_version": pack.research_policy_version,
            "status": pack.status,
            "confidence": pack.confidence,
            "scope": "market_context_only_not_video_evidence",
            "market_summary": None,
            "sections": sections,
            "sources": [],
        }
    }

    def fits(candidate: CitedFinding, section_name: str | None) -> bool:
        needed = selected_ids | set(candidate.source_ids)
        if len(needed) > max_sources:
            return False
        target: Any
        if section_name is None:
            target = base["research"]
            target["market_summary"] = _prompt_finding(candidate)
        else:
            target = sections.setdefault(section_name, [])
            target.append(_prompt_finding(candidate))
        base["research"]["sources"] = [
            _prompt_source(source_by_id[source_id]) for source_id in sorted(needed)
        ]
        rendered = _json_compact(base)
        if len(rendered) <= max_chars:
            selected_ids.update(candidate.source_ids)
            return True
        if section_name is None:
            target["market_summary"] = None
        else:
            target.pop()
            if not target:
                sections.pop(section_name)
        base["research"]["sources"] = [
            _prompt_source(source_by_id[source_id]) for source_id in sorted(selected_ids)
        ]
        return False

    if pack.market_summary is not None:
        fits(pack.market_summary, None)
    for name in _PRIORITY_SECTIONS:
        count = 0
        for finding in pack.section(name):
            if count >= max_findings_per_section:
                break
            if fits(finding, name):
                count += 1
    rendered = _json_compact(base)
    if not selected_ids or len(rendered) > max_chars:
        raise CampaignResearchError("prompt budget cannot fit a cited research context")
    return rendered


def serialize_brief_fallback(campaign: Mapping[str, Any], *, max_chars: int = 1_200) -> str:
    """Explicitly represent the safe ordinary-brief fallback as compact JSON."""
    if not isinstance(campaign, Mapping):
        raise CampaignResearchError("campaign must be an object")
    if not 128 <= max_chars <= 1_200:
        raise CampaignResearchError("fallback budget is outside the hard limit")
    payload = {
        "research": {"status": "unavailable", "fallback": "campaign_brief_only"},
        "campaign_brief": sanitize_campaign(dict(campaign)),
    }
    rendered = _json_compact(payload)
    if len(rendered) > max_chars:
        raise CampaignResearchError("fallback brief exceeds prompt budget")
    return rendered


def research_context_for_prompt(
    campaign: Mapping[str, Any],
    pack: CampaignResearchPack | None,
    *,
    now: datetime,
    research_policy_version: str = RESEARCH_POLICY_VERSION,
    max_chars: int = MAX_PROMPT_CHARS,
) -> str:
    """Use research only while a compatible pack is valid; otherwise use the brief."""
    fingerprint = campaign_fingerprint(campaign, research_policy_version=research_policy_version)
    if is_reusable_research_pack(
        pack,
        campaign_fingerprint_value=fingerprint,
        now=now,
        research_policy_version=research_policy_version,
    ):
        assert pack is not None
        return serialize_research_for_prompt(pack, max_chars=max_chars)
    return serialize_brief_fallback(campaign, max_chars=min(max_chars, 1_200))
