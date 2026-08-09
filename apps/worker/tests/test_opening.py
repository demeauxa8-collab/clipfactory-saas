from pathlib import Path

from PIL import Image, ImageFilter

from app.models import MontageSegment, Transcript, TranscriptWord
from app.pipeline.captions import FACE_CROP_MARGIN_V, FIT_BLUR_MARGIN_V, write_ass_for_montage
from app.pipeline.edl import EditIntentPlan, EditShotIntent, FramingIntent, compile_edit_intent
from app.pipeline.edl_captions import (
    _MARGIN_V_BY_POSITION,
    THEME_STYLES,
    CaptionPlan,
    build_caption_plan,
    render_ass,
    write_ass_for_edl,
)
from app.pipeline.opening import (
    DEFAULT_HOOK_SECONDS,
    HOOK_LINE_HEIGHT_RATIO,
    HOOK_MAX_BOTTOM_Y,
    HOOK_MAX_LINES,
    HOOK_STYLE_NAME,
    SEARCH_RADIUS_SECONDS,
    FrameCandidate,
    choose_opening_frame,
    hook_dialogue_line,
    hook_layout,
    score_frame,
)

APOS = "’"  # noqa: RUF001 (typographic apostrophe is intentional data)

# ---------------------------------------------------------------------------
# Synthetic frames (deterministic, no source video needed)
# ---------------------------------------------------------------------------

WIDTH, HEIGHT = 512, 288


def _detailed(mean_level: int = 128, amplitude: int = 60) -> Image.Image:
    """A busy, isotropic pattern: plenty of edges on both axes."""
    image = Image.new("L", (WIDTH, HEIGHT))
    pixels = image.load()
    assert pixels is not None
    for y in range(HEIGHT):
        for x in range(WIDTH):
            checker = amplitude if ((x // 3) + (y // 3)) % 2 else -amplitude
            pixels[x, y] = max(0, min(255, mean_level + checker))
    return image


def _write(image: Image.Image, path: Path) -> str:
    image.save(path, format="PNG")
    return str(path)


def _sharp(tmp_path: Path, name: str = "sharp.png") -> str:
    return _write(_detailed(), tmp_path / name)


def _blurred(tmp_path: Path, name: str = "blurred.png") -> str:
    return _write(_detailed().filter(ImageFilter.GaussianBlur(3)), tmp_path / name)


def _motion_blurred(tmp_path: Path, name: str = "motion.png") -> str:
    """Horizontal-only smear: detail survives vertically, dies horizontally."""
    horizontal = ImageFilter.Kernel(
        (5, 5), [0] * 10 + [0.2] * 5 + [0] * 10, scale=1.0, offset=0
    )
    smeared = _detailed()
    for _ in range(3):
        smeared = smeared.filter(horizontal)
    return _write(smeared, tmp_path / name)


# ---------------------------------------------------------------------------
# A. frame measurement
# ---------------------------------------------------------------------------

def test_sharp_frame_scores_above_blurred_frame(tmp_path) -> None:
    sharp = score_frame(_sharp(tmp_path))
    blurred = score_frame(_blurred(tmp_path))
    assert sharp is not None and blurred is not None
    assert sharp.sharpness > blurred.sharpness
    assert sharp.sharpness_score > blurred.sharpness_score
    assert sharp.score > blurred.score


def test_underexposed_and_blown_frames_lose_the_exposure_term(tmp_path) -> None:
    good = score_frame(_write(_detailed(mean_level=130), tmp_path / "good.png"))
    dark = score_frame(_write(_detailed(mean_level=6, amplitude=5), tmp_path / "dark.png"))
    blown = score_frame(_write(_detailed(mean_level=252, amplitude=3), tmp_path / "blown.png"))
    assert good is not None and dark is not None and blown is not None
    assert good.exposure_score == 1.0
    assert dark.exposure_score == 0.0
    assert blown.exposure_score == 0.0
    assert dark.clipped_fraction >= 0.4
    assert blown.clipped_fraction >= 0.4


def test_motion_blur_is_detected_as_directional_smear(tmp_path) -> None:
    clean = score_frame(_sharp(tmp_path))
    defocus = score_frame(_blurred(tmp_path))
    smeared = score_frame(_motion_blurred(tmp_path))
    assert clean is not None and defocus is not None and smeared is not None
    # An isotropic pattern has near-equal gradient energy on both axes, and so
    # does the same pattern out of focus: defocus is the sharpness term's job.
    assert clean.motion_blur < 0.2
    assert defocus.motion_blur < 0.2
    # A one-axis smear collapses one of the two energies.
    assert smeared.motion_blur > 0.35
    assert smeared.motion_blur > 3 * clean.motion_blur


def test_unreadable_file_is_skipped_not_fatal(tmp_path) -> None:
    broken = tmp_path / "broken.jpg"
    broken.write_text("not an image", encoding="utf-8")
    assert score_frame(str(broken)) is None
    assert score_frame(str(tmp_path / "missing.jpg")) is None


# ---------------------------------------------------------------------------
# A. candidate selection
# ---------------------------------------------------------------------------

def test_chooses_the_sharp_candidate_over_the_blurred_original(tmp_path) -> None:
    choice = choose_opening_frame(
        [
            FrameCandidate(offset_seconds=0.0, path=_blurred(tmp_path)),
            FrameCandidate(offset_seconds=0.2, path=_sharp(tmp_path)),
        ]
    )
    assert choice is not None
    assert choice.offset_seconds == 0.2
    assert choice.baseline_score is not None
    assert choice.gain is not None and choice.gain > 0
    assert choice.is_worth_shifting is True


def test_keeps_the_original_when_nothing_is_better(tmp_path) -> None:
    choice = choose_opening_frame(
        [
            FrameCandidate(offset_seconds=0.0, path=_sharp(tmp_path)),
            FrameCandidate(offset_seconds=0.2, path=_blurred(tmp_path)),
        ]
    )
    assert choice is not None
    assert choice.offset_seconds == 0.0
    assert choice.gain == 0.0
    assert choice.is_worth_shifting is False


def test_equal_frames_never_drift_from_the_cut(tmp_path) -> None:
    same = _sharp(tmp_path)
    choice = choose_opening_frame(
        [
            FrameCandidate(offset_seconds=-0.3, path=same),
            FrameCandidate(offset_seconds=0.0, path=same),
            FrameCandidate(offset_seconds=0.3, path=same),
        ]
    )
    assert choice is not None
    assert choice.offset_seconds == 0.0
    assert choice.is_worth_shifting is False


def test_search_window_is_capped_at_the_module_radius(tmp_path) -> None:
    choice = choose_opening_frame(
        [
            FrameCandidate(offset_seconds=0.0, path=_blurred(tmp_path)),
            # Far outside the window: even a perfect frame is not eligible.
            FrameCandidate(offset_seconds=1.5, path=_sharp(tmp_path)),
        ],
        search_radius_seconds=5.0,
    )
    assert choice is not None
    assert choice.offset_seconds == 0.0
    assert all(
        abs(item.candidate.offset_seconds) <= SEARCH_RADIUS_SECONDS
        for item in choice.considered
    )


def test_never_shifts_past_the_first_word(tmp_path) -> None:
    """A gorgeous frame that would swallow the first word is rejected."""
    choice = choose_opening_frame(
        [
            FrameCandidate(offset_seconds=0.0, path=_blurred(tmp_path)),
            FrameCandidate(offset_seconds=-0.2, path=_blurred(tmp_path, "b2.png")),
            FrameCandidate(offset_seconds=0.35, path=_sharp(tmp_path)),
        ],
        first_word_offset_seconds=0.40,
        lead_in_seconds=0.12,
    )
    assert choice is not None
    # 0.40 - 0.12 = 0.28 is the latest usable start, so 0.35 is out.
    assert choice.offset_seconds <= 0.28
    assert 0.35 not in [item.candidate.offset_seconds for item in choice.considered]


def test_lead_in_keeps_a_breath_before_the_first_word(tmp_path) -> None:
    sharp = _sharp(tmp_path)
    kept = choose_opening_frame(
        [FrameCandidate(offset_seconds=0.2, path=sharp)],
        first_word_offset_seconds=0.4,
        lead_in_seconds=0.12,
    )
    assert kept is not None and kept.offset_seconds == 0.2
    # Same candidate, but now the word starts right on it.
    dropped = choose_opening_frame(
        [FrameCandidate(offset_seconds=0.2, path=sharp)],
        first_word_offset_seconds=0.25,
        lead_in_seconds=0.12,
    )
    assert dropped is None


def test_external_quality_is_the_deep_vision_extension_point(tmp_path) -> None:
    """Eyes-open/mouth-closed cannot be measured here; vision can inject it."""
    blurred = _blurred(tmp_path)
    sharp = _sharp(tmp_path)
    without = choose_opening_frame(
        [
            FrameCandidate(offset_seconds=0.0, path=blurred),
            FrameCandidate(offset_seconds=0.2, path=sharp),
        ]
    )
    assert without is not None and without.offset_seconds == 0.2
    # The sharp frame is a mid-blink: vision scores it 0, the soft one 1.
    with_vision = choose_opening_frame(
        [
            FrameCandidate(offset_seconds=0.0, path=blurred, external_quality=1.0),
            FrameCandidate(offset_seconds=0.2, path=sharp, external_quality=0.0),
        ]
    )
    assert with_vision is not None and with_vision.offset_seconds == 0.0


def test_no_eligible_candidate_returns_none(tmp_path) -> None:
    assert choose_opening_frame([]) is None
    assert (
        choose_opening_frame([FrameCandidate(offset_seconds=2.0, path=_sharp(tmp_path))])
        is None
    )


# ---------------------------------------------------------------------------
# B. hook layout
# ---------------------------------------------------------------------------

def test_short_hook_stays_on_one_line_at_full_size(tmp_path) -> None:
    layout = hook_layout("1 euro pour")
    assert layout is not None
    assert layout.lines == ("1 euro pour",)
    assert layout.font_size == 108
    assert layout.truncated is False


def test_long_hook_wraps_and_shrinks_inside_the_top_band() -> None:
    layout = hook_layout(
        f"Il a lancé sa boutique avec un seul euro et voilà ce qui s{APOS}est passé"
    )
    assert layout is not None
    assert len(layout.lines) > 1
    assert len(layout.lines) <= HOOK_MAX_LINES
    assert layout.font_size < 108
    assert layout.bottom_y <= HOOK_MAX_BOTTOM_Y
    assert layout.truncated is False


def test_absurdly_long_hook_is_cut_rather_than_overflowing() -> None:
    layout = hook_layout("mot " * 80)
    assert layout is not None
    assert layout.truncated is True
    assert layout.lines[-1].endswith("…")
    assert layout.bottom_y <= HOOK_MAX_BOTTOM_Y
    assert len(layout.lines) <= HOOK_MAX_LINES


def test_hook_layout_ignores_empty_text() -> None:
    assert hook_layout("") is None
    assert hook_layout("   ") is None
    assert hook_dialogue_line("") is None


def test_hook_never_reaches_any_caption_line(tmp_path) -> None:
    """Geometry proof: the lowest hook pixel stays above the highest caption."""
    layout = hook_layout("mot " * 80)  # worst case: full band
    assert layout is not None
    caption_margins = [
        FACE_CROP_MARGIN_V,
        FIT_BLUR_MARGIN_V,
        *_MARGIN_V_BY_POSITION.values(),
    ]
    tallest_caption = max(style.font_size for style in THEME_STYLES.values())
    line_height = round(tallest_caption * HOOK_LINE_HEIGHT_RATIO)
    for margin_v in caption_margins:
        # Captions are bottom-anchored: their top pixel on a 1920 px canvas.
        caption_top = 1920 - margin_v - line_height
        assert layout.bottom_y < caption_top


# ---------------------------------------------------------------------------
# B. hook in the montage ASS writer
# ---------------------------------------------------------------------------

WORDS = [
    TranscriptWord("un", 0.0, 0.3),
    TranscriptWord("euro", 0.35, 0.6),
    TranscriptWord("seulement", 0.65, 1.1),
    TranscriptWord("pour", 1.2, 1.5),
    TranscriptWord("lancer", 1.55, 2.0),
    TranscriptWord("la", 2.1, 2.3),
    TranscriptWord("boutique", 2.35, 3.0),
]


def _write_clip(tmp_path, **kwargs) -> str:
    out = tmp_path / "clip.ass"
    assert write_ass_for_montage(
        transcript=Transcript(text="", words=WORDS),
        segments=[MontageSegment(role="single", start=0.0, end=3.0)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
        **kwargs,
    )
    return out.read_text(encoding="utf-8")


def test_hook_is_absent_by_default(tmp_path) -> None:
    plain = _write_clip(tmp_path)
    assert HOOK_STYLE_NAME not in plain
    assert "Dialogue: 1," not in plain


def test_default_output_is_byte_identical_without_a_hook(tmp_path) -> None:
    before = _write_clip(tmp_path)
    after = _write_clip(tmp_path, hook_text=None)
    assert before == after


def test_hook_emits_one_static_event_in_its_own_style(tmp_path) -> None:
    text = _write_clip(tmp_path, hook_text="1 euro pour se lancer")
    hook_lines = [line for line in text.splitlines() if line.startswith("Dialogue: 1,")]
    assert len(hook_lines) == 1
    hook = hook_lines[0]
    assert HOOK_STYLE_NAME in hook
    assert hook.startswith("Dialogue: 1,0:00:00.00,0:00:02.00,")
    assert f"Style: {HOOK_STYLE_NAME}" in text
    # No karaoke: the hook carries no per-word highlight override.
    assert "\\fscx" not in hook
    assert "76E600" not in hook


def test_captions_still_render_next_to_the_hook(tmp_path) -> None:
    text = _write_clip(tmp_path, hook_text="1 euro pour se lancer")
    caption_lines = [line for line in text.splitlines() if line.startswith("Dialogue: 0,")]
    assert caption_lines
    assert any("EURO" in line for line in caption_lines)
    # Captions keep layer 0, the hook owns layer 1: they never share a plane.
    assert all(HOOK_STYLE_NAME not in line for line in caption_lines)


def test_hook_disappears_after_the_configured_window(tmp_path) -> None:
    text = _write_clip(tmp_path, hook_text="1 euro pour se lancer", hook_seconds=1.5)
    hook = next(line for line in text.splitlines() if line.startswith("Dialogue: 1,"))
    assert hook.startswith("Dialogue: 1,0:00:00.00,0:00:01.50,")


def test_hook_is_clamped_to_a_short_clip(tmp_path) -> None:
    out = tmp_path / "short.ass"
    assert write_ass_for_montage(
        transcript=Transcript(text="", words=[TranscriptWord("va", 0.0, 0.9)]),
        segments=[MontageSegment(role="single", start=0.0, end=0.9)],
        out_path=str(out),
        audio_crossfade_seconds=0.0,
        hook_text="promesse",
        hook_seconds=DEFAULT_HOOK_SECONDS,
    )
    hook = next(
        line for line in out.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue: 1,")
    )
    assert hook.startswith("Dialogue: 1,0:00:00.00,0:00:00.90,")


def test_hook_text_cannot_break_the_ass_tag_stream(tmp_path) -> None:
    text = _write_clip(tmp_path, hook_text="il gagne {\\c&HFF0000&} par jour")
    hook = next(line for line in text.splitlines() if line.startswith("Dialogue: 1,"))
    assert "{\\c&HFF0000&}" not in hook
    assert "(\\c&HFF0000&)" in hook


# ---------------------------------------------------------------------------
# B. hook in the EDL ASS writer
# ---------------------------------------------------------------------------

def _edl_plan() -> CaptionPlan:
    words = [
        TranscriptWord("preuve", 0.00, 0.30),
        TranscriptWord("très", 0.31, 0.66),
        TranscriptWord("forte", 0.67, 1.05),
    ]
    transcript = Transcript(text=" ".join(word.word for word in words), words=words)
    plan = EditIntentPlan(
        schema_version="2.0",
        editorial_thesis="Open on the proof.",
        shots=(
            EditShotIntent(
                shot_id="hook",
                role="hook",
                from_word_id=0,
                to_word_id=2,
                framing=FramingIntent("locked_face"),
                caption_theme="hook_bold",
            ),
        ),
    )
    edl = compile_edit_intent(plan, transcript, source_duration_ms=20_000)
    return build_caption_plan(edl, transcript)


def test_edl_ass_has_no_hook_by_default() -> None:
    document = render_ass(_edl_plan())
    assert HOOK_STYLE_NAME not in document
    assert "Dialogue: 1," not in document


def test_edl_ass_renders_the_hook_above_the_captions() -> None:
    document = render_ass(_edl_plan(), hook_text="Il a tout misé sur 1 euro")
    assert f"Style: {HOOK_STYLE_NAME}" in document
    hook_lines = [line for line in document.splitlines() if line.startswith("Dialogue: 1,")]
    assert len(hook_lines) == 1
    # The compiled plan is ~1.16 s long, so the 2 s hook is clamped to the clip.
    assert hook_lines[0].startswith("Dialogue: 1,0:00:00.00,0:00:01.16,")
    assert HOOK_STYLE_NAME in hook_lines[0]


def test_edl_writer_keeps_its_no_cue_contract(tmp_path) -> None:
    empty = CaptionPlan(duration_ms=3_000, cues=())
    out = tmp_path / "empty.ass"
    assert write_ass_for_edl(empty, out_path=str(out)) is False
    assert not out.exists()
    # A hook alone is still worth burning in.
    assert write_ass_for_edl(empty, out_path=str(out), hook_text="la promesse") is True
    assert HOOK_STYLE_NAME in out.read_text(encoding="utf-8")
