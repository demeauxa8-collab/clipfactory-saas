from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.routers import clips, media
from app.services import storage
from app.settings import Settings


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = SimpleNamespace(
        storage_backend="local", storage_local_dir=str(tmp_path),
        media_signing_secret="x" * 32, api_base_url="http://testserver",
    )
    monkeypatch.setattr(media, "get_settings", lambda: settings)
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(media.router)
    return TestClient(app), tmp_path


def test_signed_media_and_range(client):
    http, root = client
    (root / "clips").mkdir()
    (root / "clips" / "sample.mp4").write_bytes(b"a" * 200)
    url = storage.presigned_get_url("clips/sample.mp4")
    assert http.get(url).status_code == 200
    response = http.get(url, headers={"Range": "bytes=0-99"})
    assert response.status_code == 206
    assert len(response.content) == 100
    assert response.headers["content-type"].startswith("video/mp4")
    assert "content-disposition" not in response.headers
    assert "attachment" in http.get(url + "&download=1").headers["content-disposition"]


def test_signature_expiry_tamper_and_missing(client):
    http, root = client
    (root / "sample.mp4").write_bytes(b"video")
    url = storage.presigned_get_url("sample.mp4")
    assert http.get(storage.presigned_get_url("sample.mp4", expires_in=-1)).status_code == 403
    assert http.get(url.replace("sig=", "sig=0")).status_code == 403
    assert http.get(url.replace("sample.mp4", "other.mp4")).status_code == 403
    assert http.get(storage.presigned_get_url("absent.mp4")).status_code == 404


@pytest.mark.asyncio
async def test_path_escape_and_symlink(client):
    _, root = client
    outside = root.parent / "outside.mp4"
    outside.write_bytes(b"outside")
    (root / "link.mp4").symlink_to(outside)
    for key in ("../outside.mp4", "/outside.mp4", "link.mp4"):
        url = storage.presigned_get_url(key)
        query = parse_qs(urlparse(url).query)
        with pytest.raises(Exception) as exc:
            await media.get_media(key, query["exp"][0], query["sig"][0])
        assert getattr(exc.value, "status_code", None) == 404
    outside.unlink()


def test_local_storage_configuration_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("STORAGE_LOCAL_DIR", raising=False)
    monkeypatch.delenv("MEDIA_SIGNING_SECRET", raising=False)
    base = dict(
        database_url="postgres://example", supabase_url="https://example.invalid",
        supabase_service_role_key="x", supabase_jwt_secret="x",
        stripe_secret_key="x", stripe_webhook_secret="x", stripe_starter_price_id="x",
        openai_api_key="x", anthropic_api_key="x", storage_backend="local",
    )
    with pytest.raises(ValueError):
        Settings(**base, media_signing_secret="x" * 32)
    with pytest.raises(ValueError):
        Settings(**base, storage_local_dir=str(tmp_path), media_signing_secret="short")
    assert Settings(**base, storage_local_dir=str(tmp_path), media_signing_secret="x" * 32)


@pytest.mark.asyncio
async def test_clip_download_keeps_ownership_gate_and_storage_contract(client, monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.row = {"r2_key": "clips/owned.mp4"}

        async def fetchrow(self, sql, clip_id, user_id):
            assert "c.user_id = $2" in sql and "j.status = 'completed'" in sql
            assert (clip_id, user_id) == ("clip-1", "user-1")
            return self.row

    connection = FakeConnection()

    class Acquired:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, *_):
            return False

    pool = SimpleNamespace(acquire=lambda: Acquired())
    monkeypatch.setattr(clips, "get_pool", lambda: pool)
    monkeypatch.setattr(clips.analytics, "track_with_pool", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(clips.analytics, "fire_and_forget", lambda *_args: None)
    user = SimpleNamespace(user_id="user-1")

    local = await clips.download_clip("clip-1", user)
    assert "/media/clips/owned.mp4?" in local.url
    assert local.expires_in_seconds == 600

    class FakeS3:
        def generate_presigned_url(self, *_args, **_kwargs):
            return "https://r2.example/owned.mp4"

    monkeypatch.setattr(storage, "_s3_client", lambda: FakeS3())
    monkeypatch.setattr(storage, "get_settings", lambda: SimpleNamespace(
        storage_backend="r2", r2_bucket_clips="clips",
    ))
    remote = await clips.download_clip("clip-1", user)
    assert remote.url == "https://r2.example/owned.mp4"

    connection.row = None
    with pytest.raises(HTTPException) as exc:
        await clips.download_clip("clip-1", user)
    assert exc.value.status_code == 404
