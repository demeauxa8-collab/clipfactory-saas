from __future__ import annotations

import pytest

from app.models import ArcSegmentSpec, SegmentVision, StoryArc, VisionResult
from app.pipeline.score import (
    ARC_WEIGHTS,
    _campaign_fit_score,
    _editing_continuity_score,
    _keyword_fit_score,
    joint_compatibility,
    score_arc,
)
from app.pipeline.story_arcs import _parse_arcs

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _seg(start: float, end: float, *, role: str = "single", text: str = "") -> ArcSegmentSpec:
    return ArcSegmentSpec(role=role, start=start, end=end, transcript_excerpt=text)  # type: ignore[arg-type]


def _arc(
    segments: list[ArcSegmentSpec],
    *,
    title: str = "clip",
    continuity_risk: str = "low",
    campaign_fit_llm: int | None = None,
    link_reason: str | None = None,
) -> StoryArc:
    return StoryArc(
        title=title,
        arc_type="continuous",
        segments=segments,
        viral_reason="",
        estimated_retention=60,
        continuity_risk=continuity_risk,
        link_reason=link_reason,
        campaign_fit_llm=campaign_fit_llm,
    )


def _vision(
    idx: int,
    *,
    decor: str = "studio",
    person: bool = True,
    score: int = 75,
    energy: int = 75,
    problems: list[str] | None = None,
) -> SegmentVision:
    return SegmentVision(
        segment_idx=idx,
        frames_used=5,
        vision=VisionResult(
            decor=decor,
            person_visible=person,
            energy=energy,
            action="talking head",
            proof_objects=[],
            problems=problems or [],
            visual_score=score,
        ),
    )


# ---------------------------------------------------------------------------
# 1. Weights
# ---------------------------------------------------------------------------


def test_arc_weights_sum_to_one() -> None:
    assert sum(ARC_WEIGHTS.values()) == pytest.approx(1.0)
    # Every scored dimension is present.
    assert set(ARC_WEIGHTS) == {
        "visual_proof",
        "hook_strength",
        "payoff_strength",
        "campaign_fit",
        "editing_continuity",
        "retention",
    }


# ---------------------------------------------------------------------------
# 2. _parse_arcs — montage-v2 multi-segment + bounds
# ---------------------------------------------------------------------------


def test_parse_arcs_accepts_multi_segment_with_link_reason() -> None:
    payload = {
        "arcs": [
            {
                "title": "setup then payoff",
                "arc_type": "setup_payoff",
                "segments": [
                    {"role": "setup", "start": 120.0, "end": 128.0, "transcript_excerpt": "a"},
                    {"role": "payoff", "start": 750.0, "end": 762.0, "transcript_excerpt": "b"},
                ],
                "link_reason": "the promise at 2:00 is proven at 12:30",
                "campaign_fit": 82,
                "campaign_fit_reason": "shows the result the audience wants",
            }
        ]
    }
    arcs = _parse_arcs(payload)
    assert len(arcs) == 1
    arc = arcs[0]
    assert len(arc.segments) == 2
    assert arc.link_reason == "the promise at 2:00 is proven at 12:30"
    assert arc.campaign_fit_llm == 82
    assert arc.campaign_fit_reason == "shows the result the audience wants"


def test_parse_arcs_keeps_multi_segment_missing_link_reason() -> None:
    payload = {
        "arcs": [
            {
                "title": "no link stated",
                "segments": [
                    {"role": "setup", "start": 10.0, "end": 18.0, "transcript_excerpt": "a"},
                    {"role": "payoff", "start": 40.0, "end": 48.0, "transcript_excerpt": "b"},
                ],
            }
        ]
    }
    arcs = _parse_arcs(payload)
    # Downgraded but not dropped.
    assert len(arcs) == 1
    assert arcs[0].link_reason is None
    assert len(arcs[0].segments) == 2


def test_parse_arcs_segment_bounds_3_to_30() -> None:
    payload = {
        "arcs": [
            {
                "title": "too short + too long segments dropped",
                "segments": [
                    {"role": "setup", "start": 0.0, "end": 2.0, "transcript_excerpt": "tiny"},
                    {"role": "single", "start": 10.0, "end": 30.0, "transcript_excerpt": "ok"},
                    {"role": "payoff", "start": 50.0, "end": 90.0, "transcript_excerpt": "huge"},
                ],
            }
        ]
    }
    arcs = _parse_arcs(payload)
    # 2s and 40s segments dropped, only the 20s survives -> single-segment arc.
    assert len(arcs) == 1
    assert len(arcs[0].segments) == 1
    assert arcs[0].segments[0].start == 10.0


def test_parse_arcs_total_duration_bounds_12_to_60() -> None:
    too_short = {
        "arcs": [
            {
                "title": "total 9s",
                "segments": [
                    {"role": "setup", "start": 0.0, "end": 5.0, "transcript_excerpt": "a"},
                    {"role": "payoff", "start": 20.0, "end": 24.0, "transcript_excerpt": "b"},
                ],
            }
        ]
    }
    assert _parse_arcs(too_short) == []

    too_long = {
        "arcs": [
            {
                "title": "total 75s",
                "segments": [
                    {"role": "setup", "start": 0.0, "end": 25.0, "transcript_excerpt": "a"},
                    {"role": "transition", "start": 40.0, "end": 65.0, "transcript_excerpt": "b"},
                    {"role": "payoff", "start": 80.0, "end": 105.0, "transcript_excerpt": "c"},
                ],
            }
        ]
    }
    assert _parse_arcs(too_long) == []


# ---------------------------------------------------------------------------
# 3. joint_compatibility
# ---------------------------------------------------------------------------


def test_joint_compatibility_continuous_when_same_decor_and_person() -> None:
    a = _vision(0, decor="studio", person=True).vision
    b = _vision(1, decor="studio", person=True).vision
    assert joint_compatibility(a, b) == "continuous"


def test_joint_compatibility_scene_change_on_decor_diff() -> None:
    a = _vision(0, decor="studio", person=True).vision
    b = _vision(1, decor="desktop", person=True).vision
    assert joint_compatibility(a, b) == "scene_change"


def test_joint_compatibility_scene_change_on_person_diff() -> None:
    a = _vision(0, decor="studio", person=True).vision
    b = _vision(1, decor="studio", person=False).vision
    assert joint_compatibility(a, b) == "scene_change"


def test_joint_compatibility_scene_change_when_vision_missing() -> None:
    a = _vision(0).vision
    assert joint_compatibility(a, None) == "scene_change"
    assert joint_compatibility(None, None) == "scene_change"


# ---------------------------------------------------------------------------
# 4. _editing_continuity_score — per-joint, not per-segment
# ---------------------------------------------------------------------------


def test_editing_continuity_single_segment_is_full() -> None:
    arc = _arc([_seg(0, 20)])
    assert _editing_continuity_score(arc, [_vision(0)]) == 100


def test_editing_continuity_penalises_per_joint() -> None:
    arc = _arc([_seg(0, 15, role="setup"), _seg(30, 45, role="payoff")])
    continuous = _editing_continuity_score(
        arc, [_vision(0, decor="studio"), _vision(1, decor="studio")]
    )
    scene_change = _editing_continuity_score(
        arc, [_vision(0, decor="studio"), _vision(1, decor="desktop")]
    )
    missing = _editing_continuity_score(arc, [_vision(0)])  # no vision for idx 1
    assert continuous == 97   # 100 - 3
    assert scene_change == 92  # 100 - 8
    assert missing == 94       # 100 - 6


def test_editing_continuity_three_segments_not_crushed() -> None:
    # Old policy subtracted 40 per extra segment (-> 20). New per-joint scoring on
    # two continuous joints stays high.
    arc = _arc(
        [
            _seg(0, 15, role="setup"),
            _seg(30, 45, role="transition"),
            _seg(60, 75, role="payoff"),
        ]
    )
    score = _editing_continuity_score(
        arc, [_vision(0, decor="studio"), _vision(1, decor="studio"), _vision(2, decor="studio")]
    )
    assert score == 94  # 100 - 3 - 3


# ---------------------------------------------------------------------------
# 5. campaign fit — fuzzy keyword match (typo tolerance)
# ---------------------------------------------------------------------------


def test_keyword_fit_fuzzy_matches_typo_in_brief() -> None:
    arc = _arc([_seg(0, 20, text="comment lancer son business en ligne")])
    # Brief has a typo: "buinesse" should still match "business" in the text.
    campaign = {"niche": "buinesse", "audience": "", "avoid_topics": []}
    assert _keyword_fit_score(arc, campaign) == 64  # 60 + 4


def test_keyword_fit_no_match_stays_baseline() -> None:
    arc = _arc([_seg(0, 20, text="recette de cuisine facile")])
    campaign = {"niche": "buinesse", "audience": "", "avoid_topics": []}
    assert _keyword_fit_score(arc, campaign) == 60


def test_keyword_fit_avoid_penalty_unchanged() -> None:
    arc = _arc([_seg(0, 20, text="parlons de crypto aujourd'hui")])
    campaign = {"niche": "", "audience": "", "avoid_topics": ["crypto"]}
    assert _keyword_fit_score(arc, campaign) == 35  # 60 - 25


def test_campaign_fit_blends_llm_and_keyword() -> None:
    arc = _arc(
        [_seg(0, 20, text="mon business a explosé")],
        campaign_fit_llm=80,
    )
    campaign = {"niche": "buinesse", "audience": "", "avoid_topics": []}
    # 0.5 * 80 + 0.5 * 64 = 72
    assert _campaign_fit_score(arc, campaign) == 72


def test_campaign_fit_defaults_llm_to_60_when_absent() -> None:
    arc = _arc([_seg(0, 20, text="recette de cuisine")])  # no keyword match, no llm
    campaign = {"niche": "buinesse", "audience": "", "avoid_topics": []}
    # 0.5 * 60 + 0.5 * 60 = 60
    assert _campaign_fit_score(arc, campaign) == 60


# ---------------------------------------------------------------------------
# 6. score_arc — multi-segment no longer crushed
# ---------------------------------------------------------------------------


def test_score_arc_multi_segment_not_crushed() -> None:
    campaign = {"niche": "business", "audience": "entrepreneurs", "avoid_topics": []}
    single = score_arc(
        arc=_arc([_seg(0, 20, text="j'ai gagné 10000 euros ce mois")], campaign_fit_llm=80),
        per_segment_vision=[_vision(0)],
        campaign=campaign,
    )
    multi = score_arc(
        arc=_arc(
            [
                _seg(0, 15, role="setup", text="j'ai gagné 10000 euros ce mois"),
                _seg(40, 55, role="payoff", text="voici la preuve business"),
            ],
            campaign_fit_llm=80,
            link_reason="promise then proof",
        ),
        per_segment_vision=[_vision(0), _vision(1)],
        campaign=campaign,
    )
    # Old 0.6 multiplier would have dropped the multi-segment score far below the
    # single. Now they are comparable (multi only pays the small per-joint cost).
    assert multi.score_total >= single.score_total - 6
    assert multi.score_total > 55
