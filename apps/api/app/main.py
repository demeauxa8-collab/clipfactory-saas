from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import close_pool, init_pool
from .routers import billing, campaigns, clips, credits, feedback, health, jobs, me
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


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ClipFactory API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_dev else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["authorization", "content-type", "stripe-signature"],
    )

    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(credits.router)
    app.include_router(campaigns.router)
    app.include_router(jobs.router)
    app.include_router(clips.router)
    app.include_router(feedback.router)
    app.include_router(billing.router)

    return app


app = create_app()
