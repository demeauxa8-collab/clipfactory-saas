from __future__ import annotations

from dataclasses import dataclass

import asyncpg

TRIAL_PLAN_CODE = "trial"

# How many jobs a trial account may run in total. Credits alone are not a
# sufficient guard: 15 credits would otherwise buy fifteen one-minute videos
# instead of the single real one we want to show off.
TRIAL_MAX_JOBS = 1

# How many clips of a finished job a trial account can download: none.
#
# The clips are still rendered and stored — the visitor sees the real thing,
# scored and captioned, and paying unlocks the files instantly instead of
# starting a render. What is free is the analysis, not the deliverable. Handing
# out one finished clip lets a visitor take the value and leave.
TRIAL_UNLOCKED_CLIPS = 0


@dataclass(frozen=True)
class Entitlements:
    """What a user is allowed to do right now, plan and trial rules folded in."""

    plan_code: str
    status: str
    max_video_minutes: int
    max_clips_per_video: int
    max_concurrent_jobs: int

    @property
    def is_trial(self) -> bool:
        return self.plan_code == TRIAL_PLAN_CODE

    @property
    def max_jobs_total(self) -> int | None:
        """Lifetime job cap, or None when unlimited."""
        return TRIAL_MAX_JOBS if self.is_trial else None

    def clip_is_locked(self, idx: int) -> bool:
        """True when this clip needs a paid plan to be downloaded."""
        return self.is_trial and idx >= TRIAL_UNLOCKED_CLIPS


async def load(conn: asyncpg.Connection, user_id: str) -> Entitlements | None:
    """Resolves the plan currently backing this user, or None if they have none.

    A paid subscription always wins over the trial: the trial row is created
    with a null current_period_end, so `nulls last` pushes it behind any real
    subscription the moment one exists.
    """
    row = await conn.fetchrow(
        """
        select s.plan_code, s.status,
               p.max_video_minutes, p.max_clips_per_video, p.max_concurrent_jobs
          from subscriptions s
          join plan_definitions p on p.code = s.plan_code
         where s.user_id = $1 and s.status in ('trialing', 'active')
         order by s.current_period_end desc nulls last
         limit 1
        """,
        user_id,
    )
    if row is None:
        return None
    return Entitlements(
        plan_code=row["plan_code"],
        status=row["status"],
        max_video_minutes=int(row["max_video_minutes"]),
        max_clips_per_video=int(row["max_clips_per_video"]),
        max_concurrent_jobs=int(row["max_concurrent_jobs"]),
    )
