import hashlib
import json
from pathlib import Path

import pytest

from app.pipeline.audio_assets import (
    MANIFEST_VERSION,
    AudioAssetError,
    load_audio_asset_manifest,
    parse_audio_asset_manifest,
)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _asset(
    *,
    asset_id: str = "music_uplift_01",
    kind: str = "music",
    relative_path: str = "music/uplift.wav",
    content: bytes = b"licensed-local-audio",
    **overrides: object,
) -> dict[str, object]:
    asset: dict[str, object] = {
        "id": asset_id,
        "kind": kind,
        "relative_path": relative_path,
        "sha256": _sha256(content),
        "duration_seconds": 12.5,
        "license": {
            "status": "cleared",
            "scopes": ["commercial_social_organic", "commercial_social_paid"],
            "source": "licensed_library",
            "attribution_required": False,
        },
        "moods": ["uplifting", "modern"],
        "tags": ["productivity", "clean"],
        "energy": 64,
        "mix": {
            "default_gain_db": -24.0,
            "max_gain_db": -16.0,
            "fade_in_ms": 180,
            "fade_out_ms": 350,
        },
        "bpm": 120,
        "beat_offset_seconds": 0.18,
        "loop_safe": True,
    }
    asset.update(overrides)
    return asset


def _manifest(*assets: dict[str, object]) -> dict[str, object]:
    return {"version": MANIFEST_VERSION, "assets": list(assets)}


def _write_asset(root: Path, relative_path: str, content: bytes) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_resolve_uses_only_verified_manifest_id_and_safe_llm_catalog(tmp_path: Path) -> None:
    content = b"licensed-local-audio"
    local_file = _write_asset(tmp_path, "music/uplift.wav", content)
    registry = parse_audio_asset_manifest(_manifest(_asset(content=content)), asset_root=tmp_path)

    resolved = registry.resolve("music_uplift_01")

    assert resolved.path == local_file.resolve()
    assert resolved.asset.license.status == "cleared"
    assert registry.llm_catalog() == [
        {
            "id": "music_uplift_01",
            "kind": "music",
            "moods": ["uplifting", "modern"],
            "tags": ["productivity", "clean"],
            "roles": [],
            "energy": 64,
            "bpm": 120,
            "loop_safe": True,
        }
    ]
    assert "relative_path" not in registry.llm_catalog()[0]
    assert "sha256" not in registry.llm_catalog()[0]


@pytest.mark.parametrize(
    "asset_id",
    ["../music_uplift_01", "music/uplift", "https://example.com/audio.mp3", "MUSIC_UPLIFT_01"],
)
def test_resolution_rejects_urls_paths_and_unsafe_ids(tmp_path: Path, asset_id: str) -> None:
    content = b"licensed-local-audio"
    _write_asset(tmp_path, "music/uplift.wav", content)
    registry = parse_audio_asset_manifest(_manifest(_asset(content=content)), asset_root=tmp_path)

    with pytest.raises(AudioAssetError, match="safe manifest ID"):
        registry.resolve(asset_id)


@pytest.mark.parametrize(
    "relative_path",
    ["../outside.wav", "/tmp/outside.wav", "music\\outside.wav", "https://example.com/a.wav"],
)
def test_manifest_rejects_absolute_traversal_and_url_paths(
    tmp_path: Path, relative_path: str
) -> None:
    with pytest.raises(AudioAssetError, match="relative_path"):
        parse_audio_asset_manifest(
            _manifest(_asset(relative_path=relative_path)), asset_root=tmp_path
        )


def test_resolution_rejects_symlink_that_escapes_asset_root(tmp_path: Path) -> None:
    content = b"licensed-local-audio"
    outside = tmp_path.parent / "outside.wav"
    outside.write_bytes(content)
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    (music_dir / "uplift.wav").symlink_to(outside)
    registry = parse_audio_asset_manifest(_manifest(_asset(content=content)), asset_root=tmp_path)

    with pytest.raises(AudioAssetError, match="escapes asset_root"):
        registry.resolve("music_uplift_01")


def test_resolution_rejects_missing_or_tampered_file(tmp_path: Path) -> None:
    content = b"licensed-local-audio"
    registry = parse_audio_asset_manifest(_manifest(_asset(content=content)), asset_root=tmp_path)

    with pytest.raises(AudioAssetError, match="missing"):
        registry.resolve("music_uplift_01")

    local_file = _write_asset(tmp_path, "music/uplift.wav", b"tampered")
    assert local_file.exists()
    with pytest.raises(AudioAssetError, match="checksum"):
        registry.resolve("music_uplift_01")


def test_resolution_requires_cleared_license_scope(tmp_path: Path) -> None:
    content = b"licensed-local-audio"
    _write_asset(tmp_path, "music/uplift.wav", content)
    organic_only = _asset(
        content=content,
        license={
            "status": "cleared",
            "scopes": ["commercial_social_organic"],
            "source": "licensed_library",
            "attribution_required": False,
        },
    )
    registry = parse_audio_asset_manifest(_manifest(organic_only), asset_root=tmp_path)

    with pytest.raises(AudioAssetError, match="not cleared"):
        registry.resolve("music_uplift_01", required_scope="commercial_social_paid")
    assert registry.resolve("music_uplift_01", required_scope="commercial_social_organic")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", "music-unsafe", "asset.id"),
        ("sha256", "abcd", "sha256"),
        ("energy", 101, "energy"),
        ("duration_seconds", 0, "duration_seconds"),
        (
            "mix",
            {"default_gain_db": 1, "max_gain_db": 0, "fade_in_ms": 0, "fade_out_ms": 0},
            "default_gain",
        ),
        (
            "mix",
            {"default_gain_db": -12, "max_gain_db": -16, "fade_in_ms": 0, "fade_out_ms": 0},
            "must not exceed",
        ),
    ],
)
def test_manifest_rejects_invalid_ids_hashes_and_bounded_mix(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    with pytest.raises(AudioAssetError, match=message):
        parse_audio_asset_manifest(_manifest(_asset(**{field: value})), asset_root=tmp_path)


def test_manifest_requires_exact_version_and_unique_ids(tmp_path: Path) -> None:
    content = b"licensed-local-audio"
    with pytest.raises(AudioAssetError, match="version"):
        parse_audio_asset_manifest(
            {"version": MANIFEST_VERSION + 1, "assets": [_asset()]}, asset_root=tmp_path
        )
    with pytest.raises(AudioAssetError, match=r"duplicate asset\.id"):
        parse_audio_asset_manifest(
            _manifest(
                _asset(content=content),
                _asset(relative_path="music/uplift_02.wav", content=content),
            ),
            asset_root=tmp_path,
        )


def test_sfx_has_no_bpm_or_loop_and_exposes_roles(tmp_path: Path) -> None:
    content = b"short-sfx"
    _write_asset(tmp_path, "sfx/whoosh.wav", content)
    sfx = _asset(
        asset_id="sfx_whoosh_01",
        kind="sfx",
        relative_path="sfx/whoosh.wav",
        content=content,
        bpm=None,
        beat_offset_seconds=None,
        loop_safe=False,
        roles=["transition", "punch_in"],
    )
    registry = parse_audio_asset_manifest(_manifest(sfx), asset_root=tmp_path)

    assert registry.resolve("sfx_whoosh_01").asset.kind == "sfx"
    assert registry.llm_catalog()[0]["roles"] == ["transition", "punch_in"]

    bad_sfx = dict(sfx)
    bad_sfx["loop_safe"] = True
    with pytest.raises(AudioAssetError, match="cannot be loop_safe"):
        parse_audio_asset_manifest(_manifest(bad_sfx), asset_root=tmp_path)


def test_loads_local_json_manifest_only(tmp_path: Path) -> None:
    content = b"licensed-local-audio"
    _write_asset(tmp_path, "music/uplift.wav", content)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        '{"version": 1, "assets": ['
        + json.dumps(_asset(content=content))
        + "]}",
        encoding="utf-8",
    )

    registry = load_audio_asset_manifest(manifest_path, asset_root=tmp_path)

    assert registry.resolve("music_uplift_01").path.name == "uplift.wav"
    with pytest.raises(AudioAssetError, match="not a URL"):
        load_audio_asset_manifest("https://example.com/manifest.json", asset_root=tmp_path)
