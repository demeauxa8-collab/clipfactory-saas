from __future__ import annotations

import os
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
    _s3().upload_file(local_path, s.r2_bucket_clips, key, ExtraArgs={"ContentType": content_type})
    return os.path.getsize(local_path)
