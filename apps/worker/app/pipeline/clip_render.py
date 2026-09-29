"""One reviewable contract between selected source words and a delivered MP4.

The current selector and the experimental director share the EDL compiler,
caption engine and renderer. A failed operation never triggers a caption-less
or differently framed retry. Each successful render retains its exact plan,
word occurrences, technical measurements and file digests in a JSON sidecar.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from ..models import MontageCandidate, MontageSegment, Transcript
from .boundaries import MAX_CLIP_SECONDS, MIN_CLIP_SECONDS, MIN_SEGMENT_SECONDS
from .editor_v2 import EditorV2Error, PreparedV2Edit, prepare_v2_edit
from .editorial_qc import EditorialQCPolicy
from .edl import EditIntentPlan, EditScope, EditShotIntent, FramingIntent, InclusiveWordRange
from .edl_captions import write_ass_for_edl
from .ffmpeg import FFmpegError, RenderQualityReport, render_compiled_edl, validate_rendered_clip


class ClipRejected(ValueError):
    """A candidate cannot be delivered under the clipping contract."""


@dataclass(frozen=True)
class DeliveredClip:
    prepared: PreparedV2Edit
    quality: RenderQualityReport
    output_path: str
    manifest_path: str
    rendered_duration_seconds: float
    output_sha256: str


def file_sha256(path: str) -> str:
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def transcript_sha256(transcript: Transcript) -> str:
    encoded = json.dumps(asdict(transcript), sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def prepare_candidate_edit(
    candidate: MontageCandidate,
    transcript: Transcript,
    *,
    source_duration_seconds: float,
    framings: list[tuple[str, float]],
    min_clip_seconds: float = MIN_CLIP_SECONDS,
    max_clip_seconds: float = MAX_CLIP_SECONDS,
    width: int = 1080,
    height: int = 1920,
) -> PreparedV2Edit:
    """Adapt the existing selector to the same word-ID EDL as the director.

    Only fully included words are selected. Rolls may occupy silence, never an
    adjacent unselected word. All words of each chosen segment are required;
    the adapter cannot drop the setup or payoff to satisfy a duration target.
    """
    if not math.isfinite(source_duration_seconds) or source_duration_seconds <= 0:
        raise ClipRejected("invalid_source_duration")
    if not transcript.words or not candidate.segments:
        raise ClipRejected("no_spoken_content")
    if len(framings) != len(candidate.segments):
        raise ClipRejected("framing_count_mismatch")
    shots: list[EditShotIntent] = []
    required: list[InclusiveWordRange] = []
    for index, (segment, framing) in enumerate(zip(candidate.segments, framings, strict=True)):
        if (
            not math.isfinite(segment.start) or not math.isfinite(segment.end)
            or not 0 <= segment.start < segment.end <= source_duration_seconds + 0.001
        ):
            raise ClipRejected(f"segment_{index}:invalid_source_range")
        if segment.end - segment.start < MIN_SEGMENT_SECONDS:
            raise ClipRejected(f"segment_{index}:too_short_after_repair")
        word_ids = [
            i for i, word in enumerate(transcript.words)
            if word.start >= segment.start - 0.001 and word.end <= segment.end + 0.001
            and word.word.strip()
        ]
        if not word_ids:
            raise ClipRejected(f"segment_{index}:no_complete_words")
        first, last = word_ids[0], word_ids[-1]
        # Any substantially cut boundary word signals a bad selection, rather
        # than permission to silently remove it while adapting to the EDL.
        for word in transcript.words:
            overlap = min(word.end, segment.end) - max(word.start, segment.start)
            if overlap > 0.025 and (
                word.start < segment.start - 0.025 or word.end > segment.end + 0.025
            ):
                raise ClipRejected(f"segment_{index}:partial_boundary_word")
        first_word, last_word = transcript.words[first], transcript.words[last]
        mode, center = framing
        if mode not in {"face_crop", "fit_blur"}:
            raise ClipRejected(f"segment_{index}:unknown_framing")
        role = "hook" if index == 0 else (
            "payoff" if index == len(candidate.segments) - 1 else "bridge"
        )
        shots.append(EditShotIntent(
            shot_id=f"segment_{index:02d}", role=role,
            from_word_id=first, to_word_id=last,
            framing=FramingIntent("locked_face" if mode == "face_crop" else "fit_blur", center),
            # A selected arc provides a narrative unit; a hard joint preserves
            # its full dialogue. Decorative transitions require director evidence.
            transition_out="hard_cut",
            pre_roll_ms=min(250, max(0, round((first_word.start - segment.start) * 1000))),
            post_roll_ms=min(400, max(0, round((segment.end - last_word.end) * 1000))),
        ))
        required.append(InclusiveWordRange(first, last))
    scope = EditScope(
        allowed_word_ranges=(InclusiveWordRange(0, len(transcript.words) - 1),),
        required_word_ranges=tuple(required),
    )
    policy = EditorialQCPolicy(
        final_roles=frozenset({"hook"}) if len(shots) == 1 else frozenset({"payoff"}),
        required_word_ranges=tuple(required),
        # Pronouns alone cannot prove missing context. The selector already
        # evaluates self-containment; the director can supply explicit referents.
        weak_opening_tokens=frozenset(),
    )
    try:
        prepared = prepare_v2_edit(
            EditIntentPlan("2.0", candidate.rationale or candidate.title or "Selected source arc",
                           tuple(shots)),
            transcript, source_duration_ms=round(source_duration_seconds * 1000),
            edit_scope=scope, qc_policy=policy, width=width, height=height,
        )
    except EditorV2Error as exc:
        raise ClipRejected(str(exc)) from exc
    duration = prepared.edl.duration_frames / prepared.edl.fps
    if not min_clip_seconds <= duration <= max_clip_seconds:
        raise ClipRejected(f"final_duration_out_of_bounds:{duration:.3f}")
    if any(
        (shot.source_out_ms - shot.source_in_ms) / 1000 < MIN_SEGMENT_SECONDS
        for shot in prepared.edl.shots
    ):
        raise ClipRejected("segment_too_short_after_compilation")
    # Persist only the final compiler-owned windows. The selection model's
    # original proposal remains available separately in candidate.arc.
    candidate.segments = [
        MontageSegment(
            role=segment.role,
            start=shot.source_in_ms / 1000,
            end=shot.source_out_ms / 1000,
            transcript_excerpt=" ".join(
                word.word for word in transcript.words[shot.from_word_id:shot.to_word_id + 1]
                if word.word.strip()
            ),
            why=segment.why,
        )
        for segment, shot in zip(candidate.segments, prepared.edl.shots, strict=True)
    ]
    candidate.transcript_excerpt = " ... ".join(s.transcript_excerpt for s in candidate.segments)
    return prepared


async def render_prepared_candidate(
    *,
    prepared: PreparedV2Edit,
    source: str,
    transcript: Transcript,
    out_path: str,
    source_sha256: str,
) -> DeliveredClip:
    """Execute the frozen EDL, require captions and validate the actual output."""
    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    captions = output.with_suffix(".ass")
    if not prepared.captions.cues or not write_ass_for_edl(
        prepared.captions, out_path=str(captions)
    ):
        raise ClipRejected("missing_required_captions")
    intended = prepared.edl.duration_frames / prepared.edl.fps
    try:
        await render_compiled_edl(
            source=source, edl=prepared.edl, transcript=transcript,
            out_path=str(output), subtitles_path=str(captions),
        )
        quality = await validate_rendered_clip(
            path=str(output), expected_duration_seconds=intended,
            expected_width=prepared.edl.width, expected_height=prepared.edl.height,
            expected_fps=prepared.edl.fps,
        )
    except FFmpegError as exc:
        raise ClipRejected(f"render_failed:{exc}") from exc
    if not quality.ok:
        raise ClipRejected("render_qc:" + ",".join(quality.problems))
    digest = await asyncio.to_thread(file_sha256, str(output))
    manifest = {
        "schema_version": "1.0", "renderer": "compiled_edl_v2",
        "source_sha256": source_sha256, "transcript_sha256": transcript_sha256(transcript),
        "output_sha256": digest, "captions_sha256": file_sha256(str(captions)),
        "edl": asdict(prepared.edl), "editorial_qc": asdict(prepared.qc),
        "captions": asdict(prepared.captions), "technical_qc": asdict(quality),
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )
    return DeliveredClip(
        prepared, quality, str(output), str(manifest_path),
        quality.duration_seconds or intended, digest,
    )
