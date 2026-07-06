from __future__ import annotations

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
class Transcript:
    text: str
    words: list[TranscriptWord]
    language: str | None = None


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
# Story arcs (text reasoning on transcript + video map)
# =============================================================


@dataclass
class ArcSegmentSpec:
    role: SegmentRole
    start: float
    end: float
    transcript_excerpt: str
    why: str | None = None


@dataclass
class StoryArc:
    title: str
    arc_type: ArcType
    segments: list[ArcSegmentSpec]
    viral_reason: str
    estimated_retention: int       # 0-100
    continuity_risk: str            # "low" | "medium" | "high"
    suggested_hook: str | None = None


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
