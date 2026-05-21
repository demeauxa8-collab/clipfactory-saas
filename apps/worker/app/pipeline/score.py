from __future__ import annotations

from typing import Any

from ..models import ScoredClip, TextCandidate, VisionResult

WEIGHTS = {
    "hook": 0.35,
    "emotion": 0.20,
    "visual": 0.25,
    "campaign_fit": 0.15,
    "editing_difficulty": 0.05,
}


def _editing_difficulty_score(candidate: TextCandidate, vision: VisionResult | None) -> int:
    """Higher = easier to edit. Penalise very long clips and visual problems."""
    base = 100
    duration = candidate.end - candidate.start
    if duration > 60:
        base -= 20
    if duration < 15:
        base -= 10
    if vision is not None:
        if "no face" in vision.problems:
            base -= 25
        if "dark" in vision.problems:
            base -= 15
        if "unreadable slide" in vision.problems:
            base -= 10
        if "blurry" in vision.problems:
            base -= 15
    return max(0, min(100, base))


def _campaign_fit_score(candidate: TextCandidate, campaign: dict[str, Any]) -> int:
    """Lightweight V1: keyword overlap + avoid-list penalty.

    The candidate's `why` field is the LLM's own justification of fit — we use it
    as a soft signal. Real fit-scoring with a learned model is V2.
    """
    fit = 60  # neutral baseline
    txt = " ".join(
        [
            candidate.transcript_excerpt or "",
            candidate.why or "",
            candidate.suggested_title or "",
            candidate.suggested_hook or "",
        ]
    ).lower()

    audience = (campaign.get("audience") or "").lower()
    niche = (campaign.get("niche") or "").lower()
    for keyword in set(filter(None, (audience.split() + niche.split()))):
        if len(keyword) >= 4 and keyword in txt:
            fit = min(100, fit + 4)

    for avoid in campaign.get("avoid_topics") or []:
        if avoid and avoid.lower() in txt:
            fit = max(0, fit - 25)

    return fit


def score_candidate(
    *,
    candidate: TextCandidate,
    vision: VisionResult | None,
    campaign: dict[str, Any],
) -> ScoredClip:
    visual = vision.visual_score if vision is not None else None
    campaign_fit = _campaign_fit_score(candidate, campaign)
    editing = _editing_difficulty_score(candidate, vision)

    breakdown: dict[str, int] = {
        "hook": candidate.hook_score_text,
        "emotion": candidate.emotion_score,
        "campaign_fit": campaign_fit,
        "editing_difficulty": editing,
    }
    if visual is not None:
        breakdown["visual"] = visual

    if visual is None:
        # Renormalise without the visual term to be fair.
        total_weight = sum(w for k, w in WEIGHTS.items() if k != "visual")
        weighted = (
            WEIGHTS["hook"] * breakdown["hook"]
            + WEIGHTS["emotion"] * breakdown["emotion"]
            + WEIGHTS["campaign_fit"] * breakdown["campaign_fit"]
            + WEIGHTS["editing_difficulty"] * breakdown["editing_difficulty"]
        )
        score_total = round(weighted / total_weight)
    else:
        weighted = (
            WEIGHTS["hook"] * breakdown["hook"]
            + WEIGHTS["emotion"] * breakdown["emotion"]
            + WEIGHTS["visual"] * breakdown["visual"]
            + WEIGHTS["campaign_fit"] * breakdown["campaign_fit"]
            + WEIGHTS["editing_difficulty"] * breakdown["editing_difficulty"]
        )
        score_total = round(weighted)

    return ScoredClip(
        candidate=candidate,
        vision=vision,
        campaign_fit=campaign_fit,
        editing_difficulty=editing,
        score_total=max(0, min(100, score_total)),
        score_breakdown=breakdown,
    )


def rank_and_pick(scored: list[ScoredClip], target_clip_count: int) -> list[ScoredClip]:
    ordered = sorted(scored, key=lambda s: s.score_total, reverse=True)
    return ordered[: max(1, target_clip_count)]
