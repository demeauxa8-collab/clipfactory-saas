#!/usr/bin/env python3
"""Render three reviewable V2 edits from the retained ClipFactory fixture.

This is a local benchmark harness, not a production runner switch.  The plans
exercise the same closed EDL contract that an LLM returns, including exact word
boundaries, non-linear ordering, framing variation, effects and transitions.
No provider or network API is called.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.models import Transcript, TranscriptWord
from app.pipeline.editor_v2 import RenderedV2Edit, render_v2_edit
from app.pipeline.editorial_qc import EditorialQCPolicy
from app.pipeline.edl import (
    EditIntentPlan,
    EditScope,
    EditShotIntent,
    EffectIntent,
    FramingIntent,
    InclusiveWordRange,
)

VARIANT_NAMES = ("proof_first", "curiosity", "creator_led")


@dataclass(frozen=True)
class VariantSpec:
    plan: EditIntentPlan
    scope: EditScope
    qc_policy: EditorialQCPolicy
    target_duration_seconds: int


def _load_transcript(fixture_path: Path) -> Transcript:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    transcript = payload.get("transcript") or {}
    words = [TranscriptWord(**word) for word in transcript.get("words") or []]
    if not words:
        raise ValueError("fixture transcript has no words")
    return Transcript(
        text=str(transcript.get("text") or " ".join(word.word for word in words)),
        words=words,
        language=transcript.get("language"),
    )


def _anchor(transcript: Transcript, start: int, end: int, *, edge: str) -> str:
    if edge == "start":
        selected = transcript.words[start : min(end + 1, start + 3)]
    else:
        selected = transcript.words[max(start, end - 2) : end + 1]
    return " ".join(word.word for word in selected if word.word.strip())


def _shot(
    transcript: Transcript,
    shot_id: str,
    role: str,
    start: int,
    end: int,
    *,
    framing: str,
    caption_theme: str,
    speed: float = 1.0,
    effects: tuple[EffectIntent, ...] = (),
    transition: str = "hard_cut",
) -> EditShotIntent:
    return EditShotIntent(
        shot_id=shot_id,
        role=role,  # type: ignore[arg-type]
        from_word_id=start,
        to_word_id=end,
        start_anchor=_anchor(transcript, start, end, edge="start"),
        end_anchor=_anchor(transcript, start, end, edge="end"),
        framing=FramingIntent(framing, center_x=0.5, base_scale=1.06),  # type: ignore[arg-type]
        effects=effects,
        transition_out=transition,  # type: ignore[arg-type]
        caption_theme=caption_theme,  # type: ignore[arg-type]
        speed=speed,
        pre_roll_ms=0,
        post_roll_ms=90,
    )


def _scope_and_policy(
    shots: tuple[EditShotIntent, ...],
    *,
    protected: tuple[InclusiveWordRange, ...],
    required: tuple[InclusiveWordRange, ...],
) -> tuple[EditScope, EditorialQCPolicy]:
    scope = EditScope(
        allowed_word_ranges=tuple(
            InclusiveWordRange(shot.from_word_id, shot.to_word_id) for shot in shots
        ),
        protected_word_ranges=protected,
        required_word_ranges=required,
    )
    policy = EditorialQCPolicy(
        protected_word_ranges=protected,
        required_word_ranges=required,
    )
    return scope, policy


def _proof_first(transcript: Transcript) -> VariantSpec:
    shots = (
        _shot(
            transcript,
            "proof_hook",
            "hook",
            2310,
            2327,
            framing="fit_blur",
            caption_theme="hook_bold",
            effects=(EffectIntent("punch_in", 2313, 420, 0.65),),
            transition="hard_impact",
        ),
        _shot(
            transcript,
            "ten_visits",
            "setup",
            2356,
            2378,
            framing="locked_face",
            caption_theme="standard_karaoke",
            speed=1.06,
            transition="time_jump",
        ),
        _shot(
            transcript,
            "conversion_proof",
            "proof",
            2379,
            2388,
            framing="fit_blur",
            caption_theme="proof_clean",
            effects=(EffectIntent("color_pop", 2383, 520, 0.45),),
            transition="contrast",
        ),
        _shot(
            transcript,
            "profit_math",
            "payoff",
            2582,
            2618,
            framing="fit_blur",
            caption_theme="proof_clean",
            speed=1.04,
            effects=(EffectIntent("punch_in", 2615, 500, 0.55),),
            transition="reveal",
        ),
        _shot(
            transcript,
            "scale_cta",
            "cta",
            2662,
            2686,
            framing="locked_face",
            caption_theme="standard_karaoke",
            speed=1.04,
        ),
    )
    protected = (
        InclusiveWordRange(2313, 2320),
        InclusiveWordRange(2582, 2618),
    )
    required = protected
    scope, policy = _scope_and_policy(shots, protected=protected, required=required)
    return VariantSpec(
        plan=EditIntentPlan(
            "2.0",
            "Open on the sale, prove conversion, quantify profit, "
            "then invite the scaling follow-up.",
            shots,
        ),
        scope=scope,
        qc_policy=policy,
        target_duration_seconds=23,
    )


def _curiosity(transcript: Transcript) -> VariantSpec:
    shots = (
        _shot(
            transcript,
            "risk_hook",
            "hook",
            2264,
            2289,
            framing="locked_face",
            caption_theme="hook_bold",
            speed=1.08,
            effects=(EffectIntent("zoom_out", 2280, 500, 0.45),),
            transition="reveal",
        ),
        _shot(
            transcript,
            "day_later",
            "setup",
            2235,
            2254,
            framing="locked_face",
            caption_theme="standard_karaoke",
            speed=1.08,
            transition="time_jump",
        ),
        _shot(
            transcript,
            "sale_reveal",
            "proof",
            2310,
            2320,
            framing="fit_blur",
            caption_theme="reaction_pop",
            effects=(EffectIntent("flash", 2313, 140, 0.45),),
            transition="hard_impact",
        ),
        _shot(
            transcript,
            "conversion_payoff",
            "payoff",
            2356,
            2388,
            framing="fit_blur",
            caption_theme="proof_clean",
            speed=1.08,
            effects=(EffectIntent("color_pop", 2379, 450, 0.4),),
            transition="contrast",
        ),
        _shot(
            transcript,
            "comment_cta",
            "cta",
            2845,
            2859,
            framing="locked_face",
            caption_theme="standard_karaoke",
            speed=1.04,
        ),
    )
    protected = (
        InclusiveWordRange(2264, 2289),
        InclusiveWordRange(2313, 2320),
        InclusiveWordRange(2356, 2388),
    )
    required = (InclusiveWordRange(2313, 2320), InclusiveWordRange(2356, 2388))
    scope, policy = _scope_and_policy(shots, protected=protected, required=required)
    return VariantSpec(
        plan=EditIntentPlan(
            "2.0",
            "Create loss-versus-win tension, reveal the sale, prove it with "
            "conversion, then ask for the next challenge.",
            shots,
        ),
        scope=scope,
        qc_policy=policy,
        target_duration_seconds=18,
    )


def _creator_led(transcript: Transcript) -> VariantSpec:
    shots = (
        _shot(
            transcript,
            "creator_hook",
            "hook",
            17,
            35,
            framing="locked_face",
            caption_theme="hook_bold",
            effects=(EffectIntent("punch_in", 20, 400, 0.55),),
            transition="contrast",
        ),
        _shot(
            transcript,
            "challenge_promise",
            "setup",
            36,
            51,
            framing="locked_face",
            caption_theme="standard_karaoke",
            speed=1.04,
            transition="time_jump",
        ),
        _shot(
            transcript,
            "profit_proof",
            "proof",
            2582,
            2618,
            framing="fit_blur",
            caption_theme="proof_clean",
            speed=1.04,
            effects=(EffectIntent("color_pop", 2615, 500, 0.45),),
            transition="hard_impact",
        ),
        _shot(
            transcript,
            "low_barrier_payoff",
            "payoff",
            2703,
            2717,
            framing="locked_face",
            caption_theme="reaction_pop",
            effects=(EffectIntent("punch_in", 2709, 380, 0.4),),
            transition="reveal",
        ),
        _shot(
            transcript,
            "creator_cta",
            "cta",
            2662,
            2686,
            framing="locked_face",
            caption_theme="standard_karaoke",
            speed=1.04,
        ),
    )
    protected = (
        InclusiveWordRange(17, 28),
        InclusiveWordRange(2582, 2618),
        InclusiveWordRange(2703, 2717),
    )
    required = (InclusiveWordRange(17, 28), InclusiveWordRange(2582, 2618))
    scope, policy = _scope_and_policy(shots, protected=protected, required=required)
    return VariantSpec(
        plan=EditIntentPlan(
            "2.0",
            "Establish creator authority, state the low-capital promise, prove "
            "margin, conclude, then invite the follow-up.",
            shots,
        ),
        scope=scope,
        qc_policy=policy,
        target_duration_seconds=22,
    )


def build_variant(name: str, transcript: Transcript) -> VariantSpec:
    builders = {
        "proof_first": _proof_first,
        "curiosity": _curiosity,
        "creator_led": _creator_led,
    }
    try:
        return builders[name](transcript)
    except KeyError as exc:
        raise ValueError(f"unknown variant {name!r}") from exc


def _report(result: RenderedV2Edit, *, wall_seconds: float) -> dict[str, object]:
    return {
        "source_path": result.source_path,
        "output_path": result.output_path,
        "subtitles_path": result.subtitles_path,
        "rendered_duration_seconds": result.rendered_duration_seconds,
        "black_frame_seconds": result.black_frame_seconds,
        "black_frame_ratio": result.black_frame_ratio,
        "resolved_audio_asset_ids": result.resolved_audio_asset_ids,
        "render_wall_seconds": wall_seconds,
        "realtime_factor": (
            wall_seconds / result.rendered_duration_seconds
            if result.rendered_duration_seconds > 0
            else None
        ),
        "edl": asdict(result.prepared.edl),
        "editorial_qc": asdict(result.prepared.qc),
    }


async def _run(args: argparse.Namespace) -> None:
    source = Path(args.source).resolve()
    fixture = Path(args.fixture).resolve()
    output_dir = Path(args.out_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    transcript = _load_transcript(fixture)
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        raise RuntimeError("ffmpeg and ffprobe must be installed")

    names = VARIANT_NAMES if args.variant == "all" else (args.variant,)
    width, height = ((540, 960) if args.preview else (1080, 1920))
    summary: dict[str, object] = {
        "fixture": str(fixture),
        "source": str(source),
        "canvas": {"width": width, "height": height, "fps": 30},
        "variants": {},
    }
    for name in names:
        spec = build_variant(name, transcript)
        output = output_dir / f"{name}.mp4"
        started = time.perf_counter()
        result = await render_v2_edit(
            source=str(source),
            transcript=transcript,
            plan=spec.plan,
            out_path=str(output),
            target_duration_seconds=spec.target_duration_seconds,
            edit_scope=spec.scope,
            qc_policy=spec.qc_policy,
            width=width,
            height=height,
            fps=30,
            ffmpeg_bin=ffmpeg,
            ffprobe_bin=ffprobe,
        )
        report = _report(result, wall_seconds=time.perf_counter() - started)
        (output_dir / f"{name}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary["variants"][name] = report  # type: ignore[index]
        print(
            f"{name}: {result.rendered_duration_seconds:.3f}s -> {output} "
            f"({report['render_wall_seconds']:.2f}s wall)"
        )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--variant", choices=("all", *VARIANT_NAMES), default="all")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="render 540x960 instead of the full 1080x1920 review outputs",
    )
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
