"""Parsing contract for the story-arc selection response.

The selection model is prompted for a rich editorial payload (video_read,
opening_words, self_contained, payoff_line). Everything here checks that we stay
tolerant: a missing, null or garbage field must degrade to a default instead of
losing the whole arc, and the montage-v2 duration bounds must keep holding.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.models import StoryArc, Transcript, TranscriptSentence, TranscriptWord
from app.pipeline.boundaries import MIN_CLIP_SECONDS
from app.pipeline.story_arcs import (
    MAX_ARC_SECONDS,
    MAX_SEGMENT_SECONDS,
    MIN_ARC_SECONDS,
    MIN_SEGMENT_SECONDS,
    _coerce_bool,
    _parse_arcs,
)

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _segment(start: float, end: float, **over: Any) -> dict[str, Any]:
    seg = {
        "role": "single",
        "start": start,
        "end": end,
        "transcript_excerpt": "j ai fait 4 millions en e commerce",
        "why": "states the credential",
    }
    seg.update(over)
    return seg


def _arc(**over: Any) -> dict[str, Any]:
    arc = {
        "title": "1 euro to a profitable store",
        "arc_type": "continuous",
        "opening_words": "J ai seulement un euro pour lancer une boutique",
        "self_contained": True,
        "segments": [_segment(0.0, 14.0)],
        "payoff_line": "On est a environ 50 euros benefice",
        "viral_reason": "a number lands the claim",
        "estimated_retention": 88,
        "continuity_risk": "low",
        "campaign_fit": 91,
        "campaign_fit_reason": "proves the method works",
        "suggested_hook": "1 euro pour lancer un business",
    }
    arc.update(over)
    return arc


def _payload(*arcs: dict[str, Any], **root: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"arcs": list(arcs)}
    out.update(root)
    return out


# ---------------------------------------------------------------------------
# 1. New editorial fields
# ---------------------------------------------------------------------------


def test_parses_editorial_fields() -> None:
    (arc,) = _parse_arcs(_payload(_arc(), video_read="a man launches a store"))
    assert arc.opening_words == "J ai seulement un euro pour lancer une boutique"
    assert arc.payoff_line == "On est a environ 50 euros benefice"
    assert arc.self_contained is True
    assert arc.suggested_hook == "1 euro pour lancer un business"
    assert arc.campaign_fit_llm == 91


def test_missing_editorial_fields_default_to_none() -> None:
    raw = _arc()
    for key in ("opening_words", "payoff_line", "self_contained", "suggested_hook"):
        raw.pop(key)
    (arc,) = _parse_arcs(_payload(raw))
    assert arc.opening_words is None
    assert arc.payoff_line is None
    # Absent self-report is optimistic: the verifier downstream is the real gate.
    assert arc.self_contained is True


def test_null_and_blank_editorial_fields_become_none() -> None:
    (arc,) = _parse_arcs(
        _payload(_arc(opening_words=None, payoff_line="   ", campaign_fit_reason=None))
    )
    assert arc.opening_words is None
    assert arc.payoff_line is None
    assert arc.campaign_fit_reason is None


def test_self_contained_false_is_kept_and_flagged() -> None:
    """We keep the arc: dropping it here would hide the signal from the scorer."""
    (arc,) = _parse_arcs(_payload(_arc(self_contained=False)))
    assert arc.self_contained is False


def test_video_read_does_not_break_parsing() -> None:
    # Root-level garbage must not take the arcs down with it.
    arcs = _parse_arcs(_payload(_arc(), video_read={"unexpected": "object"}))
    assert len(arcs) == 1


# ---------------------------------------------------------------------------
# 2. Garbage tolerance
# ---------------------------------------------------------------------------


def test_garbage_typed_fields_do_not_lose_the_arc() -> None:
    (arc,) = _parse_arcs(
        _payload(
            _arc(
                opening_words=["not", "a", "string"],
                payoff_line={"nope": 1},
                estimated_retention="not a number",
                campaign_fit="nonsense",
                self_contained="garbage",
            )
        )
    )
    assert arc.opening_words is None
    assert arc.payoff_line is None
    assert arc.estimated_retention == 0
    assert arc.campaign_fit_llm == 0
    assert arc.self_contained is True  # unparseable -> optimistic default


def test_unusable_payloads_return_empty() -> None:
    assert _parse_arcs("just a string") == []
    assert _parse_arcs(None) == []
    assert _parse_arcs({"arcs": ["not an object", 42]}) == []
    assert _parse_arcs({"arcs": [{"segments": []}]}) == []


def test_bare_list_payload_is_accepted() -> None:
    assert len(_parse_arcs([_arc()])) == 1


def test_coerce_bool_accepts_common_llm_spellings() -> None:
    assert _coerce_bool(True) is True
    assert _coerce_bool("false") is False
    assert _coerce_bool("NON") is False
    assert _coerce_bool("yes") is True
    assert _coerce_bool(0) is False
    assert _coerce_bool(None) is True          # default
    assert _coerce_bool("maybe") is True       # default
    assert _coerce_bool("maybe", default=False) is False


# ---------------------------------------------------------------------------
# 3. Duration + segment-count bounds (montage-v2)
# ---------------------------------------------------------------------------


def test_segment_shorter_than_minimum_is_dropped() -> None:
    short = MIN_SEGMENT_SECONDS - 0.5
    assert _parse_arcs(_payload(_arc(segments=[_segment(0.0, short)]))) == []


def test_segment_longer_than_maximum_is_dropped() -> None:
    long_end = MAX_SEGMENT_SECONDS + 1.0
    assert _parse_arcs(_payload(_arc(segments=[_segment(0.0, long_end)]))) == []


def test_arc_below_total_minimum_is_dropped_without_a_transcript() -> None:
    # Two valid segments that together stay under the arc floor. With no
    # transcript there is nothing to extend the arc onto, so it still goes.
    below = (MIN_ARC_SECONDS / 2) - 1.0
    segments = [_segment(0.0, below), _segment(100.0, 100.0 + below)]
    assert _parse_arcs(_payload(_arc(segments=segments))) == []


def test_arc_above_total_maximum_is_dropped() -> None:
    segments = [
        _segment(0.0, MAX_SEGMENT_SECONDS),
        _segment(100.0, 100.0 + MAX_SEGMENT_SECONDS),
        _segment(200.0, 200.0 + MAX_SEGMENT_SECONDS),
    ]
    assert 3 * MAX_SEGMENT_SECONDS > MAX_ARC_SECONDS
    assert _parse_arcs(_payload(_arc(segments=segments))) == []


def test_arc_at_the_duration_floor_is_kept() -> None:
    (arc,) = _parse_arcs(_payload(_arc(segments=[_segment(0.0, MIN_ARC_SECONDS)])))
    assert sum(s.end - s.start for s in arc.segments) == MIN_ARC_SECONDS


def test_more_than_three_segments_is_dropped() -> None:
    segments = [_segment(i * 100.0, i * 100.0 + 5.0) for i in range(4)]
    assert _parse_arcs(_payload(_arc(segments=segments))) == []


def test_segment_without_end_is_dropped_not_treated_as_zero_length() -> None:
    """Observed in the wild: the model emits `start` only. It must not silently
    become a 0s segment, and it must not take a sibling segment down with it."""
    raw = _arc(segments=[_segment(0.0, 14.0), {"role": "payoff", "start": 500.0}])
    (arc,) = _parse_arcs(_payload(raw))
    assert len(arc.segments) == 1
    assert arc.segments[0].end == 14.0


# ---------------------------------------------------------------------------
# 3b. Repair instead of reject (the 8.6s cold open that used to die here)
# ---------------------------------------------------------------------------


def _sentence_transcript(
    n_sentences: int = 8, *, sentence_seconds: float = 4.0
) -> Transcript:
    """A transcript cut into clean 4s sentences, each one 4 words long."""
    words: list[TranscriptWord] = []
    sentences: list[TranscriptSentence] = []
    step = sentence_seconds / 4.0
    for s in range(n_sentences):
        base = s * sentence_seconds
        for w in range(4):
            words.append(TranscriptWord("mot", base + w * step, base + (w + 1) * step))
        sentences.append(
            TranscriptSentence(f"Phrase {s}.", base, base + sentence_seconds)
        )
    return Transcript(text="", words=words, sentences=sentences)


def test_short_arc_is_extended_to_the_floor_instead_of_being_dropped() -> None:
    """The real case: "Moi c'est Gaspar, j'ai fait 4 millions et demi" — 8.6s,
    campaign_fit 95, thrown away by a floor it missed by 3.4s."""
    (arc,) = _parse_arcs(
        _payload(_arc(segments=[_segment(0.0, 8.6)])),
        transcript=_sentence_transcript(),
    )
    total = sum(s.end - s.start for s in arc.segments)
    assert total >= MIN_ARC_SECONDS
    # Extended to a real sentence end (12.0) + padding, not to a raw 12.0 cut.
    assert arc.segments[0].end == pytest.approx(12.0 + 0.22)


def test_repair_extends_the_last_segment_of_a_multi_segment_arc() -> None:
    (arc,) = _parse_arcs(
        _payload(_arc(segments=[_segment(0.0, 4.0), _segment(16.0, 20.0)])),
        transcript=_sentence_transcript(),
    )
    assert arc.segments[0].end == pytest.approx(4.0)          # untouched
    assert arc.segments[1].end == pytest.approx(24.0 + 0.22)  # grown to a sentence end
    assert sum(s.end - s.start for s in arc.segments) >= MIN_ARC_SECONDS


def test_repair_gives_up_when_the_transcript_runs_out() -> None:
    # One 4s sentence in the whole transcript: nothing to extend onto.
    (transcript) = _sentence_transcript(n_sentences=1)
    assert _parse_arcs(
        _payload(_arc(segments=[_segment(0.0, 4.0)])), transcript=transcript
    ) == []


def test_repair_never_breaks_the_segment_ceiling() -> None:
    # The next sentence only ends at 40s: reaching the floor would mean a
    # segment longer than MAX_SEGMENT_SECONDS, so we drop instead of forcing.
    long_sentences = _sentence_transcript(n_sentences=3, sentence_seconds=40.0)
    assert _parse_arcs(
        _payload(_arc(segments=[_segment(0.0, 4.0)])), transcript=long_sentences
    ) == []


def test_arc_already_above_the_floor_is_left_alone() -> None:
    (arc,) = _parse_arcs(
        _payload(_arc(segments=[_segment(0.0, 16.0)])),
        transcript=_sentence_transcript(),
    )
    assert arc.segments[0].end == pytest.approx(16.0)


def test_the_arc_floor_is_the_shared_clip_floor() -> None:
    """One constant, documented once in boundaries.py, used by prompt + code."""
    assert MIN_ARC_SECONDS == MIN_CLIP_SECONDS == 12.0


# ---------------------------------------------------------------------------
# 4. Multi-segment link_reason
# ---------------------------------------------------------------------------


def _multi(**over: Any) -> dict[str, Any]:
    return _arc(
        segments=[
            _segment(10.0, 20.0, role="setup"),
            _segment(560.0, 572.0, role="payoff"),
        ],
        **over,
    )


def test_multi_segment_with_link_reason_is_kept() -> None:
    (arc,) = _parse_arcs(_payload(_multi(link_reason="the promise is proven at 9:20")))
    assert len(arc.segments) == 2
    assert arc.link_reason == "the promise is proven at 9:20"


def test_multi_segment_without_link_reason_is_kept_but_flagged() -> None:
    """Kept on purpose (the scorer treats the joint as an ordinary cut) — the
    parser only logs a warning so the case stays visible in the job logs."""
    arcs = _parse_arcs(_payload(_multi(link_reason=None)))
    assert len(arcs) == 1
    assert arcs[0].link_reason is None
    assert len(arcs[0].segments) == 2


def test_single_segment_keeps_null_link_reason() -> None:
    (arc,) = _parse_arcs(_payload(_arc(link_reason=None)))
    assert arc.link_reason is None


# ---------------------------------------------------------------------------
# 5. Backward compatibility
# ---------------------------------------------------------------------------


def test_story_arc_constructs_without_the_new_fields() -> None:
    """The simple pipeline and the tests build StoryArc positionally/partially."""
    arc = StoryArc(
        title="legacy",
        arc_type="continuous",
        segments=[],
        viral_reason="",
        estimated_retention=50,
        continuity_risk="low",
    )
    assert arc.opening_words is None
    assert arc.payoff_line is None
    assert arc.self_contained is True


def test_legacy_payload_without_new_fields_still_parses() -> None:
    legacy = {
        "title": "old shape",
        "arc_type": "setup_payoff",
        "segments": [_segment(0.0, 20.0)],
        "viral_reason": "still fine",
        "estimated_retention": 70,
        "continuity_risk": "medium",
    }
    (arc,) = _parse_arcs(_payload(legacy))
    assert arc.title == "old shape"
    assert arc.campaign_fit_llm is None
    assert arc.self_contained is True
