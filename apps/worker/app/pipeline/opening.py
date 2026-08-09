"""First-second craft: opening frame choice and the on-screen hook overlay.

Two things decide whether a vertical clip is watched past its first second:

1. the frame the platform freezes as the thumbnail (the very first frame of the
   clip), and
2. the promise printed on top of it.

Both live here, because both are decisions about the same instant and both must
respect the same rule: the spoken word owns the clock. Nothing in this module
may move a cut past the first word, and nothing here invents a timestamp — the
caller passes offsets it already computed from the word-level transcript.

Part 1 — opening frame
----------------------
``choose_opening_frame`` ranks already-extracted candidate frames and returns
the best offset *and* its score, so the caller can keep the original cut when
nothing beats it. Everything is measured with Pillow (already a dependency):

* sharpness      variance of the 3x3 Laplacian on a normalized grayscale copy;
* exposure       mean luma inside a comfortable band, penalized by the fraction
                 of crushed/blown pixels;
* stillness      1 - gradient anisotropy. Motion blur smears detail along the
                 direction of travel, so it collapses the gradient energy on one
                 axis while leaving the other one intact. Defocus blur, by
                 contrast, kills both axes and is already caught by sharpness.

What this CANNOT measure without a new dependency (honest list): eyes open or
mid-blink, mouth closed vs caught mid-syllable, gaze direction, expression, and
whether the subject is even facing the camera. Those need a face/landmark model.
The extension point is ``FrameCandidate.external_quality``: when the deep-vision
pass can score a frame on those criteria, it fills that field with a 0..1 value
and it is blended in with ``EXTERNAL_WEIGHT``. No other code has to change.

Part 2 — hook overlay
---------------------
``hook_style_line`` / ``hook_dialogue_line`` build the ASS title card shown over
the first ~2 s. It is deliberately unlike the karaoke captions: top third of the
frame instead of the bottom, amber instead of white, no word-by-word highlight,
one static block. The layout shrinks and wraps the text so the block never
leaves the reserved top band, which is what keeps it from ever colliding with
the captions living at the bottom.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image

# ---------------------------------------------------------------------------
# Part 1 — opening frame selection
# ---------------------------------------------------------------------------

# Frames are normalized to a common width before measurement so that sharpness
# is comparable between sources of different resolutions.
WORK_WIDTH = 320

# Laplacian variance is unbounded, so it is squashed by v / (v + K). K is the
# value that scores 0.5; it was calibrated on real 512 px frames extracted from
# a 720p talking-head source (visibly blurred frames land near 40-120, clean
# frames near 400-1500).
SHARPNESS_HALF_POINT = 260.0

# Mean luma band that reads well after platform re-encoding, and the outer
# limits where a frame is considered unusable (0.0). The band is deliberately
# generous on the bright side: sunny outdoor vlogs and white product pages are
# normal footage, not mistakes.
EXPOSURE_IDEAL_LOW = 80.0
EXPOSURE_IDEAL_HIGH = 195.0
EXPOSURE_FLOOR = 20.0
EXPOSURE_CEILING = 245.0
# Fraction of crushed (<=2) or blown (>=253) pixels at which the clipping
# penalty saturates. A blown sky costs some points, it never disqualifies a
# frame on its own, hence the capped penalty.
CLIPPING_TOLERANCE = 0.35
MAX_CLIPPING_PENALTY = 0.6

WEIGHT_SHARPNESS = 0.55
WEIGHT_EXPOSURE = 0.30
WEIGHT_STILLNESS = 0.15
# Weight given to an externally supplied 0..1 quality (deep vision: eyes open,
# mouth closed, facing camera). Absent by default.
EXTERNAL_WEIGHT = 0.35

# Hard cap on how far the opening may be nudged. Larger windows change which
# words open the clip, which is a different (and much riskier) decision.
SEARCH_RADIUS_SECONDS = 0.4
# Silence kept in front of the first word: a clip that opens exactly on the
# attack of a syllable sounds clipped.
DEFAULT_LEAD_IN_SECONDS = 0.12
# Score subtracted at the very edge of the search window, scaled linearly with
# distance: a marginally prettier frame is not worth a visible drift.
DRIFT_PENALTY = 0.05
# Below this gain the caller should keep the original frame.
DEFAULT_MIN_GAIN = 0.04


@dataclass(frozen=True)
class FrameCandidate:
    """One already-extracted still, with its offset from the current cut point.

    ``offset_seconds`` is relative to the cut the clip currently uses: 0.0 is
    the frame we would ship today, negative starts earlier, positive later.

    ``external_quality`` is the extension point for criteria this module cannot
    measure (eyes open, mouth closed, gaze). It is a 0..1 score; leave it None
    until a vision pass can fill it.
    """

    offset_seconds: float
    path: str
    external_quality: float | None = None


@dataclass(frozen=True)
class FrameQuality:
    """Measured quality of a single still, all sub-scores normalized to 0..1."""

    sharpness: float  # raw Laplacian variance, kept for logs/thresholds
    sharpness_score: float
    brightness: float  # raw mean luma 0..255
    exposure_score: float
    clipped_fraction: float
    motion_blur: float  # 0 = isotropic detail, 1 = fully directional smear
    score: float


@dataclass(frozen=True)
class ScoredFrame:
    """A candidate with its measured quality and its final ranking score."""

    candidate: FrameCandidate
    quality: FrameQuality
    score: float  # quality.score blended with external_quality, minus drift


@dataclass(frozen=True)
class OpeningFrameChoice:
    """Best eligible candidate, plus what the original cut scored.

    The caller decides: ``gain`` is None when the original frame was not part of
    the candidate list, otherwise it is ``score - baseline_score``.
    """

    offset_seconds: float
    path: str
    score: float
    quality: FrameQuality
    baseline_offset_seconds: float
    baseline_score: float | None
    gain: float | None
    min_gain: float
    considered: tuple[ScoredFrame, ...]

    @property
    def is_worth_shifting(self) -> bool:
        """True when moving the cut is justified by a real quality gain."""
        if self.offset_seconds == self.baseline_offset_seconds:
            return False
        if self.gain is None:
            return True
        return self.gain >= self.min_gain


def _load_luma(path: str) -> tuple[list[int], int, int, list[int]] | None:
    """Return (pixels, width, height, full_resolution_histogram) or None.

    Clipping is measured on the full-resolution histogram (downscaling averages
    blown highlights away), sharpness on the normalized copy.
    """
    try:
        with Image.open(path) as image:
            grey = image.convert("L")
            histogram = grey.histogram()
            width, height = grey.size
            if width <= 0 or height <= 0:
                return None
            if width > WORK_WIDTH:
                new_height = max(1, round(height * WORK_WIDTH / width))
                grey = grey.resize((WORK_WIDTH, new_height), Image.Resampling.BILINEAR)
            # "L" mode packs one byte per pixel, so the raw buffer already is
            # the luma plane in row-major order.
            pixels = list(grey.tobytes())
            work_width, work_height = grey.size
    except (OSError, ValueError):
        return None
    if work_width < 3 or work_height < 3:
        return None
    return pixels, work_width, work_height, histogram


def _detail_metrics(pixels: list[int], width: int, height: int) -> tuple[float, float]:
    """Single pass returning (laplacian_variance, gradient_anisotropy).

    Anisotropy is |Ex - Ey| / (Ex + Ey) over squared first differences: a whip
    pan or a fast hand smears one axis only, so the two energies diverge.
    """
    total = 0.0
    total_squared = 0.0
    energy_x = 0.0
    energy_y = 0.0
    count = 0
    for y in range(1, height - 1):
        row = y * width
        above = row - width
        below = row + width
        for x in range(1, width - 1):
            index = row + x
            centre = pixels[index]
            left = pixels[index - 1]
            right = pixels[index + 1]
            up = pixels[above + x]
            down = pixels[below + x]
            laplacian = left + right + up + down - 4 * centre
            total += laplacian
            total_squared += laplacian * laplacian
            dx = right - centre
            dy = down - centre
            energy_x += dx * dx
            energy_y += dy * dy
            count += 1
    if count == 0:
        return 0.0, 0.0
    mean = total / count
    variance = max(0.0, total_squared / count - mean * mean)
    energy_sum = energy_x + energy_y
    anisotropy = abs(energy_x - energy_y) / energy_sum if energy_sum > 0 else 0.0
    return variance, min(1.0, anisotropy)


def _exposure_score(histogram: list[int], *, pixel_count: int) -> tuple[float, float, float]:
    """Return (brightness, clipped_fraction, exposure_score)."""
    if pixel_count <= 0:
        return 0.0, 1.0, 0.0
    weighted = sum(level * count for level, count in enumerate(histogram))
    brightness = weighted / pixel_count
    clipped = sum(histogram[:3]) + sum(histogram[253:])
    clipped_fraction = clipped / pixel_count

    if EXPOSURE_IDEAL_LOW <= brightness <= EXPOSURE_IDEAL_HIGH:
        band = 1.0
    elif brightness < EXPOSURE_IDEAL_LOW:
        span = EXPOSURE_IDEAL_LOW - EXPOSURE_FLOOR
        band = max(0.0, (brightness - EXPOSURE_FLOOR) / span) if span > 0 else 0.0
    else:
        span = EXPOSURE_CEILING - EXPOSURE_IDEAL_HIGH
        band = max(0.0, (EXPOSURE_CEILING - brightness) / span) if span > 0 else 0.0

    saturation = min(1.0, clipped_fraction / CLIPPING_TOLERANCE) if CLIPPING_TOLERANCE > 0 else 0.0
    penalty = MAX_CLIPPING_PENALTY * saturation
    return brightness, clipped_fraction, max(0.0, band * (1.0 - penalty))


def score_frame(path: str) -> FrameQuality | None:
    """Measure one still. Returns None when the file cannot be read as an image."""
    loaded = _load_luma(path)
    if loaded is None:
        return None
    pixels, width, height, histogram = loaded
    variance, anisotropy = _detail_metrics(pixels, width, height)
    sharpness_score = variance / (variance + SHARPNESS_HALF_POINT)
    brightness, clipped_fraction, exposure = _exposure_score(
        histogram, pixel_count=sum(histogram)
    )
    stillness = 1.0 - anisotropy
    score = (
        WEIGHT_SHARPNESS * sharpness_score
        + WEIGHT_EXPOSURE * exposure
        + WEIGHT_STILLNESS * stillness
    )
    return FrameQuality(
        sharpness=variance,
        sharpness_score=sharpness_score,
        brightness=brightness,
        exposure_score=exposure,
        clipped_fraction=clipped_fraction,
        motion_blur=anisotropy,
        score=min(1.0, max(0.0, score)),
    )


def _is_eligible(
    candidate: FrameCandidate,
    *,
    baseline_offset_seconds: float,
    search_radius_seconds: float,
    latest_offset_seconds: float | None,
) -> bool:
    distance = abs(candidate.offset_seconds - baseline_offset_seconds)
    if distance > search_radius_seconds + 1e-9:
        return False
    if latest_offset_seconds is None:
        return True
    return candidate.offset_seconds <= latest_offset_seconds + 1e-9


def choose_opening_frame(
    candidates: Sequence[FrameCandidate],
    *,
    baseline_offset_seconds: float = 0.0,
    first_word_offset_seconds: float | None = None,
    lead_in_seconds: float = DEFAULT_LEAD_IN_SECONDS,
    search_radius_seconds: float = SEARCH_RADIUS_SECONDS,
    min_gain: float = DEFAULT_MIN_GAIN,
) -> OpeningFrameChoice | None:
    """Pick the best opening frame among already-extracted candidates.

    ``first_word_offset_seconds`` is the offset (same origin as the candidates)
    at which the first spoken word starts. No candidate later than
    ``first_word_offset_seconds - lead_in_seconds`` is ever eligible: text beats
    picture, and a prettier frame is never worth eating the first word. The
    search window itself is clamped to ``SEARCH_RADIUS_SECONDS``.

    Returns None when no candidate is eligible or readable. Otherwise the result
    carries the winning offset, its score, and the score of the original cut so
    the caller can leave the clip alone (``is_worth_shifting``).
    """
    search_radius_seconds = min(max(0.0, search_radius_seconds), SEARCH_RADIUS_SECONDS)
    latest_offset_seconds: float | None = None
    if first_word_offset_seconds is not None:
        latest_offset_seconds = first_word_offset_seconds - max(0.0, lead_in_seconds)

    scored: list[ScoredFrame] = []
    for candidate in candidates:
        if not _is_eligible(
            candidate,
            baseline_offset_seconds=baseline_offset_seconds,
            search_radius_seconds=search_radius_seconds,
            latest_offset_seconds=latest_offset_seconds,
        ):
            continue
        quality = score_frame(candidate.path)
        if quality is None:
            continue
        score = quality.score
        if candidate.external_quality is not None:
            external = min(1.0, max(0.0, candidate.external_quality))
            score = (1.0 - EXTERNAL_WEIGHT) * score + EXTERNAL_WEIGHT * external
        if search_radius_seconds > 0:
            distance = abs(candidate.offset_seconds - baseline_offset_seconds)
            score -= DRIFT_PENALTY * (distance / search_radius_seconds)
        scored.append(ScoredFrame(candidate=candidate, quality=quality, score=score))

    if not scored:
        return None

    baseline = next(
        (
            item
            for item in scored
            if abs(item.candidate.offset_seconds - baseline_offset_seconds) <= 1e-9
        ),
        None,
    )
    # Ties go to the smallest move, then to the earliest offset, so the result
    # is deterministic and biased towards leaving the cut where it is.
    best = min(
        scored,
        key=lambda item: (
            -item.score,
            abs(item.candidate.offset_seconds - baseline_offset_seconds),
            item.candidate.offset_seconds,
        ),
    )
    baseline_score = baseline.score if baseline is not None else None
    return OpeningFrameChoice(
        offset_seconds=best.candidate.offset_seconds,
        path=best.candidate.path,
        score=best.score,
        quality=best.quality,
        baseline_offset_seconds=baseline_offset_seconds,
        baseline_score=baseline_score,
        gain=None if baseline_score is None else best.score - baseline_score,
        min_gain=min_gain,
        considered=tuple(scored),
    )


# ---------------------------------------------------------------------------
# Part 2 — on-screen hook overlay
# ---------------------------------------------------------------------------

HOOK_STYLE_NAME = "CFOpeningHook"
# White type on a near-opaque black card (BorderStyle 3). Checked on real
# renders: an amber/yellow hook reads as "the creator's own burned-in yellow
# subtitles" on the many FR vlogs that use them, which is exactly the confusion
# the karaoke highlight colour was chosen to avoid. The card also survives any
# background — blown sky, white product page, dark room — which a plain outline
# does not. Distinction from the captions comes from the card, the top-third
# placement, the size and the absence of any word highlight.
HOOK_PRIMARY_BGR = "FFFFFF"
HOOK_BOX_ABGR = "2A000000"  # ~84% opaque black card
HOOK_BORDER_STYLE = 3
DEFAULT_HOOK_SECONDS = 2.0
# Alignment 8 (top-centre), so MarginV counts down from the top edge.
HOOK_ALIGNMENT = 8
HOOK_MARGIN_V = 200
HOOK_MARGIN_H = 60
HOOK_LAYER = 1
# The hook block must stay inside the top third of the 1920 px canvas. Captions
# are bottom-anchored (the highest supported MarginV is 1_050, i.e. a baseline
# at y=870), so this ceiling is what guarantees the two never overlap.
HOOK_MAX_BOTTOM_Y = 620
HOOK_BASE_FONT_SIZE = 108
HOOK_MIN_FONT_SIZE = 60
HOOK_FONT_STEP = 4
HOOK_MAX_LINES = 4
HOOK_LINE_HEIGHT_RATIO = 1.2
# Character budget of one line at HOOK_BASE_FONT_SIZE inside the safe width
# (1080 - 2 * HOOK_MARGIN_H). Mirrors the caption budget (15 chars at font 110
# inside 1080 - 2 * 80) and stays conservative: the hook keeps the model's
# sentence case, whose lowercase glyphs are narrower than the caption capitals.
HOOK_CHARS_AT_BASE = 16
# With BorderStyle 3 the Outline field is the card's padding.
HOOK_BOX_PADDING = 14
HOOK_SHADOW = 0
# Instant on (the first frame is the thumbnail: the promise must be there),
# gentle fade out so the hook clears the way for the captions.
HOOK_FADE_OUT_MS = 220


@dataclass(frozen=True)
class HookLayout:
    """Wrapped hook text with the font size that makes it fit the top band."""

    lines: tuple[str, ...]
    font_size: int
    truncated: bool

    @property
    def line_height(self) -> int:
        return round(self.font_size * HOOK_LINE_HEIGHT_RATIO)

    @property
    def height(self) -> int:
        return self.line_height * len(self.lines)

    @property
    def bottom_y(self) -> int:
        """Lowest pixel the block can paint, card padding included."""
        return HOOK_MARGIN_V + self.height + HOOK_BOX_PADDING


def _sanitize_hook(text: str) -> str:
    """Collapse whitespace and neutralize the braces libass reads as overrides."""
    cleaned = text.replace("{", "(").replace("}", ")")
    return " ".join(cleaned.split())


def _chars_per_line(font_size: int) -> int:
    """Character budget of one line at ``font_size`` (width scales inversely)."""
    return max(1, round(HOOK_CHARS_AT_BASE * HOOK_BASE_FONT_SIZE / font_size))


def _wrap_by_chars(words: list[str], max_chars: int) -> list[str]:
    """Greedy word wrap by character count; over-long words get their own line."""
    lines: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        candidate = len(word) if not current else length + 1 + len(word)
        if current and candidate > max_chars:
            lines.append(" ".join(current))
            current = [word]
            length = len(word)
        else:
            current.append(word)
            length = candidate
    if current:
        lines.append(" ".join(current))
    return lines


def _fits(lines: list[str], font_size: int) -> bool:
    if len(lines) > HOOK_MAX_LINES:
        return False
    height = round(font_size * HOOK_LINE_HEIGHT_RATIO) * len(lines)
    return HOOK_MARGIN_V + height + HOOK_BOX_PADDING <= HOOK_MAX_BOTTOM_Y


def hook_layout(text: str) -> HookLayout | None:
    """Wrap ``text`` at the largest font size that stays inside the top band.

    Shrinking mirrors what captions already do for over-long lines. If even the
    minimum size overflows (a hook far longer than the 100-char contract), the
    text is cut on a word boundary and marked ``truncated`` — an unreadable wall
    of text over the face is worse than a shortened promise.
    """
    cleaned = _sanitize_hook(text)
    if not cleaned:
        return None
    words = cleaned.split(" ")

    size = HOOK_BASE_FONT_SIZE
    while size >= HOOK_MIN_FONT_SIZE:
        lines = _wrap_by_chars(words, _chars_per_line(size))
        if _fits(lines, size):
            return HookLayout(lines=tuple(lines), font_size=size, truncated=False)
        size -= HOOK_FONT_STEP

    size = HOOK_MIN_FONT_SIZE
    max_chars = _chars_per_line(size)
    lines = _wrap_by_chars(words, max_chars)
    budget = HOOK_MAX_BOTTOM_Y - HOOK_MARGIN_V - HOOK_BOX_PADDING
    max_lines = max(1, min(HOOK_MAX_LINES, budget // round(size * HOOK_LINE_HEIGHT_RATIO)))
    kept = lines[:max_lines]
    kept[-1] = kept[-1][: max(1, max_chars - 1)].rstrip() + "…"
    return HookLayout(lines=tuple(kept), font_size=size, truncated=True)


def hook_style_line() -> str:
    """The ``Style:`` line to append to a [V4+ Styles] block.

    Same field order as the caption styles (ASS_STYLE_FORMAT): bold white type
    on an opaque black card, top-centre aligned inside the reserved band.
    """
    return (
        f"Style: {HOOK_STYLE_NAME},Inter,{HOOK_BASE_FONT_SIZE},"
        f"&H00{HOOK_PRIMARY_BGR},&H00{HOOK_PRIMARY_BGR},&H00000000,&H{HOOK_BOX_ABGR},"
        f"1,0,0,0,100,100,0,0,{HOOK_BORDER_STYLE},{HOOK_BOX_PADDING},{HOOK_SHADOW},"
        f"{HOOK_ALIGNMENT},{HOOK_MARGIN_H},{HOOK_MARGIN_H},{HOOK_MARGIN_V},1"
    )


def _format_ass_time(seconds: float) -> str:
    centiseconds = int(max(0.0, seconds) * 100)
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, rest = divmod(remainder, 6_000)
    return f"{hours}:{minutes:02d}:{rest // 100:02d}.{rest % 100:02d}"


def hook_dialogue_line(
    text: str,
    *,
    start_seconds: float = 0.0,
    end_seconds: float = DEFAULT_HOOK_SECONDS,
) -> str | None:
    """Render the hook as one static ASS Dialogue line, or None if it cannot show.

    Returns None for empty text or a non-positive window, so callers can pass a
    model field straight through without pre-checking it.
    """
    if end_seconds <= start_seconds:
        return None
    layout = hook_layout(text)
    if layout is None:
        return None
    override = f"{{\\fad(0,{HOOK_FADE_OUT_MS})"
    if layout.font_size != HOOK_BASE_FONT_SIZE:
        override += f"\\fs{layout.font_size}"
    override += "}"
    body = "\\N".join(layout.lines)
    return (
        f"Dialogue: {HOOK_LAYER},{_format_ass_time(start_seconds)},"
        f"{_format_ass_time(end_seconds)},{HOOK_STYLE_NAME},,0,0,0,,{override}{body}"
    )
