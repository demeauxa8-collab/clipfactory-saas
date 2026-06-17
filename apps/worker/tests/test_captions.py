from pathlib import Path

from app.models import MontageSegment, Transcript, TranscriptWord
from app.pipeline.captions import HIGHLIGHT_BGR, write_ass_for_montage


def _transcript() -> Transcript:
    words = [
        TranscriptWord("Bonjour", 0.0, 0.4),
        TranscriptWord("tout", 0.45, 0.7),
        TranscriptWord("le", 0.75, 0.85),
        TranscriptWord("monde", 0.9, 1.3),
    ]
    return Transcript(text="Bonjour tout le monde", words=words)


def _dialogue_lines(path: str) -> list[str]:
    return [
        ln for ln in Path(path).read_text(encoding="utf-8").splitlines()
        if ln.startswith("Dialogue:")
    ]


def test_karaoke_emits_one_event_per_word(tmp_path) -> None:
    out = tmp_path / "clip.ass"
    ok = write_ass_for_montage(
        transcript=_transcript(),
        segments=[MontageSegment(role="single", start=0.0, end=1.3)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
    )
    assert ok
    lines = _dialogue_lines(str(out))
    # One chunk of 4 words → one Dialogue event per word.
    assert len(lines) == 4
    # Each event highlights exactly one word with the accent colour.
    assert all(line.count(HIGHLIGHT_BGR) == 1 for line in lines)
    # Every event still shows the full chunk text (4 words rendered).
    for line in lines:
        text = line.split(",", 9)[-1]
        assert text.count("Bonjour") == 1
        assert text.count("monde") == 1


def test_karaoke_holds_highlight_until_next_word_no_gap(tmp_path) -> None:
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=_transcript(),
        segments=[MontageSegment(role="single", start=0.0, end=1.3)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
    )
    lines = _dialogue_lines(str(out))
    # End of event N == start of event N+1 → contiguous coverage, no flicker.
    ends = [ln.split(",")[2] for ln in lines]
    starts = [ln.split(",")[1] for ln in lines]
    assert ends[:-1] == starts[1:]


def test_static_mode_emits_one_event_per_chunk(tmp_path) -> None:
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=_transcript(),
        segments=[MontageSegment(role="single", start=0.0, end=1.3)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
        karaoke=False,
    )
    lines = _dialogue_lines(str(out))
    assert len(lines) == 1
    assert HIGHLIGHT_BGR not in lines[0]


def test_no_words_returns_false(tmp_path) -> None:
    out = tmp_path / "clip.ass"
    ok = write_ass_for_montage(
        transcript=Transcript(text="", words=[]),
        segments=[MontageSegment(role="single", start=0.0, end=1.3)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
    )
    assert ok is False
