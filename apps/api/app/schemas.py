from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

JobStatus = Literal[
    "queued",
    "downloading",
    "transcribing",
    "analyzing",
    "rendering",
    "completed",
    "failed",
    "canceled",
]

FeedbackKind = Literal["good", "bad"]


# =============================================================
# Profile, subscription, credits
# =============================================================


class Profile(BaseModel):
    user_id: str
    email: str
    full_name: str | None = None


class SubscriptionInfo(BaseModel):
    plan_code: str
    status: str
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class CreditBalance(BaseModel):
    balance: int


class MeResponse(BaseModel):
    profile: Profile
    subscription: SubscriptionInfo | None = None
    credits: CreditBalance


# =============================================================
# Auth abuse protection
# =============================================================


class TurnstileVerifyRequest(BaseModel):
    token: str = Field(min_length=1, max_length=4096)


class TurnstileVerifyResponse(BaseModel):
    ok: bool


# =============================================================
# Campaigns
# =============================================================


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    audience: str = Field(default="", max_length=400)
    niche: str = Field(default="", max_length=120)
    tone: str = Field(default="", max_length=120)
    goal: str = Field(default="", max_length=400)
    avoid_topics: list[str] = Field(default_factory=list)
    example_hooks: list[str] = Field(default_factory=list)


class Campaign(BaseModel):
    id: str
    name: str
    audience: str
    niche: str
    tone: str
    goal: str
    avoid_topics: list[str]
    example_hooks: list[str]
    created_at: datetime


# =============================================================
# Jobs
# =============================================================


class JobCreate(BaseModel):
    campaign_id: str
    source_url: HttpUrl
    target_clip_count: int = Field(default=3, ge=1, le=3)


class JobOut(BaseModel):
    id: str
    campaign_id: str | None = None
    source_url: str
    target_clip_count: int
    status: JobStatus
    current_step: str | None = None
    duration_seconds: int | None = None
    credits_estimated: int
    credits_charged: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    failed_step: str | None = None
    retry_count: int = 0
    transcription_cost_cents: int | None = None
    analysis_tokens: int | None = None
    vision_frames_count: int | None = None
    render_seconds: int | None = None
    storage_bytes: int | None = None
    total_cost_estimate_cents: int | None = None
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


# =============================================================
# Clips
# =============================================================


SegmentRole = Literal["setup", "transition", "payoff", "single"]


class ClipSegment(BaseModel):
    role: SegmentRole = "single"
    start: float
    end: float
    transcript_excerpt: str = ""


class ClipOut(BaseModel):
    id: str
    job_id: str
    idx: int
    title: str | None = None
    hook_text: str | None = None
    rationale: str | None = None
    visual_summary: str | None = None
    transcript_excerpt: str | None = None
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    rendered_duration_seconds: float | None = None
    segments: list[ClipSegment] = Field(default_factory=list)
    score_total: int | None = None
    score_breakdown: dict[str, int] | None = None
    width: int
    height: int


class ClipDownloadUrl(BaseModel):
    url: str
    expires_in_seconds: int


class JobWithClips(BaseModel):
    job: JobOut
    clips: list[ClipOut]


# =============================================================
# Feedback
# =============================================================


class FeedbackCreate(BaseModel):
    kind: FeedbackKind
    note: str | None = Field(default=None, max_length=500)


class Feedback(BaseModel):
    id: str
    clip_id: str
    kind: FeedbackKind
    note: str | None
    created_at: datetime


# =============================================================
# Billing
# =============================================================


class CheckoutCreate(BaseModel):
    plan_code: Literal["starter"] = "starter"


class CheckoutResponse(BaseModel):
    checkout_url: str
