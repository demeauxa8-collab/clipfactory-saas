#!/usr/bin/env python3
"""Replay retained proposals against the actual clipping path, without providers.

Run once with the baseline checkout on PYTHONPATH and --engine legacy, then
with the candidate checkout and --engine compiled. Never regenerate proposals
between comparisons. The report separates surviving candidates, source-word
boundary defects, technical QC, time and output hashes; it is not a virality
score or a substitute for a blind human editorial review.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import time
from dataclasses import asdict, fields
from pathlib import Path

import structlog

import app
from app.models import (
    ArcSegmentSpec,
    JobContext,
    StoryArc,
    Transcript,
    TranscriptSentence,
    TranscriptWord,
)
from app.pipeline.boundaries import (
    anchor_arcs_to_transcript,
    filter_arcs_by_duration,
    snap_arc_segments,
)
from app.pipeline.captions import FIT_BLUR_MARGIN_V, write_ass_for_montage
from app.pipeline.ffmpeg import probe_media, render_montage_clip, validate_rendered_clip
from app.pipeline.runner import _guard_black_open
from app.pipeline.score import rank_and_pick, score_arc
from app.pipeline.verify import verify_arcs


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dataclass_args(cls, raw):
    names = {item.name for item in fields(cls)}
    return {key: value for key, value in raw.items() if key in names}


def boundary_defects(segments, transcript):
    defects = []
    for index, segment in enumerate(segments):
        for word_id, word in enumerate(transcript.words):
            for edge, boundary in (("start", segment.start), ("end", segment.end)):
                if word.start + 0.025 < boundary < word.end - 0.025:
                    defects.append(
                        {
                            "segment": index,
                            "edge": edge,
                            "word_id": word_id,
                            "word": word.word,
                            "boundary": boundary,
                        }
                    )
    return defects


async def run(args):
    root = Path(args.out_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    fixture = json.loads(Path(args.fixture).read_text())
    raw_transcript = (
        json.loads(Path(args.transcript).read_text())
        if args.transcript
        else (fixture["transcript"])
    )
    transcript = Transcript(
        text=raw_transcript.get("text", ""),
        language=raw_transcript.get("language"),
        words=[TranscriptWord(**x) for x in raw_transcript["words"]],
        sentences=[TranscriptSentence(**x) for x in raw_transcript.get("sentences", [])],
    )
    proposals = json.loads(Path(args.proposals).read_text())["arcs"]
    arcs = []
    for raw in proposals:
        data = dataclass_args(StoryArc, raw)
        data["segments"] = [
            ArcSegmentSpec(**dataclass_args(ArcSegmentSpec, x)) for x in raw["segments"]
        ]
        arcs.append(StoryArc(**data))
    baseline = args.engine == "legacy"
    probe = await probe_media(args.source)
    report = {
        "engine": args.engine,
        "source_sha256": digest(Path(args.source)),
        "fixture_sha256": digest(Path(args.fixture)),
        "proposals_sha256": digest(Path(args.proposals)),
        "proposals": len(arcs),
        "source_probe": asdict(probe),
        "clips": [],
        "rejected": [],
    }
    report["transcript_sha256"] = hashlib.sha256(
        json.dumps(asdict(transcript), sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()
    app_root = Path(app.__file__).resolve().parent
    code_files = {
        str(path.relative_to(app_root)): digest(path) for path in sorted(app_root.rglob("*.py"))
    }
    code_files["benchmark_clipping.py"] = digest(Path(__file__))
    report["code_files"] = code_files
    report["code_sha256"] = hashlib.sha256(
        json.dumps(code_files, sort_keys=True).encode()
    ).hexdigest()
    report["code_revision"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    report["working_tree_dirty"] = bool(
        subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    )
    kwargs = {} if baseline else {"strict": True}
    arcs, anchor_report = anchor_arcs_to_transcript(arcs, transcript, **kwargs)
    report["anchoring"] = asdict(anchor_report)
    arcs, dropped = verify_arcs(transcript, arcs)
    report["verification_dropped"] = dropped
    kwargs = {} if baseline else {"safe_padding": True}
    arcs, snap_report = snap_arc_segments(
        arcs, transcript.words, sentences=transcript.sentences, **kwargs
    )
    arcs, duration_report = filter_arcs_by_duration(
        arcs,
        min_segment_seconds=3,
        max_segment_seconds=60,
        min_clip_seconds=12,
        max_clip_seconds=60,
    )
    report["snapping"] = asdict(snap_report)
    report["duration_guard"] = asdict(duration_report)
    candidates = rank_and_pick(
        [
            score_arc(
                arc=arc,
                per_segment_vision=[],
                campaign=fixture.get("campaign", {}),
                opening_text=" ".join(
                    w.word
                    for w in transcript.words
                    if arc.segments[0].start <= w.start < arc.segments[0].start + 3
                ),
            )
            for arc in arcs
        ],
        len(arcs),
    )
    context = JobContext(
        "offline",
        "offline",
        fixture.get("campaign", {}),
        "",
        3,
        str(root),
        source_path=args.source,
        duration_seconds=round(probe.duration_seconds),
        transcript=transcript,
    )
    report["ranked"] = len(candidates)
    for index, candidate in enumerate(candidates):
        if len(report["clips"]) >= args.render_limit:
            break
        started = time.monotonic()
        try:
            guarded = await _guard_black_open(
                ctx=context, cand=candidate, candidate_idx=index, log_ctx=structlog.get_logger()
            )
            if not baseline and not guarded:
                raise ValueError("unsafe_black_opening")
            output = root / f"clip_{index:02d}.mp4"
            if baseline:
                captions = output.with_suffix(".ass")
                has_captions = write_ass_for_montage(
                    transcript=transcript,
                    segments=candidate.segments,
                    out_path=str(captions),
                    audio_crossfade_seconds=0,
                    margin_v=FIT_BLUR_MARGIN_V,
                )
                duration = await render_montage_clip(
                    source=args.source,
                    segments=[(s.start, s.end) for s in candidate.segments],
                    out_path=str(output),
                    workdir=str(root / "tmp"),
                    subtitles_path=str(captions) if has_captions else None,
                    framings=[("fit_blur", 0.5)] * len(candidate.segments),
                )
                qc = await validate_rendered_clip(
                    path=str(output), expected_duration_seconds=duration
                )
                manifest = None
            else:
                from app.pipeline.clip_render import (
                    prepare_candidate_edit,
                    render_prepared_candidate,
                )

                plan = prepare_candidate_edit(
                    candidate,
                    transcript,
                    source_duration_seconds=probe.duration_seconds,
                    framings=[("fit_blur", 0.5)] * len(candidate.segments),
                )
                result = await render_prepared_candidate(
                    prepared=plan,
                    source=args.source,
                    transcript=transcript,
                    out_path=str(output),
                    source_sha256=report["source_sha256"],
                )
                duration, qc, manifest = (
                    result.rendered_duration_seconds,
                    result.quality,
                    result.manifest_path,
                )
            report["clips"].append(
                {
                    "candidate_index": index,
                    "title": candidate.title,
                    "segments": [asdict(s) for s in candidate.segments],
                    "boundary_defects": boundary_defects(candidate.segments, transcript),
                    "qc": asdict(qc),
                    "duration_seconds": duration,
                    "wall_seconds": time.monotonic() - started,
                    "path": str(output),
                    "output_sha256": digest(output),
                    "manifest": manifest,
                }
            )
        except Exception as exc:
            report["rejected"].append(
                {
                    "title": candidate.title,
                    "reason": str(exc),
                    "wall_seconds": time.monotonic() - started,
                }
            )
        (root / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (root / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "report": str(root / "report.json"),
                "rendered": len(report["clips"]),
                "rejected": len(report["rejected"]),
                "ranked": len(candidates),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--transcript")
    parser.add_argument("--proposals", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--engine", choices=("legacy", "compiled"), default="compiled")
    parser.add_argument("--render-limit", type=int, default=3)
    asyncio.run(run(parser.parse_args()))
