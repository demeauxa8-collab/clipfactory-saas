from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

# Reuse the pack factory from the quality policy suite.  It intentionally has
# three public, canonical sources and an official-primary exception, which
# makes provenance failures easy to distinguish from policy failures.
from test_campaign_research_quality import _pack, _trusted_attestations

from app.pipeline.research_attestation_authority import (
    HMACSHA256ResearchAttestationAuthority,
    ResearchAttestationAuthorityError,
    issue_research_attestations,
    verify_research_attestations,
)

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
OWNER_ID = "owner_one"
CAMPAIGN_ID = "campaign_one"
KEY = HMACSHA256ResearchAttestationAuthority("research_key", b"r" * 32)


def _issued():
    pack = _pack()
    return pack, issue_research_attestations(
        pack,
        _trusted_attestations(pack),
        owner_id=OWNER_ID,
        campaign_id=CAMPAIGN_ID,
        signer=KEY,
        issued_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        authority_id="classification_batch_one",
    )


def test_verified_capability_binds_exact_pack_scope_labels_and_ttl() -> None:
    pack, issued = _issued()
    verified = verify_research_attestations(
        issued,
        pack,
        verifier=KEY,
        owner_id=OWNER_ID,
        campaign_id=CAMPAIGN_ID,
        now=NOW + timedelta(minutes=1),
    )
    assert verified.attestations == tuple(
        sorted(_trusted_attestations(pack), key=lambda item: item.source_id)
    )
    assert verified.authority_digest == issued.authority_digest


@pytest.mark.parametrize(
    ("verifier", "owner_id", "campaign_id"),
    (
        (HMACSHA256ResearchAttestationAuthority("other_key", b"r" * 32), OWNER_ID, CAMPAIGN_ID),
        (KEY, "other_owner", CAMPAIGN_ID),
        (KEY, OWNER_ID, "other_campaign"),
    ),
)
def test_verification_rejects_wrong_key_or_tenant_scope(verifier, owner_id, campaign_id) -> None:
    pack, issued = _issued()
    with pytest.raises(ResearchAttestationAuthorityError):
        verify_research_attestations(
            issued,
            pack,
            verifier=verifier,
            owner_id=owner_id,
            campaign_id=campaign_id,
            now=NOW + timedelta(minutes=1),
        )


def test_verification_rejects_signature_content_url_and_expiry_tampering() -> None:
    pack, issued = _issued()
    bad_signature = replace(issued, signature="0" * 64)
    changed_label = replace(
        issued.attestations[0],
        editor_group="different_editor",
    )
    bad_labels = replace(issued, attestations=(changed_label, *issued.attestations[1:]))
    wrong_url = replace(issued.attestations[0], url_digest="a" * 64)
    bad_url = replace(issued, attestations=(wrong_url, *issued.attestations[1:]))
    changed_pack = replace(pack, confidence=0.7)
    for candidate, instant in (
        (bad_signature, NOW + timedelta(minutes=1)),
        (bad_labels, NOW + timedelta(minutes=1)),
        (bad_url, NOW + timedelta(minutes=1)),
        (issued, NOW + timedelta(hours=1)),
    ):
        with pytest.raises(ResearchAttestationAuthorityError):
            verify_research_attestations(
                candidate,
                pack,
                verifier=KEY,
                owner_id=OWNER_ID,
                campaign_id=CAMPAIGN_ID,
                now=instant,
            )
    with pytest.raises(ResearchAttestationAuthorityError, match="exact research pack"):
        verify_research_attestations(
            issued,
            changed_pack,
            verifier=KEY,
            owner_id=OWNER_ID,
            campaign_id=CAMPAIGN_ID,
            now=NOW + timedelta(minutes=1),
        )


def test_issue_rejects_duplicate_missing_extra_and_wrong_url_source_sets() -> None:
    pack = _pack()
    labels = _trusted_attestations(pack)
    extra = replace(labels[0], source_id="extra_source")
    wrong_url = replace(labels[0], url_digest="a" * 64)
    for candidate in (
        (labels[0], labels[0], labels[1]),
        labels[:2],
        (*labels, extra),
        (wrong_url, *labels[1:]),
    ):
        with pytest.raises(ResearchAttestationAuthorityError):
            issue_research_attestations(
                pack,
                candidate,
                owner_id=OWNER_ID,
                campaign_id=CAMPAIGN_ID,
                signer=KEY,
                issued_at=NOW,
                expires_at=NOW + timedelta(hours=1),
                authority_id="classification_batch_one",
            )


def test_issue_rejects_invalid_lifetime() -> None:
    pack = _pack()
    with pytest.raises(ResearchAttestationAuthorityError):
        issue_research_attestations(
            pack,
            _trusted_attestations(pack),
            owner_id=OWNER_ID,
            campaign_id=CAMPAIGN_ID,
            signer=KEY,
            issued_at=NOW,
            expires_at=NOW + timedelta(hours=25),
            authority_id="classification_batch_one",
        )
