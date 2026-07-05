from __future__ import annotations

import os
import shutil
from functools import lru_cache

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
    s = get_settings()
    if s.storage_backend == "local":
        # Dev/validation mode: copy into STORAGE_LOCAL_DIR instead of R2 so the
        # pipeline runs end-to-end without Cloudflare creds. Open the files from
        # that directory directly (the web download link needs R2).
        dest = os.path.join(s.storage_local_dir, key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(local_path, dest)
        return os.path.getsize(dest)
    _s3().upload_file(local_path, s.r2_bucket_clips, key, ExtraArgs={"ContentType": content_type})
    return os.path.getsize(local_path)
