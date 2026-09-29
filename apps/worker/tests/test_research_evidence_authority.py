from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.pipeline.campaign_research_runtime import NormalizedResearchDocument
from app.pipeline.research_evidence_authority import (
    EvidenceSpanClaim,
    HmacSha256ResearchEvidenceAuthority,
    ResearchEvidenceAuthorityError,
    issue_research_evidence,
    verify_research_evidence,
)
from test_campaign_research_quality import _pack

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
OWNER_ID = "owner_one"
CAMPAIGN_ID = "campaign_one"
KEY = HmacSha256ResearchEvidenceAuthority("evidence.key", b"e" * 32)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _documents(pack):
    return tuple(
        NormalizedResearchDocument(
            url=source.url,
            title=f"Document for {source.source_id}",
            content=f"Verified public evidence for {source.source_id}. Stable source excerpt.",
            content_digest=_digest(
                f"Verified public evidence for {source.source_id}. Stable source excerpt."
            ),
        )
        for source in pack.sources
    )


def _claims(pack, documents):
    by_source = {source.source_id: document for source, document in zip(pack.sources, documents)}
    return tuple(
        EvidenceSpanClaim(
            finding_id=finding.finding_id,
            source_id=source_id,
            document_content_digest=by_source[source_id].content_digest,
            excerpt=by_source[source_id].content,
            char_start=0,
            char_end=len(by_source[source_id].content),
        )
        for finding in pack.iter_findings()
        for source_id in finding.source_ids
    )


def _issued():
    pack = _pack()
    documents = _documents(pack)
    claims = _claims(pack, documents)
    issued = issue_research_evidence(
        pack,
        documents,
        claims,
        owner_id=OWNER_ID,
        campaign_id=CAMPAIGN_ID,
        signer=KEY,
        issued_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        authority_id="evidence_batch_one",
    )
    return pack, documents, claims, issued


def test_issue_and_verify_seal_exact_spans_without_serializing_text_or_urls() -> None:
    pack, documents, _, issued = _issued()
    verified = verify_research_evidence(
        issued,
        pack,
        documents,
        verifier=KEY,
        owner_id=OWNER_ID,
        campaign_id=CAMPAIGN_ID,
        now=NOW + timedelta(minutes=1),
    )
    assert verified == issued
    payload = str(issued.unsigned_payload())
    assert "Verified public evidence" not in payload
    assert all(source.url not in payload for source in pack.sources)
    assert len(issued.document_bindings) == len(pack.sources)
    assert {item.finding_id for item in issued.evidence_bindings} == {
        finding.finding_id for finding in pack.iter_findings()
    }


def test_issue_rejects_invented_finding_wrong_source_document_url_span_and_digest() -> None:
    pack, documents, claims, _ = _issued()
    wrong_source = replace(claims[0], source_id="not_cited_source")
    invented = replace(claims[0], finding_id="invented_finding")
    wrong_digest = replace(claims[0], document_content_digest="0" * 64)
    wrong_span = replace(claims[0], excerpt="not in document")
    wrong_url_documents = (
        replace(documents[0], url=pack.sources[1].url),
        *documents[1:],
    )
    for candidate_documents, candidate_claims in (
        (documents, (wrong_source, *claims[1:])),
        (documents, (invented, *claims[1:])),
        (documents, (wrong_digest, *claims[1:])),
        (documents, (wrong_span, *claims[1:])),
        (wrong_url_documents, claims),
    ):
        with pytest.raises(ResearchEvidenceAuthorityError):
            issue_research_evidence(
                pack,
                candidate_documents,
                candidate_claims,
                owner_id=OWNER_ID,
                campaign_id=CAMPAIGN_ID,
                signer=KEY,
                issued_at=NOW,
                expires_at=NOW + timedelta(hours=1),
                authority_id="evidence_batch_one",
            )


def test_issue_rejects_missing_finding_or_cited_source_coverage() -> None:
    pack, documents, claims, _ = _issued()
    missing_finding = tuple(claim for claim in claims if claim.finding_id != claims[0].finding_id)
    # src_three is cited only by the negative finding in the factory.
    missing_source = tuple(claim for claim in claims if claim.source_id != "src_three")
    for candidate in (missing_finding, missing_source):
        with pytest.raises(ResearchEvidenceAuthorityError):
            issue_research_evidence(
                pack,
                documents,
                candidate,
                owner_id=OWNER_ID,
                campaign_id=CAMPAIGN_ID,
                signer=KEY,
                issued_at=NOW,
                expires_at=NOW + timedelta(hours=1),
                authority_id="evidence_batch_one",
            )


def test_verification_rejects_tamper_wrong_key_scope_expiry_pack_and_document_substitution() -> None:
    pack, documents, _, issued = _issued()
    other_key = HmacSha256ResearchEvidenceAuthority("other.key", b"e" * 32)
    tampered = replace(issued, signature="0" * 64)
    changed_document = replace(
        documents[0],
        content="Different normalized source text.",
        content_digest=_digest("Different normalized source text."),
    )
    for candidate, verifier, owner_id, campaign_id, now, supplied_documents in (
        (tampered, KEY, OWNER_ID, CAMPAIGN_ID, NOW + timedelta(minutes=1), documents),
        (issued, other_key, OWNER_ID, CAMPAIGN_ID, NOW + timedelta(minutes=1), documents),
        (issued, KEY, "other_owner", CAMPAIGN_ID, NOW + timedelta(minutes=1), documents),
        (issued, KEY, OWNER_ID, "other_campaign", NOW + timedelta(minutes=1), documents),
        (issued, KEY, OWNER_ID, CAMPAIGN_ID, NOW + timedelta(hours=1), documents),
        (issued, KEY, OWNER_ID, CAMPAIGN_ID, NOW + timedelta(minutes=1), (changed_document, *documents[1:])),
    ):
        with pytest.raises(ResearchEvidenceAuthorityError):
            verify_research_evidence(
                candidate,
                pack,
                supplied_documents,
                verifier=verifier,
                owner_id=owner_id,
                campaign_id=campaign_id,
                now=now,
            )


def test_deterministic_ordering_produces_same_manifest() -> None:
    pack, documents, claims, issued = _issued()
    reordered = issue_research_evidence(
        pack,
        tuple(reversed(documents)),
        tuple(reversed(claims)),
        owner_id=OWNER_ID,
        campaign_id=CAMPAIGN_ID,
        signer=KEY,
        issued_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        authority_id="evidence_batch_one",
    )
    assert reordered == issued
