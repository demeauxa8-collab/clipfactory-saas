from app.pipeline.analyze import (
    MAX_SIMPLE_SEGMENT_SECONDS,
    MIN_SIMPLE_SEGMENT_SECONDS,
    _parse_segments_as_arcs,
)


def _segment(duration: float) -> dict[str, object]:
    return {
        "title": "Clip",
        "start": 10.0,
        "end": 10.0 + duration,
        "transcript_excerpt": "début puis une conclusion autonome",
        "start_anchor": "début puis une conclusion",
        "end_anchor": "puis une conclusion autonome",
        "hook_score_text": 80,
        "emotion_score": 70,
    }


def test_simple_parser_uses_the_prompt_20_to_60_second_contract() -> None:
    payload = {
        "segments": [
            _segment(19.9),
            _segment(20.0),
            _segment(35.0),
            _segment(60.0),
            _segment(60.1),
        ]
    }
    arcs = _parse_segments_as_arcs(payload)
    assert [arc.segments[0].end - arc.segments[0].start for arc in arcs] == [
        20.0,
        35.0,
        60.0,
    ]
    assert MIN_SIMPLE_SEGMENT_SECONDS == 20.0
    assert MAX_SIMPLE_SEGMENT_SECONDS == 60.0


def test_simple_end_anchor_is_not_misrepresented_as_semantic_payoff() -> None:
    (arc,) = _parse_segments_as_arcs({"segments": [_segment(30.0)]})
    assert arc.segments[0].end_anchor == "puis une conclusion autonome"
    assert arc.payoff_line is None
