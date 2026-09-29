from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import media
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


def test_local_storage_configuration_validation(tmp_path: Path):
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
