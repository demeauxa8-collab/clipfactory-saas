from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.pipeline.campaign_research import (
    CampaignResearchPack,
    CampaignResearchSection,
    CampaignResearchSource,
    CitedFinding,
    campaign_fingerprint,
    unavailable_research_pack,
)
from app.pipeline.campaign_research_quality import (
    CampaignResearchQualityError,
    SourceClassificationAttestation,
    evaluate_campaign_research_quality,
    source_url_digest,
)

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
CAMPAIGN = {"name": "Proof", "audience": "Founders", "niche": "SaaS", "goal": "Demo"}
SECTIONS = (
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


def _source(
    source_id: str, *, host: str, accessed_at: str = "2026-08-01T10:00:00+00:00"
) -> CampaignResearchSource:
    return CampaignResearchSource(
        "1.0",
        source_id,
        f"https://{host}/report",
        f"Report {source_id}",
        "Synthetic publisher",
        None,
        accessed_at,
        "official",
        "primary",
        "Synthetic evidence summary",
    )


def _finding(
    finding_id: str,
    source_ids: tuple[str, ...],
    *,
    kind: str = "fact",
    scope: str = "market_context",
) -> CitedFinding:
    return CitedFinding(
        "1.0",
        finding_id,
        kind,  # type: ignore[arg-type]
        scope,  # type: ignore[arg-type]
        "Evidence wording is deliberately irrelevant to this quality audit.",
        source_ids,
        0.8,
        "2026-08-01T00:00:00+00:00",
        "2026-08-30T00:00:00+00:00",
    )


def _pack(*, sources: tuple[CampaignResearchSource, ...] | None = None) -> CampaignResearchPack:
    sources = sources or (
        _source("src_one", host="one.example.com"),
        _source("src_two", host="two.example.org"),
        _source("src_three", host="three.example.net"),
    )
    fact = _finding("market_fact", ("src_one", "src_two"))
    negative = _finding(
        "negative_official",
        ("src_three",),
        kind="negative_evidence",
        scope="sampled_sources",
    )
    sections = tuple(
        CampaignResearchSection(
            "1.0",
            name,
            (
                (_finding(f"fact_{name}", ("src_one", "src_two")),)
                if name in {"audience_vocabulary", "audience_objections", "expected_proof"}
                else (negative,) if name == "avoid_topics" else ()
            ),
        )
        for name in SECTIONS
    )
    return CampaignResearchPack(
        "1.0",
        "1.0",
        campaign_fingerprint(CAMPAIGN),
        "2026-08-09T10:00:00+00:00",
        "2026-08-23T10:00:00+00:00",
        "complete",
        fact,
        sections,
        sources,
        0.8,
    )


def _attestation(
    source: CampaignResearchSource,
    *,
    editor_group: str | None = None,
    domain_group: str | None = None,
    source_type: str = "industry",
    evidence_tier: str = "secondary",
    authority: str = "established",
) -> SourceClassificationAttestation:
    return SourceClassificationAttestation(
        "1.0",
        source.source_id,
        source_url_digest(source),
        source_type,
        evidence_tier,
        authority,  # type: ignore[arg-type]
        editor_group or f"editor_{source.source_id}",
        domain_group or f"domain_{source.source_id}",
    )


def _trusted_attestations(
    pack: CampaignResearchPack,
) -> tuple[SourceClassificationAttestation, ...]:
    first, second, third = pack.sources
    return (
        _attestation(first),
        _attestation(second),
        _attestation(
            third,
            source_type="official",
            evidence_tier="primary",
            authority="verified_official",
        ),
    )


def test_trusted_complete_requires_independent_attested_evidence_and_is_deterministic() -> None:
    pack = _pack()
    attestations = _trusted_attestations(pack)
    first = evaluate_campaign_research_quality(pack, attestations, NOW)
    second = evaluate_campaign_research_quality(pack, tuple(reversed(attestations)), NOW)
    assert first.status == "trusted_complete"
    assert first.codes == ()
    assert first.independent_group_count == 3
    assert first.covered_critical_sections == (
        "audience_objections",
        "audience_vocabulary",
        "expected_proof",
    )
    assert first.contrary_evidence_present
    assert "fact_expected_proof" in first.triangulated_finding_ids
    assert "negative_official" in first.official_primary_finding_ids
    assert first.audit_digest == second.audit_digest
    assert "https://" not in str(first.to_audit_dict())
    assert "Evidence wording" not in str(first.to_audit_dict())


def test_self_declared_official_primary_cannot_replace_an_attestation() -> None:
    pack = _pack()
    forged = _attestation(
        pack.sources[0],
        source_type="community",
        evidence_tier="community",
        authority="unverified",
    )
    result = evaluate_campaign_research_quality(pack, (forged,), NOW)
    assert result.status == "limited"
    assert "ATTESTATIONS_MISSING" in result.codes
    assert "FINDING_UNTRIANGULATED" in result.codes
    assert "fact_expected_proof" not in result.official_primary_finding_ids


def test_shared_editor_or_domain_prevents_fake_subdomain_diversity() -> None:
    pack = _pack()
    attestations = tuple(
        _attestation(source, editor_group="same_editor", domain_group="example.com")
        for source in pack.sources
    )
    result = evaluate_campaign_research_quality(pack, attestations, NOW)
    assert result.status == "limited"
    assert result.independent_group_count == 1
    assert result.distinct_editor_group_count == 1
    assert result.distinct_domain_group_count == 1
    assert result.largest_group_fraction == 1.0
    assert {"INSUFFICIENT_INDEPENDENCE", "SOURCE_CONCENTRATION_HIGH"} <= set(result.codes)


def test_single_source_fact_requires_verified_official_primary_exception() -> None:
    pack = _pack()
    source = pack.sources[0]
    single_fact = _finding("single_fact", (source.source_id,))
    negative = _finding(
        "negative_triangulated",
        ("src_two", "src_three"),
        kind="negative_evidence",
        scope="sampled_sources",
    )
    single_pack = replace(
        pack,
        market_summary=single_fact,
        sections=tuple(
            (
                replace(
                    section,
                    findings=(_finding(f"single_{section.name}", (source.source_id,)),),
                )
                if section.findings and section.name != "avoid_topics"
                else (
                    replace(section, findings=(negative,))
                    if section.name == "avoid_topics"
                    else section
                )
            )
            for section in pack.sections
        ),
        sources=pack.sources,
    )
    ordinary = evaluate_campaign_research_quality(
        single_pack,
        (_attestation(source), _attestation(pack.sources[1]), _trusted_attestations(pack)[2]),
        NOW,
    )
    official = evaluate_campaign_research_quality(
        single_pack,
        (
            _attestation(
                source,
                source_type="official",
                evidence_tier="primary",
                authority="verified_official",
            ),
            _attestation(pack.sources[1]),
            _trusted_attestations(pack)[2],
        ),
        NOW,
    )
    assert "single_fact" not in ordinary.official_primary_finding_ids
    assert "FINDING_UNTRIANGULATED" in ordinary.codes
    assert "single_fact" in official.official_primary_finding_ids
    assert "FINDING_UNTRIANGULATED" not in official.codes


def test_stale_unavailable_and_invalid_binding_fail_closed_to_nontrusted_status() -> None:
    stale_sources = tuple(
        replace(source, accessed_at="2026-06-01T10:00:00+00:00") for source in _pack().sources
    )
    stale_pack = _pack(sources=stale_sources)
    stale = evaluate_campaign_research_quality(stale_pack, _trusted_attestations(stale_pack), NOW)
    assert stale.status == "limited"
    assert "SOURCES_STALE" in stale.codes

    unavailable = unavailable_research_pack(
        campaign_fingerprint_value=campaign_fingerprint(CAMPAIGN),
        generated_at="2026-08-09T10:00:00+00:00",
        expires_at="2026-08-23T10:00:00+00:00",
    )
    blocked = evaluate_campaign_research_quality(unavailable, (), NOW)
    assert (blocked.status, blocked.codes) == ("blocked", ("UNAVAILABLE_RESEARCH",))

    valid_pack = _pack()
    wrong_url = replace(_trusted_attestations(valid_pack)[0], url_digest="a" * 64)
    invalid = evaluate_campaign_research_quality(valid_pack, (wrong_url,), NOW)
    assert invalid.status == "limited"
    assert invalid.invalid_attestation_source_ids == ("src_one",)
    assert "ATTESTATIONS_INVALID" in invalid.codes


def test_rejects_non_tuple_attestations_and_naive_as_of() -> None:
    pack = _pack()
    with pytest.raises(CampaignResearchQualityError, match="tuple"):
        evaluate_campaign_research_quality(pack, list(_trusted_attestations(pack)), NOW)  # type: ignore[arg-type]
    with pytest.raises(CampaignResearchQualityError, match="timezone"):
        evaluate_campaign_research_quality(pack, _trusted_attestations(pack), datetime(2026, 8, 9))
