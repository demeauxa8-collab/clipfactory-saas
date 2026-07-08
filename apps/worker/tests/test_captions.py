from pathlib import Path

from app.models import MontageSegment, Transcript, TranscriptWord
from app.pipeline.captions import HIGHLIGHT_BGR, write_ass_for_montage
from app.pipeline.transcribe import merge_french_elisions

APOS = "’"  # typographic apostrophe used by the elision repair


def _dialogue_lines(path: str) -> list[str]:
    return [
        ln for ln in Path(path).read_text(encoding="utf-8").splitlines()
        if ln.startswith("Dialogue:")
    ]


def _text_of(line: str) -> str:
    return line.split(",", 9)[-1]


# ---------------------------------------------------------------------------
# French elision repair (transcribe.merge_french_elisions)
# ---------------------------------------------------------------------------

def test_merge_elision_j_ai() -> None:
    merged = merge_french_elisions(
        [TranscriptWord("J", 0.0, 0.2), TranscriptWord("ai", 0.25, 0.5)]
    )
    assert len(merged) == 1
    assert merged[0].word == f"J{APOS}ai"
    # Timing spans the first word's start to the second word's end.
    assert (merged[0].start, merged[0].end) == (0.0, 0.5)


def test_merge_elision_preserves_case_and_lowercase_forms() -> None:
    merged = merge_french_elisions(
        [
            TranscriptWord("l", 0.0, 0.1),
            TranscriptWord("objectif", 0.15, 0.6),
            TranscriptWord("c", 0.7, 0.8),
            TranscriptWord("est", 0.85, 1.0),
            TranscriptWord("qu", 1.1, 1.2),
            TranscriptWord("en", 1.25, 1.4),
        ]
    )
    assert [w.word for w in merged] == [
        f"l{APOS}objectif",
        f"c{APOS}est",
        f"qu{APOS}en",
    ]


def test_merge_aujourdhui() -> None:
    merged = merge_french_elisions(
        [TranscriptWord("aujourd", 1.0, 1.3), TranscriptWord("hui", 1.35, 1.6)]
    )
    assert len(merged) == 1
    assert merged[0].word == f"aujourd{APOS}hui"
    assert (merged[0].start, merged[0].end) == (1.0, 1.6)


def test_merge_does_not_touch_non_elided_or_consonant() -> None:
    words = [
        TranscriptWord("le", 0.0, 0.2),      # not an elidable single letter
        TranscriptWord("monde", 0.25, 0.6),  # consonant start anyway
        TranscriptWord("d", 0.7, 0.8),       # elidable, but next is a consonant
        TranscriptWord("bien", 0.85, 1.1),
    ]
    merged = merge_french_elisions(words)
    assert [w.word for w in merged] == ["le", "monde", "d", "bien"]


def test_merge_input_not_mutated() -> None:
    original = [TranscriptWord("J", 0.0, 0.2), TranscriptWord("ai", 0.25, 0.5)]
    merge_french_elisions(original)
    assert [w.word for w in original] == ["J", "ai"]


# ---------------------------------------------------------------------------
# Grouping: 2-3 words, early cut on pause, no orphan single words
# ---------------------------------------------------------------------------

def _group_texts(path: str) -> list[str]:
    """One entry per caption group (the karaoke events of a group all share the
    same word set, so we dedupe by the uppercased word tuple in order)."""
    seen: list[str] = []
    for ln in _dialogue_lines(path):
        # Strip ASS override blocks to get the plain uppercased word sequence.
        raw = _text_of(ln)
        plain = []
        skip = False
        for ch in raw:
            if ch == "{":
                skip = True
            elif ch == "}":
                skip = False
            elif not skip:
                plain.append(ch)
        key = "".join(plain).strip()
        if not seen or seen[-1] != key:
            seen.append(key)
    return seen


def test_pause_forces_a_group_break(tmp_path) -> None:
    words = [
        TranscriptWord("un", 0.0, 0.3),
        TranscriptWord("deux", 0.35, 0.6),
        TranscriptWord("trois", 0.65, 0.9),
        # 0.6s silence -> forces a new group
        TranscriptWord("quatre", 1.5, 1.8),
        TranscriptWord("cinq", 1.85, 2.1),
    ]
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=Transcript(text="", words=words),
        segments=[MontageSegment(role="single", start=0.0, end=2.1)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
    )
    groups = _group_texts(str(out))
    # trois (before the pause) and quatre (after) never share a caption.
    for g in groups:
        assert not ("TROIS" in g and "QUATRE" in g)
    joined = " || ".join(groups)
    assert "UN DEUX TROIS" in joined
    assert "QUATRE CINQ" in joined


def test_four_words_split_two_two_no_orphan(tmp_path) -> None:
    words = [
        TranscriptWord("alpha", 0.0, 0.3),
        TranscriptWord("bravo", 0.35, 0.6),
        TranscriptWord("charlie", 0.65, 0.9),
        TranscriptWord("delta", 0.95, 1.2),
    ]
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=Transcript(text="", words=words),
        segments=[MontageSegment(role="single", start=0.0, end=1.2)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
    )
    groups = _group_texts(str(out))
    # No pause, 4 words, chunk max 3 -> balanced [2, 2], never a lone word.
    assert len(groups) == 2
    assert all(len(g.split()) == 2 for g in groups)


def test_single_word_group_allowed_when_isolated_by_pauses(tmp_path) -> None:
    words = [
        TranscriptWord("alpha", 0.0, 0.4),
        TranscriptWord("bravo", 2.0, 2.4),    # long pause before and after
        TranscriptWord("charlie", 4.0, 4.4),
    ]
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=Transcript(text="", words=words),
        segments=[MontageSegment(role="single", start=0.0, end=4.4)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
    )
    groups = _group_texts(str(out))
    assert groups == ["ALPHA", "BRAVO", "CHARLIE"]


# ---------------------------------------------------------------------------
# Rendering: uppercase + highlight only content words in green (76E600)
# ---------------------------------------------------------------------------

def test_uppercase_and_highlight_rules(tmp_path) -> None:
    words = [
        TranscriptWord("objectif", 0.0, 0.4),  # content word -> highlighted
        TranscriptWord("mais", 0.45, 0.7),     # stop-word (>2 chars) -> plain
        TranscriptWord("clair", 0.75, 1.1),    # content word -> highlighted
    ]
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=Transcript(text="", words=words),
        segments=[MontageSegment(role="single", start=0.0, end=1.1)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
    )
    lines = _dialogue_lines(str(out))
    # One 3-word chunk -> one karaoke event per word (active word by index).
    assert len(lines) == 3
    # Text is rendered all-caps.
    assert "OBJECTIF" in lines[0]
    assert "MAIS" in lines[1]
    # Content words are accented in green; the stop-word event is never accented.
    assert HIGHLIGHT_BGR == "76E600"
    assert HIGHLIGHT_BGR in lines[0]   # objectif active
    assert HIGHLIGHT_BGR not in lines[1]  # mais active but stop-word
    assert HIGHLIGHT_BGR in lines[2]   # clair active


def test_short_token_not_highlighted(tmp_path) -> None:
    words = [
        TranscriptWord("et", 0.0, 0.2),       # <= 2 chars -> never highlighted
        TranscriptWord("puissant", 0.25, 0.7),  # content word -> highlighted
    ]
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=Transcript(text="", words=words),
        segments=[MontageSegment(role="single", start=0.0, end=0.7)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
    )
    lines = _dialogue_lines(str(out))
    assert len(lines) == 2
    assert HIGHLIGHT_BGR not in lines[0]  # "et" active but too short
    assert HIGHLIGHT_BGR in lines[1]      # "puissant" active


def test_karaoke_holds_highlight_within_group_no_gap(tmp_path) -> None:
    words = [
        TranscriptWord("premier", 0.0, 0.4),
        TranscriptWord("deuxieme", 0.45, 0.9),
    ]
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=Transcript(text="", words=words),
        segments=[MontageSegment(role="single", start=0.0, end=0.9)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
    )
    lines = _dialogue_lines(str(out))
    ends = [ln.split(",")[2] for ln in lines]
    starts = [ln.split(",")[1] for ln in lines]
    # Contiguous coverage across the two events of the single group.
    assert ends[:-1] == starts[1:]


def test_static_mode_emits_one_event_per_chunk(tmp_path) -> None:
    words = [
        TranscriptWord("objectif", 0.0, 0.4),
        TranscriptWord("clair", 0.45, 0.9),
    ]
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=Transcript(text="", words=words),
        segments=[MontageSegment(role="single", start=0.0, end=0.9)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
        karaoke=False,
    )
    lines = _dialogue_lines(str(out))
    assert len(lines) == 1
    assert HIGHLIGHT_BGR not in lines[0]
    assert "OBJECTIF CLAIR" in lines[0]


def test_no_words_returns_false(tmp_path) -> None:
    out = tmp_path / "clip.ass"
    ok = write_ass_for_montage(
        transcript=Transcript(text="", words=[]),
        segments=[MontageSegment(role="single", start=0.0, end=1.3)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
    )
    assert ok is False


# ---------------------------------------------------------------------------
# Per-segment captions: MarginV per event, segment attribution, joint cuts
# ---------------------------------------------------------------------------

def _margin_of(line: str) -> int:
    """MarginV is Dialogue field index 7 (times carry no comma, so a plain
    comma split is unambiguous up to the Text field)."""
    return int(line.split(",")[7])


def test_default_margin_field_is_zero_when_no_per_segment(tmp_path) -> None:
    # Without margins_per_segment every event keeps MarginV=0 (style default),
    # exactly like before this feature.
    words = [
        TranscriptWord("objectif", 0.0, 0.4),
        TranscriptWord("clair", 0.45, 0.9),
    ]
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=Transcript(text="", words=words),
        segments=[MontageSegment(role="single", start=0.0, end=0.9)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
    )
    lines = _dialogue_lines(str(out))
    assert lines
    assert all(_margin_of(ln) == 0 for ln in lines)


def test_per_segment_margins_applied_per_event(tmp_path) -> None:
    # Two distant segments (setup 0-2s, payoff 10-12s) with distinct framings:
    # face-crop margin 400 for segment 0, fit-blur margin 620 for segment 1.
    words = [
        TranscriptWord("alpha", 0.0, 0.4),
        TranscriptWord("bravo", 0.5, 0.9),
        TranscriptWord("charlie", 10.0, 10.4),
        TranscriptWord("delta", 10.5, 10.9),
    ]
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=Transcript(text="", words=words),
        segments=[
            MontageSegment(role="setup", start=0.0, end=2.0),
            MontageSegment(role="payoff", start=10.0, end=12.0),
        ],
        out_path=str(out),
        audio_crossfade_seconds=0.15,
        margins_per_segment=[400, 620],
    )
    lines = _dialogue_lines(str(out))
    saw_seg0 = saw_seg1 = False
    for ln in lines:
        text = _text_of(ln)
        margin = _margin_of(ln)
        # A group never straddles the joint, so no event mixes both segments.
        assert not (
            ("ALPHA" in text or "BRAVO" in text)
            and ("CHARLIE" in text or "DELTA" in text)
        )
        if "ALPHA" in text or "BRAVO" in text:
            assert margin == 400
            saw_seg0 = True
        elif "CHARLIE" in text or "DELTA" in text:
            assert margin == 620
            saw_seg1 = True
    assert saw_seg0 and saw_seg1


def test_group_cut_at_segment_joint_without_pause(tmp_path) -> None:
    # Contiguous on the final timeline (no >=0.3s pause) but crossing the joint:
    # alpha/bravo live in segment 0, charlie in segment 1. Without the joint cut
    # a single 3-word chunk would swallow all three; the cut must split them.
    words = [
        TranscriptWord("alpha", 0.0, 0.3),
        TranscriptWord("bravo", 0.35, 0.6),
        TranscriptWord("charlie", 0.65, 0.95),
    ]
    out = tmp_path / "clip.ass"
    write_ass_for_montage(
        transcript=Transcript(text="", words=words),
        segments=[
            MontageSegment(role="setup", start=0.0, end=0.65),
            MontageSegment(role="payoff", start=0.65, end=2.0),
        ],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
        margins_per_segment=[400, 620],
    )
    groups = _group_texts(str(out))
    assert groups == ["ALPHA BRAVO", "CHARLIE"]
    for g in groups:
        assert not ("BRAVO" in g and "CHARLIE" in g)
    # And the margins follow: the "ALPHA BRAVO" events sit at 400, "CHARLIE" at 620.
    for ln in _dialogue_lines(str(out)):
        text = _text_of(ln)
        if "CHARLIE" in text:
            assert _margin_of(ln) == 620
        else:
            assert _margin_of(ln) == 400
