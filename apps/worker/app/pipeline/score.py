from __future__ import annotations

import difflib
from typing import Any

from ..models import (
    MontageCandidate,
    MontageSegment,
    SegmentVision,
    StoryArc,
    VisionResult,
)

# Montage-v2 weights. Multi-segment clips are first-class now, so the mix leans on
# campaign fit and payoff strength alongside watchability and a first-2-seconds
# hook. The LLM's self-reported retention stays discounted. Weights sum to 1.0.
ARC_WEIGHTS = {
    "visual_proof": 0.28,
    "hook_strength": 0.20,
    "payoff_strength": 0.18,
    "campaign_fit": 0.12,
    "editing_continuity": 0.12,
    "retention": 0.10,
}

# A clip with no visible person anywhere is almost always weak b-roll for a
# creator video — multiply the final score down hard.
NO_PERSON_PENALTY = 0.55

# Fuzzy keyword match threshold — tolerates typos in the brief ("buinesse"
# ~= "business") without matching unrelated words.
_FUZZY_RATIO = 0.8


def joint_compatibility(a: VisionResult | None, b: VisionResult | None) -> str:
    """Classify the cut between two adjacent segments, for the renderer to pick a
    transition. 'continuous' = same decor AND same person visibility (a natural
    hard cut); 'scene_change' = anything else (needs an intentional transition,
    or one side has no vision)."""
    if a is None or b is None:
        return "scene_change"
    if a.decor == b.decor and a.person_visible == b.person_visible:
        return "continuous"
    return "scene_change"


def _fuzzy_contains(keyword: str, words: set[str]) -> bool:
    """True if any word in the text closely matches the keyword (typo-tolerant)."""
    return any(
        difflib.SequenceMatcher(None, keyword, w).ratio() >= _FUZZY_RATIO
        for w in words
    )


def _keyword_fit_score(arc: StoryArc, campaign: dict[str, Any]) -> int:
    """Keyword overlap (fuzzy) + avoid-list penalty. Baseline 60."""
    fit = 60  # neutral baseline
    txt = " ".join(
        [
            arc.title or "",
            arc.viral_reason or "",
            arc.suggested_hook or "",
            *[s.transcript_excerpt or "" for s in arc.segments],
        ]
    ).lower()
    words = set(txt.split())

    audience = (campaign.get("audience") or "").lower()
    niche = (campaign.get("niche") or "").lower()
    for keyword in set(filter(None, (audience.split() + niche.split()))):
        if len(keyword) >= 4 and _fuzzy_contains(keyword, words):
            fit = min(100, fit + 4)

    for avoid in campaign.get("avoid_topics") or []:
        if avoid and avoid.lower() in txt:
            fit = max(0, fit - 25)

    return fit


def _campaign_fit_score(arc: StoryArc, campaign: dict[str, Any]) -> int:
    """Blend the LLM's campaign-fit self-report with a fuzzy keyword overlap.
    Falls back to a neutral 60 for the LLM half when it did not report a value."""
    keyword_fit = _keyword_fit_score(arc, campaign)
    llm = arc.campaign_fit_llm if arc.campaign_fit_llm is not None else 60
    return max(0, min(100, round(0.5 * llm + 0.5 * keyword_fit)))


def _editing_continuity_score(arc: StoryArc, per_segment_vision: list[SegmentVision]) -> int:
    """Higher = cleaner to cut. Instead of punishing every extra segment, we score
    each JOINT by how compatible the two adjacent segments look."""
    base = 100
    if arc.continuity_risk == "high":
        base -= 35
    elif arc.continuity_risk == "medium":
        base -= 15

    # Per-joint continuity: a hard cut between two visually identical scenes is
    # cheap; a scene change is a real (but manageable) transition; a missing
    # vision leaves us blind, so it sits between the two.
    visions_by_idx = {sv.segment_idx: sv.vision for sv in per_segment_vision}
    for i in range(len(arc.segments) - 1):
        a = visions_by_idx.get(i)
        b = visions_by_idx.get(i + 1)
        if a is None or b is None:
            base -= 6
        elif joint_compatibility(a, b) == "continuous":
            base -= 3
        else:
            base -= 8

    for sv in per_segment_vision:
        if sv.vision is None:
            continue
        if "no face" in sv.vision.problems:
            base -= 12
        if "dark" in sv.vision.problems:
            base -= 5
        if "unreadable slide" in sv.vision.problems:
            base -= 3

    return max(0, min(100, base))


def _payoff_strength(arc: StoryArc, per_segment_vision: list[SegmentVision]) -> int:
    """Strength of the last segment's payoff. Uses LLM signals + last-segment vision."""
    base = arc.estimated_retention or 60
    if per_segment_vision:
        last = per_segment_vision[-1].vision
        if last is not None:
            if last.energy >= 70:
                base += 10
            if last.visual_score >= 70:
                base += 5
    return max(0, min(100, base))


_HOOK_KEYWORDS = (
    "jamais", "incroyable", "fou", "choqu", "impossible", "€", "euros",
    "personne", "tout le monde", "arnaque", "secret",
)


def _hook_strength(arc: StoryArc, per_segment_vision: list[SegmentVision]) -> int:
    """How hard the first 2 seconds grab the viewer: tight, punchy, face on camera."""
    first = arc.segments[0] if arc.segments else None
    if first is None:
        return 40
    base = 45
    dur = max(0.0, first.end - first.start)
    if dur <= 30:  # tight, fast-hitting hook
        base += 10
    ex = first.transcript_excerpt or ""
    if 30 <= len(ex) <= 180:  # meaty but not bloated
        base += 15
    low = ex.lower()
    if ("?" in ex) or any(w in low for w in _HOOK_KEYWORDS):
        base += 10
    if per_segment_vision and per_segment_vision[0].vision is not None:
        v = per_segment_vision[0].vision
        if v.person_visible:
            base += 15
        if v.energy >= 70:
            base += 10
        elif v.energy >= 55:
            base += 5
    if arc.suggested_hook and len(arc.suggested_hook) >= 15:
        base += 5
    return max(0, min(100, base))


def _visual_proof(per_segment_vision: list[SegmentVision]) -> int | None:
    scores = [sv.vision.visual_score for sv in per_segment_vision if sv.vision is not None]
    if not scores:
        return None
    # Worst segment dominates — if any segment looks bad, the whole clip suffers
    avg = sum(scores) / len(scores)
    worst = min(scores)
    return round(0.6 * avg + 0.4 * worst)


def _retention(arc: StoryArc) -> int:
    return arc.estimated_retention or 60


def _arc_to_montage_segments(arc: StoryArc) -> list[MontageSegment]:
    return [
        MontageSegment(
            role=s.role if s.role in {"setup", "transition", "payoff", "single"} else "single",  # type: ignore[arg-type]
            start=s.start,
            end=s.end,
            transcript_excerpt=s.transcript_excerpt,
            why=s.why,
        )
        for s in arc.segments
    ]


def score_arc(
    *,
    arc: StoryArc,
    per_segment_vision: list[SegmentVision],
    campaign: dict[str, Any],
) -> MontageCandidate:
    visual = _visual_proof(per_segment_vision)
    campaign_fit = _campaign_fit_score(arc, campaign)
    payoff = _payoff_strength(arc, per_segment_vision)
    hook = _hook_strength(arc, per_segment_vision)
    editing = _editing_continuity_score(arc, per_segment_vision)
    retention = _retention(arc)

    breakdown: dict[str, int] = {
        "payoff_strength": payoff,
        "hook_strength": hook,
        "campaign_fit": campaign_fit,
        "editing_continuity": editing,
        "retention": retention,
    }
    if visual is not None:
        breakdown["visual_proof"] = visual

    # Renormalise if vision is missing
    if visual is None:
        total_weight = sum(w for k, w in ARC_WEIGHTS.items() if k != "visual_proof")
        weighted = sum(
            ARC_WEIGHTS[k] * breakdown[k] for k in ARC_WEIGHTS if k != "visual_proof"
        )
        score_total = round(weighted / total_weight)
    else:
        weighted = sum(ARC_WEIGHTS[k] * breakdown[k] for k in ARC_WEIGHTS)
        score_total = round(weighted)

    # Faceless clips (no visible person in any segment) are almost always weak
    # b-roll for a creator video — knock the score down so face-cam moments win.
    any_person = any(
        sv.vision is not None and sv.vision.person_visible for sv in per_segment_vision
    )
    if per_segment_vision and not any_person:
        score_total = round(score_total * NO_PERSON_PENALTY)

    # Montage-v2: multi-segment clips are no longer penalised as a class — the
    # per-joint editing_continuity term already prices in the transition cost.
    score_total = max(0, min(100, score_total))

    # Visual summary (concise)
    visual_summary: str | None = None
    if per_segment_vision:
        bits: list[str] = []
        for sv in per_segment_vision:
            if sv.vision is None:
                continue
            v = sv.vision
            bits.append(
                f"seg{sv.segment_idx + 1}={v.decor}/{v.action}/score{v.visual_score}"
            )
        if bits:
            visual_summary = "; ".join(bits)
        else:
            visual_summary = "vision unavailable"

    transcript_excerpt = " | ".join(
        s.transcript_excerpt for s in arc.segments if s.transcript_excerpt
    )

    return MontageCandidate(
        title=arc.title or None,
        hook=arc.suggested_hook,
        segments=_arc_to_montage_segments(arc),
        rationale=arc.viral_reason or None,
        score_total=max(0, min(100, score_total)),
        score_breakdown=breakdown,
        visual_summary=visual_summary,
        transcript_excerpt=transcript_excerpt or None,
        arc_type=arc.arc_type,
        arc=arc,
    )


def rank_and_pick(
    candidates: list[MontageCandidate], target_clip_count: int
) -> list[MontageCandidate]:
    ordered = sorted(candidates, key=lambda c: c.score_total, reverse=True)
    return ordered[: max(1, target_clip_count)]
