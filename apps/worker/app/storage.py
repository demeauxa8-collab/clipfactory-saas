from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.config import Config

from .settings import get_settings


@lru_cache(maxsize=1)
def _s3():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.r2_endpoint_url,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def upload_file(local_path: str, key: str, content_type: str = "video/mp4") -> int:
    """Persist a clip and return its byte size.

    Two backends:
    - "r2"   → upload to Cloudflare R2 (prod)
    - "local"→ copy to STORAGE_LOCAL_DIR/<key> (dev / pipeline validation)

    `key` keeps the same shape in both modes (clips/<user>/<job>/<idx>.mp4)
    so the rest of the pipeline doesn't care which backend is active.
    """
    s = get_settings()
    if s.storage_backend == "local":
        dest = Path(s.storage_local_dir) / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, dest)
        return os.path.getsize(dest)
    _s3().upload_file(local_path, s.r2_bucket_clips, key, ExtraArgs={"ContentType": content_type})
    return os.path.getsize(local_path)
