"""YouTube's "most replayed" curve: parsing, modelling, and its weight on the score.

The contract under test is the one that lets us ship this at all: the curve is a
BONUS. It is missing more often than not, and when it is missing nothing may
change — not the score, not the ranking, not the job.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.models import (
    ArcSegmentSpec,
    AudienceHeatmap,
    SegmentVision,
    StoryArc,
    VisionResult,
)
from app.pipeline.ffmpeg import HEATMAP_CACHE_FILENAME, fetch_audience_heatmap
from app.pipeline.score import (
    _PRE_AUDIENCE_ARC_WEIGHTS,
    ARC_WEIGHTS,
    AUDIENCE_WEIGHT,
    _audience_score,
    rank_and_pick,
    score_arc,
)

CAMPAIGN = {
    "name": "gaspard grojean",
    "audience": "jeun en quete de formation buinesse",
    "niche": "buinesse et train de vie luxueux",
    "goal": "créez des clips pour inciter a acheter sa formation buinesse",
    "avoid_topics": [],
}


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _seg(start: float, end: float, *, text: str = "on a fait 4000 euros") -> ArcSegmentSpec:
    return ArcSegmentSpec(role="single", start=start, end=end, transcript_excerpt=text)


def _arc(segments: list[ArcSegmentSpec], *, title: str = "clip") -> StoryArc:
    return StoryArc(
        title=title,
        arc_type="continuous",
        segments=segments,
        viral_reason="",
        estimated_retention=70,
        continuity_risk="low",
        campaign_fit_llm=80,
    )


def _vision(idx: int) -> SegmentVision:
    return SegmentVision(
        segment_idx=idx,
        frames_used=5,
        vision=VisionResult(
            decor="studio",
            person_visible=True,
            energy=75,
            action="talking head",
            proof_objects=[],
            problems=[],
            visual_score=75,
        ),
    )


def _raw_points(values: list[float], *, bucket: float = 6.0) -> list[dict[str, float]]:
    """yt-dlp-shaped payload: contiguous buckets carrying `values`."""
    return [
        {"start_time": i * bucket, "end_time": (i + 1) * bucket, "value": v}
        for i, v in enumerate(values)
    ]


def _two_peak_curve(
    *, buckets: int = 100, span: float = 595.0
) -> tuple[AudienceHeatmap, float, float]:
    """A realistic 100-bucket curve over a 595 s video: a hot opening, a strong
    peak around 40%, a smaller one around 80%, a flat trough in between.

    Returns (heatmap, peak_center_seconds, trough_center_seconds).
    """
    width = span / buckets
    values: list[float] = []
    for i in range(buckets):
        pos = i / buckets
        v = 0.10
        if pos < 0.03:  # everybody restarts the intro
            v = 0.85
        if 0.38 <= pos <= 0.44:
            v = 1.00
        elif 0.78 <= pos <= 0.82:
            v = 0.60
        elif 0.55 <= pos <= 0.70:
            v = 0.05
        values.append(v)
    heatmap = AudienceHeatmap.from_points(_raw_points(values, bucket=width))
    assert heatmap is not None
    return heatmap, 0.41 * span, 0.62 * span


# ---------------------------------------------------------------------------
# 1. Model
# ---------------------------------------------------------------------------


def test_from_points_parses_yt_dlp_payload() -> None:
    heatmap = AudienceHeatmap.from_points(_raw_points([0.2, 0.9, 0.5]))
    assert heatmap is not None
    assert [p.value for p in heatmap.points] == [0.2, 0.9, 0.5]
    assert heatmap.points[0].start == 0.0 and heatmap.points[0].end == 6.0


def test_from_points_returns_none_when_there_is_no_curve() -> None:
    # Every shape yt-dlp can hand us for "this video has no heatmap".
    assert AudienceHeatmap.from_points(None) is None
    assert AudienceHeatmap.from_points([]) is None
    assert AudienceHeatmap.from_points("NA") is None
    assert AudienceHeatmap.from_points({"points": []}) is None


def test_from_points_skips_junk_instead_of_raising() -> None:
    heatmap = AudienceHeatmap.from_points(
        [
            {"start_time": 0.0, "end_time": 6.0, "value": 0.4},
            {"start_time": 6.0, "end_time": 6.0, "value": 0.9},   # empty bucket
            {"start_time": "x", "end_time": 18.0, "value": 0.9},  # unparseable
            {"start_time": 18.0, "value": 0.9},                   # missing field
            {"start_time": 24.0, "end_time": 30.0, "value": -1.0},  # impossible
            "not a dict",
            {"start_time": 30.0, "end_time": 36.0, "value": 0.7},
        ]
    )
    assert heatmap is not None
    assert [p.value for p in heatmap.points] == [0.4, 0.7]


def test_from_points_sorts_by_start() -> None:
    heatmap = AudienceHeatmap.from_points(
        [
            {"start_time": 12.0, "end_time": 18.0, "value": 0.3},
            {"start_time": 0.0, "end_time": 6.0, "value": 0.9},
        ]
    )
    assert heatmap is not None
    assert [p.start for p in heatmap.points] == [0.0, 12.0]


def test_intensity_between_is_overlap_weighted() -> None:
    heatmap = AudienceHeatmap.from_points(_raw_points([0.0, 1.0]))
    assert heatmap is not None
    # Whole curve: equal buckets -> plain mean.
    assert heatmap.intensity_between(0.0, 12.0) == pytest.approx(0.5)
    # 2 s of the first bucket against 6 s of the second: the long one dominates.
    assert heatmap.intensity_between(4.0, 12.0) == pytest.approx(0.75)
    # Inside one bucket only.
    assert heatmap.intensity_between(7.0, 9.0) == pytest.approx(1.0)


def test_intensity_between_outside_the_curve_is_none() -> None:
    heatmap = AudienceHeatmap.from_points(_raw_points([0.5, 0.5]))
    assert heatmap is not None
    assert heatmap.intensity_between(600.0, 620.0) is None


def test_intensity_between_handles_a_zero_length_window() -> None:
    heatmap = AudienceHeatmap.from_points(_raw_points([0.2, 0.8]))
    assert heatmap is not None
    assert heatmap.intensity_between(9.0, 9.0) == pytest.approx(0.8)


def test_percentile_is_relative_to_this_video_only() -> None:
    """A globally cold video and a globally hot one rank their own moments the
    same way — which is the whole point of `value` being per-video."""
    cold = AudienceHeatmap.from_points(_raw_points([0.01, 0.02, 0.03, 0.04]))
    hot = AudienceHeatmap.from_points(_raw_points([0.61, 0.62, 0.63, 0.64]))
    assert cold is not None and hot is not None
    assert cold.percentile_of(0.04) == hot.percentile_of(0.64) == 87.5
    assert cold.percentile_of(0.01) == hot.percentile_of(0.61) == 12.5


def test_percentile_survives_a_floating_point_tie() -> None:
    """Regression, caught on the fixture: a window lying on a flat stretch of the
    curve averages back to the buckets' own value, but through a weighted sum —
    so it lands a whisker below it. Compared strictly, every tied bucket counts
    as "above" and the moment reads 15 instead of 48. Same footage, 33 points.
    """
    width = 595 / 100
    flat = AudienceHeatmap.from_points(
        [
            {
                "start_time": i * width,
                "end_time": i * width + width,
                "value": 0.05 if i < 15 else 0.14,
            }
            for i in range(100)
        ]
    )
    assert flat is not None
    mean = flat.intensity_between(561.6, 585.9)
    assert mean == 0.13999999999999999 != 0.14  # the dust that started this
    assert flat.percentile_of(mean) == flat.percentile_of(0.14) == pytest.approx(57.5)
    assert _audience_score(_arc([_seg(561.6, 585.9)]), flat) == 58


def test_peaks_returns_the_hottest_buckets_first() -> None:
    heatmap = AudienceHeatmap.from_points(_raw_points([0.1, 0.9, 0.4, 0.6]))
    assert heatmap is not None
    assert [p.value for p in heatmap.peaks(2)] == [0.9, 0.6]


# ---------------------------------------------------------------------------
# 2. The audience criterion
# ---------------------------------------------------------------------------


def test_audience_score_is_none_without_a_curve() -> None:
    assert _audience_score(_arc([_seg(10, 30)]), None) is None
    assert _audience_score(_arc([_seg(10, 30)]), AudienceHeatmap(points=[])) is None


def test_audience_score_is_none_when_the_arc_misses_the_curve() -> None:
    heatmap = AudienceHeatmap.from_points(_raw_points([0.5] * 4))
    assert _audience_score(_arc([_seg(500, 520)]), heatmap) is None


def test_audience_score_ranks_a_peak_above_a_trough() -> None:
    heatmap, peak, trough = _two_peak_curve()
    on_peak = _audience_score(_arc([_seg(peak - 8, peak + 8)]), heatmap)
    in_trough = _audience_score(_arc([_seg(trough - 8, trough + 8)]), heatmap)
    assert on_peak is not None and in_trough is not None
    assert on_peak > 90
    assert in_trough < 20


def test_audience_score_weights_segments_by_duration() -> None:
    """A 3 s stub on a peak must not carry a 24 s segment sitting in a trough.

    On a ramp curve (each bucket hotter than the last) percentiles are dense
    enough to read the weighting off the score directly.
    """
    ramp = AudienceHeatmap.from_points(
        _raw_points([i / 100 for i in range(100)], bucket=5.95)
    )
    assert ramp is not None
    cold, hot = 0.0, 500.0
    balanced = _audience_score(_arc([_seg(cold, cold + 24), _seg(hot, hot + 24)]), ramp)
    hot_stub = _audience_score(_arc([_seg(cold, cold + 24), _seg(hot, hot + 3)]), ramp)
    assert balanced is not None and hot_stub is not None
    assert balanced > hot_stub + 20


# ---------------------------------------------------------------------------
# 3. Weights — the no-regression contract
# ---------------------------------------------------------------------------


def test_weights_are_the_previous_ones_shaved_pro_rata() -> None:
    """Drop the audience term and renormalise: we must land back exactly on the
    weights that shipped before it existed."""
    assert sum(ARC_WEIGHTS.values()) == pytest.approx(1.0)
    assert ARC_WEIGHTS["audience"] == AUDIENCE_WEIGHT
    without = {k: v for k, v in ARC_WEIGHTS.items() if k != "audience"}
    total = sum(without.values())
    for key, weight in without.items():
        assert weight / total == pytest.approx(_PRE_AUDIENCE_ARC_WEIGHTS[key])


def test_score_is_byte_for_byte_unchanged_without_a_curve() -> None:
    """The legacy formula, recomputed by hand, against what score_arc returns."""
    arc = _arc([_seg(10, 34, text="on a fait 4000 euros de benefice")])
    vision = [_vision(0)]
    candidate = score_arc(arc=arc, per_segment_vision=vision, campaign=CAMPAIGN)

    assert "audience" not in candidate.score_breakdown
    legacy = round(
        sum(
            _PRE_AUDIENCE_ARC_WEIGHTS[k] * v for k, v in candidate.score_breakdown.items()
        )
    )
    assert candidate.score_total == legacy


def test_a_curve_that_misses_the_arc_scores_like_no_curve_at_all() -> None:
    arc = _arc([_seg(500, 524)])
    heatmap = AudienceHeatmap.from_points(_raw_points([0.9] * 4))  # covers 0..24 s
    without = score_arc(arc=arc, per_segment_vision=[_vision(0)], campaign=CAMPAIGN)
    with_curve = score_arc(
        arc=arc,
        per_segment_vision=[_vision(0)],
        campaign=CAMPAIGN,
        audience_heatmap=heatmap,
    )
    assert with_curve.score_total == without.score_total


def test_audience_moves_the_score_but_does_not_own_it() -> None:
    heatmap, peak, trough = _two_peak_curve()
    peak_arc = _arc([_seg(peak - 12, peak + 12)], title="peak")
    trough_arc = _arc([_seg(trough - 12, trough + 12)], title="trough")

    base_peak = score_arc(arc=peak_arc, per_segment_vision=[_vision(0)], campaign=CAMPAIGN)
    base_trough = score_arc(
        arc=trough_arc, per_segment_vision=[_vision(0)], campaign=CAMPAIGN
    )
    # Same everything except the window: the legacy score cannot tell them apart.
    assert base_peak.score_total == base_trough.score_total

    scored_peak = score_arc(
        arc=peak_arc,
        per_segment_vision=[_vision(0)],
        campaign=CAMPAIGN,
        audience_heatmap=heatmap,
    )
    scored_trough = score_arc(
        arc=trough_arc,
        per_segment_vision=[_vision(0)],
        campaign=CAMPAIGN,
        audience_heatmap=heatmap,
    )
    assert scored_peak.score_total > base_peak.score_total
    assert scored_trough.score_total < base_trough.score_total
    # Loud enough to reorder comparable clips, quiet enough not to be the score.
    gap = scored_peak.score_total - scored_trough.score_total
    assert 6 <= gap <= 14


def test_a_peak_arc_overtakes_a_slightly_better_looking_trough_arc() -> None:
    """End to end through rank_and_pick: real audience data arbitrates a tie the
    craft signals cannot break."""
    heatmap, peak, trough = _two_peak_curve()
    contenders = [
        _arc([_seg(trough - 12, trough + 12, text="le produit coute 14 euros")], title="trough"),
        _arc([_seg(peak - 12, peak + 12, text="le produit coute 14 euros")], title="peak"),
    ]
    blind = rank_and_pick(
        [score_arc(arc=a, per_segment_vision=[_vision(0)], campaign=CAMPAIGN) for a in contenders],
        2,
    )
    informed = rank_and_pick(
        [
            score_arc(
                arc=a,
                per_segment_vision=[_vision(0)],
                campaign=CAMPAIGN,
                audience_heatmap=heatmap,
            )
            for a in contenders
        ],
        2,
    )
    assert [c.title for c in blind] == ["trough", "peak"]     # tie, input order
    assert [c.title for c in informed] == ["peak", "trough"]  # audience arbitrates


# ---------------------------------------------------------------------------
# 4. Fetching — a bonus that cannot break a job
# ---------------------------------------------------------------------------


def test_fetch_reads_the_workdir_cache_without_touching_the_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The source cache lets a re-run skip the download; the curve has to survive
    that path, otherwise it is lost on every retry."""
    points = _raw_points([0.3, 0.7])
    (tmp_path / HEATMAP_CACHE_FILENAME).write_text(json.dumps({"points": points}))

    def _explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("cache hit must not spawn yt-dlp")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _explode)
    got = asyncio.run(fetch_audience_heatmap("https://youtu.be/x", str(tmp_path)))
    assert got == points


def test_fetch_caches_the_absence_of_a_curve_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / HEATMAP_CACHE_FILENAME).write_text(json.dumps({"points": None}))

    def _explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a cached miss must not spawn yt-dlp either")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _explode)
    assert asyncio.run(fetch_audience_heatmap("https://youtu.be/x", str(tmp_path))) is None


def test_fetch_never_raises_when_yt_dlp_blows_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("yt-dlp: no such file")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _boom)
    assert asyncio.run(fetch_audience_heatmap("https://youtu.be/x", str(tmp_path))) is None
    # Nothing written: a transient failure must not poison the cache.
    assert not (tmp_path / HEATMAP_CACHE_FILENAME).exists()


class _FakeProc:
    def __init__(self, stdout: bytes, returncode: int = 0) -> None:
        self._stdout = stdout
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, b""

    def kill(self) -> None:  # pragma: no cover - not reached in these tests
        pass

    async def wait(self) -> int:  # pragma: no cover - not reached in these tests
        return self.returncode


def _fake_yt_dlp(stdout: bytes, returncode: int = 0):
    async def _spawn(*_args: object, **_kwargs: object) -> _FakeProc:
        return _FakeProc(stdout, returncode)

    return _spawn


def test_fetch_parses_yt_dlp_output_and_writes_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    points = _raw_points([0.1, 0.9])
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", _fake_yt_dlp(json.dumps(points).encode())
    )
    got = asyncio.run(fetch_audience_heatmap("https://youtu.be/x", str(tmp_path)))
    assert got == points
    cached = json.loads((tmp_path / HEATMAP_CACHE_FILENAME).read_text())
    assert cached == {"points": points}


def test_fetch_reads_na_as_no_curve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """What yt-dlp actually prints for a video YouTube has no heatmap for — the
    real behaviour of the benchmark source itself."""
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_yt_dlp(b"NA\n"))
    assert asyncio.run(fetch_audience_heatmap("https://youtu.be/x", str(tmp_path))) is None
    assert json.loads((tmp_path / HEATMAP_CACHE_FILENAME).read_text()) == {"points": None}


def test_fetch_survives_a_nonzero_exit_and_garbage_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_yt_dlp(b"", returncode=1))
    assert asyncio.run(fetch_audience_heatmap("https://youtu.be/x", str(tmp_path))) is None

    other = tmp_path / "garbage"
    other.mkdir()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_yt_dlp(b"<html>429</html>"))
    assert asyncio.run(fetch_audience_heatmap("https://youtu.be/x", str(other))) is None


def test_fetch_ignores_a_corrupt_cache_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / HEATMAP_CACHE_FILENAME).write_text("{ truncated")
    points = _raw_points([0.4, 0.6])
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", _fake_yt_dlp(json.dumps(points).encode())
    )
    assert asyncio.run(fetch_audience_heatmap("https://youtu.be/x", str(tmp_path))) == points
