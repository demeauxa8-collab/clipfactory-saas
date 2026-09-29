"""Hold presentation constant to compare the two sets of selected source words."""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from full_stack_benchmark import ROOT, SOURCE, inputs, read, save

from app.models import MontageCandidate, MontageSegment
from app.pipeline.clip_render import (
    file_sha256,
    prepare_candidate_edit,
    render_prepared_candidate,
)


async def main():
    _, transcript = inputs()
    results = []
    for row in read("comparison.json"):
        index = row["index"]
        source_manifest = ROOT / "director_final" / f"clip_{index:02d}.manifest.json"
        original = read(str(source_manifest.relative_to(ROOT)))
        candidate = MontageCandidate(
            title=row["title"],
            hook=None,
            segments=[
                MontageSegment("single", s["source_in_ms"] / 1000, s["source_out_ms"] / 1000)
                for s in original["edl"]["shots"]
            ],
            rationale=original["edl"]["editorial_thesis"],
            score_total=row["selector_score"],
            score_breakdown={},
        )
        prepared = prepare_candidate_edit(
            candidate,
            transcript,
            source_duration_seconds=595.220,
            framings=[("fit_blur", 0.5)] * len(candidate.segments),
        )
        expected = [(s["from_word_id"], s["to_word_id"]) for s in original["edl"]["shots"]]
        actual = [(s.from_word_id, s.to_word_id) for s in prepared.edl.shots]
        if expected != actual:
            raise ValueError("presentation control must not change director-selected words")
        delivered = await render_prepared_candidate(
            prepared=prepared,
            source=str(SOURCE),
            transcript=transcript,
            out_path=str(ROOT / "director_matched" / f"clip_{index:02d}.mp4"),
            source_sha256=read("inputs.json")["source_sha256"],
        )
        results.append(
            {
                "index": index,
                "title": row["title"],
                "director_manifest_sha256": file_sha256(str(source_manifest)),
                "word_ranges_preserved": actual,
                "presentation": "benchmark_control_fit_blur_and_selector_caption_theme",
                "model_selected_presentation": False,
                "output": delivered.output_path,
                "manifest": delivered.manifest_path,
                "technical_qc": asdict(delivered.quality),
            }
        )
        save("matched-presentation.json", results)


if __name__ == "__main__":
    asyncio.run(main())
