"""Local-first orchestration for ClipFactory's compiled V2 edit path.

This module deliberately stops short of activating V2 in the production job
runner.  It connects the provider-independent pieces behind one explicit API:
compile an untrusted edit intent, run deterministic editorial QC, build
occurrence-accurate captions, then execute the trusted FFmpeg plan.

Music/SFX remain fail-closed until a licensed asset registry resolves their IDs
to verified local files.  The orchestration never silently drops an operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models import Transcript
from .audio_assets import AudioAssetError, AudioAssetRegistry
from .audio_render_plan import AudioRenderPlanError, resolve_audio_render_plan
from .editorial_qc import EditorialQCPolicy, EditorialQCReport, evaluate_editorial_qc
from .edl import (
    CompiledEDL,
    EditIntentPlan,
    EditScope,
    EDLValidationError,
    compile_edit_intent,
)
from .edl_captions import CaptionPlan, build_caption_plan, write_ass_for_edl
from .ffmpeg import FFmpegError, detect_black_intervals, probe_media, render_compiled_edl


class EditorV2Error(RuntimeError):
    """A V2 edit cannot safely advance to the next pipeline stage."""


@dataclass(frozen=True)
class PreparedV2Edit:
    """Validated, QC'd edit state before any media is written."""

    edl: CompiledEDL
    qc: EditorialQCReport
    captions: CaptionPlan


@dataclass(frozen=True)
class RenderedV2Edit:
    """Local artefacts and reports produced by one V2 render."""

    prepared: PreparedV2Edit
    source_path: str
    output_path: str
    subtitles_path: str | None
    rendered_duration_seconds: float
    black_frame_seconds: float
    black_frame_ratio: float
    resolved_audio_asset_ids: tuple[str, ...]


def prepare_v2_edit(
    plan: EditIntentPlan,
    transcript: Transcript,
    *,
    source_duration_ms: int,
    target_duration_seconds: int | None = None,
    edit_scope: EditScope | None = None,
    allowed_music_asset_ids: set[str] | frozenset[str] | None = None,
    allowed_sfx_asset_ids: set[str] | frozenset[str] | None = None,
    qc_policy: EditorialQCPolicy | None = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    allow_fallback_preview: bool = False,
) -> PreparedV2Edit:
    """Compile and editorially validate a plan without invoking FFmpeg."""

    try:
        edl = compile_edit_intent(
            plan,
            transcript,
            source_duration_ms=source_duration_ms,
            target_duration_seconds=target_duration_seconds,
            width=width,
            height=height,
            fps=fps,
            allowed_music_asset_ids=allowed_music_asset_ids,
            allowed_sfx_asset_ids=allowed_sfx_asset_ids,
            edit_scope=edit_scope,
        )
    except EDLValidationError as exc:
        raise EditorV2Error(f"edit intent rejected: {exc}") from exc

    qc = evaluate_editorial_qc(edl, transcript, policy=qc_policy)
    if qc.status == "reject":
        codes = ", ".join(finding.code for finding in qc.findings)
        raise EditorV2Error(f"editorial QC rejected the edit: {codes}")
    if qc.status == "pass_with_fallback" and not allow_fallback_preview:
        codes = ", ".join(finding.code for finding in qc.findings)
        raise EditorV2Error(f"editorial QC requires fallback handling: {codes}")

    captions = build_caption_plan(edl, transcript)
    return PreparedV2Edit(edl=edl, qc=qc, captions=captions)


async def render_v2_edit(
    *,
    source: str,
    transcript: Transcript,
    plan: EditIntentPlan,
    out_path: str,
    target_duration_seconds: int | None = None,
    edit_scope: EditScope | None = None,
    allowed_music_asset_ids: set[str] | frozenset[str] | None = None,
    allowed_sfx_asset_ids: set[str] | frozenset[str] | None = None,
    qc_policy: EditorialQCPolicy | None = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    allow_fallback_preview: bool = False,
    max_black_frame_ratio: float = 0.15,
    audio_registry: AudioAssetRegistry | None = None,
    required_audio_license_scope: str = "commercial_social_paid",
    ffmpeg_bin: str | None = None,
    ffprobe_bin: str | None = None,
) -> RenderedV2Edit:
    """Compile, QC, caption and render one plan in the local V2 path."""

    source_path = Path(source)
    if not 0.0 <= max_black_frame_ratio <= 1.0:
        raise EditorV2Error("max_black_frame_ratio must be in [0, 1]")
    if audio_registry is None and (plan.music or plan.sfx):
        raise EditorV2Error("an audio registry is required for music or SFX")

    if audio_registry is not None:
        catalogue = audio_registry.llm_catalog()
        registry_music_ids = {
            str(item["id"]) for item in catalogue if item["kind"] == "music"
        }
        registry_sfx_ids = {
            str(item["id"]) for item in catalogue if item["kind"] == "sfx"
        }
        allowed_music_asset_ids = (
            registry_music_ids
            if allowed_music_asset_ids is None
            else set(allowed_music_asset_ids) & registry_music_ids
        )
        allowed_sfx_asset_ids = (
            registry_sfx_ids
            if allowed_sfx_asset_ids is None
            else set(allowed_sfx_asset_ids) & registry_sfx_ids
        )
    if not source_path.is_file():
        raise EditorV2Error(f"source file does not exist: {source}")
    try:
        source_probe = await probe_media(str(source_path), ffprobe_bin=ffprobe_bin)
    except FFmpegError as exc:
        raise EditorV2Error(f"source probe failed: {exc}") from exc
    if not source_probe.has_video:
        raise EditorV2Error("source has no video stream")

    prepared = prepare_v2_edit(
        plan,
        transcript,
        source_duration_ms=round(source_probe.duration_seconds * 1000),
        target_duration_seconds=target_duration_seconds,
        edit_scope=edit_scope,
        allowed_music_asset_ids=allowed_music_asset_ids,
        allowed_sfx_asset_ids=allowed_sfx_asset_ids,
        qc_policy=qc_policy,
        width=width,
        height=height,
        fps=fps,
        allow_fallback_preview=allow_fallback_preview,
    )

    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    captions_path = output.with_suffix(".ass")
    has_captions = write_ass_for_edl(
        prepared.captions,
        out_path=str(captions_path),
    )
    audio_plan = None
    if audio_registry is not None:
        try:
            audio_plan = resolve_audio_render_plan(
                prepared.edl,
                audio_registry,
                required_scope=required_audio_license_scope,
            )
        except (AudioAssetError, AudioRenderPlanError) as exc:
            raise EditorV2Error(f"audio asset resolution failed: {exc}") from exc
    try:
        rendered_duration = await render_compiled_edl(
            source=str(source_path),
            edl=prepared.edl,
            transcript=transcript,
            out_path=str(output),
            subtitles_path=str(captions_path) if has_captions else None,
            audio_plan=audio_plan,
            ffmpeg_bin=ffmpeg_bin,
            ffprobe_bin=ffprobe_bin,
        )
    except FFmpegError as exc:
        raise EditorV2Error(f"render failed: {exc}") from exc

    black_intervals = await detect_black_intervals(
        str(output),
        0.0,
        window_seconds=rendered_duration,
        min_black_seconds=0.25,
        pix_threshold=0.10,
        ffmpeg_bin=ffmpeg_bin,
    )
    black_seconds = sum(max(0.0, end - start) for start, end in black_intervals)
    black_ratio = (
        min(1.0, black_seconds / rendered_duration) if rendered_duration > 0 else 1.0
    )
    if black_ratio > max_black_frame_ratio:
        raise EditorV2Error(
            f"technical QC rejected black-frame coverage {black_ratio:.1%} "
            f"(maximum {max_black_frame_ratio:.1%})"
        )

    return RenderedV2Edit(
        prepared=prepared,
        source_path=str(source_path),
        output_path=str(output),
        subtitles_path=str(captions_path) if has_captions else None,
        rendered_duration_seconds=rendered_duration,
        black_frame_seconds=black_seconds,
        black_frame_ratio=black_ratio,
        resolved_audio_asset_ids=tuple(
            [item.track.asset_id for item in audio_plan.music]
            + [item.cue.asset_id for item in audio_plan.sfx]
        )
        if audio_plan is not None
        else (),
    )
