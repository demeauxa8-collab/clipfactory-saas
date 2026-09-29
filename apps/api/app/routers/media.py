"""Serve local media using short-lived HMAC URLs issued by the clips API."""

from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..settings import get_settings

router = APIRouter(tags=["media"])


@router.get("/media/{key:path}")
async def get_media(
    key: str, exp: str = "", sig: str = "", download: str = Query(default="0"),
) -> FileResponse:
    settings = get_settings()
    if settings.storage_backend != "local":
        raise HTTPException(status_code=404)
    try:
        expiry = int(exp)
    except ValueError as exc:
        raise HTTPException(status_code=403) from exc
    expected = hmac.new(settings.media_signing_secret.encode("utf-8"),
                        f"{key}|{expiry}".encode(), hashlib.sha256).hexdigest()
    if expiry < time.time() or not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=403)

    relative = PurePosixPath(key)
    if not key or relative.is_absolute() or ".." in relative.parts or "\x00" in key:
        raise HTTPException(status_code=404)
    root = Path(settings.storage_local_dir).resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(
        path, media_type="video/mp4",
        filename=path.name if download == "1" else None,
        content_disposition_type="attachment",
        headers={"Cache-Control": "private, max-age=600"},
    )
