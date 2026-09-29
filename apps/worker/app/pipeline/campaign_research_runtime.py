"""Bounded, injectable campaign-research orchestration.

This is deliberately a *provider boundary*, not an HTTP implementation.  The
search, fetch, synthesis and cache clients are injected, so this module is
testable without making network calls.  Every artefact leaving the boundary is
validated before it can become campaign context.
"""

from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

from ..safety import sanitize_campaign, sanitize_text
from .campaign_research import (
    CampaignResearchError,
    CampaignResearchPack,
    campaign_fingerprint,
    canonical_public_url,
    is_reusable_research_pack,
    parse_campaign_research_pack,
    unavailable_research_pack,
)

QueryKind = Literal[
    "audience_language",
    "pains_objections",
    "proof_expectations",
    "competitor_angles",
    "saturated_claims",
    "platform_context",
]
FailureStage = Literal["cache", "search", "fetch", "validation", "synthesis", "parse"]
_KINDS: tuple[QueryKind, ...] = (
    "audience_language",
    "pains_objections",
    "proof_expectations",
    "competitor_angles",
    "saturated_claims",
    "platform_context",
)
_ALLOWED_MIME_TYPES = frozenset({"text/html", "text/plain", "application/json"})
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_LONG_TOKEN_RE = re.compile(r"\b(?:[a-f0-9]{32,}|[a-z0-9_-]{20,})\b", re.IGNORECASE)
_SKIPPED_HTML_TAGS = frozenset({"script", "style", "noscript", "template", "svg"})


class CampaignResearchRuntimeError(CampaignResearchError):
    """An untrusted provider value broke the runtime boundary."""


@dataclass(frozen=True)
class CampaignResearchPolicy:
    """Closed local limits; a provider must not be able to enlarge these."""

    version: str = "1.0"
    query_count: int = 6
    results_per_query: int = 3
    retained_sources: int = 15
    fetches: int = 15
    max_snippet_chars: int = 500
    max_body_chars: int = 12_000
    max_bytes: int = 200_000
    timeout_seconds: float = 10.0
    max_redirects: int = 3
    ttl_days: int = 14

    def __post_init__(self) -> None:
        if (
            self.version != "1.0"
            or not 4 <= self.query_count <= 6
            or not 1 <= self.results_per_query <= 5
            or not 1 <= self.retained_sources <= 15
            or not 1 <= self.fetches <= 15
            or not 1 <= self.max_snippet_chars <= 500
            or not 1 <= self.max_body_chars <= 12_000
            or not 1 <= self.max_bytes <= 200_000
            or not 0 < self.timeout_seconds <= 20
            or not 0 <= self.max_redirects <= 3
            or not 1 <= self.ttl_days <= 30
        ):
            raise ValueError("research policy exceeds hard limits")


@dataclass(frozen=True)
class ResearchQuery:
    kind: QueryKind
    text: str

    def __post_init__(self) -> None:
        if self.kind not in _KINDS or not isinstance(self.text, str):
            raise CampaignResearchRuntimeError("invalid research query")
        text = sanitize_text(self.text, max_len=240)
        if not text or len(text) > 240:
            raise CampaignResearchRuntimeError("invalid bounded research query")
        object.__setattr__(self, "text", text)


@dataclass(frozen=True)
class CampaignResearchQueryPlan:
    policy_version: str
    fingerprint: str
    queries: tuple[ResearchQuery, ...]

    def __post_init__(self) -> None:
        if self.policy_version != "1.0" or not re.fullmatch(r"[a-f0-9]{64}", self.fingerprint):
            raise CampaignResearchRuntimeError("invalid query plan identity")
        if not isinstance(self.queries, tuple) or not 4 <= len(self.queries) <= 6:
            raise CampaignResearchRuntimeError("invalid query plan")
        if any(not isinstance(query, ResearchQuery) for query in self.queries):
            raise CampaignResearchRuntimeError("invalid query plan values")
        if len({query.kind for query in self.queries}) != len(self.queries):
            raise CampaignResearchRuntimeError("query kinds must be unique")

    @property
    def digest(self) -> str:
        payload = {
            "policy_version": self.policy_version,
            "fingerprint": self.fingerprint,
            "queries": [{"kind": item.kind, "text": item.text} for item in self.queries],
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()


@dataclass(frozen=True)
class SearchResult:
    """A bounded result only; snippets never cross into the synthesis prompt."""

    url: str
    title: str
    snippet: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", canonical_public_url(self.url))
        if not isinstance(self.title, str) or not isinstance(self.snippet, str):
            raise CampaignResearchRuntimeError("invalid search result")
        title = sanitize_text(self.title, max_len=180)
        snippet = sanitize_text(self.snippet, max_len=500)
        if not title:
            raise CampaignResearchRuntimeError("search title cannot be empty")
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "snippet", snippet)


@dataclass(frozen=True)
class FetchHop:
    """One DNS-pinned HTTP hop, including the actual connected peer IP.

    A production adapter must populate ``connected_ip`` from the transport
    socket, not from another DNS lookup.  Keeping it distinct from
    ``resolved_ips`` lets this provider-independent boundary reject DNS rebinding
    and redirect hops whose peer was never authorised.
    """

    url: str
    resolved_ips: tuple[str, ...]
    connected_ip: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", canonical_public_url(self.url))
        if not isinstance(self.resolved_ips, tuple) or not self.resolved_ips:
            raise CampaignResearchRuntimeError("every fetch hop requires resolved public IPs")
        parsed: list[str] = []
        for value in self.resolved_ips:
            if not isinstance(value, str):
                raise CampaignResearchRuntimeError("resolved IP must be text")
            try:
                address = ipaddress.ip_address(value)
            except ValueError as exc:
                raise CampaignResearchRuntimeError("resolved IP is malformed") from exc
            if not address.is_global:
                raise CampaignResearchRuntimeError("resolved IP is not public")
            parsed.append(address.compressed)
        resolved = tuple(sorted(set(parsed)))
        object.__setattr__(self, "resolved_ips", resolved)
        if not isinstance(self.connected_ip, str):
            raise CampaignResearchRuntimeError("connected IP must be text")
        try:
            connected = ipaddress.ip_address(self.connected_ip)
        except ValueError as exc:
            raise CampaignResearchRuntimeError("connected IP is malformed") from exc
        if not connected.is_global:
            raise CampaignResearchRuntimeError("connected IP is not public")
        if connected.compressed not in resolved:
            raise CampaignResearchRuntimeError("connected IP was not in the pinned DNS result")
        object.__setattr__(self, "connected_ip", connected.compressed)


@dataclass(frozen=True)
class FetchedDocument:
    """Raw provider document retained only until the single synthesis call.

    ``hops`` is intentionally not a flat list of addresses.  It binds every
    redirect URL to its actual DNS result, preventing an adapter from proving
    only the first host while following a private redirect later.
    """

    requested_url: str
    final_url: str
    title: str
    mime_type: str
    body: str
    declared_bytes: int
    hops: tuple[FetchHop, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_url", canonical_public_url(self.requested_url))
        object.__setattr__(self, "final_url", canonical_public_url(self.final_url))
        if (
            not isinstance(self.title, str)
            or not isinstance(self.mime_type, str)
            or not isinstance(self.body, str)
        ):
            raise CampaignResearchRuntimeError("fetched document text fields are invalid")
        if isinstance(self.declared_bytes, bool) or not isinstance(self.declared_bytes, int):
            raise CampaignResearchRuntimeError("declared bytes must be an integer")
        if (
            not isinstance(self.hops, tuple)
            or not self.hops
            or any(not isinstance(hop, FetchHop) for hop in self.hops)
        ):
            raise CampaignResearchRuntimeError("fetched document requires immutable fetch hops")


class _VisibleHTMLText(HTMLParser):
    """Small deterministic extractor; active/hidden document nodes never reach synthesis."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in _SKIPPED_HTML_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in _SKIPPED_HTML_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


@dataclass(frozen=True)
class NormalizedResearchDocument:
    """Prompt-safe evidence projection; raw HTTP bodies and DNS traces are excluded."""

    url: str
    title: str
    content: str
    content_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", canonical_public_url(self.url))
        if not isinstance(self.title, str) or not self.title or len(self.title) > 180:
            raise CampaignResearchRuntimeError("normalized document title is invalid")
        if not isinstance(self.content, str) or not self.content or len(self.content) > 12_000:
            raise CampaignResearchRuntimeError("normalized document content is invalid")
        if not isinstance(self.content_digest, str) or not re.fullmatch(
            r"[a-f0-9]{64}", self.content_digest
        ):
            raise CampaignResearchRuntimeError("normalized document digest is invalid")


@dataclass(frozen=True)
class ResearchFailure:
    stage: FailureStage
    code: str
    subject: str | None = None

    def __post_init__(self) -> None:
        if self.stage not in {"cache", "search", "fetch", "validation", "synthesis", "parse"}:
            raise CampaignResearchRuntimeError("unknown failure stage")
        if not isinstance(self.code, str) or not self.code or len(self.code) > 80:
            raise CampaignResearchRuntimeError("invalid failure code")
        if self.subject is not None and (
            not isinstance(self.subject, str) or len(self.subject) > 240
        ):
            raise CampaignResearchRuntimeError("invalid failure subject")


@dataclass(frozen=True)
class ResearchCounters:
    query_calls: int = 0
    search_results_seen: int = 0
    fetch_calls: int = 0
    safe_documents: int = 0
    synthesis_calls: int = 0


@dataclass(frozen=True)
class ResearchRunTelemetry:
    counters: ResearchCounters
    failures: tuple[ResearchFailure, ...] = ()
    cache_hit: bool = False


DEFAULT_POLICY = CampaignResearchPolicy()


class SearchClient(Protocol):
    async def search(
        self, query: ResearchQuery, *, limit: int, timeout: float
    ) -> Sequence[SearchResult]: ...


class FetchClient(Protocol):
    async def fetch(
        self, url: str, *, timeout: float, max_bytes: int, max_redirects: int
    ) -> FetchedDocument: ...


class SynthesisClient(Protocol):
    async def synthesize(
        self,
        *,
        campaign: Mapping[str, Any],
        sources: Sequence[NormalizedResearchDocument],
        policy: CampaignResearchPolicy,
    ) -> Mapping[str, Any]: ...


class ResearchCache(Protocol):
    async def get(self, key: str) -> CampaignResearchPack | None: ...

    async def put(self, key: str, pack: CampaignResearchPack) -> None: ...


def _query_safe_value(value: str, maximum: int) -> str:
    """Do not place addresses, identifiers or credentials in provider queries."""
    value = _URL_RE.sub(" ", value)
    value = _EMAIL_RE.sub(" ", value)
    value = _LONG_TOKEN_RE.sub(" ", value)
    return sanitize_text(value, max_len=maximum)


def build_query_plan(
    campaign: Mapping[str, Any], policy: CampaignResearchPolicy = DEFAULT_POLICY
) -> CampaignResearchQueryPlan:
    if not isinstance(campaign, Mapping):
        raise CampaignResearchRuntimeError("campaign must be an object")
    sanitized = sanitize_campaign(dict(campaign))
    fingerprint = campaign_fingerprint(sanitized, research_policy_version=policy.version)
    base = " ".join(
        item
        for item in (
            _query_safe_value(sanitized["niche"], 100),
            _query_safe_value(sanitized["audience"], 100),
            _query_safe_value(sanitized["goal"], 100),
        )
        if item
    )
    base = base[:180].strip() or "market audience"
    queries = tuple(
        ResearchQuery(kind=kind, text=f"{base} {kind.replace('_', ' ')}")
        for kind in _KINDS[: policy.query_count]
    )
    return CampaignResearchQueryPlan(policy.version, fingerprint, queries)


def _failure_code(error: Exception) -> str:
    """Stable, non-sensitive observability code; never include provider bodies."""
    name = type(error).__name__.lower()
    return re.sub(r"[^a-z0-9_]+", "_", name)[:80] or "unknown_error"


def _url_subject(value: str) -> str:
    """Stable telemetry identity without query strings, paths, or provider tokens."""
    host = urlsplit(value).hostname or "unknown"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{host}:{digest}"[:240]


def validate_fetched_document(
    document: FetchedDocument,
    *,
    requested_url: str,
    policy: CampaignResearchPolicy = DEFAULT_POLICY,
) -> FetchedDocument:
    """Validate DNS/redirect, MIME and byte contracts before synthesis."""
    if not isinstance(document, FetchedDocument):
        raise CampaignResearchRuntimeError("fetch client returned an invalid document")
    requested = canonical_public_url(requested_url)
    if document.requested_url != requested or document.hops[0].url != requested:
        raise CampaignResearchRuntimeError("fetch trace does not start at requested URL")
    if document.hops[-1].url != document.final_url:
        raise CampaignResearchRuntimeError("fetch trace does not end at final URL")
    if len(document.hops) - 1 > policy.max_redirects:
        raise CampaignResearchRuntimeError("too many redirects")
    mime = document.mime_type.split(";", 1)[0].strip().lower()
    if mime not in _ALLOWED_MIME_TYPES:
        raise CampaignResearchRuntimeError("unsupported MIME type")
    actual_bytes = len(document.body.encode("utf-8"))
    if document.declared_bytes < 0 or document.declared_bytes > policy.max_bytes:
        raise CampaignResearchRuntimeError("declared body exceeds byte limit")
    if actual_bytes > policy.max_bytes or actual_bytes > document.declared_bytes:
        raise CampaignResearchRuntimeError("actual body exceeds declared byte limit")
    if len(document.body) > policy.max_body_chars:
        raise CampaignResearchRuntimeError("body exceeds character limit")
    title = sanitize_text(document.title, max_len=180)
    if not title:
        raise CampaignResearchRuntimeError("fetched title cannot be empty")
    return FetchedDocument(
        requested_url=requested,
        final_url=document.final_url,
        title=title,
        mime_type=mime,
        body=document.body,
        declared_bytes=document.declared_bytes,
        hops=document.hops,
    )


def normalize_fetched_document(
    document: FetchedDocument,
    *,
    policy: CampaignResearchPolicy = DEFAULT_POLICY,
) -> NormalizedResearchDocument:
    """Project a validated fetch into inert text before any model/provider sees it."""
    mime = document.mime_type.split(";", 1)[0].strip().lower()
    body = document.body
    if mime == "text/html":
        parser = _VisibleHTMLText()
        try:
            parser.feed(body)
            parser.close()
        except (AssertionError, ValueError) as exc:
            raise CampaignResearchRuntimeError("HTML extraction failed") from exc
        body = " ".join(parser.parts)
    else:
        body = html.unescape(body)
    content = sanitize_text(body, max_len=policy.max_body_chars)
    if not content:
        raise CampaignResearchRuntimeError("document has no safe visible content")
    return NormalizedResearchDocument(
        url=document.final_url,
        title=sanitize_text(document.title, max_len=180),
        content=content,
        content_digest=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


def _now_iso(now: datetime) -> str:
    if now.tzinfo is None or now.utcoffset() is None:
        raise CampaignResearchRuntimeError("now must include a timezone")
    return now.astimezone(UTC).isoformat()


def _pack_generated_no_later_than(pack: CampaignResearchPack, now: datetime) -> bool:
    """The contract parser already established a timezone-aware ISO instant."""
    generated = datetime.fromisoformat(pack.generated_at.replace("Z", "+00:00")).astimezone(UTC)
    return generated <= now.astimezone(UTC)


class CampaignResearchCoordinator:
    """Run bounded research once, yielding either a valid pack or explicit fallback."""

    def __init__(
        self,
        search: SearchClient,
        fetch: FetchClient,
        synthesis: SynthesisClient,
        cache: ResearchCache,
        policy: CampaignResearchPolicy = DEFAULT_POLICY,
    ) -> None:
        self.search = search
        self.fetch = fetch
        self.synthesis = synthesis
        self.cache = cache
        self.policy = policy
        self.last_telemetry = ResearchRunTelemetry(ResearchCounters())

    async def prepare(
        self, campaign: Mapping[str, Any], now: datetime, force_refresh: bool = False
    ) -> CampaignResearchPack:
        # Validate once at ingress.  A naive clock must never silently acquire
        # the worker host's local timezone and change cache semantics.
        _now_iso(now)
        plan = build_query_plan(campaign, self.policy)
        counters = ResearchCounters()
        failures: list[ResearchFailure] = []

        if not force_refresh:
            try:
                cached = await self.cache.get(plan.digest)
            except Exception as error:
                failures.append(ResearchFailure("cache", _failure_code(error)))
            else:
                if is_reusable_research_pack(
                    cached,
                    campaign_fingerprint_value=plan.fingerprint,
                    now=now,
                    research_policy_version=self.policy.version,
                ) and _pack_generated_no_later_than(cached, now):
                    self.last_telemetry = ResearchRunTelemetry(
                        counters, tuple(failures), cache_hit=True
                    )
                    return cached

        results: list[SearchResult] = []
        for query in plan.queries:
            counters = ResearchCounters(
                query_calls=counters.query_calls + 1,
                search_results_seen=counters.search_results_seen,
                fetch_calls=counters.fetch_calls,
                safe_documents=counters.safe_documents,
                synthesis_calls=counters.synthesis_calls,
            )
            try:
                response = await self.search.search(
                    query, limit=self.policy.results_per_query, timeout=self.policy.timeout_seconds
                )
                if isinstance(response, (str, bytes)) or not isinstance(response, Sequence):
                    raise CampaignResearchRuntimeError("search client returned a non-sequence")
                bounded = response[: self.policy.results_per_query]
                safe_results: list[SearchResult] = []
                for item in bounded:
                    if not isinstance(item, SearchResult):
                        raise CampaignResearchRuntimeError(
                            "search client returned an invalid result"
                        )
                    safe_results.append(
                        SearchResult(
                            url=item.url,
                            title=item.title,
                            snippet=sanitize_text(
                                item.snippet, max_len=self.policy.max_snippet_chars
                            ),
                        )
                    )
                results.extend(safe_results)
                counters = ResearchCounters(
                    query_calls=counters.query_calls,
                    search_results_seen=counters.search_results_seen + len(safe_results),
                    fetch_calls=counters.fetch_calls,
                    safe_documents=counters.safe_documents,
                    synthesis_calls=counters.synthesis_calls,
                )
            except Exception as error:
                failures.append(ResearchFailure("search", _failure_code(error), query.kind))

        urls: list[str] = []
        for result in results:
            if result.url not in urls:
                urls.append(result.url)
            if len(urls) >= min(self.policy.fetches, self.policy.retained_sources):
                break

        documents: list[NormalizedResearchDocument] = []
        final_urls: set[str] = set()
        for url in urls:
            counters = ResearchCounters(
                query_calls=counters.query_calls,
                search_results_seen=counters.search_results_seen,
                fetch_calls=counters.fetch_calls + 1,
                safe_documents=counters.safe_documents,
                synthesis_calls=counters.synthesis_calls,
            )
            try:
                document = await self.fetch.fetch(
                    url,
                    timeout=self.policy.timeout_seconds,
                    max_bytes=self.policy.max_bytes,
                    max_redirects=self.policy.max_redirects,
                )
                safe_fetch = validate_fetched_document(
                    document, requested_url=url, policy=self.policy
                )
                safe_document = normalize_fetched_document(safe_fetch, policy=self.policy)
                if safe_document.url not in final_urls:
                    final_urls.add(safe_document.url)
                    documents.append(safe_document)
                    counters = ResearchCounters(
                        query_calls=counters.query_calls,
                        search_results_seen=counters.search_results_seen,
                        fetch_calls=counters.fetch_calls,
                        safe_documents=counters.safe_documents + 1,
                        synthesis_calls=counters.synthesis_calls,
                    )
            except CampaignResearchError as error:
                failures.append(
                    ResearchFailure("validation", _failure_code(error), _url_subject(url))
                )
            except Exception as error:
                failures.append(ResearchFailure("fetch", _failure_code(error), _url_subject(url)))

        if not documents:
            return self._unavailable(plan, now, counters, failures)

        counters = ResearchCounters(
            query_calls=counters.query_calls,
            search_results_seen=counters.search_results_seen,
            fetch_calls=counters.fetch_calls,
            safe_documents=counters.safe_documents,
            synthesis_calls=counters.synthesis_calls + 1,
        )
        try:
            raw_pack = await self.synthesis.synthesize(
                campaign=sanitize_campaign(dict(campaign)),
                sources=tuple(documents),
                policy=self.policy,
            )
        except Exception as error:
            failures.append(ResearchFailure("synthesis", _failure_code(error)))
            return self._unavailable(plan, now, counters, failures)
        try:
            pack = parse_campaign_research_pack(raw_pack)
            safe_urls = {document.url for document in documents}
            if (
                pack.status == "unavailable"
                or len(pack.sources) > self.policy.retained_sources
                or not {source.url for source in pack.sources}.issubset(safe_urls)
                or pack.campaign_fingerprint != plan.fingerprint
                or pack.research_policy_version != self.policy.version
                or not _pack_generated_no_later_than(pack, now)
                or not is_reusable_research_pack(
                    pack,
                    campaign_fingerprint_value=plan.fingerprint,
                    now=now,
                    research_policy_version=self.policy.version,
                )
            ):
                raise CampaignResearchRuntimeError("synthesis pack violates runtime contract")
        except Exception as error:
            failures.append(ResearchFailure("parse", _failure_code(error)))
            return self._unavailable(plan, now, counters, failures)

        try:
            await self.cache.put(plan.digest, pack)
        except Exception as error:
            failures.append(ResearchFailure("cache", _failure_code(error)))
        self.last_telemetry = ResearchRunTelemetry(counters, tuple(failures))
        return pack

    def _unavailable(
        self,
        plan: CampaignResearchQueryPlan,
        now: datetime,
        counters: ResearchCounters,
        failures: list[ResearchFailure],
    ) -> CampaignResearchPack:
        self.last_telemetry = ResearchRunTelemetry(counters, tuple(failures))
        return unavailable_research_pack(
            campaign_fingerprint_value=plan.fingerprint,
            generated_at=_now_iso(now),
            expires_at=_now_iso(now + timedelta(days=self.policy.ttl_days)),
            research_policy_version=self.policy.version,
        )
