from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.pipeline.knowledge_ingestion import (
    KnowledgeIngestionError,
    compose_vault_snapshot,
)
from app.pipeline.knowledge_tenant_authority import (
    _VERIFIED_TENANT_VAULT_TOKEN,
    HMACSHA256TenantAuthority,
    KnowledgeTenantAuthorityError,
    VerifiedTenantVaultAuthority,
    issue_tenant_vault_authority,
    vault_content_digest,
    verify_tenant_vault_authority,
)
from app.pipeline.knowledge_vault import KnowledgeNote, KnowledgeRelation, KnowledgeVault

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
CAMPAIGN_ID = "campaign_acme"
SOURCE_ID = "source_launch"
ALICE = "owner_alice"
BOB = "owner_bob"


def _vault() -> KnowledgeVault:
    campaign = KnowledgeNote(
        "campaign_proof",
        "proof",
        "campaign",
        "validated",
        "high",
        "Campaign proof",
        "Only this campaign may use this proof note.",
        version=2,
        campaign_id=CAMPAIGN_ID,
    )
    # A campaign-local fixture is enough to assert the owner/campaign/source
    # capability contract; the authority always binds the full target tuple.
    evidence = KnowledgeNote(
        "campaign_evidence",
        "observation",
        "campaign",
        "observation",
        "high",
        "Campaign evidence",
        "An independently stored campaign observation.",
        campaign_id=CAMPAIGN_ID,
    )
    return KnowledgeVault(
        (campaign, evidence),
        (KnowledgeRelation("campaign_evidence", "campaign_proof", "supports"),),
    )


def _authority(vault: KnowledgeVault, *, owner_id: str = ALICE, expires_at: datetime | None = None):
    signer = HMACSHA256TenantAuthority("tenant_2026", b"k" * 32)
    issued = issue_tenant_vault_authority(
        vault,
        owner_id=owner_id,
        campaign_id=CAMPAIGN_ID,
        source_id=SOURCE_ID,
        signer=signer,
        issued_at=NOW,
        expires_at=expires_at or NOW + timedelta(hours=1),
        authority_id="vault_grant_01",
    )
    return issued, signer


def test_authority_rejects_owner_relabel_and_campaign_or_source_scope_changes() -> None:
    vault = _vault()
    issued, signer = _authority(vault)
    for kwargs in (
        {"owner_id": BOB, "campaign_id": CAMPAIGN_ID, "source_id": SOURCE_ID},
        {"owner_id": ALICE, "campaign_id": "campaign_other", "source_id": SOURCE_ID},
        {"owner_id": ALICE, "campaign_id": CAMPAIGN_ID, "source_id": "source_other"},
    ):
        with pytest.raises(KnowledgeTenantAuthorityError, match="scope"):
            verify_tenant_vault_authority(
                issued,
                vault,
                verifier=signer,
                now=NOW,
                **kwargs,
            )


def test_authority_digest_covers_note_content_version_and_relations() -> None:
    vault = _vault()
    issued, signer = _authority(vault)
    changed_content = KnowledgeVault(
        (replace(vault.notes[0], content="Tampered"), vault.notes[1]), vault.relations
    )
    changed_version = KnowledgeVault(
        (replace(vault.notes[0], version=3), vault.notes[1]), vault.relations
    )
    changed_relation = KnowledgeVault(vault.notes)
    assert (
        len(
            {
                vault_content_digest(vault),
                vault_content_digest(changed_content),
                vault_content_digest(changed_version),
                vault_content_digest(changed_relation),
            }
        )
        == 4
    )
    for tampered in (changed_content, changed_version, changed_relation):
        with pytest.raises(KnowledgeTenantAuthorityError, match="exact vault"):
            verify_tenant_vault_authority(
                issued,
                tampered,
                verifier=signer,
                owner_id=ALICE,
                campaign_id=CAMPAIGN_ID,
                source_id=SOURCE_ID,
                now=NOW,
            )


def test_expiry_and_key_rotation_fail_closed_and_secret_is_not_repr() -> None:
    vault = _vault()
    issued, signer = _authority(vault)
    with pytest.raises(KnowledgeTenantAuthorityError, match="expired"):
        verify_tenant_vault_authority(
            issued,
            vault,
            verifier=signer,
            owner_id=ALICE,
            campaign_id=CAMPAIGN_ID,
            source_id=SOURCE_ID,
            now=NOW + timedelta(hours=1),
        )
    with pytest.raises(KnowledgeTenantAuthorityError, match="rotation"):
        verify_tenant_vault_authority(
            issued,
            vault,
            verifier=HMACSHA256TenantAuthority("tenant_rotated", b"k" * 32),
            owner_id=ALICE,
            campaign_id=CAMPAIGN_ID,
            source_id=SOURCE_ID,
            now=NOW,
        )
    assert "kkkk" not in repr(signer)


def test_composition_requires_private_capability_and_allows_global_shared() -> None:
    private = _vault()
    with pytest.raises(KnowledgeIngestionError, match="signed tenant"):
        compose_vault_snapshot(
            private,
            owner_id=ALICE,
            campaign_id=CAMPAIGN_ID,
            source_id=SOURCE_ID,
            revision="r1",
        )
    issued, signer = _authority(private)
    snapshot = compose_vault_snapshot(
        private,
        owner_id=ALICE,
        campaign_id=CAMPAIGN_ID,
        source_id=SOURCE_ID,
        revision="r1",
        tenant_authority=issued,
        tenant_authority_verifier=signer,
        authority_now=NOW,
    )
    assert snapshot.tenant_authority_digest == issued.authority_digest
    with pytest.raises(KnowledgeIngestionError, match="tenant vault authority"):
        compose_vault_snapshot(
            private,
            owner_id=BOB,
            campaign_id=CAMPAIGN_ID,
            source_id=SOURCE_ID,
            revision="r1",
            tenant_authority=issued,
            tenant_authority_verifier=signer,
            authority_now=NOW,
        )

    global_only = KnowledgeVault(
        (
            KnowledgeNote(
                "global_principle",
                "principle",
                "global",
                "curated",
                "high",
                "Shared principle",
                "Global knowledge remains deliberately shareable.",
            ),
        )
    )
    shared = compose_vault_snapshot(
        global_only,
        owner_id=BOB,
        campaign_id="campaign_other",
        source_id="source_other",
        revision="r1",
    )
    assert shared.tenant_authority_digest is None


def test_consumer_rejects_an_importable_private_token_without_revalidating_envelope() -> None:
    """Capabilities are not accepted as bearer values at a trust boundary."""
    private = _vault()
    issued, _ = _authority(private)
    forged_capability = VerifiedTenantVaultAuthority(
        issued,
        _token=_VERIFIED_TENANT_VAULT_TOKEN,
    )
    with pytest.raises(KnowledgeIngestionError, match="signed tenant vault authority"):
        compose_vault_snapshot(
            private,
            owner_id=ALICE,
            campaign_id=CAMPAIGN_ID,
            source_id=SOURCE_ID,
            revision="r1",
            tenant_authority=forged_capability,  # type: ignore[arg-type]
            authority_now=NOW,
        )
