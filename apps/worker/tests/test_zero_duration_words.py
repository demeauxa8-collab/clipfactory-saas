"""whisper-1 zero-length words get a real, non-overlapping span."""

from itertools import pairwise

import pytest

from app.models import TranscriptWord
from app.pipeline.transcribe import repair_zero_duration_words


def w(word, start, end):
    return TranscriptWord(word=word, start=start, end=end)


def spans(words):
    return [(x.word, round(x.start, 3), round(x.end, 3)) for x in words]


def assert_well_formed(words):
    for x in words:
        assert x.end - x.start > 0, x
    for a, b in pairwise(words):
        assert a.end <= b.start + 1e-9, (a, b)


def test_positive_words_are_untouched():
    words = [w("a", 0.0, 0.3), w("b", 0.3, 0.7)]
    assert spans(repair_zero_duration_words(words)) == spans(words)


def test_zero_word_packed_between_neighbours_borrows_time():
    words = [w("je", 1.0, 1.4), w("a", 1.4, 1.4), w("dit", 1.4, 1.9)]
    out = repair_zero_duration_words(words)
    assert_well_formed(out)
    assert out[1].end - out[1].start >= 0.05 - 1e-9
    # Neighbours keep their own minimum and the outer bounds do not move.
    assert out[0].start == 1.0 and out[2].end == 1.9
    assert out[0].end - out[0].start >= 0.05


def test_zero_word_in_a_gap_uses_the_gap_without_swallowing_silence():
    words = [w("avant", 0.0, 0.5), w("euh", 2.0, 2.0), w("après", 5.0, 5.4)]
    out = repair_zero_duration_words(words)
    assert_well_formed(out)
    assert out[1].start >= 0.5 and out[1].end <= 5.0
    assert out[1].end - out[1].start == pytest.approx(0.2)
    assert out[1].start <= 2.0 <= out[1].end


def test_a_run_of_zero_words_is_split_evenly():
    words = [w("a", 0.0, 1.0), w("b", 1.0, 1.0), w("c", 1.0, 1.0), w("d", 1.0, 2.0)]
    out = repair_zero_duration_words(words)
    assert_well_formed(out)
    assert out[1].end - out[1].start == pytest.approx(out[2].end - out[2].start)


def test_trailing_and_leading_zero_words():
    out = repair_zero_duration_words([w("a", 0.0, 0.0), w("b", 0.0, 0.4), w("c", 0.4, 0.4)])
    assert_well_formed(out)
    assert out[0].start >= 0.0


def test_no_room_at_all_leaves_the_run_unchanged():
    words = [w("a", 1.0, 1.05), w("b", 1.05, 1.05), w("c", 1.05, 1.1)]
    out = repair_zero_duration_words(words, min_duration=0.05)
    assert spans(out) == spans(words)


def test_input_is_not_mutated_and_is_deterministic():
    words = [w("je", 1.0, 1.4), w("a", 1.4, 1.4), w("dit", 1.4, 1.9)]
    first = repair_zero_duration_words(words)
    assert words[1].start == words[1].end == 1.4
    assert spans(first) == spans(repair_zero_duration_words(words))
