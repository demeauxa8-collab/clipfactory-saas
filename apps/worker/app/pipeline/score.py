from __future__ import annotations

from typing import Any

from ..models import (
    MontageCandidate,
    MontageSegment,
    SegmentVision,
    StoryArc,
)

# Story-arc weights (multi-segment).
# Short-form lives or dies on *watchability*: a person on camera delivering a
# punchy line beats a "high-retention" faceless screencast every time. So the
# real visual signal dominates, and the LLM's self-reported retention — which is
# chronically inflated — is discounted.
ARC_WEIGHTS = {
    "visual_proof": 0.35,
    "payoff_strength": 0.20,
    "setup_clarity": 0.15,
    "retention": 0.10,
    "campaign_fit": 0.10,
    "editing_continuity": 0.10,
}

# A clip with no visible person anywhere is almost always weak b-roll for a
# creator video — multiply the final score down hard.
NO_PERSON_PENALTY = 0.65


def _campaign_fit_score(arc: StoryArc, campaign: dict[str, Any]) -> int:
    """Lightweight V1: keyword overlap + avoid-list penalty."""
    fit = 60  # neutral baseline
    txt = " ".join(
        [
            arc.title or "",
            arc.viral_reason or "",
            arc.suggested_hook or "",
            *[s.transcript_excerpt or "" for s in arc.segments],
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


def _editing_continuity_score(arc: StoryArc, per_segment_vision: list[SegmentVision]) -> int:
    """Higher = easier to cut. Penalises multi-segment with visual problems and
    high-risk transitions claimed by the LLM."""
    base = 100
    if arc.continuity_risk == "high":
        base -= 25
    elif arc.continuity_risk == "medium":
        base -= 10

    # Multi-segment: small base penalty (concat is always slightly harder than a single cut)
    if len(arc.segments) > 1:
        base -= 5 * (len(arc.segments) - 1)

    for sv in per_segment_vision:
        if sv.vision is None:
            continue
        if "no face" in sv.vision.problems:
            base -= 8
        if "dark" in sv.vision.problems:
            base -= 5
        if "unreadable slide" in sv.vision.problems:
            base -= 3

    return max(0, min(100, base))


def _payoff_strength(arc: StoryArc, per_segment_vision: list[SegmentVision]) -> int:
    """Strength of the last segment's payoff. Uses LLM signals + last-segment vision."""
    base = arc.estimated_retention or 60
    if arc.arc_type in {"setup_payoff", "promise_failure", "before_after", "decision_consequence"}:
        base += 10
    if per_segment_vision:
        last = per_segment_vision[-1].vision
        if last is not None:
            if last.energy >= 70:
                base += 10
            if last.visual_score >= 70:
                base += 5
    return max(0, min(100, base))


def _setup_clarity(arc: StoryArc, per_segment_vision: list[SegmentVision]) -> int:
    """How clearly the first segment frames what the clip is about."""
    base = 60
    first_seg = arc.segments[0] if arc.segments else None
    if first_seg and first_seg.transcript_excerpt:
        # Excerpt length is a proxy for clarity: too short → unclear, too long → bloated
        excerpt_len = len(first_seg.transcript_excerpt)
        if 40 <= excerpt_len <= 200:
            base += 15
        if arc.suggested_hook:
            base += 10
    if per_segment_vision:
        first_v = per_segment_vision[0].vision
        if first_v is not None and first_v.person_visible:
            base += 8
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
    setup = _setup_clarity(arc, per_segment_vision)
    editing = _editing_continuity_score(arc, per_segment_vision)
    retention = _retention(arc)

    breakdown: dict[str, int] = {
        "payoff_strength": payoff,
        "setup_clarity": setup,
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
