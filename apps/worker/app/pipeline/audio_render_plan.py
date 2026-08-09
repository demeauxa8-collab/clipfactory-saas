"""Trusted bridge from a compiled EDL to renderer-ready local audio assets.

The EDL carries only catalogue IDs and timeline coordinates.  This module is
the final non-FFmpeg boundary: it resolves those IDs using the local registry,
rechecks rights and integrity, and reduces free numeric audio intent to bounded
gains and a closed ducking-preset catalogue.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .audio_assets import AudioAssetRegistry, ResolvedAudioAsset
from .edl import CompiledEDL, CompiledMusicTrack, CompiledSFXCue


class AudioRenderPlanError(ValueError):
    """A compiled EDL cannot be turned into a safe local audio render plan."""


DuckingProfileId = Literal["none", "soft_duck", "voice_priority"]

# Additional renderer-side ceilings.  The manifest retains the tighter limit
# per asset; these system limits prevent an unusually permissive manifest from
# making background audio overpower dialogue.
MAX_MUSIC_RENDER_GAIN_DB = -12.0
MAX_SFX_RENDER_GAIN_DB = -6.0
MASTER_TARGET_LUFS = -14.0
MASTER_TRUE_PEAK_DB = -1.5


@dataclass(frozen=True)
class DuckingPreset:
    """A closed sidechain policy, not a collection of LLM-controlled knobs."""

    id: DuckingProfileId
    threshold: float | None
    ratio: float | None
    attack_ms: float | None
    release_ms: float | None


DUCKING_PRESETS: dict[DuckingProfileId, DuckingPreset] = {
    "none": DuckingPreset("none", None, None, None, None),
    "soft_duck": DuckingPreset("soft_duck", 0.14, 4.0, 30.0, 450.0),
    "voice_priority": DuckingPreset("voice_priority", 0.10, 8.0, 15.0, 320.0),
}


@dataclass(frozen=True)
class ResolvedMusicRenderTrack:
    track: CompiledMusicTrack
    asset: ResolvedAudioAsset
    effective_gain_db: float
    ducking: DuckingPreset


@dataclass(frozen=True)
class ResolvedSFXRenderCue:
    cue: CompiledSFXCue
    asset: ResolvedAudioAsset
    effective_gain_db: float


@dataclass(frozen=True)
class AudioRenderPlan:
    """Renderer-safe audio inputs whose paths were verified by the registry."""

    duration_ms: int
    music: tuple[ResolvedMusicRenderTrack, ...]
    sfx: tuple[ResolvedSFXRenderCue, ...]
    master_target_lufs: float = MASTER_TARGET_LUFS
    master_true_peak_db: float = MASTER_TRUE_PEAK_DB


def _require_finite(value: float, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise AudioRenderPlanError(f"{label} must be a finite number")
    return float(value)


def _validate_timeline_range(start_ms: int, end_ms: int, *, duration_ms: int, label: str) -> None:
    if not 0 <= start_ms < end_ms <= duration_ms:
        raise AudioRenderPlanError(f"{label} must sit inside the compiled EDL timeline")


def _ducking_for_db(ducking_db: float) -> DuckingPreset:
    """Translate legacy bounded reduction intent into one closed preset."""
    reduction = _require_finite(ducking_db, label="music ducking_db")
    if not -24.0 <= reduction <= 0.0:
        raise AudioRenderPlanError("music ducking_db must be in [-24, 0]")
    if reduction == 0.0:
        return DUCKING_PRESETS["none"]
    if reduction <= -12.0:
        return DUCKING_PRESETS["voice_priority"]
    return DUCKING_PRESETS["soft_duck"]


def _music_gain(track: CompiledMusicTrack, asset: ResolvedAudioAsset) -> float:
    requested = _require_finite(track.gain_db, label="music gain_db")
    if not -40.0 <= requested <= -6.0:
        raise AudioRenderPlanError("music gain_db must be in [-40, -6]")
    return min(requested, asset.asset.mix.max_gain_db, MAX_MUSIC_RENDER_GAIN_DB)


def _sfx_gain(cue: CompiledSFXCue, asset: ResolvedAudioAsset) -> float:
    requested = _require_finite(cue.gain_db, label="SFX gain_db")
    if not -30.0 <= requested <= 6.0:
        raise AudioRenderPlanError("SFX gain_db must be in [-30, 6]")
    return min(requested, asset.asset.mix.max_gain_db, MAX_SFX_RENDER_GAIN_DB)


def _sfx_budget(duration_ms: int) -> int:
    if duration_ms <= 0:
        raise AudioRenderPlanError("compiled EDL duration_ms must be positive")
    return min(4, math.ceil((duration_ms / 1000) / 8))


def resolve_audio_render_plan(
    edl: CompiledEDL,
    registry: AudioAssetRegistry,
    *,
    required_scope: str = "commercial_social_paid",
) -> AudioRenderPlan:
    """Resolve verified local audio inputs for one compiled output timeline.

    The caller may pass only a compiled EDL and trusted registry.  In
    particular, this API intentionally takes no paths, URLs, FFmpeg snippets,
    arbitrary compressor settings, or unchecked asset metadata.
    """
    duration_ms = edl.duration_ms
    if duration_ms <= 0:
        raise AudioRenderPlanError("compiled EDL duration_ms must be positive")
    if len(edl.music) > 1:
        raise AudioRenderPlanError("V1 permits at most one music bed")
    budget = _sfx_budget(duration_ms)
    if len(edl.sfx) > budget:
        raise AudioRenderPlanError(
            f"SFX budget exceeded: {len(edl.sfx)} cues for {duration_ms}ms (maximum {budget})"
        )

    music: list[ResolvedMusicRenderTrack] = []
    for track in edl.music:
        _validate_timeline_range(
            track.timeline_in_ms,
            track.timeline_out_ms,
            duration_ms=duration_ms,
            label="music track",
        )
        asset = registry.resolve(track.asset_id, required_scope=required_scope)
        if asset.asset.kind != "music":
            raise AudioRenderPlanError("music track references a non-music asset")
        if track.loop and not asset.asset.loop_safe:
            raise AudioRenderPlanError("looping music asset is not declared loop_safe")
        music.append(
            ResolvedMusicRenderTrack(
                track=track,
                asset=asset,
                effective_gain_db=_music_gain(track, asset),
                ducking=_ducking_for_db(track.ducking_db),
            )
        )

    sfx: list[ResolvedSFXRenderCue] = []
    for cue in edl.sfx:
        if not 0 <= cue.timeline_at_ms < duration_ms:
            raise AudioRenderPlanError("SFX cue must sit inside the compiled EDL timeline")
        asset = registry.resolve(cue.asset_id, required_scope=required_scope)
        if asset.asset.kind != "sfx":
            raise AudioRenderPlanError("SFX cue references a non-SFX asset")
        sfx.append(
            ResolvedSFXRenderCue(
                cue=cue,
                asset=asset,
                effective_gain_db=_sfx_gain(cue, asset),
            )
        )

    return AudioRenderPlan(
        duration_ms=duration_ms,
        music=tuple(music),
        sfx=tuple(sorted(sfx, key=lambda item: (item.cue.timeline_at_ms, item.cue.asset_id))),
    )
