from __future__ import annotations

import asyncio
import os
import tempfile

import structlog
from openai import AsyncOpenAI

from ..models import Transcript, TranscriptSentence, TranscriptWord
from ..settings import get_settings

log = structlog.get_logger()


# --- French elision repair -------------------------------------------------
# whisper-1 returns French elisions as separate, apostrophe-less tokens
# ("J", "ai" for "j'ai"). We stitch them back together with the typographic
# apostrophe so both the LLM prompt text and the burned-in captions read right.
_APOSTROPHE = "’"  # noqa: RUF001 (typographic apostrophe is intentional data)
_ELIDED_TOKENS = frozenset(
    {"j", "l", "d", "c", "s", "n", "m", "t", "qu", "jusqu", "puisqu", "lorsqu"}
)
# Vowels (+ h muet) that trigger elision when they open the following word.
_ELISION_VOWELS = "aeiouyéèêëàâîïôûùh"


def _elision_starts_with_vowel(word: str) -> bool:
    w = word.strip()
    return bool(w) and w[0].lower() in _ELISION_VOWELS


def _merge_two(a: TranscriptWord, b: TranscriptWord) -> TranscriptWord:
    return TranscriptWord(
        word=f"{a.word.strip()}{_APOSTROPHE}{b.word.strip()}",
        start=a.start,
        end=b.end,
    )


def merge_french_elisions(words: list[TranscriptWord]) -> list[TranscriptWord]:
    """Rebuild French elisions that whisper-1 splits and strips of apostrophes.

    Pure function: returns a new list; the input words are never mutated. An
    elidable token ("j", "l", "qu", …) is fused with the following vowel-initial
    word using U+2019 ("J" + "ai" -> "J'ai"), and the fixed "aujourd" + "hui"
    contraction becomes "aujourd'hui". The merged word spans [start_a, end_b].
    """
    if not words:
        return []

    # Pass 1 — the fixed "aujourd'hui" (aujourd is not otherwise elidable).
    stage: list[TranscriptWord] = []
    i, n = 0, len(words)
    while i < n:
        cur = words[i]
        if (
            i + 1 < n
            and cur.word.strip().lower() == "aujourd"
            and words[i + 1].word.strip().lower() == "hui"
        ):
            stage.append(_merge_two(cur, words[i + 1]))
            i += 2
            continue
        stage.append(cur)
        i += 1

    # Pass 2 — elidable token + vowel-initial next word.
    out: list[TranscriptWord] = []
    i, m = 0, len(stage)
    while i < m:
        cur = stage[i]
        if (
            i + 1 < m
            and cur.word.strip().lower() in _ELIDED_TOKENS
            and _elision_starts_with_vowel(stage[i + 1].word)
        ):
            out.append(_merge_two(cur, stage[i + 1]))
            i += 2
            continue
        out.append(cur)
        i += 1
    return out


async def _extract_audio(src_path: str, ffmpeg_bin: str) -> str:
    """Downmix to a compact 16 kHz mono MP3.

    OpenAI's transcription endpoint caps uploads at 25 MB. Sending the raw video
    blows past that on ~10 min clips, so we strip the video track and compress
    the audio (a 30 min plan-cap clip lands around ~14 MB at 64 kbps).
    """
    fd, out_path = tempfile.mkstemp(suffix=".mp3", prefix="cf_audio_")
    os.close(fd)
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_bin, "-y", "-i", src_path,
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k",
        out_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extract failed: {stderr.decode()[-400:]}")
    return out_path


ZERO_DURATION_EPSILON = 1e-3


def repair_zero_duration_words(
    words: list[TranscriptWord],
    *,
    min_duration: float = 0.05,
    target_duration: float = 0.2,
) -> list[TranscriptWord]:
    """Give whisper's zero-length words a real, non-overlapping time span.

    whisper-1 sometimes returns ``start == end`` for short words (often packed
    against a neighbour). Captions and cut snapping then see a word that is never
    on screen. Deterministic repair, per run of consecutive zero-length words:

    1. the run may use the room between the previous word's end and the next
       word's start, at most ``target_duration`` per word, centred on the
       original timestamp (a word never swallows a long silence);
    2. if that room is below ``min_duration`` per word, time is borrowed from
       the neighbours, each keeping at least ``min_duration`` itself;
    3. the resulting span is split evenly across the run.

    Words with a positive duration are only touched when they lend time. If no
    room can be found at all, the run is left unchanged. Returns new objects.
    """
    out = [TranscriptWord(word=w.word, start=w.start, end=w.end) for w in words]
    i = 0
    while i < len(out):
        if out[i].end - out[i].start >= ZERO_DURATION_EPSILON:
            i += 1
            continue
        j = i
        while j + 1 < len(out) and out[j + 1].end - out[j + 1].start < ZERO_DURATION_EPSILON:
            j += 1
        n = j - i + 1
        prev = out[i - 1] if i > 0 else None
        nxt = out[j + 1] if j + 1 < len(out) else None
        run_lo = min(w.start for w in out[i : j + 1])
        run_hi = max(w.end for w in out[i : j + 1])
        lo = prev.end if prev else max(0.0, run_lo - n * target_duration)
        hi = nxt.start if nxt else run_hi + n * target_duration
        if hi < lo:
            hi = lo
        want = n * target_duration
        center = min(max((run_lo + run_hi) / 2, lo), hi)
        a = max(lo, center - want / 2)
        b = min(hi, center + want / 2)
        if b - a < want:
            a = max(lo, b - want)
        if b - a < want:
            b = min(hi, a + want)
        need = n * min_duration
        if b - a < need and prev is not None:
            slack = max(0.0, prev.end - prev.start - min_duration)
            take = min(slack, need - (b - a))
            if take > 0 and a <= prev.end + 1e-9:
                prev.end -= take
                a = prev.end
        if b - a < need and nxt is not None:
            slack = max(0.0, nxt.end - nxt.start - min_duration)
            take = min(slack, need - (b - a))
            if take > 0 and b >= nxt.start - 1e-9:
                nxt.start += take
                b = nxt.start
        if b - a >= ZERO_DURATION_EPSILON * n:
            step = (b - a) / n
            for k in range(n):
                out[i + k].start = a + k * step
                out[i + k].end = a + (k + 1) * step
        i = j + 1
    return out


def _field(obj: object, name: str) -> object:
    """Read a field off a verbose_json entry, dict or pydantic object alike."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def parse_sentences(raw_segments: object) -> list[TranscriptSentence]:
    """Turn the verbose_json "segments" list into punctuated sentences.

    Defensive on purpose: one malformed entry must not cost us the whole list,
    and an ASR that returns no segments at all simply yields [] (the boundary
    detector then falls back to inter-word gaps).
    """
    out: list[TranscriptSentence] = []
    if not isinstance(raw_segments, (list, tuple)):
        return out
    for seg in raw_segments:
        try:
            text = str(_field(seg, "text") or "").strip()
            start = float(_field(seg, "start"))  # type: ignore[arg-type]
            end = float(_field(seg, "end"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if not text or end <= start:
            continue
        out.append(TranscriptSentence(text=text, start=start, end=end))
    out.sort(key=lambda s: (s.start, s.end))
    return out


async def transcribe(audio_or_video_path: str) -> Transcript:
    settings = get_settings()
    # Generous timeout + retries: whisper-1 on a ~30 min clip can be slow, and a
    # single transient timeout should not fail the whole job.
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=180.0, max_retries=3)

    audio_path = await _extract_audio(audio_or_video_path, settings.ffmpeg_bin)
    try:
        with open(audio_path, "rb") as fh:
            resp = await client.audio.transcriptions.create(
                file=fh,
                model=settings.openai_transcribe_model,
                response_format="verbose_json",
                # "segment" costs nothing extra and is the only place we get
                # punctuation: sentence boundaries come from there, not from
                # guessing silences between packed-together words.
                timestamp_granularities=["word", "segment"],
            )
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass

    text = getattr(resp, "text", "") or ""
    words: list[TranscriptWord] = []
    raw_words = getattr(resp, "words", None) or []
    for w in raw_words:
        try:
            words.append(
                TranscriptWord(
                    word=str(w.get("word") if isinstance(w, dict) else w.word),
                    start=float(w.get("start") if isinstance(w, dict) else w.start),
                    end=float(w.get("end") if isinstance(w, dict) else w.end),
                )
            )
        except Exception:
            continue

    # Repair French elisions before anything downstream (LLM prompt text and
    # burned-in captions both read from these words).
    words = merge_french_elisions(words)
    # whisper-1 can emit zero-length words; give them a real span so captions
    # show them and boundary snapping can see them.
    words = repair_zero_duration_words(words)

    sentences = parse_sentences(getattr(resp, "segments", None))

    lang = getattr(resp, "language", None)
    log.info(
        "transcribe.done",
        words=len(words),
        sentences=len(sentences),
        language=lang,
    )
    if not sentences:
        # Not fatal (boundaries.py degrades to gap detection) but worth seeing:
        # every downstream cut is less precise without punctuation.
        log.warning("transcribe.no_sentences", model=settings.openai_transcribe_model)
    return Transcript(text=text, words=words, language=lang, sentences=sentences)


def transcript_to_timestamped_lines(t: Transcript, line_seconds: float = 12.0) -> str:
    """Compact representation used in the candidate prompt.

    We chunk the transcript words into ~12 second lines so the LLM gets explicit
    timestamps without exploding the token budget.
    """
    if not t.words:
        return f"[0.0] {t.text.strip()}"

    lines: list[str] = []
    bucket: list[str] = []
    bucket_start = t.words[0].start
    for w in t.words:
        if w.start - bucket_start >= line_seconds:
            lines.append(f"[{bucket_start:.1f}] {' '.join(bucket).strip()}")
            bucket = []
            bucket_start = w.start
        bucket.append(w.word)
    if bucket:
        lines.append(f"[{bucket_start:.1f}] {' '.join(bucket).strip()}")
    return "\n".join(lines)


def words_in_window(t: Transcript, start: float, end: float) -> list[TranscriptWord]:
    return [w for w in t.words if w.end >= start and w.start <= end]
