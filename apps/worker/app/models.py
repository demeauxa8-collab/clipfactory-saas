from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

SegmentRole = Literal["setup", "transition", "payoff", "single"]
ArcType = Literal[
    # Single-segment moment types (current policy)
    "hook",
    "reaction",
    "contrarian",
    "revelation",
    "phrase_visual_proof",
    # Legacy multi-segment types (kept for backward compat / defensive parsing)
    "setup_payoff",
    "promise_failure",
    "before_after",
    "challenge_result",
    "question_revelation",
    "decision_consequence",
    "continuous",
]


# =============================================================
# Transcript
# =============================================================


@dataclass
class TranscriptWord:
    word: str
    start: float
    end: float


@dataclass
class TranscriptSentence:
    """A punctuated sentence, straight from the ASR.

    verbose_json returns two parallel views of the same audio: "words" (precise
    timings, no punctuation) and "segments" (punctuated sentences with their own
    start/end). We used to keep only the words, then re-derive phrase boundaries
    from silences — unreliable when the ASR packs words back to back. These are
    the real boundaries.
    """

    text: str
    start: float
    end: float


@dataclass
class Transcript:
    text: str
    words: list[TranscriptWord]
    language: str | None = None
    # Optional + empty by default: older cached transcripts and every hand-built
    # Transcript in the tests keep working without them.
    sentences: list[TranscriptSentence] = field(default_factory=list)


# =============================================================
# Video map (cheap global vision pass)
# =============================================================


@dataclass
class VideoEvent:
    id: str
    start: float
    end: float
    decor: str
    people: str
    objects: list[str]
    action: str
    transcript_summary: str
    visual_importance: int       # 0-100
    narrative_role: str          # "setup" | "payoff" | "neutral" | "transition"


@dataclass
class VideoMap:
    summary: str
    events: list[VideoEvent]


# =============================================================
# Audience heatmap (YouTube "most replayed")
# =============================================================


@dataclass
class HeatmapPoint:
    """One bucket of the re-watch curve. YouTube always returns 100 of them,
    evenly spread over the whole video."""

    start: float
    end: float
    value: float


@dataclass
class AudienceHeatmap:
    """YouTube's "most replayed" curve — the only signal in this pipeline that
    is measured audience behaviour instead of a model's opinion.

    READ THIS BEFORE USING `value`. It is normalised PER VIDEO: YouTube scales
    the curve so this video's most re-watched bucket is 1.0 and its least
    re-watched one sits near 0.0. It is not a view count, not a watch time, not
    a retention percentage, and it carries no absolute meaning whatsoever. A
    500-view vlog and a 50M-view clip both peak at exactly 1.0.

    The only legitimate question it answers is "is this moment re-watched more
    than the REST OF THIS VIDEO?" — comparisons across sources are meaningless
    and must never be made. Everything downstream therefore ranks a moment
    against this video's own points (see `percentile_of`) rather than reading
    `value` as a score.
    """

    points: list[HeatmapPoint] = field(default_factory=list)

    @classmethod
    def from_points(cls, raw: Any) -> AudienceHeatmap | None:
        """Build from yt-dlp's `heatmap` payload, or return None.

        Deliberately paranoid: this is a bonus signal fed by a third-party
        scraper whose shape can change under us, so anything unparseable is
        skipped rather than raised. No points survive -> None, and the caller
        behaves exactly as if YouTube had published no curve at all.
        """
        if not isinstance(raw, (list, tuple)):
            return None
        points: list[HeatmapPoint] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                start = float(item["start_time"])
                end = float(item["end_time"])
                value = float(item["value"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (math.isfinite(start) and math.isfinite(end) and math.isfinite(value)):
                continue
            if end <= start or value < 0:
                continue
            points.append(HeatmapPoint(start=start, end=end, value=value))
        if not points:
            return None
        points.sort(key=lambda p: p.start)
        return cls(points=points)

    def intensity_between(self, start: float, end: float) -> float | None:
        """Mean re-watch intensity over [start, end], weighted by how much of
        each bucket the window actually covers.

        None when the window lands outside the curve — the caller must then
        drop the audience term rather than invent a value for it.
        """
        lo_edge, hi_edge = (start, end) if end > start else (start, start)
        weighted = 0.0
        covered = 0.0
        for p in self.points:
            overlap = min(hi_edge, p.end) - max(lo_edge, p.start)
            if overlap > 0:
                weighted += p.value * overlap
                covered += overlap
        if covered > 0:
            return weighted / covered
        # Zero-length window, or one sitting exactly on a bucket edge: fall back
        # to the bucket containing its start.
        for p in self.points:
            if p.start <= lo_edge <= p.end:
                return p.value
        return None

    def percentile_of(self, value: float) -> float:
        """Rank of `value` among this video's own bucket intensities, 0..100.

        A rank and not a ratio, on purpose: `value` is only comparable inside
        one video, and a video that is globally little re-watched still spreads
        its own moments across the full 0..100 range instead of being scored
        down as a block.

        Ties are compared with a tolerance, and that is load-bearing rather than
        cosmetic. A window sitting on a flat stretch of the curve averages back
        to the very value the buckets carry, but through a weighted sum — so it
        lands on 0.139999999999 instead of 0.14, every equal bucket counts as
        "above", and the moment reads 15 when it should read 48. Measured on the
        fixture: a 33-point swing on identical footage.
        """
        if not self.points:
            return 0.0
        tolerance = 1e-9
        below = sum(1 for p in self.points if p.value < value - tolerance)
        equal = sum(1 for p in self.points if abs(p.value - value) <= tolerance)
        return 100.0 * (below + 0.5 * equal) / len(self.points)

    def peaks(self, limit: int = 3) -> list[HeatmapPoint]:
        """The most re-watched buckets, hottest first — for logs and debugging."""
        return sorted(self.points, key=lambda p: (-p.value, p.start))[: max(0, limit)]


# =============================================================
# Story arcs (text reasoning on transcript + video map)
# =============================================================


@dataclass
class ArcSegmentSpec:
    role: SegmentRole
    start: float
    end: float
    transcript_excerpt: str
    why: str | None = None
    # The model chooses words, not authoritative seconds. These verbatim anchors
    # let deterministic code recover the exact first and last transcript words
    # before FFmpeg sees the segment. Optional for old/simple payloads.
    start_anchor: str | None = None
    end_anchor: str | None = None
    # Internal provenance set by the deterministic transcript aligner. These
    # flags are deliberately separate from the model payload: once an explicit
    # anchor has been resolved, later phrase snapping must not move that edge.
    start_anchor_resolved: bool = False
    end_anchor_resolved: bool = False


@dataclass
class StoryArc:
    title: str
    arc_type: ArcType
    segments: list[ArcSegmentSpec]
    viral_reason: str
    estimated_retention: int       # 0-100
    continuity_risk: str            # "low" | "medium" | "high"
    suggested_hook: str | None = None
    # Montage-v2: narrative thread between distant segments (required for
    # multi-segment arcs) and the LLM's own campaign-fit self-report.
    link_reason: str | None = None
    campaign_fit_llm: int | None = None    # 0-100, LLM self-report, None if absent
    campaign_fit_reason: str | None = None
    # Editorial self-check reported by the selection model. All optional so older
    # payloads (and the simple pipeline) keep constructing StoryArc unchanged.
    opening_words: str | None = None   # first ~8 words of the clip, verbatim
    self_contained: bool = True        # understandable with zero outside context
    payoff_line: str | None = None     # verbatim line that makes the clip land


# =============================================================
# Vision (deep, on top arcs only)
# =============================================================


@dataclass
class VisionResult:
    decor: str
    person_visible: bool
    energy: int                 # 0-100
    action: str
    proof_objects: list[str]
    problems: list[str]
    visual_score: int           # 0-100
    face_center_x: float | None = None   # 0=left .. 1=right, None if no face
    burned_captions: bool = False        # source already has captions burned in


@dataclass
class SegmentVision:
    """Deep vision aggregated per segment of an arc."""

    segment_idx: int
    frames_used: int
    vision: VisionResult | None
    tokens_used: int = 0


# =============================================================
# Final scored montage (what we render)
# =============================================================


@dataclass
class MontageSegment:
    role: SegmentRole
    start: float
    end: float
    transcript_excerpt: str = ""
    why: str | None = None


@dataclass
class MontageCandidate:
    title: str | None
    hook: str | None
    segments: list[MontageSegment]
    rationale: str | None
    score_total: int               # 0-100
    score_breakdown: dict[str, int]
    visual_summary: str | None = None
    transcript_excerpt: str | None = None
    arc_type: ArcType | None = None
    arc: StoryArc | None = None
    vision_per_segment: list[SegmentVision] = field(default_factory=list)


# =============================================================
# Job context — what travels through the pipeline
# =============================================================


@dataclass
class JobContext:
    job_id: str
    user_id: str
    campaign: dict[str, Any]
    source_url: str
    target_clip_count: int
    workdir: str

    # Filled as the pipeline progresses
    source_path: str | None = None
    duration_seconds: int | None = None
    source_r2_key: str | None = None
    transcript: Transcript | None = None
    video_map: VideoMap | None = None
    # Bonus signal, absent far more often than not (young video, few views,
    # non-YouTube source, network down). Never gate a step on it.
    audience_heatmap: AudienceHeatmap | None = None
    story_arcs: list[StoryArc] = field(default_factory=list)
    montage_candidates: list[MontageCandidate] = field(default_factory=list)

    # Cost accounting
    transcription_cost_cents: int = 0
    analysis_tokens: int = 0
    vision_frames_count: int = 0
    video_map_cost_cents: int = 0
    deep_vision_cost_cents: int = 0
    render_seconds: int = 0
    storage_bytes: int = 0

    # Provider tracking
    primary_provider: str = ""
    fallback_used: bool = False


def is_long_video(duration_seconds: int | None, threshold_seconds: int = 300) -> bool:
    """Pipeline router: ≥ 5 min → story-first, < 5 min → simple."""
    return (duration_seconds or 0) >= threshold_seconds
