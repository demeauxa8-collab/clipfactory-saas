from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .db import close_pool, get_pool, init_pool
from .log_sanitize import scrub_email_values
from .rate_limit import limiter
from .routers import (
    admin,
    auth,
    billing,
    campaigns,
    clips,
    credits,
    events,
    feedback,
    health,
    jobs,
    me,
    public,
)
from .services import analytics
from .settings import get_settings

# Paths we never record as analytics (noise / infra).
_SKIP_PREFIXES = ("/health", "/docs", "/openapi", "/redoc")


def _configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper())
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            scrub_email_values,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper())),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging(settings.log_level)
    await init_pool()
    yield
    await close_pool()


def _assert_safe_cors(allowed: list[str], env: str) -> None:
    if env == "prod" and ("*" in allowed or not allowed):
        raise RuntimeError(
            "Refusing to start: CORS_ALLOW_ORIGINS must be an explicit whitelist in prod."
        )


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": {"code": "rate_limit_exceeded", "message": str(exc.detail)}},
    )


def _record_api_request(request: Request, status_code: int) -> None:
    """Schedule an analytics event for one API call. Best-effort, non-blocking."""
    if request.method == "OPTIONS":
        return
    path = request.url.path
    if path == "/events" or path.startswith(_SKIP_PREFIXES):
        return
    route = request.scope.get("route")
    route_template = getattr(route, "path", path)
    analytics.fire_and_forget(
        analytics.track_with_pool(
            get_pool(),
            event_name="api_request",
            source="api",
            user_id=getattr(request.state, "user_id", None),
            properties={
                "method": request.method,
                "route": route_template,
                "status": status_code,
            },
            path=path,
        )
    )


def create_app() -> FastAPI:
    settings = get_settings()
    _assert_safe_cors(settings.cors_origins_list, settings.env)

    app = FastAPI(
        title="ClipFactory API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_dev else None,
        redoc_url=None,
    )

    # Rate limit must be wired before routers
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["authorization", "content-type", "stripe-signature"],
    )

    app.include_router(health.router)
    app.include_router(public.router)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(credits.router)
    app.include_router(campaigns.router)
    app.include_router(jobs.router)
    app.include_router(clips.router)
    app.include_router(feedback.router)
    app.include_router(billing.router)
    app.include_router(events.router)
    app.include_router(admin.router)

    # Auto-track every API call (route template + status). Runs after the route so
    # request.state.user_id (stashed by the auth dep) is available for attribution.
    @app.middleware("http")
    async def track_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        try:
            _record_api_request(request, response.status_code)
        except Exception:
            pass
        return response

    return app


app = create_app()
