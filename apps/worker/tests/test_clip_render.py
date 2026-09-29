from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from app.models import MontageCandidate, MontageSegment, Transcript, TranscriptWord
from app.pipeline import clip_render
from app.pipeline.clip_render import ClipRejected, prepare_candidate_edit, render_prepared_candidate
from app.pipeline.ffmpeg import FFmpegError


def transcript() -> Transcript:
    words = [TranscriptWord(f"word{i}", i * 0.5, i * 0.5 + 0.44) for i in range(40)]
    return Transcript(" ".join(w.word for w in words), words)


def candidate(start=1.0, end=14.44) -> MontageCandidate:
    return MontageCandidate("Proof", "Original hook", [MontageSegment("single", start, end)],
                            "A complete source passage.", 80, {})


def prepared():
    return prepare_candidate_edit(candidate(), transcript(), source_duration_seconds=20,
                                  framings=[("fit_blur", 0.5)])


def test_adapter_preserves_all_selected_words_and_persists_compiled_timing():
    selected = candidate()
    result = prepare_candidate_edit(selected, transcript(), source_duration_seconds=20,
                                    framings=[("fit_blur", 0.5)])
    assert result.qc.status == "pass"
    assert [w.word_id for w in result.edl.shots[0].word_occurrences] == list(range(2, 29))
    assert selected.segments[0].start == result.edl.shots[0].source_in_ms / 1000
    assert selected.segments[0].end == result.edl.shots[0].source_out_ms / 1000
    assert selected.transcript_excerpt == " ".join(f"word{i}" for i in range(2, 29))
    assert {w.word_id for cue in result.captions.cues for w in cue.words} == set(range(2, 29))


@pytest.mark.parametrize("start,end,reason", [
    (2.0, 12.0, "final_duration_out_of_bounds"),
    (float("nan"), 14.0, "invalid_source_range"),
    (-0.1, 14.0, "invalid_source_range"),
    (1.0, 21.0, "invalid_source_range"),
    (1.2, 14.44, "partial_boundary_word"),
    (1.0, 14.2, "partial_boundary_word"),
])
def test_adapter_rechecks_final_bounds_after_mutation(start, end, reason):
    with pytest.raises(ClipRejected, match=reason):
        prepare_candidate_edit(candidate(start, end), transcript(), source_duration_seconds=20,
                               framings=[("fit_blur", 0.5)])


async def test_renderer_failure_never_retries_without_required_captions(monkeypatch, tmp_path):
    render = AsyncMock(side_effect=FFmpegError("encoder failed"))
    monkeypatch.setattr(clip_render, "render_compiled_edl", render)
    with pytest.raises(ClipRejected, match="render_failed"):
        await render_prepared_candidate(prepared=prepared(), source="source.mp4",
                                        transcript=transcript(),
                                        out_path=str(tmp_path / "clip.mp4"),
                                        source_sha256="0" * 64)
    assert render.await_count == 1
    assert render.call_args.kwargs["subtitles_path"].endswith(".ass")


async def test_empty_caption_plan_cannot_be_delivered(monkeypatch, tmp_path):
    plan = prepared()
    plan = replace(plan, captions=replace(plan.captions, cues=()))
    render = AsyncMock()
    monkeypatch.setattr(clip_render, "render_compiled_edl", render)
    with pytest.raises(ClipRejected, match="missing_required_captions"):
        await render_prepared_candidate(prepared=plan, source="source.mp4", transcript=transcript(),
                                        out_path=str(tmp_path / "clip.mp4"), source_sha256="0" * 64)
    render.assert_not_awaited()
