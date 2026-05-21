from __future__ import annotations

from functools import lru_cache

import boto3
from botocore.config import Config

from ..settings import get_settings


@lru_cache(maxsize=1)
def _s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def presigned_get_url(key: str, expires_in: int = 600) -> str:
    settings = get_settings()
    client = _s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_clips, "Key": key},
        ExpiresIn=expires_in,
    )


def upload_file(local_path: str, key: str, content_type: str = "video/mp4") -> None:
    settings = get_settings()
    client = _s3_client()
    client.upload_file(
        local_path,
        settings.r2_bucket_clips,
        key,
        ExtraArgs={"ContentType": content_type},
    )
