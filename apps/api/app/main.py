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

from .db import close_pool, init_pool
from .rate_limit import limiter
from .routers import (
    admin,
    auth,
    billing,
    campaigns,
    clips,
    credits,
    feedback,
    health,
    jobs,
    me,
    public,
)
from .settings import get_settings


def _configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper())
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
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
    app.include_router(admin.router)

    return app


app = create_app()
