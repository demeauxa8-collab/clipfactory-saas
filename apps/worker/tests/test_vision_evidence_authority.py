from __future__ import annotations

from dataclasses import replace

import pytest

import app.pipeline.vision_evidence_authority as vision_authority
from app.pipeline.editorial_beats import (
    EditorialBeat,
    EditorialBeatGraph,
    SourceMoment,
    VisualBeat,
    VisualFocusRegion,
)
from app.pipeline.editorial_context import graph_digest
from app.pipeline.edl import EditScope, InclusiveWordRange
from app.pipeline.vision_evidence_authority import (
    HMACSHA256VisionEvidenceAuthority,
    VerifiedVisionEvidenceSet,
    VisionEvidenceAuthorityError,
    VisualEvidenceAttestation,
    graph_requires_vision_evidence,
    issue_vision_evidence_set,
    verify_vision_evidence_capability,
)

KEY = HMACSHA256VisionEvidenceAuthority("vision_key_2026", b"v" * 32)
OWNER_ID = "owner_01"
CAMPAIGN_ID = "b4c282cc-848f-4a80-bf53-9b3c82080d41"
SOURCE_ID = "42bb1d18-7e1e-4e63-b517-73f78d0a9229"
ASSET_DIGEST = "a" * 64
NOW = "2026-08-09T12:00:00Z"


def _graph() -> EditorialBeatGraph:
    roi = VisualFocusRegion(0.1, 0.15, 0.75, 0.6)
    visual = VisualBeat(
        "visual_screen",
        "event_screen",
        200,
        1_500,
        "screen_proof",
        "none",
        "readable",
        "still",
        "upper",
        93,
        roi,
        "verified_candidate",
    )
    return EditorialBeatGraph(
        "1.0",
        4,
        EditScope((InclusiveWordRange(0, 3),)),
        (SourceMoment("moment_proof", InclusiveWordRange(0, 3), 0, 1_600, "proof"),),
        (visual,),
        (),
        (
            EditorialBeat(
                "beat_proof",
                "moment_proof",
                ("visual_screen",),
                (),
                "prove",
                ("source_safe", "screen_focus"),
            ),
        ),
        (),
    )


def _attestation(graph: EditorialBeatGraph, **changes: object) -> VisualEvidenceAttestation:
    visual = graph.visual_beats[0]
    values: dict[str, object] = {
        "schema_version": "1.0",
        "attestation_id": "attestation_screen",
        "owner_id": OWNER_ID,
        "campaign_id": CAMPAIGN_ID,
        "source_id": SOURCE_ID,
        "source_asset_digest": ASSET_DIGEST,
        "graph_digest": graph_digest(graph),
        "visual_id": visual.visual_id,
        "source_in_ms": visual.source_in_ms,
        "source_out_ms": visual.source_out_ms,
        "sampled_frame_digests": ("1" * 64, "2" * 64),
        "focus_region": visual.focus_region,
        "verifier_policy_version": "vision_policy.1",
        "verifier_model_version": "vision_model.2026_08",
        "valid_from": "2026-08-09T10:00:00Z",
        "valid_until": "2026-08-09T13:00:00Z",
    }
    values.update(changes)
    return VisualEvidenceAttestation(**values)  # type: ignore[arg-type]


def _issued_and_verified(graph: EditorialBeatGraph | None = None):
    graph = graph or _graph()
    issued = issue_vision_evidence_set(
        graph,
        (_attestation(graph),),
        signer=KEY,
        owner_id=OWNER_ID,
        campaign_id=CAMPAIGN_ID,
        source_id=SOURCE_ID,
        source_asset_digest=ASSET_DIGEST,
        issued_at="2026-08-09T11:00:00Z",
        expires_at="2026-08-09T13:00:00Z",
        evidence_set_id="vision_set_01",
    )
    verified = verify_vision_evidence_capability(
        issued,
        graph,
        verifier=KEY,
        now=NOW,
        expected_owner_id=OWNER_ID,
        expected_campaign_id=CAMPAIGN_ID,
        expected_source_id=SOURCE_ID,
    )
    return issued, verified


def test_valid_screen_focus_candidate_has_a_sealed_exact_visual_capability() -> None:
    graph = _graph()
    issued, verified = _issued_and_verified(graph)
    assert graph_requires_vision_evidence(graph)
    assert issued.audit_digest == verified.audit_digest
    verified.validate_visual_ids(
        ("visual_screen",),
        verifier=KEY,
        graph=graph,
        owner_id=OWNER_ID,
        campaign_id=CAMPAIGN_ID,
        source_id=SOURCE_ID,
        now=NOW,
    )
    with pytest.raises(VisionEvidenceAuthorityError, match="must be created"):
        VerifiedVisionEvidenceSet(issued, graph, _token=object())


def test_candidate_graph_refuses_missing_or_wrong_asset_attestations() -> None:
    graph = _graph()
    common = {
        "signer": KEY,
        "owner_id": OWNER_ID,
        "campaign_id": CAMPAIGN_ID,
        "source_id": SOURCE_ID,
        "source_asset_digest": ASSET_DIGEST,
        "issued_at": "2026-08-09T11:00:00Z",
        "expires_at": "2026-08-09T13:00:00Z",
        "evidence_set_id": "vision_set_01",
    }
    with pytest.raises(VisionEvidenceAuthorityError, match="requires vision attestations"):
        issue_vision_evidence_set(graph, (), **common)
    with pytest.raises(VisionEvidenceAuthorityError, match="source asset"):
        issue_vision_evidence_set(
            graph,
            (_attestation(graph, source_asset_digest="b" * 64),),
            **common,
        )


@pytest.mark.parametrize(
    "changes, match",
    [
        ({"graph_digest": "0" * 64}, "graph digest"),
        ({"source_in_ms": 201}, "source window"),
        ({"focus_region": VisualFocusRegion(0.2, 0.15, 0.75, 0.6)}, "exact graph ROI"),
    ],
)
def test_attestation_rejects_graph_window_and_roi_replays(
    changes: dict[str, object], match: str
) -> None:
    graph = _graph()
    with pytest.raises(VisionEvidenceAuthorityError, match=match):
        issue_vision_evidence_set(
            graph,
            (_attestation(graph, **changes),),
            signer=KEY,
            owner_id=OWNER_ID,
            campaign_id=CAMPAIGN_ID,
            source_id=SOURCE_ID,
            source_asset_digest=ASSET_DIGEST,
            issued_at="2026-08-09T11:00:00Z",
            expires_at="2026-08-09T13:00:00Z",
            evidence_set_id="vision_set_01",
        )


def test_empty_frames_and_expired_or_tampered_set_fail_closed() -> None:
    graph = _graph()
    with pytest.raises(VisionEvidenceAuthorityError, match="non-empty"):
        _attestation(graph, sampled_frame_digests=())
    issued, _ = _issued_and_verified(graph)
    with pytest.raises(VisionEvidenceAuthorityError, match="signature"):
        verify_vision_evidence_capability(
            replace(issued, signature="0" * 64),
            graph,
            verifier=KEY,
            now=NOW,
            expected_owner_id=OWNER_ID,
            expected_campaign_id=CAMPAIGN_ID,
            expected_source_id=SOURCE_ID,
        )


def test_importing_the_private_token_does_not_bypass_consumer_signature_recheck() -> None:
    graph = _graph()
    issued, _ = _issued_and_verified(graph)
    forged = VerifiedVisionEvidenceSet(
        replace(issued, signature="0" * 64),
        graph,
        _token=vision_authority._VERIFIED_VISION_EVIDENCE_TOKEN,
    )
    with pytest.raises(VisionEvidenceAuthorityError, match="signature"):
        forged.validate_graph(
            graph,
            verifier=KEY,
            owner_id=OWNER_ID,
            campaign_id=CAMPAIGN_ID,
            source_id=SOURCE_ID,
            now=NOW,
        )
    with pytest.raises(VisionEvidenceAuthorityError, match="expired"):
        verify_vision_evidence_capability(
            issued,
            graph,
            verifier=KEY,
            now="2026-08-09T13:00:00Z",
            expected_owner_id=OWNER_ID,
            expected_campaign_id=CAMPAIGN_ID,
            expected_source_id=SOURCE_ID,
        )
