import asyncio
import shutil

import pytest

from app.pipeline.audio_map import (
    AudioMap,
    AudioMapError,
    ProtectedWordSpan,
    SilenceInterval,
    TimedWord,
    build_audio_map,
    classify_silences,
    parse_astats,
    parse_ebur128,
    parse_silencedetect,
    propose_micro_cuts,
)
from app.pipeline.ffmpeg import analyze_audio_map


def _words() -> list[TimedWord]:
    return [
        TimedWord("w_001", 0.00, 0.40),
        TimedWord("w_002", 1.80, 2.20),
        TimedWord("w_003", 3.10, 3.45),
        TimedWord("w_004", 4.80, 5.20),
    ]


def test_parse_silencedetect_pairs_lines_ignores_dangling_and_clamps_duration() -> None:
    output = """
    [silencedetect @ 0x1] silence_start: -0.02
    [silencedetect @ 0x1] silence_end: 0.600 | silence_duration: 0.620
    [silencedetect @ 0x1] silence_start: 1.100
    [silencedetect @ 0x1] silence_end: 2.800 | silence_duration: 1.700
    [silencedetect @ 0x1] silence_start: 9.000
    """

    assert parse_silencedetect(output, duration_seconds=2.0) == (
        SilenceInterval(0.0, 0.6),
        SilenceInterval(1.1, 2.0),
    )


def test_parse_silencedetect_merges_overlapping_threshold_fragments() -> None:
    output = """
    silence_start: 1.0
    silence_end: 1.8 | silence_duration: 0.8
    silence_start: 1.7
    silence_end: 2.3 | silence_duration: 0.6
    """

    assert parse_silencedetect(output) == (SilenceInterval(1.0, 2.3),)


def test_parse_ebur128_reads_samples_summary_and_infinity() -> None:
    output = """
    [Parsed_ebur128_0] t: 0.100 M: -inf S: -inf I: -70.0 LUFS LRA: 0.0 LU
    [Parsed_ebur128_0] t: 3.100 M: -18.3 S: -20.1 I: -21.0 LUFS LRA: 2.0 LU
    Integrated loudness:
      I: -20.4 LUFS
    """

    points, integrated = parse_ebur128(output)

    assert len(points) == 2
    assert points[0].momentary_lufs is None
    assert points[1].short_term_lufs == -20.1
    assert integrated == -20.4


def test_parse_astats_reads_final_rms_and_peak_values() -> None:
    output = """
    [Parsed_astats] RMS level dB: -24.0
    [Parsed_astats] Peak level dB: -3.0
    [Parsed_astats] Overall RMS level dB: -18.4
    [Parsed_astats] Overall Peak level dB: -1.2
    """

    assert parse_astats(output) == (-18.4, -1.2)


def test_build_audio_map_combines_ffmpeg_evidence() -> None:
    audio_map = build_audio_map(
        silencedetect_output="silence_start: 1.0\nsilence_end: 2.0",
        duration_seconds=3.0,
        ebur128_output="t: 2.0 M: -18.0 S: -20.0 I: -19.0 LUFS",
        astats_output="RMS level dB: -21.0\nPeak level dB: -1.1",
    )

    assert audio_map.silences == (SilenceInterval(1.0, 2.0),)
    assert audio_map.integrated_lufs == -19.0
    assert audio_map.rms_db == -21.0
    assert audio_map.peak_db == -1.1


def test_classify_keeps_short_and_edge_pauses_but_marks_bounded_dead_air() -> None:
    audio_map = AudioMap(
        duration_seconds=6.0,
        silences=(
            SilenceInterval(0.0, 0.8),
            SilenceInterval(0.45, 0.75),
            SilenceInterval(2.25, 3.0),
            SilenceInterval(5.25, 6.0),
        ),
    )

    classified = classify_silences(audio_map, _words(), minimum_dead_air_seconds=0.55)

    assert [item.kind for item in classified] == [
        "kept_pause",
        "too_short",
        "dead_air",
        "kept_pause",
    ]
    assert classified[2].left_word_id == "w_002"
    assert classified[2].right_word_id == "w_003"


def test_classify_preserves_explicit_word_span_pause() -> None:
    audio_map = AudioMap(
        duration_seconds=4.0,
        silences=(SilenceInterval(2.25, 3.0),),
    )

    classified = classify_silences(
        audio_map,
        _words(),
        protected_spans=[ProtectedWordSpan("w_002", "w_003", reason="pre_payoff")],
    )

    assert classified[0].kind == "protected_pause"
    assert classified[0].reason == "intersects_protected_word_span"


def test_propose_micro_cuts_preserves_natural_edges_and_word_ids() -> None:
    audio_map = AudioMap(
        duration_seconds=4.0,
        silences=(SilenceInterval(2.25, 3.0),),
    )

    cuts = propose_micro_cuts(
        audio_map,
        _words(),
        preserve_left_seconds=0.10,
        preserve_right_seconds=0.14,
        max_cut_seconds=0.75,
    )

    assert len(cuts) == 1
    assert cuts[0].start == pytest.approx(2.35)
    assert cuts[0].end == pytest.approx(2.86)
    assert cuts[0].left_word_id == "w_002"
    assert cuts[0].right_word_id == "w_003"
    assert cuts[0].source_silence == SilenceInterval(2.25, 3.0)


def test_propose_micro_cuts_caps_duration_and_never_cuts_protected_pause() -> None:
    audio_map = AudioMap(
        duration_seconds=5.0,
        silences=(SilenceInterval(2.25, 3.0), SilenceInterval(3.50, 4.70)),
    )

    cuts = propose_micro_cuts(
        audio_map,
        _words(),
        protected_spans=[ProtectedWordSpan("w_002", "w_003")],
        max_cut_seconds=0.20,
    )

    assert len(cuts) == 1
    assert cuts[0].left_word_id == "w_003"
    assert cuts[0].right_word_id == "w_004"
    assert cuts[0].duration_seconds == pytest.approx(0.20)


@pytest.mark.parametrize(
    "words, message",
    [
        ([], "at least one"),
        ([TimedWord("w", 1.0, 0.5)], "ordered"),
        ([TimedWord("w", 0.0, 0.1), TimedWord("w", 0.2, 0.3)], "unique"),
        ([TimedWord("a", 0.0, 1.0), TimedWord("b", 0.5, 1.2)], "ordered"),
    ],
)
def test_classification_rejects_invalid_word_clock(words: list[TimedWord], message: str) -> None:
    with pytest.raises(AudioMapError, match=message):
        classify_silences(AudioMap(None, (SilenceInterval(0.2, 0.9),)), words)


def test_protected_span_unknown_or_reversed_id_is_rejected() -> None:
    audio_map = AudioMap(4.0, (SilenceInterval(2.25, 3.0),))

    with pytest.raises(AudioMapError, match="unknown"):
        classify_silences(
            audio_map,
            _words(),
            protected_spans=[ProtectedWordSpan("missing", "w_003")],
        )
    with pytest.raises(AudioMapError, match="must not follow"):
        classify_silences(
            audio_map,
            _words(),
            protected_spans=[ProtectedWordSpan("w_003", "w_002")],
        )


def test_micro_cut_configuration_is_validated() -> None:
    audio_map = AudioMap(4.0, (SilenceInterval(2.25, 3.0),))

    with pytest.raises(AudioMapError, match="bounds"):
        propose_micro_cuts(audio_map, _words(), preserve_left_seconds=-0.1)
    assert propose_micro_cuts(audio_map, _words(), max_cuts=0) == ()


async def _analyze_synthetic_pause(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    assert ffmpeg is not None and ffprobe is not None
    source = tmp_path / "pause.wav"
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=0.5",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=48000:cl=stereo:d=0.6",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=660:sample_rate=48000:duration=0.5",
        "-filter_complex",
        "[0:a][1:a][2:a]concat=n=3:v=0:a=1[a]",
        "-map",
        "[a]",
        str(source),
    )
    _, stderr = await proc.communicate()
    assert proc.returncode == 0, stderr.decode("utf-8", "replace")
    return await analyze_audio_map(
        str(source),
        silence_noise_db=-45.0,
        min_silence_seconds=0.25,
        ffmpeg_bin=ffmpeg,
        ffprobe_bin=ffprobe,
    )


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)
def test_real_audio_map_uses_one_ffmpeg_analysis_pass(tmp_path) -> None:
    audio_map = asyncio.run(_analyze_synthetic_pause(tmp_path))

    assert any(
        silence.start == pytest.approx(0.5, abs=0.03)
        and silence.end == pytest.approx(1.1, abs=0.03)
        for silence in audio_map.silences
    )
    assert audio_map.integrated_lufs is not None
    assert audio_map.rms_db is not None
    assert audio_map.peak_db is not None
