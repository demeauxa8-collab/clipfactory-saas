from app.models import ArcSegmentSpec, StoryArc, TranscriptWord
from app.pipeline.boundaries import snap_arc_segments, snap_segment


def test_snap_segment_expands_to_nearby_silence_boundaries() -> None:
    words = [
        TranscriptWord("Avant", 8.0, 8.2),
        TranscriptWord("pause.", 8.25, 8.5),
        TranscriptWord("Bonjour", 9.4, 9.8),
        TranscriptWord("tout", 10.85, 11.0),
        TranscriptWord("le", 12.05, 12.12),
        TranscriptWord("monde.", 13.16, 13.6),
        TranscriptWord("Suite", 14.5, 14.8),
    ]

    start, end = snap_segment(words, 9.7, 13.2)

    assert start == 9.4
    assert end == 13.6


def test_snap_arc_segments_preserves_segment_why() -> None:
    words = [
        TranscriptWord("Setup", 1.0, 1.2),
        TranscriptWord("clair.", 1.25, 1.6),
        TranscriptWord("Payoff", 5.0, 5.4),
        TranscriptWord("net.", 5.45, 5.8),
    ]
    arc = StoryArc(
        title="Arc",
        arc_type="setup_payoff",
        segments=[
            ArcSegmentSpec(
                role="setup",
                start=1.1,
                end=5.4,
                transcript_excerpt="Setup clair",
                why="pose le contexte",
            )
        ],
        viral_reason="contraste",
        estimated_retention=80,
        continuity_risk="low",
    )

    snapped, report = snap_arc_segments([arc], words)

    assert report.segments_changed == 1
    assert snapped[0].segments[0].why == "pose le contexte"
    assert snapped[0].segments[0].start == 1.0
    assert snapped[0].segments[0].end == 5.8
