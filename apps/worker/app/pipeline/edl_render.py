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

DIALOGUE_JOIN_FADE_SECONDS = 0.008
MAX_RENDER_DECODE_ISLANDS = 16
MAX_RENDER_DURATION_SECONDS = 180
MAX_RENDER_COMPLEXITY = 120
MAX_RENDER_PIXELS = 2160 * 3840


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
            "-accurate_seek",
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
    timeline_in_frame: int
    timeline_out_frame: int
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


def _effect_timeline_frame(
    effect: EffectIntent,
    *,
    shot: CompiledShot,
    transcript: Transcript,
) -> int:
    """Resolve a word-targeted effect to an authoritative output frame."""
    if effect.at_word_id is None:
        return shot.timeline_in_frame
    if not 0 <= effect.at_word_id < len(transcript.words):
        raise EDLRenderError(
            f"shot {shot.shot_id}: effect refers to transcript word {effect.at_word_id}"
        )
    # The EDL compiler has already quantized each reused word occurrence onto
    # the rendered frame timeline.  Prefer it over recomputing from source
    # seconds, which is subtly wrong after frame rounding and source reuse.
    for occurrence in getattr(shot, "word_occurrences", ()):
        if occurrence.word_id == effect.at_word_id:
            return occurrence.timeline_in_frame
    raise EDLRenderError(
        f"shot {shot.shot_id}: effect word {effect.at_word_id} has no compiled occurrence"
    )


def _validate_edl(edl: CompiledEDL, transcript: Transcript) -> dict[str, DecodeIsland]:
    if edl.width <= 0 or edl.height <= 0 or edl.fps <= 0 or edl.duration_ms <= 0:
        raise EDLRenderError("EDL output dimensions, fps and duration must be positive")
    if edl.fps not in {24, 25, 30, 50, 60}:
        raise EDLRenderError("EDL fps is outside the supported render catalogue")
    if edl.width * edl.height > MAX_RENDER_PIXELS:
        raise EDLRenderError("EDL output canvas exceeds the render pixel budget")
    if edl.duration_frames > edl.fps * MAX_RENDER_DURATION_SECONDS:
        raise EDLRenderError("EDL duration exceeds the short-form render budget")
    if edl.duration_ms != round(edl.duration_frames * 1000 / edl.fps):
        raise EDLRenderError("EDL milliseconds do not match its frame-authoritative duration")
    if not edl.shots or not edl.decode_islands:
        raise EDLRenderError("EDL needs at least one shot and one decode island")
    if len(edl.decode_islands) > MAX_RENDER_DECODE_ISLANDS:
        raise EDLRenderError("EDL exceeds the decode-island performance budget")
    complexity = (
        len(edl.shots)
        + sum(shot.framing.mode == "fit_blur" for shot in edl.shots)
        + sum(len(shot.effects) * 3 for shot in edl.shots)
    )
    if complexity > MAX_RENDER_COMPLEXITY:
        raise EDLRenderError("EDL exceeds the filtergraph complexity budget")

    islands = {island.island_id: island for island in edl.decode_islands}
    if len(islands) != len(edl.decode_islands):
        raise EDLRenderError("decode island IDs must be unique")
    shot_to_island: dict[str, str] = {}
    for island in edl.decode_islands:
        if island.source_out_ms <= island.source_in_ms:
            raise EDLRenderError(f"decode island {island.island_id} has no duration")
        if island.source_in_ms < 0 or island.source_out_ms - island.source_in_ms > 60_000:
            raise EDLRenderError(f"decode island {island.island_id} has unsafe source bounds")
        for shot_id in island.shot_ids:
            if shot_id in shot_to_island:
                raise EDLRenderError(f"shot {shot_id} belongs to multiple decode islands")
            shot_to_island[shot_id] = island.island_id
    expected_in = 0
    expected_in_frame = 0
    known_shot_ids: set[str] = set()
    known_occurrence_ids: set[str] = set()
    for shot in edl.shots:
        if shot.shot_id in known_shot_ids:
            raise EDLRenderError(f"duplicate EDL shot {shot.shot_id}")
        known_shot_ids.add(shot.shot_id)
        if shot.source_in_ms < 0 or shot.source_out_ms <= shot.source_in_ms:
            raise EDLRenderError(f"shot {shot.shot_id} has invalid source timing")
        if not math.isfinite(shot.speed) or not 0.5 <= shot.speed <= 2.0:
            raise EDLRenderError(f"shot {shot.shot_id} has an unsupported speed")
        if shot.timeline_in_ms != expected_in or shot.timeline_out_ms <= expected_in:
            raise EDLRenderError("EDL shots must form a contiguous positive timeline")
        expected_in = shot.timeline_out_ms
        if (
            shot.timeline_in_frame != expected_in_frame
            or shot.timeline_out_frame <= expected_in_frame
        ):
            raise EDLRenderError("EDL shots must form a contiguous positive frame timeline")
        expected_in_frame = shot.timeline_out_frame
        if (
            shot.timeline_in_ms != round(shot.timeline_in_frame * 1000 / edl.fps)
            or shot.timeline_out_ms != round(shot.timeline_out_frame * 1000 / edl.fps)
        ):
            raise EDLRenderError(
                f"shot {shot.shot_id} milliseconds do not match its frame timeline"
            )
        if (
            not math.isfinite(shot.framing.center_x)
            or not 0.0 <= shot.framing.center_x <= 1.0
            or not math.isfinite(shot.framing.base_scale)
            or not 1.0 <= shot.framing.base_scale <= 1.35
        ):
            raise EDLRenderError(f"shot {shot.shot_id} has invalid framing geometry")
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
        expected_word_ids = list(range(shot.from_word_id, shot.to_word_id + 1))
        if [item.word_id for item in shot.word_occurrences] != expected_word_ids:
            raise EDLRenderError(
                f"shot {shot.shot_id} word occurrences do not match its inclusive word range"
            )
        previous_occurrence_frame = shot.timeline_in_frame
        for occurrence in shot.word_occurrences:
            if occurrence.occurrence_id in known_occurrence_ids:
                raise EDLRenderError(
                    f"duplicate compiled word occurrence {occurrence.occurrence_id!r}"
                )
            known_occurrence_ids.add(occurrence.occurrence_id)
            if occurrence.shot_id != shot.shot_id:
                raise EDLRenderError(
                    f"word occurrence {occurrence.occurrence_id!r} belongs to another shot"
                )
            if not 0 <= occurrence.word_id < len(transcript.words):
                raise EDLRenderError(
                    f"word occurrence {occurrence.occurrence_id!r} is outside the transcript"
                )
            expected_source_in = max(
                shot.source_in_ms,
                round(transcript.words[occurrence.word_id].start * 1000),
            )
            expected_source_out = min(
                shot.source_out_ms,
                round(transcript.words[occurrence.word_id].end * 1000),
            )
            if (
                occurrence.source_in_ms != expected_source_in
                or occurrence.source_out_ms != expected_source_out
            ):
                raise EDLRenderError(
                    f"word occurrence {occurrence.occurrence_id!r} has invalid source timing"
                )
            if not (
                shot.timeline_in_frame
                <= occurrence.timeline_in_frame
                < occurrence.timeline_out_frame
                <= shot.timeline_out_frame
            ):
                raise EDLRenderError(
                    f"word occurrence {occurrence.occurrence_id!r} has invalid frame timing"
                )
            if occurrence.timeline_in_frame < previous_occurrence_frame:
                raise EDLRenderError(
                    f"word occurrence {occurrence.occurrence_id!r} is not monotonic"
                )
            previous_occurrence_frame = occurrence.timeline_in_frame
            if (
                occurrence.timeline_in_ms
                != round(occurrence.timeline_in_frame * 1000 / edl.fps)
                or occurrence.timeline_out_ms
                != round(occurrence.timeline_out_frame * 1000 / edl.fps)
            ):
                raise EDLRenderError(
                    f"word occurrence {occurrence.occurrence_id!r} is not frame-authoritative"
                )
        for effect in shot.effects:
            if (
                not 50 <= effect.duration_ms <= 1_500
                or not math.isfinite(effect.intensity)
                or not 0.0 <= effect.intensity <= 1.0
            ):
                raise EDLRenderError(f"shot {shot.shot_id} has invalid effect parameters")
            if effect.at_word_id is not None and effect.at_word_id not in expected_word_ids:
                raise EDLRenderError(
                    f"shot {shot.shot_id}: effect word {effect.at_word_id} is outside the shot"
                )
    if expected_in != edl.duration_ms:
        raise EDLRenderError("EDL duration does not match its shot timeline")
    if expected_in_frame != edl.duration_frames:
        raise EDLRenderError("EDL frame duration does not match its shot timeline")
    if set(shot_to_island) != known_shot_ids:
        raise EDLRenderError("decode islands reference an unknown shot")
    return islands


def _simple_frame_filter(shot: CompiledShot, *, width: int, height: int) -> str:
    """Closed single-input framing filters.

    ``fit_blur`` needs a split/overlay graph and is handled by
    :func:`_append_framing`. ``pip_proof`` cannot be represented honestly until
    the EDL carries an authorised proof asset, so it is rejected rather than
    silently rendered as a different effect.
    """
    mode = shot.framing.mode
    if mode == "source_safe":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
        )
    if mode == "pip_proof":
        raise EDLRenderError("pip_proof requires an authorised visual insert asset")
    if mode == "fit_blur":
        raise EDLRenderError("fit_blur must be compiled through its split graph")

    center_x = _number(shot.framing.center_x)
    scale = _number(shot.framing.base_scale)
    if mode == "screen_focus":
        center_x = "0.5"
    return (
        f"scale=w='trunc({width}*{scale}/2)*2':h='trunc({height}*{scale}/2)*2':"
        f"force_original_aspect_ratio=increase,"
        f"crop={width}:{height}:x='(iw-ow)*{center_x}':y='(ih-oh)/2'"
    )


def _append_framing(
    lines: list[str],
    *,
    source_label: str,
    target_label: str,
    shot: CompiledShot,
    shot_index: int,
    width: int,
    height: int,
) -> None:
    """Render a framing preset, including the real fit+blur composition."""
    if shot.framing.mode != "fit_blur":
        lines.append(
            f"[{source_label}]"
            f"{_simple_frame_filter(shot, width=width, height=height)}"
            f"[{target_label}]"
        )
        return

    background = f"frame_{shot_index}_bg"
    foreground = f"frame_{shot_index}_fg"
    blurred = f"frame_{shot_index}_blurred"
    fitted = f"frame_{shot_index}_fitted"
    lines.append(f"[{source_label}]split=2[{background}][{foreground}]")
    lines.append(
        f"[{background}]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},boxblur=20:2[{blurred}]"
    )
    lines.append(
        f"[{foreground}]scale={width}:{height}:force_original_aspect_ratio=decrease"
        f"[{fitted}]"
    )
    lines.append(
        f"[{blurred}][{fitted}]overlay=(W-w)/2:(H-h)/2,setsar=1[{target_label}]"
    )


def _split_effect(
    lines: list[str],
    *,
    source_label: str,
    target_label: str,
    prefix: str,
    start_frame: int,
    end_frame: int,
    shot_frames: int,
    fps: int,
    effect_filter: str,
) -> None:
    """Apply an effect only within an output-time interval without re-timing."""
    pieces: list[tuple[int, int, str, str | None]] = []
    if start_frame > 0:
        pieces.append((0, start_frame, f"{prefix}_pre", None))
    pieces.append((start_frame, end_frame, f"{prefix}_mid", effect_filter))
    if end_frame < shot_frames:
        pieces.append((end_frame, shot_frames, f"{prefix}_post", None))

    split_labels = "".join(f"[{name}_in]" for _, _, name, _ in pieces)
    lines.append(f"[{source_label}]split={len(pieces)}{split_labels}")
    output_labels: list[str] = []
    for piece_start, piece_end, name, piece_filter in pieces:
        output = f"{name}_out"
        chain = (
            f"[{name}_in]trim=start_frame={piece_start}:"
            f"end_frame={piece_end},setpts=N/({fps}*TB)"
        )
        if piece_filter:
            chain += f",{piece_filter}"
        chain += ",setsar=1"
        lines.append(f"{chain}[{output}]")
        output_labels.append(f"[{output}]")
    if len(output_labels) == 1:
        lines.append(f"{output_labels[0]}null[{target_label}]")
    else:
        lines.append(
            "".join(output_labels)
            + f"concat=n={len(output_labels)}:v=1:a=0[{target_label}]"
        )


def _freeze_effect(
    lines: list[str],
    *,
    source_label: str,
    target_label: str,
    prefix: str,
    start_frame: int,
    end_frame: int,
    shot_frames: int,
    fps: int,
) -> None:
    """Freeze a moment while preserving the compiled shot's exact duration.

    The hold replaces source material after the sampled frame.  This is the
    only duration-conserving implementation without asking the EDL compiler to
    reserve extra source time for a freeze.
    """
    hold_frames = end_frame - start_frame
    hold = _number(hold_frames / fps)
    pieces: list[tuple[str, str]] = []
    split_names: list[str] = []
    if start_frame > 0:
        split_names.append(f"{prefix}_pre_in")
    split_names.append(f"{prefix}_frame_in")
    if end_frame < shot_frames:
        split_names.append(f"{prefix}_post_in")
    lines.append(
        f"[{source_label}]split={len(split_names)}"
        + "".join(f"[{name}]" for name in split_names)
    )
    if start_frame > 0:
        lines.append(
            f"[{prefix}_pre_in]trim=start_frame=0:end_frame={start_frame},"
            f"setpts=N/({fps}*TB),setsar=1[{prefix}_pre_out]"
        )
        pieces.append((f"{prefix}_pre_out", "pre"))
    lines.append(
        f"[{prefix}_frame_in]trim=start_frame={start_frame}:"
        f"end_frame={start_frame + 1},setpts=N/({fps}*TB),"
        f"tpad=stop_mode=clone:stop_duration={hold},trim=end_frame={hold_frames},"
        f"setpts=N/({fps}*TB),setsar=1[{prefix}_frame_out]"
    )
    pieces.append((f"{prefix}_frame_out", "frame"))
    if end_frame < shot_frames:
        lines.append(
            f"[{prefix}_post_in]trim=start_frame={end_frame}:"
            f"end_frame={shot_frames},setpts=N/({fps}*TB),"
            f"setsar=1[{prefix}_post_out]"
        )
        pieces.append((f"{prefix}_post_out", "post"))
    labels = "".join(f"[{label}]" for label, _ in pieces)
    if len(pieces) == 1:
        lines.append(f"{labels}null[{target_label}]")
    else:
        lines.append(f"{labels}concat=n={len(pieces)}:v=1:a=0[{target_label}]")


def _effect_filter(kind: str, *, intensity: float, width: int, height: int, fps: int) -> str:
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
        raise EDLRenderError(
            "speed_ramp needs explicit source reservation/keyframes and is not renderable yet"
        )
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
    shot_frames = shot.timeline_out_frame - shot.timeline_in_frame
    for index, effect in enumerate(shot.effects):
        start_absolute_frame = _effect_timeline_frame(
            effect,
            shot=shot,
            transcript=transcript,
        )
        start_relative_frame = max(
            0,
            start_absolute_frame - shot.timeline_in_frame,
        )
        duration_frames = max(1, round(effect.duration_ms * fps / 1000))
        end_relative_frame = min(shot_frames, start_relative_frame + duration_frames)
        if end_relative_frame <= start_relative_frame:
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
                start_frame=start_relative_frame,
                end_frame=end_relative_frame,
                shot_frames=shot_frames,
                fps=fps,
            )
        else:
            _split_effect(
                lines,
                source_label=current,
                target_label=target,
                prefix=prefix,
                start_frame=start_relative_frame,
                end_frame=end_relative_frame,
                shot_frames=shot_frames,
                fps=fps,
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
                timeline_in_ms=round(
                    (shot.timeline_in_frame + start_relative_frame) * 1000 / fps
                ),
                timeline_out_ms=round(
                    (shot.timeline_in_frame + end_relative_frame) * 1000 / fps
                ),
                timeline_in_frame=shot.timeline_in_frame + start_relative_frame,
                timeline_out_frame=shot.timeline_in_frame + end_relative_frame,
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
            cut_frame = outgoing.timeline_out_frame
            fade_frames = min(
                max(1, round(edl.fps * 0.09)),
                cut_frame,
                edl.duration_frames - cut_frame,
            )
            if fade_frames <= 0:
                continue
            # A fade-to-black at both sides of the cut produced a visible
            # black flash in short-form playback.  Keep the incoming image
            # visible and reveal it with a three-frame exposure/contrast ramp.
            # The expression is evaluated on the authoritative output PTS, so
            # this remains duration- and frame-preserving without an overlap.
            start = _number(cut_frame / edl.fps)
            duration = _number(fade_frames / edl.fps)
            progress = f"(t-{start})/{duration}"
            active = f"between(t,{start},{_number((cut_frame + fade_frames) / edl.fps)})"
            lines.append(
                f"[{current}]eq="
                f"brightness='if({active},-0.12*(1-{progress}),0)':"
                f"contrast='if({active},1.12-0.12*{progress},1)':"
                f"eval=frame[{target}]"
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


def compile_ffmpeg_render_plan(
    edl: CompiledEDL,
    transcript: Transcript,
    *,
    source_has_audio: bool = True,
) -> FFmpegRenderPlan:
    """Lower a validated EDL into an island-aware, source-audio FFmpeg graph.

    This function is deterministic: the same EDL/transcript returns byte-for-
    byte identical graph text.  It does not call FFmpeg and never resolves an
    external asset ID to a filesystem path.
    """
    if not transcript.words:
        raise EDLRenderError("a transcript is required for word-timed effects")
    islands = _validate_edl(edl, transcript)

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
    video_source_by_shot: dict[str, str] = {}
    audio_source_by_shot: dict[str, str] = {}
    # Each accurately sought island is decoded exactly once.  Split that
    # decoded stream into the EDL occurrences that reuse it; referencing one
    # input label repeatedly is invalid for a complex filtergraph.
    for island in edl.decode_islands:
        input_spec = input_by_island[island.island_id]
        ordered_shot_ids = tuple(
            shot.shot_id for shot in edl.shots if shot_to_island[shot.shot_id] == island.island_id
        )
        video_labels = tuple(
            f"island_{input_spec.input_index}_v_{index}"
            for index in range(len(ordered_shot_ids))
        )
        if len(video_labels) == 1:
            lines.append(f"[{input_spec.input_index}:v]null[{video_labels[0]}]")
        else:
            labels = "".join(f"[{label}]" for label in video_labels)
            lines.append(f"[{input_spec.input_index}:v]split={len(video_labels)}{labels}")
        video_source_by_shot.update(dict(zip(ordered_shot_ids, video_labels, strict=True)))

        if source_has_audio:
            audio_labels = tuple(
                f"island_{input_spec.input_index}_a_{index}"
                for index in range(len(ordered_shot_ids))
            )
            if len(audio_labels) == 1:
                lines.append(f"[{input_spec.input_index}:a]anull[{audio_labels[0]}]")
            else:
                labels = "".join(f"[{label}]" for label in audio_labels)
                lines.append(f"[{input_spec.input_index}:a]asplit={len(audio_labels)}{labels}")
            audio_source_by_shot.update(dict(zip(ordered_shot_ids, audio_labels, strict=True)))

    rendered_shots: list[RenderedShot] = []
    rendered_effects: list[RenderedEffect] = []
    video_concat_inputs: list[str] = []
    audio_concat_inputs: list[str] = []
    for shot_index, shot in enumerate(edl.shots):
        island = islands[shot_to_island[shot.shot_id]]
        input_spec = input_by_island[island.island_id]
        offset_in = shot.source_in_ms - island.source_in_ms
        offset_out = shot.source_out_ms - island.source_in_ms
        raw_video = f"v_raw_{shot_index}"
        framed_video = f"v_frame_{shot_index}"
        base_audio = f"a_base_{shot_index}"
        speed = _number(shot.speed)
        shot_frames = shot.timeline_out_frame - shot.timeline_in_frame
        shot_duration = _number(shot_frames / edl.fps)
        lines.append(
            f"[{video_source_by_shot[shot.shot_id]}]"
            f"trim=start={_seconds(offset_in)}:end={_seconds(offset_out)},"
            f"setpts=(PTS-STARTPTS)/{speed},fps={edl.fps}[{raw_video}]"
        )
        _append_framing(
            lines,
            source_label=raw_video,
            target_label=framed_video,
            shot=shot,
            shot_index=shot_index,
            width=edl.width,
            height=edl.height,
        )
        if source_has_audio:
            lines.append(
                f"[{audio_source_by_shot[shot.shot_id]}]"
                f"atrim=start={_seconds(offset_in)}:end={_seconds(offset_out)},"
                f"asetpts=PTS-STARTPTS,atempo={speed},aresample=48000,"
                f"aformat=sample_rates=48000:channel_layouts=stereo,"
                f"apad=pad_dur={shot_duration},atrim=duration={shot_duration},"
                f"asetpts=PTS-STARTPTS[{base_audio}]"
            )
        else:
            lines.append(
                "anullsrc=r=48000:cl=stereo,"
                f"atrim=duration={shot_duration},asetpts=PTS-STARTPTS[{base_audio}]"
            )
        video_label, effect_records = _apply_effects(
            lines,
            shot=shot,
            shot_index=shot_index,
            source_label=framed_video,
            transcript=transcript,
            width=edl.width,
            height=edl.height,
            fps=edl.fps,
        )
        rendered_effects.extend(effect_records)
        normalized_video = f"v_shot_{shot_index}"
        lines.append(
            f"[{video_label}]tpad=stop_mode=clone:stop_duration=0.100,"
            f"trim=end_frame={shot_frames},setpts=N/({edl.fps}*TB),setsar=1"
            f"[{normalized_video}]"
        )
        video_concat_inputs.append(f"[{normalized_video}]")
        audio_concat_inputs.append(f"[{base_audio}]")
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

    lines.append(
        "".join(video_concat_inputs)
        + f"concat=n={len(edl.shots)}:v=1:a=0[v_concat]"
    )
    if len(audio_concat_inputs) == 1:
        lines.append(f"{audio_concat_inputs[0]}anull[a_concat]")
    else:
        previous_audio = audio_concat_inputs[0]
        for join_index, next_audio in enumerate(audio_concat_inputs[1:], start=1):
            output_label = "a_concat" if join_index == len(audio_concat_inputs) - 1 else (
                f"a_join_{join_index}"
            )
            lines.append(
                f"{previous_audio}{next_audio}"
                f"acrossfade=d={DIALOGUE_JOIN_FADE_SECONDS:.3f}:o=0:"
                f"c1=tri:c2=tri[{output_label}]"
            )
            previous_audio = f"[{output_label}]"
    transitioned_video, transitions = _apply_transitions(
        lines, edl=edl, source_label="v_concat"
    )
    duration = _number(edl.duration_frames / edl.fps)
    # FFmpeg rounds a frame count after speed changes.  Pad a single safe
    # margin, then trim both streams back to the compiler's authoritative EDL.
    lines.append(
        f"[{transitioned_video}]tpad=stop_mode=clone:stop_duration=0.100,"
        f"trim=end_frame={edl.duration_frames},setpts=N/({edl.fps}*TB)[v_dialogue]"
    )
    lines.append(
        f"[a_concat]apad=pad_dur={duration},atrim=duration={duration},"
        "asetpts=PTS-STARTPTS[a_dialogue]"
    )
    limitations = (
        "Music and SFX catalogue IDs are deferred until a trusted asset resolver provides paths.",
        "pip_proof is rejected until the EDL carries an authorised visual insert asset.",
        "follow_primary_face is a static crop until framing analysis supplies a motion track.",
        "speed_ramp is rejected until the EDL reserves source time and keyframes explicitly.",
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
        requires_source_audio=source_has_audio,
        deferred_music_asset_ids=tuple(track.asset_id for track in edl.music),
        deferred_sfx_asset_ids=tuple(cue.asset_id for cue in edl.sfx),
        limitations=limitations,
    )
