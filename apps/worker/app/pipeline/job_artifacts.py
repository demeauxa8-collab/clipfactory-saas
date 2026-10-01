"""Retain reviewable stage inputs and outcomes under an attempt-specific key."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import structlog

from ..models import JobContext
from ..settings import get_settings
from ..storage import upload_file

log = structlog.get_logger()


async def checkpoint_job(ctx: JobContext, stage: str, payload: dict[str, Any]) -> str | None:
    """Best-effort diagnostic checkpoint; delivered clip manifests are mandatory.

    These are audit/replay artifacts, not executable instructions for a retry.
    Explicit attempt keys prevent older attempts overwriting newer evidence.
    """
    if not stage or any(c not in "abcdefghijklmnopqrstuvwxyz_" for c in stage):
        raise ValueError("invalid checkpoint stage")
    if get_settings().storage_backend == "local":
        return None
    path = Path(ctx.workdir) / f"{stage}.json"
    key = f"jobs/{ctx.user_id}/{ctx.job_id}/{ctx.run_token}/{stage}.json"
    document = {
        "schema_version": "1.0",
        "job_id": ctx.job_id,
        "attempt_id": ctx.run_token,
        "stage": stage,
        **payload,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False, allow_nan=False) + "\n")
        ctx.storage_bytes += await asyncio.to_thread(
            upload_file, str(path), key, "application/json"
        )
    except Exception as exc:
        log.warning(
            "pipeline.checkpoint_failed",
            job_id=ctx.job_id,
            stage=stage,
            error_type=type(exc).__name__,
        )
        return None
    log.info("pipeline.checkpoint_saved", job_id=ctx.job_id, stage=stage, key=key)
    return key
