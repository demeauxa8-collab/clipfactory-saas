"""Safe FFmpeg render-plan generation for a compiled ClipFactory EDL.

The EDL compiler owns editorial validation.  This module owns the next trust
boundary: it turns only that compiled representation into fixed FFmpeg graph
syntax.  The LLM never controls a filter name, expression, path or stream
label.  A caller may use :meth:`FFmpegRenderPlan.input_args` with its trusted
source path, then append encoder/output arguments and execute FFmpeg.

This is intentionally a planning layer, not an executor.  Keeping it pure
makes the eventual renderer easy to test and lets a job queue cache plans.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from ..models import Transcript
from .edl import CompiledEDL, CompiledShot, DecodeIsland, EffectIntent


class EDLRenderError(ValueError):
    """A malformed compiled EDL cannot be lowered into a safe FFmpeg graph."""


@dataclass(frozen=True)
class DecodeIslandInput:
    """One seek/decode input.  ``source_path`` is deliberately absent here."""

    island_id: str
    input_index: int
    source_in_ms: int
    source_out_ms: int

    @property
    def duration_ms(self) -> int:
        return self.source_out_ms - self.source_in_ms

    def input_args(self, source_path: str | Path) -> list[str]:
        """Return an argv fragment, never a shell command.

        Each island has its own input context.  ``-ss``/``-t`` are deliberately
        input options: FFmpeg then decodes just this nearby source window,
        instead of opening a decoder for every micro-cut.
        """
        return [
            "-ss",
            _seconds(self.source_in_ms),
            "-t",
            _seconds(self.duration_ms),
            "-i",
            str(source_path),
        ]


@dataclass(frozen=True)
class RenderedShot:
    """Traceability between one EDL shot and its island-relative trim."""

    shot_id: str
    island_id: str
    input_index: int
    island_offset_in_ms: int
    island_offset_out_ms: int
    timeline_in_ms: int
    timeline_out_ms: int


@dataclass(frozen=True)
class RenderedEffect:
    shot_id: str
    kind: str
    timeline_in_ms: int
    timeline_out_ms: int
    intensity: float


@dataclass(frozen=True)
class RenderedTransition:
    from_shot_id: str
    to_shot_id: str
    kind: str
    timeline_at_ms: int


@dataclass(frozen=True)
class FFmpegRenderPlan:
    """A deterministic graph plus separately auditable input/output metadata.

    The graph concatenates source dialogue audio and finished video only.
    Licensed music/SFX remain structured EDL tracks until a trusted asset
    resolver maps their catalogue IDs to private files.  This avoids allowing
    model-generated file paths into an FFmpeg command.
    """

    inputs: tuple[DecodeIslandInput, ...]
    shots: tuple[RenderedShot, ...]
    effects: tuple[RenderedEffect, ...]
    transitions: tuple[RenderedTransition, ...]
    filter_complex: str
    video_label: str
    audio_label: str
    duration_ms: int
    fps: int
    width: int
    height: int
    requires_source_audio: bool = True
    deferred_music_asset_ids: tuple[str, ...] = ()
    deferred_sfx_asset_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def input_args(self, source_path: str | Path) -> list[str]:
        """Build all input argv fragments for a trusted local source path."""
        args: list[str] = []
        for item in self.inputs:
            args.extend(item.input_args(source_path))
        return args


def _seconds(value_ms: int) -> str:
    if value_ms < 0:
        raise EDLRenderError("milliseconds must be non-negative")
    return f"{value_ms / 1000:.3f}"


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise EDLRenderError("filter numbers must be finite")
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _effect_timeline_ms(
    effect: EffectIntent,
    *,
    shot: CompiledShot,
    transcript: Transcript,
) -> int:
    """Resolve a word-targeted effect to a clamped output-timeline instant."""
    if effect.at_word_id is None:
        return shot.timeline_in_ms
    if not 0 <= effect.at_word_id < len(transcript.words):
        raise EDLRenderError(
            f"shot {shot.shot_id}: effect refers to transcript word {effect.at_word_id}"
        )
    # The EDL compiler has already quantized each reused word occurrence onto
    # the rendered frame timeline.  Prefer it over recomputing from source
    # seconds, which is subtly wrong after frame rounding and source reuse.
    for occurrence in getattr(shot, "word_occurrences", ()):
        if occurrence.word_id == effect.at_word_id:
            return occurrence.timeline_in_ms
    source_word_ms = round(transcript.words[effect.at_word_id].start * 1000)
    relative_ms = max(0, source_word_ms - shot.source_in_ms)
    return min(
        shot.timeline_out_ms,
        shot.timeline_in_ms + round(relative_ms / shot.speed),
    )


def _validate_edl(edl: CompiledEDL) -> dict[str, DecodeIsland]:
    if edl.width <= 0 or edl.height <= 0 or edl.fps <= 0 or edl.duration_ms <= 0:
        raise EDLRenderError("EDL output dimensions, fps and duration must be positive")
    if not edl.shots or not edl.decode_islands:
        raise EDLRenderError("EDL needs at least one shot and one decode island")

    islands = {island.island_id: island for island in edl.decode_islands}
    if len(islands) != len(edl.decode_islands):
        raise EDLRenderError("decode island IDs must be unique")
    shot_to_island: dict[str, str] = {}
    for island in edl.decode_islands:
        if island.source_out_ms <= island.source_in_ms:
            raise EDLRenderError(f"decode island {island.island_id} has no duration")
        for shot_id in island.shot_ids:
            if shot_id in shot_to_island:
                raise EDLRenderError(f"shot {shot_id} belongs to multiple decode islands")
            shot_to_island[shot_id] = island.island_id
    expected_in = 0
    known_shot_ids: set[str] = set()
    for shot in edl.shots:
        if shot.shot_id in known_shot_ids:
            raise EDLRenderError(f"duplicate EDL shot {shot.shot_id}")
        known_shot_ids.add(shot.shot_id)
        if shot.timeline_in_ms != expected_in or shot.timeline_out_ms <= expected_in:
            raise EDLRenderError("EDL shots must form a contiguous positive timeline")
        expected_in = shot.timeline_out_ms
        island_id = shot_to_island.get(shot.shot_id)
        if island_id is None:
            raise EDLRenderError(f"shot {shot.shot_id} is not assigned to a decode island")
        island = islands[island_id]
        is_within_island = (
            island.source_in_ms <= shot.source_in_ms
            and shot.source_out_ms <= island.source_out_ms
        )
        if not is_within_island:
            raise EDLRenderError(f"shot {shot.shot_id} lies outside decode island {island_id}")
    if expected_in != edl.duration_ms:
        raise EDLRenderError("EDL duration does not match its shot timeline")
    if set(shot_to_island) != known_shot_ids:
        raise EDLRenderError("decode islands reference an unknown shot")
    return islands


def _frame_filter(shot: CompiledShot, *, width: int, height: int) -> str:
    """Closed framing vocabulary, with deterministic safe fallbacks.

    Face/screen tracking needs analysis data that is not part of ``CompiledEDL``
    yet.  Until that is attached, ``locked_face`` and ``follow_primary_face``
    use the requested centre position; ``screen_focus`` uses a centred crop;
    ``pip_proof`` uses a clean full-frame proof view rather than inventing a
    second untrusted input stream.
    """
    mode = shot.framing.mode
    if mode == "source_safe":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
        )
    if mode == "fit_blur":
        # A true blur background needs a split+overlay graph.  A full-frame
        # crop is the deterministic no-extra-input equivalent; the renderer can
        # upgrade this to blur once it owns an overlay-capable framing asset.
        mode = "screen_focus"
    if mode == "pip_proof":
        mode = "screen_focus"

    center_x = _number(shot.framing.center_x)
    scale = _number(shot.framing.base_scale)
    if mode == "screen_focus":
        center_x = "0.5"
    return (
        f"scale=w='trunc({width}*{scale}/2)*2':h='trunc({height}*{scale}/2)*2':"
        f"force_original_aspect_ratio=increase,"
        f"crop={width}:{height}:x='(iw-ow)*{center_x}':y='(ih-oh)/2'"
    )


def _split_effect(
    lines: list[str],
    *,
    source_label: str,
    target_label: str,
    prefix: str,
    start_ms: int,
    end_ms: int,
    shot_duration_ms: int,
    effect_filter: str,
) -> None:
    """Apply an effect only within an output-time interval without re-timing."""
    start = _seconds(start_ms)
    end = _seconds(end_ms)
    duration = _seconds(shot_duration_ms)
    pre, middle, post, effected = (
        f"{prefix}_pre",
        f"{prefix}_mid",
        f"{prefix}_post",
        f"{prefix}_fx",
    )
    lines.append(f"[{source_label}]split=3[{pre}][{middle}][{post}]")
    lines.append(f"[{pre}]trim=start=0:end={start},setpts=PTS-STARTPTS[{pre}o]")
    lines.append(f"[{middle}]trim=start={start}:end={end},setpts=PTS-STARTPTS[{middle}o]")
    lines.append(f"[{middle}o]{effect_filter}[{effected}]")
    lines.append(
        f"[{post}]trim=start={end}:end={duration},setpts=PTS-STARTPTS[{post}o]"
    )
    lines.append(f"[{pre}o][{effected}][{post}o]concat=n=3:v=1:a=0[{target_label}]")


def _freeze_effect(
    lines: list[str],
    *,
    source_label: str,
    target_label: str,
    prefix: str,
    start_ms: int,
    end_ms: int,
    shot_duration_ms: int,
    fps: int,
) -> None:
    """Freeze a moment while preserving the compiled shot's exact duration.

    The hold replaces source material after the sampled frame.  This is the
    only duration-conserving implementation without asking the EDL compiler to
    reserve extra source time for a freeze.
    """
    start = _seconds(start_ms)
    end = _seconds(end_ms)
    duration = _seconds(shot_duration_ms)
    hold = _seconds(end_ms - start_ms)
    frame = _number(1 / fps)
    pre, frame_label, post = f"{prefix}_pre", f"{prefix}_frame", f"{prefix}_post"
    lines.append(f"[{source_label}]split=3[{pre}][{frame_label}][{post}]")
    lines.append(f"[{pre}]trim=start=0:end={start},setpts=PTS-STARTPTS[{pre}o]")
    lines.append(
        f"[{frame_label}]trim=start={start}:end={_number(start_ms / 1000 + 1 / fps)},"
        f"setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={hold},"
        f"trim=duration={hold},setpts=PTS-STARTPTS[{frame_label}o]"
    )
    lines.append(f"[{post}]trim=start={end}:end={duration},setpts=PTS-STARTPTS[{post}o]")
    lines.append(f"[{pre}o][{frame_label}o][{post}o]concat=n=3:v=1:a=0[{target_label}]")
    del frame  # Documents the output-frame basis and avoids a magic number.


def _effect_filter(kind: str, *, intensity: float, width: int, height: int, fps: int) -> str:
    amount = _number(intensity)
    if kind == "punch_in":
        zoom = _number(1.04 + intensity * 0.16)
        return (
            f"scale=w='trunc(iw*{zoom}/2)*2':h='trunc(ih*{zoom}/2)*2',"
            f"crop={width}:{height}:x='(iw-ow)/2':y='(ih-oh)/2'"
        )
    if kind == "zoom_out":
        start_zoom = _number(1.04 + intensity * 0.16)
        decrement = _number(0.001 + intensity * 0.005)
        return (
            f"zoompan=z='if(eq(on,0),{start_zoom},max(1.0,zoom-{decrement}))':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    if kind == "flash":
        alpha = _number(0.15 + intensity * 0.55)
        return (
            f"drawbox=x=0:y=0:w=iw:h=ih:color=white@{alpha}:t=fill,"
            "format=yuv420p"
        )
    if kind == "shake":
        pixels = _number(2 + intensity * 10)
        return (
            "scale=w='trunc(iw*1.05/2)*2':h='trunc(ih*1.05/2)*2',"
            f"crop={width}:{height}:x='(iw-ow)/2+{pixels}*sin(t*35)':"
            f"y='(ih-oh)/2+{pixels}*sin(t*29)'"
        )
    if kind == "blur":
        radius = _number(1 + intensity * 5)
        return f"boxblur=luma_radius={radius}:luma_power=1"
    if kind == "color_pop":
        contrast = _number(1.03 + intensity * 0.22)
        saturation = _number(1.05 + intensity * 0.75)
        return f"eq=contrast={contrast}:saturation={saturation}"
    if kind == "speed_ramp":
        # The EDL's top-level speed remains authoritative.  Altering a single
        # interval's PTS would change a compiled timeline; this visual ramp is
        # deliberately deferred until the schema carries source reservation.
        contrast = _number(1.02 + intensity * 0.08)
        saturation = _number(1.0 + amount * 0.2)
        return f"eq=contrast={contrast}:saturation={saturation}"
    raise EDLRenderError(f"unsupported compiled effect {kind!r}")


def _apply_effects(
    lines: list[str],
    *,
    shot: CompiledShot,
    shot_index: int,
    source_label: str,
    transcript: Transcript,
    width: int,
    height: int,
    fps: int,
) -> tuple[str, list[RenderedEffect]]:
    current = source_label
    rendered: list[RenderedEffect] = []
    shot_duration = shot.timeline_duration_ms
    for index, effect in enumerate(shot.effects):
        start_absolute = _effect_timeline_ms(effect, shot=shot, transcript=transcript)
        start_relative = max(0, start_absolute - shot.timeline_in_ms)
        end_relative = min(shot_duration, start_relative + effect.duration_ms)
        if end_relative <= start_relative:
            continue
        # Never put an LLM-visible shot ID in an FFmpeg stream label.  The EDL
        # compiler validates it, but numeric labels keep this layer standalone
        # safe even if FFmpeg's label grammar changes.
        target = f"v_fx_{shot_index}_{index}"
        prefix = f"fx_{shot_index}_{index}"
        if effect.kind == "freeze":
            _freeze_effect(
                lines,
                source_label=current,
                target_label=target,
                prefix=prefix,
                start_ms=start_relative,
                end_ms=end_relative,
                shot_duration_ms=shot_duration,
                fps=fps,
            )
        else:
            _split_effect(
                lines,
                source_label=current,
                target_label=target,
                prefix=prefix,
                start_ms=start_relative,
                end_ms=end_relative,
                shot_duration_ms=shot_duration,
                effect_filter=_effect_filter(
                    effect.kind,
                    intensity=effect.intensity,
                    width=width,
                    height=height,
                    fps=fps,
                ),
            )
        rendered.append(
            RenderedEffect(
                shot_id=shot.shot_id,
                kind=effect.kind,
                timeline_in_ms=shot.timeline_in_ms + start_relative,
                timeline_out_ms=shot.timeline_in_ms + end_relative,
                intensity=effect.intensity,
            )
        )
        current = target
    return current, rendered


def _apply_transitions(
    lines: list[str], *, edl: CompiledEDL, source_label: str
) -> tuple[str, list[RenderedTransition]]:
    """Realise closed transitions without overlapping or changing the EDL time.

    The current V2 compiler describes butt edits.  This gives the three visual
    transitions a brief treatment over that exact cut rather than adding an
    xfade overlap that would silently shorten a user-approved timeline.
    """
    current = source_label
    rendered: list[RenderedTransition] = []
    for index, (outgoing, incoming) in enumerate(zip(edl.shots, edl.shots[1:], strict=False)):
        kind = outgoing.transition_out
        cut_ms = outgoing.timeline_out_ms
        rendered.append(
            RenderedTransition(
                from_shot_id=outgoing.shot_id,
                to_shot_id=incoming.shot_id,
                kind=kind,
                timeline_at_ms=cut_ms,
            )
        )
        target = f"v_transition_{index}"
        if kind in {"hard_cut", "time_jump"}:
            # Concat already implements a frame-accurate butt cut.
            continue
        if kind == "reveal":
            fade_ms = min(90, cut_ms, edl.duration_ms - cut_ms)
            if fade_ms <= 0:
                continue
            before = _seconds(cut_ms - fade_ms)
            at = _seconds(cut_ms)
            duration = _seconds(fade_ms)
            lines.append(
                f"[{current}]fade=t=out:st={before}:d={duration}:color=black,"
                f"fade=t=in:st={at}:d={duration}:color=black[{target}]"
            )
        elif kind == "contrast":
            start = _seconds(max(0, cut_ms - 80))
            end = _seconds(min(edl.duration_ms, cut_ms + 80))
            lines.append(
                f"[{current}]eq=contrast=1.18:saturation=1.12:"
                f"enable='between(t,{start},{end})'[{target}]"
            )
        elif kind == "hard_impact":
            start = _seconds(max(0, cut_ms - 33))
            end = _seconds(min(edl.duration_ms, cut_ms + 33))
            lines.append(
                f"[{current}]drawbox=x=0:y=0:w=iw:h=ih:color=white@0.45:t=fill:"
                f"enable='between(t,{start},{end})'[{target}]"
            )
        else:
            raise EDLRenderError(f"unsupported compiled transition {kind!r}")
        current = target
    return current, rendered


def compile_ffmpeg_render_plan(edl: CompiledEDL, transcript: Transcript) -> FFmpegRenderPlan:
    """Lower a validated EDL into an island-aware, source-audio FFmpeg graph.

    This function is deterministic: the same EDL/transcript returns byte-for-
    byte identical graph text.  It does not call FFmpeg and never resolves an
    external asset ID to a filesystem path.
    """
    islands = _validate_edl(edl)
    if not transcript.words:
        raise EDLRenderError("a transcript is required for word-timed effects")

    inputs = tuple(
        DecodeIslandInput(
            island_id=island.island_id,
            input_index=index,
            source_in_ms=island.source_in_ms,
            source_out_ms=island.source_out_ms,
        )
        for index, island in enumerate(edl.decode_islands)
    )
    input_by_island = {item.island_id: item for item in inputs}
    shot_to_island = {
        shot_id: island.island_id for island in edl.decode_islands for shot_id in island.shot_ids
    }

    lines: list[str] = []
    rendered_shots: list[RenderedShot] = []
    rendered_effects: list[RenderedEffect] = []
    concat_inputs: list[str] = []
    for shot_index, shot in enumerate(edl.shots):
        island = islands[shot_to_island[shot.shot_id]]
        input_spec = input_by_island[island.island_id]
        offset_in = shot.source_in_ms - island.source_in_ms
        offset_out = shot.source_out_ms - island.source_in_ms
        base_video = f"v_base_{shot_index}"
        base_audio = f"a_{shot_index}"
        speed = _number(shot.speed)
        lines.append(
            f"[{input_spec.input_index}:v]trim=start={_seconds(offset_in)}:end={_seconds(offset_out)},"
            f"setpts=PTS-STARTPTS,setpts=PTS/{speed},fps={edl.fps},"
            f"{_frame_filter(shot, width=edl.width, height=edl.height)}[{base_video}]"
        )
        lines.append(
            f"[{input_spec.input_index}:a]atrim=start={_seconds(offset_in)}:end={_seconds(offset_out)},"
            f"asetpts=PTS-STARTPTS,atempo={speed},aresample=48000[{base_audio}]"
        )
        video_label, effect_records = _apply_effects(
            lines,
            shot=shot,
            shot_index=shot_index,
            source_label=base_video,
            transcript=transcript,
            width=edl.width,
            height=edl.height,
            fps=edl.fps,
        )
        rendered_effects.extend(effect_records)
        concat_inputs.extend((f"[{video_label}]", f"[{base_audio}]"))
        rendered_shots.append(
            RenderedShot(
                shot_id=shot.shot_id,
                island_id=island.island_id,
                input_index=input_spec.input_index,
                island_offset_in_ms=offset_in,
                island_offset_out_ms=offset_out,
                timeline_in_ms=shot.timeline_in_ms,
                timeline_out_ms=shot.timeline_out_ms,
            )
        )

    lines.append("".join(concat_inputs) + f"concat=n={len(edl.shots)}:v=1:a=1[v_concat][a_concat]")
    transitioned_video, transitions = _apply_transitions(
        lines, edl=edl, source_label="v_concat"
    )
    duration = _seconds(edl.duration_ms)
    # FFmpeg rounds a frame count after speed changes.  Pad a single safe
    # margin, then trim both streams back to the compiler's authoritative EDL.
    lines.append(
        f"[{transitioned_video}]tpad=stop_mode=clone:stop_duration=0.100,"
        f"trim=duration={duration},setpts=PTS-STARTPTS[v_dialogue]"
    )
    lines.append(
        f"[a_concat]apad=pad_dur={duration},atrim=duration={duration},"
        "asetpts=PTS-STARTPTS[a_dialogue]"
    )
    limitations = (
        "Music and SFX catalogue IDs are deferred until a trusted asset resolver provides paths.",
        (
            "fit_blur and pip_proof use deterministic single-source fallbacks "
            "until framing analysis carries overlay geometry."
        ),
        (
            "speed_ramp currently preserves the compiled timeline as a visual "
            "emphasis; time remapping needs source-reservation EDL fields."
        ),
    )
    return FFmpegRenderPlan(
        inputs=inputs,
        shots=tuple(rendered_shots),
        effects=tuple(rendered_effects),
        transitions=tuple(transitions),
        filter_complex=";".join(lines),
        video_label="v_dialogue",
        audio_label="a_dialogue",
        duration_ms=edl.duration_ms,
        fps=edl.fps,
        width=edl.width,
        height=edl.height,
        deferred_music_asset_ids=tuple(track.asset_id for track in edl.music),
        deferred_sfx_asset_ids=tuple(cue.asset_id for cue in edl.sfx),
        limitations=limitations,
    )
