#!/usr/bin/env python3
"""Measure any clip cut from our reference video against the word-level truth.

Works on OUR output and on a competitor's alike: transcribe the clip, locate
what is said inside the frozen source transcript, then judge the cut with the
same yardstick — does it open mid-sentence, does it land, is there dead air,
how big is the face, is it black on the first frame.

    python analyze_clips.py --clips-dir <dir> --fixture <fixture.json> [--out report.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path

FFMPEG = "/Users/augustindemeaux/homebrew/bin/ffmpeg"
FFPROBE = "/Users/augustindemeaux/homebrew/bin/ffprobe"

# Openings that mark a clip starting on a run-up rather than on content.
WEAK_OPENERS = {
    "et", "mais", "donc", "alors", "puis", "or", "car", "ni", "voila",
    "en", "du", "parce", "vu", "puisque", "genre", "euh", "bref", "ensuite",
    # elided forms: the fold turns "d'ailleurs" into "d ailleurs", so the head
    # word alone is meaningless — these are matched on the first TWO tokens.
    "dailleurs", "enfait", "ducoup", "envrai", "cestquoi",
}
# A weak opening can also be an elision the fold split in two ("d'ailleurs").
WEAK_OPENER_PAIRS = {
    ("d", "ailleurs"), ("en", "fait"), ("du", "coup"), ("en", "vrai"),
    ("c", "est"), ("parce", "que"), ("vu", "que"), ("alors", "la"),
    ("et", "la"), ("et", "donc"), ("mais", "bon"), ("j", "veux"),
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9\s]", " ", text)


def _tokens(text: str) -> list[str]:
    return _fold(text).split()


def _run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


@dataclass
class ClipReport:
    name: str
    duration_s: float
    width: int
    height: int
    fps: float
    has_audio: bool
    aspect: str
    # placement in the source
    source_start_s: float | None
    source_end_s: float | None
    match_ratio: float
    # editorial measurements
    first_words: str
    last_words: str
    opens_on_weak_connector: bool
    opens_at_sentence_start: bool | None
    ends_at_sentence_end: bool | None
    # technical
    black_at_open_s: float
    silence_ratio: float
    mean_volume_db: float | None
    notes: str = ""


def probe(path: Path) -> dict:
    code, out, _ = _run([FFPROBE, "-v", "error", "-show_streams", "-show_format",
                         "-of", "json", str(path)])
    if code != 0:
        return {}
    return json.loads(out)


def measure_black_open(path: Path) -> float:
    code, _, err = _run([FFMPEG, "-hide_banner", "-nostats", "-t", "2.5", "-i", str(path),
                         "-vf", "blackdetect=d=0.05:pix_th=0.10", "-an", "-f", "null", "-"])
    total = 0.0
    for m in re.finditer(r"black_start:(-?[\d.]+)\s+black_end:(-?[\d.]+)", err):
        s, e = float(m.group(1)), float(m.group(2))
        if s <= 0.05:
            total = max(total, e - max(0.0, s))
    return round(total, 3)


def measure_silence(path: Path, duration: float) -> tuple[float, float | None]:
    code, _, err = _run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path),
                         "-af", "silencedetect=n=-32dB:d=0.35,volumedetect", "-f", "null", "-"])
    silent = 0.0
    for m in re.finditer(r"silence_duration: ([\d.]+)", err):
        silent += float(m.group(1))
    vol = None
    mv = re.search(r"mean_volume: (-?[\d.]+) dB", err)
    if mv:
        vol = float(mv.group(1))
    ratio = round(silent / duration, 3) if duration > 0 else 0.0
    return ratio, vol


async def transcribe_clip(path: Path) -> str:
    """Reuse the worker's own transcription so the words match the reference.

    Cached beside the clip: this harness is re-run every time a new competitor
    export lands, and re-paying for the same audio would be silly.
    """
    cache = path.with_suffix(".said.txt")
    if cache.exists() and cache.stat().st_size > 0:
        return cache.read_text(encoding="utf-8")
    import sys
    sys.path.insert(0, "/Users/augustindemeaux/clipfactory-saas/apps/worker")
    from app.pipeline.transcribe import transcribe  # noqa: E402
    t = await transcribe(str(path))
    said = " ".join(w.word for w in t.words)
    cache.write_text(said, encoding="utf-8")
    return said


def locate_in_source(said: str, ref_words: list[dict]) -> tuple[float | None, float | None, float]:
    """Slide the clip's words over the reference transcript, keep the best match."""
    clip = _tokens(said)
    if len(clip) < 4:
        return None, None, 0.0
    ref = [_fold(w["word"]).strip() for w in ref_words]
    ref = [w if w else "·" for w in ref]
    n = len(clip)
    best, best_i = 0.0, -1
    step = max(1, n // 8)
    for i in range(0, max(1, len(ref) - n + 1), step):
        r = SequenceMatcher(None, clip, ref[i:i + n]).quick_ratio()
        if r > best:
            best, best_i = r, i
    if best_i < 0:
        return None, None, 0.0
    lo, hi = max(0, best_i - step), min(len(ref) - n, best_i + step)
    for i in range(lo, hi + 1):
        r = SequenceMatcher(None, clip, ref[i:i + n]).ratio()
        if r > best:
            best, best_i = r, i
    end_i = min(len(ref_words) - 1, best_i + n - 1)
    return ref_words[best_i]["start"], ref_words[end_i]["end"], round(best, 3)


def sentence_edges(start: float, end: float, sentences: list[dict]) -> tuple[bool | None, bool | None]:
    if not sentences:
        return None, None
    tol = 0.45
    opens = any(abs(s["start"] - start) <= tol for s in sentences)
    ends = any(abs(s["end"] - end) <= tol for s in sentences)
    return opens, ends


def analyse(path: Path, fixture: dict) -> ClipReport:
    info = probe(path)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float(info.get("format", {}).get("duration", 0) or 0)
    w, h = int(v.get("width", 0) or 0), int(v.get("height", 0) or 0)
    fr = v.get("avg_frame_rate", "0/1")
    try:
        num, den = fr.split("/")
        fps = round(float(num) / float(den), 2) if float(den) else 0.0
    except Exception:
        fps = 0.0
    aspect = f"{w}x{h}"
    if w and h:
        r = w / h
        aspect += " (9:16)" if abs(r - 0.5625) < 0.02 else " (1:1)" if abs(r - 1) < 0.02 else f" ({r:.2f})"

    said = asyncio.run(transcribe_clip(path)) if a else ""
    ref_words = fixture["transcript"]["words"]
    s0, s1, ratio = locate_in_source(said, ref_words) if said else (None, None, 0.0)
    sentences = fixture["transcript"].get("sentences") or []
    opens_sent, ends_sent = sentence_edges(s0, s1, sentences) if s0 is not None else (None, None)

    toks = _tokens(said)
    first = " ".join(said.split()[:8])
    last = " ".join(said.split()[-6:])
    weak = bool(toks) and toks[0] in WEAK_OPENERS
    if not weak and len(toks) >= 2:
        weak = (toks[0], toks[1]) in WEAK_OPENER_PAIRS

    black = measure_black_open(path)
    sil, vol = measure_silence(path, dur)

    return ClipReport(
        name=path.name, duration_s=round(dur, 2), width=w, height=h, fps=fps,
        has_audio=a is not None, aspect=aspect,
        source_start_s=round(s0, 2) if s0 is not None else None,
        source_end_s=round(s1, 2) if s1 is not None else None,
        match_ratio=ratio, first_words=first, last_words=last,
        opens_on_weak_connector=weak, opens_at_sentence_start=opens_sent,
        ends_at_sentence_end=ends_sent, black_at_open_s=black,
        silence_ratio=sil, mean_volume_db=vol,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips-dir", required=True)
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()

    fixture = json.loads(Path(args.fixture).read_text())
    clips = sorted(p for p in Path(args.clips_dir).rglob("*.mp4"))
    if not clips:
        print("aucun mp4 trouvé")
        return 1

    reports = []
    for p in clips:
        print(f"… {p.parent.name}/{p.name}")
        reports.append(analyse(p, fixture))

    print()
    hdr = f"{'clip':<26}{'durée':>7}{'format':>16}{'placé à':>10}{'match':>7}{'ouvre':>8}{'ferme':>8}{'noir':>6}{'blancs':>8}"
    print(hdr)
    print("─" * len(hdr))
    for r in reports:
        pos = f"{r.source_start_s:.0f}s" if r.source_start_s is not None else "?"
        o = "OK" if r.opens_at_sentence_start else ("MILIEU" if r.opens_at_sentence_start is False else "?")
        e = "OK" if r.ends_at_sentence_end else ("MILIEU" if r.ends_at_sentence_end is False else "?")
        if r.opens_on_weak_connector:
            o += "!"
        print(f"{r.name[:25]:<26}{r.duration_s:>6.1f}s{r.aspect:>16}{pos:>10}{r.match_ratio:>7.2f}{o:>8}{e:>8}{r.black_at_open_s:>6.2f}{r.silence_ratio*100:>7.0f}%")
    print()
    for r in reports:
        print(f"── {r.name}")
        print(f"   ouvre sur : « {r.first_words} »")
        print(f"   finit sur : « …{r.last_words} »")
        if r.match_ratio < 0.80 and r.match_ratio > 0:
            print("   (match faible = clip probablement monté depuis plusieurs "
                  "moments distants ; la position donnée est celle du segment dominant)")

    if args.out:
        Path(args.out).write_text(json.dumps([asdict(r) for r in reports], ensure_ascii=False, indent=2))
        print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
