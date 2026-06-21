"""Client analytics ingest.

The web app posts product/behaviour events here. Events are attributed to the
authenticated user and stored first-party (+ mirrored to PostHog if configured).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..auth import CurrentUser, current_user
from ..db import get_pool
from ..rate_limit import LIMIT_EVENTS, limiter
from ..schemas import EventAck, EventIn
from ..services import analytics

router = APIRouter(tags=["events"])


@router.post("/events", response_model=EventAck)
@limiter.limit(LIMIT_EVENTS)
async def ingest_event(
    request: Request, payload: EventIn, user: CurrentUser = Depends(current_user)
) -> EventAck:
    analytics.fire_and_forget(
        analytics.track_with_pool(
            get_pool(),
            event_name=payload.event,
            source="web",
            user_id=user.user_id,
            anon_id=payload.anon_id,
            session_id=payload.session_id,
            properties=dict(payload.properties),
            path=payload.path,
            referrer=payload.referrer,
        )
    )
    return EventAck()
