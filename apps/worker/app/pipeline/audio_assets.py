"""Closed, local-only music and SFX asset registry for ClipFactory EDLs.

The LLM may select an ``asset_id`` from a catalog produced by this module.  It
never supplies a URL or a file path: the worker resolves the ID through a
versioned manifest, confines it to the configured local asset root, verifies
its checksum, and checks that its cleared licence covers the requested use.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

MANIFEST_VERSION = 1
AssetKind = Literal["music", "sfx"]

# Deliberately stricter than a filesystem name.  IDs are safe to log, expose to
# the LLM, and use as FFmpeg labels after the renderer gives them a numeric
# label.  Paths, URLs, whitespace and shell metacharacters never validate.
_ASSET_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_LICENSE_SCOPES = frozenset({"commercial_social_organic", "commercial_social_paid"})
_MAX_ASSET_DURATION_SECONDS = 3_600.0
_MAX_FADE_MS = 10_000


class AudioAssetError(ValueError):
    """Raised when an audio asset manifest or selection is unsafe or invalid."""


@dataclass(frozen=True)
class LicenseGrant:
    status: Literal["cleared"]
    scopes: frozenset[str]
    source: str
    attribution_required: bool


@dataclass(frozen=True)
class MixMetadata:
    """Bounded gain and fade values that the EDL compiler may use.

    Values are intentionally conservative: the model can choose an asset, but
    it cannot turn a background bed into clipping foreground audio.
    """

    default_gain_db: float
    max_gain_db: float
    fade_in_ms: int
    fade_out_ms: int


@dataclass(frozen=True)
class AudioAsset:
    id: str
    kind: AssetKind
    relative_path: PurePosixPath
    sha256: str
    duration_seconds: float
    license: LicenseGrant
    moods: tuple[str, ...]
    tags: tuple[str, ...]
    energy: int
    mix: MixMetadata
    bpm: int | None = None
    beat_offset_seconds: float | None = None
    roles: tuple[str, ...] = ()
    loop_safe: bool = False


@dataclass(frozen=True)
class ResolvedAudioAsset:
    """A server-side, verified asset ready for the FFmpeg compiler.

    ``path`` is intentionally never part of the LLM catalog.  Only trusted
    worker code receives this object.
    """

    asset: AudioAsset
    path: Path


def _require_mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AudioAssetError(f"{field} must be an object")
    return value


def _require_string(value: object, *, field: str, max_length: int = 160) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise AudioAssetError(f"{field} must be a non-empty string up to {max_length} chars")
    return value


def _require_number(
    value: object,
    *,
    field: str,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AudioAssetError(f"{field} must be a number")
    result = float(value)
    if not minimum <= result <= maximum:
        raise AudioAssetError(f"{field} must be between {minimum} and {maximum}")
    return result


def _require_int(value: object, *, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise AudioAssetError(f"{field} must be an integer between {minimum} and {maximum}")
    return value


def _safe_tokens(value: object, *, field: str, maximum: int = 12) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or len(value) > maximum:
        raise AudioAssetError(f"{field} must contain 1 to {maximum} strings")
    tokens: list[str] = []
    for item in value:
        token = _require_string(item, field=field, max_length=48).lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", token):
            raise AudioAssetError(f"{field} contains an unsafe token")
        tokens.append(token)
    if len(set(tokens)) != len(tokens):
        raise AudioAssetError(f"{field} must not contain duplicates")
    return tuple(tokens)


def _relative_asset_path(value: object) -> PurePosixPath:
    raw = _require_string(value, field="relative_path", max_length=240)
    # JSON manifests are platform-independent. Backslashes are rejected rather
    # than normalized so a Windows path can never evade the POSIX traversal
    # checks and so the asset root remains the only location authority.
    if "\\" in raw or "://" in raw:
        raise AudioAssetError("relative_path must not contain a URL or backslashes")
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise AudioAssetError("relative_path must be a non-traversing relative path")
    return path


def _parse_license(value: object) -> LicenseGrant:
    raw = _require_mapping(value, field="license")
    if raw.get("status") != "cleared":
        raise AudioAssetError("license.status must be 'cleared'")
    scopes = _safe_tokens(raw.get("scopes"), field="license.scopes", maximum=4)
    unknown_scopes = set(scopes) - _LICENSE_SCOPES
    if unknown_scopes:
        raise AudioAssetError(f"license.scopes contains unknown values: {sorted(unknown_scopes)}")
    attribution_required = raw.get("attribution_required")
    if not isinstance(attribution_required, bool):
        raise AudioAssetError("license.attribution_required must be a boolean")
    return LicenseGrant(
        status="cleared",
        scopes=frozenset(scopes),
        source=_require_string(raw.get("source"), field="license.source", max_length=120),
        attribution_required=attribution_required,
    )


def _parse_mix(value: object) -> MixMetadata:
    raw = _require_mapping(value, field="mix")
    default_gain = _require_number(
        raw.get("default_gain_db"), field="mix.default_gain_db", minimum=-42.0, maximum=-3.0
    )
    max_gain = _require_number(
        raw.get("max_gain_db"), field="mix.max_gain_db", minimum=-30.0, maximum=0.0
    )
    if default_gain > max_gain:
        raise AudioAssetError("mix.default_gain_db must not exceed mix.max_gain_db")
    return MixMetadata(
        default_gain_db=default_gain,
        max_gain_db=max_gain,
        fade_in_ms=_require_int(
            raw.get("fade_in_ms"), field="mix.fade_in_ms", minimum=0, maximum=_MAX_FADE_MS
        ),
        fade_out_ms=_require_int(
            raw.get("fade_out_ms"), field="mix.fade_out_ms", minimum=0, maximum=_MAX_FADE_MS
        ),
    )


def _parse_asset(value: object) -> AudioAsset:
    raw = _require_mapping(value, field="asset")
    asset_id = _require_string(raw.get("id"), field="asset.id", max_length=64)
    if not _ASSET_ID_RE.fullmatch(asset_id):
        raise AudioAssetError("asset.id must match ^[a-z][a-z0-9_]{2,63}$")
    kind = raw.get("kind")
    if kind not in {"music", "sfx"}:
        raise AudioAssetError("asset.kind must be 'music' or 'sfx'")
    checksum = _require_string(raw.get("sha256"), field="asset.sha256", max_length=64).lower()
    if not _SHA256_RE.fullmatch(checksum):
        raise AudioAssetError("asset.sha256 must be a lowercase SHA-256 hex digest")

    bpm_raw = raw.get("bpm")
    bpm = (
        None
        if bpm_raw is None
        else _require_int(bpm_raw, field="asset.bpm", minimum=40, maximum=240)
    )
    beat_offset_raw = raw.get("beat_offset_seconds")
    beat_offset = (
        None
        if beat_offset_raw is None
        else _require_number(
            beat_offset_raw, field="asset.beat_offset_seconds", minimum=0.0, maximum=60.0
        )
    )
    if (bpm is None) != (beat_offset is None):
        raise AudioAssetError("asset.bpm and asset.beat_offset_seconds must be supplied together")
    if kind == "sfx" and (bpm is not None or beat_offset is not None):
        raise AudioAssetError("SFX assets must not declare BPM metadata")

    loop_safe = raw.get("loop_safe", False)
    if not isinstance(loop_safe, bool):
        raise AudioAssetError("asset.loop_safe must be a boolean")
    if kind == "sfx" and loop_safe:
        raise AudioAssetError("SFX assets cannot be loop_safe")
    roles_raw = raw.get("roles", [])
    if roles_raw:
        roles = _safe_tokens(roles_raw, field="asset.roles", maximum=8)
    else:
        roles = ()

    return AudioAsset(
        id=asset_id,
        kind=kind,
        relative_path=_relative_asset_path(raw.get("relative_path")),
        sha256=checksum,
        duration_seconds=_require_number(
            raw.get("duration_seconds"),
            field="asset.duration_seconds",
            minimum=0.01,
            maximum=_MAX_ASSET_DURATION_SECONDS,
        ),
        license=_parse_license(raw.get("license")),
        moods=_safe_tokens(raw.get("moods"), field="asset.moods"),
        tags=_safe_tokens(raw.get("tags"), field="asset.tags"),
        energy=_require_int(raw.get("energy"), field="asset.energy", minimum=0, maximum=100),
        mix=_parse_mix(raw.get("mix")),
        bpm=bpm,
        beat_offset_seconds=beat_offset,
        roles=roles,
        loop_safe=loop_safe,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class AudioAssetRegistry:
    """Validated catalog that resolves only manifest-declared local files."""

    def __init__(self, *, asset_root: Path, assets: Mapping[str, AudioAsset]) -> None:
        root = asset_root.expanduser().resolve()
        if not root.is_dir():
            raise AudioAssetError("asset_root must be an existing directory")
        self._asset_root = root
        self._assets = dict(assets)

    @property
    def asset_root(self) -> Path:
        return self._asset_root

    def llm_catalog(self) -> list[dict[str, object]]:
        """Return safe selection metadata; no local paths, checksums or rights data."""
        return [
            {
                "id": asset.id,
                "kind": asset.kind,
                "moods": list(asset.moods),
                "tags": list(asset.tags),
                "roles": list(asset.roles),
                "energy": asset.energy,
                "bpm": asset.bpm,
                "loop_safe": asset.loop_safe,
            }
            for asset in sorted(self._assets.values(), key=lambda item: item.id)
        ]

    def resolve(
        self,
        asset_id: str,
        *,
        required_scope: str = "commercial_social_paid",
        verify_hash: bool = True,
    ) -> ResolvedAudioAsset:
        """Resolve an ID selected by the LLM into a verified server-side file.

        This API deliberately accepts no path, URL, query, or arbitrary mix
        parameters.  Any input outside the manifest's ID namespace is rejected.
        """
        if not isinstance(asset_id, str) or not _ASSET_ID_RE.fullmatch(asset_id):
            raise AudioAssetError("asset_id is not a safe manifest ID")
        if required_scope not in _LICENSE_SCOPES:
            raise AudioAssetError("required_scope is not supported")
        asset = self._assets.get(asset_id)
        if asset is None:
            raise AudioAssetError("asset_id is not present in the manifest")
        if required_scope not in asset.license.scopes:
            raise AudioAssetError(f"asset_id is not cleared for {required_scope}")

        path = (self._asset_root / asset.relative_path).resolve(strict=False)
        try:
            path.relative_to(self._asset_root)
        except ValueError as exc:
            raise AudioAssetError("asset path escapes asset_root") from exc
        if not path.is_file():
            raise AudioAssetError("manifest asset file is missing")
        if verify_hash and _sha256_file(path) != asset.sha256:
            raise AudioAssetError("manifest asset checksum does not match local file")
        return ResolvedAudioAsset(asset=asset, path=path)


def parse_audio_asset_manifest(
    document: object,
    *,
    asset_root: str | Path,
) -> AudioAssetRegistry:
    """Validate a decoded v1 manifest and return its closed asset registry."""
    raw = _require_mapping(document, field="manifest")
    if raw.get("version") != MANIFEST_VERSION:
        raise AudioAssetError(f"manifest.version must equal {MANIFEST_VERSION}")
    assets_raw = raw.get("assets")
    if not isinstance(assets_raw, list) or not assets_raw:
        raise AudioAssetError("manifest.assets must be a non-empty list")

    assets: dict[str, AudioAsset] = {}
    paths: set[PurePosixPath] = set()
    for item in assets_raw:
        asset = _parse_asset(item)
        if asset.id in assets:
            raise AudioAssetError(f"duplicate asset.id: {asset.id}")
        if asset.relative_path in paths:
            raise AudioAssetError(f"duplicate asset.relative_path: {asset.relative_path}")
        assets[asset.id] = asset
        paths.add(asset.relative_path)
    return AudioAssetRegistry(asset_root=Path(asset_root), assets=assets)


def load_audio_asset_manifest(
    manifest_path: str | Path,
    *,
    asset_root: str | Path,
) -> AudioAssetRegistry:
    """Load a local JSON manifest; remote URLs are explicitly unsupported."""
    path = Path(manifest_path)
    if str(manifest_path).startswith(("http://", "https://")):
        raise AudioAssetError("manifest_path must be a local file, not a URL")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AudioAssetError("could not read local audio asset manifest") from exc
    except json.JSONDecodeError as exc:
        raise AudioAssetError("audio asset manifest is not valid JSON") from exc
    return parse_audio_asset_manifest(document, asset_root=asset_root)
