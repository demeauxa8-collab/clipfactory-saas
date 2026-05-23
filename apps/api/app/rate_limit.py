"""Rate limiting wired around the FastAPI app.

We key off the authenticated user when present, IP otherwise. Limits sit on the
write endpoints (creates) because reads are cheap and gated by RLS.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _key(request: Request) -> str:
    # If the auth middleware/dep ran before the limiter, it stashed the user_id.
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_key, default_limits=[])

# Named limits used as decorators on routes.
LIMIT_JOBS_CREATE = "10/minute"
LIMIT_CAMPAIGNS_CREATE = "30/hour"
LIMIT_FEEDBACK_CREATE = "60/minute"
LIMIT_BILLING_CHECKOUT = "5/hour"
LIMIT_STRIPE_WEBHOOK = "120/minute"  # IP-based, generous for retries
