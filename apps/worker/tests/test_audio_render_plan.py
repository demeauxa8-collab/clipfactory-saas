import hashlib
from pathlib import Path

import pytest

from app.pipeline.audio_assets import AudioAssetRegistry, parse_audio_asset_manifest
from app.pipeline.audio_render_plan import (
    DUCKING_PRESETS,
    AudioRenderPlanError,
    resolve_audio_render_plan,
)
from app.pipeline.edl import CompiledEDL, CompiledMusicTrack, CompiledSFXCue


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _manifest_asset(
    *,
    asset_id: str,
    kind: str,
    relative_path: str,
    content: bytes,
    scopes: list[str] | None = None,
    loop_safe: bool = False,
    max_gain_db: float = -8.0,
) -> dict[str, object]:
    asset: dict[str, object] = {
        "id": asset_id,
        "kind": kind,
        "relative_path": relative_path,
        "sha256": _sha256(content),
        "duration_seconds": 10.0,
        "license": {
            "status": "cleared",
            "scopes": scopes or ["commercial_social_paid"],
            "source": "licensed_library",
            "attribution_required": False,
        },
        "moods": ["modern"],
        "tags": ["clean"],
        "energy": 50,
        "mix": {
            "default_gain_db": -24.0,
            "max_gain_db": max_gain_db,
            "fade_in_ms": 120,
            "fade_out_ms": 240,
        },
        "loop_safe": loop_safe,
    }
    if kind == "music":
        asset["bpm"] = 120
        asset["beat_offset_seconds"] = 0.0
    return asset


def _registry(tmp_path: Path) -> AudioAssetRegistry:
    music_content = b"verified-music"
    sfx_content = b"verified-sfx"
    for relative_path, content in (("music/bed.wav", music_content), ("sfx/hit.wav", sfx_content)):
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return parse_audio_asset_manifest(
        {
            "version": 1,
            "assets": [
                _manifest_asset(
                    asset_id="music_bed_01",
                    kind="music",
                    relative_path="music/bed.wav",
                    content=music_content,
                    loop_safe=True,
                    max_gain_db=-16.0,
                ),
                _manifest_asset(
                    asset_id="sfx_hit_01",
                    kind="sfx",
                    relative_path="sfx/hit.wav",
                    content=sfx_content,
                    max_gain_db=-7.0,
                ),
            ],
        },
        asset_root=tmp_path,
    )


def _edl(
    *,
    duration_ms: int = 16_000,
    music: tuple[CompiledMusicTrack, ...] = (),
    sfx: tuple[CompiledSFXCue, ...] = (),
) -> CompiledEDL:
    return CompiledEDL(
        schema_version="2.0",
        editorial_thesis="Audio plan fixture",
        fps=30,
        width=1080,
        height=1920,
        duration_ms=duration_ms,
        duration_frames=duration_ms * 30 // 1000,
        shots=(),
        music=music,
        sfx=sfx,
        decode_islands=(),
    )


def _music(**overrides: object) -> CompiledMusicTrack:
    values: dict[str, object] = {
        "asset_id": "music_bed_01",
        "timeline_in_ms": 0,
        "timeline_out_ms": 16_000,
        "gain_db": -10.0,
        "ducking_db": -10.0,
        "fade_in_ms": 200,
        "fade_out_ms": 300,
        "loop": True,
    }
    values.update(overrides)
    return CompiledMusicTrack(**values)  # type: ignore[arg-type]


def _sfx(**overrides: object) -> CompiledSFXCue:
    values: dict[str, object] = {
        "asset_id": "sfx_hit_01",
        "timeline_at_ms": 2_000,
        "gain_db": -4.0,
        "shot_id": "payoff",
        "word_id": 12,
    }
    values.update(overrides)
    return CompiledSFXCue(**values)  # type: ignore[arg-type]


def test_resolves_verified_assets_clamps_gains_and_maps_closed_ducking(tmp_path: Path) -> None:
    plan = resolve_audio_render_plan(_edl(music=(_music(),), sfx=(_sfx(),)), _registry(tmp_path))

    assert plan.music[0].asset.path == (tmp_path / "music/bed.wav").resolve()
    assert plan.music[0].effective_gain_db == -16.0
    assert plan.music[0].ducking == DUCKING_PRESETS["soft_duck"]
    assert plan.sfx[0].asset.path == (tmp_path / "sfx/hit.wav").resolve()
    assert plan.sfx[0].effective_gain_db == -7.0
    assert plan.master_target_lufs == -14.0
    assert plan.master_true_peak_db == -1.5


@pytest.mark.parametrize(
    ("ducking_db", "expected"),
    [(-24.0, "voice_priority"), (-12.0, "voice_priority"), (-11.9, "soft_duck"), (0.0, "none")],
)
def test_ducking_is_reduced_to_closed_presets(
    tmp_path: Path, ducking_db: float, expected: str
) -> None:
    plan = resolve_audio_render_plan(
        _edl(music=(_music(ducking_db=ducking_db),)), _registry(tmp_path)
    )

    assert plan.music[0].ducking.id == expected


def test_registry_kind_is_authoritative_for_music_and_sfx(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    with pytest.raises(AudioRenderPlanError, match="non-music"):
        resolve_audio_render_plan(
            _edl(music=(_music(asset_id="sfx_hit_01", loop=False),)), registry
        )
    with pytest.raises(AudioRenderPlanError, match="non-SFX"):
        resolve_audio_render_plan(_edl(sfx=(_sfx(asset_id="music_bed_01"),)), registry)


def test_rejects_more_than_one_music_bed_and_duration_based_sfx_budget(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    with pytest.raises(AudioRenderPlanError, match="at most one"):
        resolve_audio_render_plan(_edl(music=(_music(), _music())), registry)

    # 16 seconds permits ceil(16 / 8) == 2 cues, so the third is rejected.
    with pytest.raises(AudioRenderPlanError, match="SFX budget exceeded"):
        resolve_audio_render_plan(
            _edl(
                sfx=(
                    _sfx(timeline_at_ms=100),
                    _sfx(timeline_at_ms=200),
                    _sfx(timeline_at_ms=300),
                )
            ),
            registry,
        )


def test_rejects_non_loop_safe_music_before_renderer(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    music_content = b"not-loop-safe"
    path = tmp_path / "music/short.wav"
    path.write_bytes(music_content)
    document = {
        "version": 1,
        "assets": [
            _manifest_asset(
                asset_id="music_short_01",
                kind="music",
                relative_path="music/short.wav",
                content=music_content,
                loop_safe=False,
            )
        ],
    }
    short_registry = parse_audio_asset_manifest(document, asset_root=tmp_path)

    with pytest.raises(AudioRenderPlanError, match="loop_safe"):
        resolve_audio_render_plan(_edl(music=(_music(asset_id="music_short_01"),)), short_registry)
    assert registry.asset_root == tmp_path.resolve()


@pytest.mark.parametrize(
    ("music", "sfx", "message"),
    [
        ((_music(gain_db=-5.0),), (), "music gain"),
        ((_music(ducking_db=-25.0),), (), "ducking"),
        ((), (_sfx(gain_db=7.0),), "SFX gain"),
        ((_music(timeline_out_ms=17_000),), (), "inside the compiled"),
        ((), (_sfx(timeline_at_ms=16_000),), "inside the compiled"),
    ],
)
def test_rechecks_compiled_numeric_and_timeline_bounds(
    tmp_path: Path,
    music: tuple[CompiledMusicTrack, ...],
    sfx: tuple[CompiledSFXCue, ...],
    message: str,
) -> None:
    with pytest.raises(AudioRenderPlanError, match=message):
        resolve_audio_render_plan(_edl(music=music, sfx=sfx), _registry(tmp_path))


def test_registry_hash_and_rights_are_rechecked_at_resolution(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    (tmp_path / "music/bed.wav").write_bytes(b"tampered")

    with pytest.raises(ValueError, match="checksum"):
        resolve_audio_render_plan(_edl(music=(_music(),)), registry)

    organic_content = b"organic-music"
    organic_path = tmp_path / "music/organic.wav"
    organic_path.write_bytes(organic_content)
    organic_registry = parse_audio_asset_manifest(
        {
            "version": 1,
            "assets": [
                _manifest_asset(
                    asset_id="music_organic_01",
                    kind="music",
                    relative_path="music/organic.wav",
                    content=organic_content,
                    scopes=["commercial_social_organic"],
                )
            ],
        },
        asset_root=tmp_path,
    )
    with pytest.raises(ValueError, match="not cleared"):
        resolve_audio_render_plan(
            _edl(music=(_music(asset_id="music_organic_01", loop=False),)), organic_registry
        )
