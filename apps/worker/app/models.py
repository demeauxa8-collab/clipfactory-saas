from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


@dataclass
class TextCandidate:
    start: float
    end: float
    hook_score_text: int  # 0-100
    emotion_score: int    # 0-100
    transcript_excerpt: str
    why: str
    suggested_title: str | None = None
    suggested_hook: str | None = None


@dataclass
class VisionResult:
    decor: str
    person_visible: bool
    energy: int           # 0-100
    action: str
    proof_objects: list[str]
    problems: list[str]
    visual_score: int     # 0-100


@dataclass
class ScoredClip:
    candidate: TextCandidate
    vision: VisionResult | None
    campaign_fit: int     # 0-100
    editing_difficulty: int  # 0-100
    score_total: int      # 0-100
    score_breakdown: dict[str, int]


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
    candidates: list[TextCandidate] = field(default_factory=list)
    scored: list[ScoredClip] = field(default_factory=list)
    # Cost accounting
    transcription_cost_cents: int = 0
    analysis_tokens: int = 0
    vision_frames_count: int = 0
    render_seconds: int = 0
    storage_bytes: int = 0
