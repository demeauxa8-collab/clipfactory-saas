#!/usr/bin/env python3
"""Editorial scoring of the arc-selection benchmark, checked against the transcript.

Reads the per-model JSON produced by bench_arcs.py and grades every model on
facts that can be verified mechanically against the frozen fixture — no taste,
no vibes:

  anchors_found      the fraction of start/end anchors that exist VERBATIM in the
                     word-level transcript. This is the load-bearing metric: the
                     pipeline dates a cut from the quoted words, so an anchor that
                     cannot be located is a cut the code cannot place.
  anchor_len_ok      anchors holding 5-12 words, as the prompt demands.
  drift_seconds      |t(first anchor word) - declared segment start|. Measures
                     whether the model can read a clock; large drift is harmless
                     (the anchor wins) but it tells us how much the seconds lie.
  weak_open          arcs whose first spoken word is a discourse connector
                     (et/mais/donc/alors/du coup...) — a cold open on those reads
                     as "started mid-sentence".
  pronoun_open       arcs opening on a bare pronoun/demonstrative with no
                     antecedent on screen (ça, il, ce, cette...).
  multi_segment      arcs built from more than one source window, and whether
                     their link_reason is present and actually references words
                     from both segments.
  campaign_fit       spread of the model's own campaign_fit self-report: all-equal
                     scores mean the model did not rank anything.
  bounds             arc totals inside [12, 60] s, segments inside [3, 30] s,
                     <= 3 segments, and (from the run log) how many arcs the
                     parser had to reject before these survived.

Usage (from apps/worker, for the venv only):
    .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/score_text_bench.py \
        --results-dir /Users/augustindemeaux/clipfactory-data/bench/results/text-2026-08-08 \
        --log /Users/augustindemeaux/clipfactory-data/bench/results/text-2026-08-08.log
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import unicodedata
from pathlib import Path
from typing import Any

FIXTURE = (
    "/Users/augustindemeaux/clipfactory-data/bench/"
    "fixture_2221f645-ed0e-47b2-8201-417d7c517a39.json"
)

MIN_CLIP_SECONDS, MAX_CLIP_SECONDS = 12.0, 60.0
MIN_SEGMENT_SECONDS, MAX_SEGMENT_SECONDS = 3.0, 30.0
MAX_SEGMENTS_PER_ARC = 3

# French discourse connectors: opening a cold clip on one of these signals the
# viewer walked in mid-sentence.
WEAK_OPENERS = {
    "et", "mais", "donc", "alors", "puis", "ensuite", "or", "car", "parce",
    "bref", "voila", "voilà", "enfin", "apres", "après", "aussi", "ainsi",
    "cependant", "neanmoins", "néanmoins", "dailleurs", "d'ailleurs", "bon",
    "ben", "bah", "euh", "ok", "oui", "non", "puisque", "tandis", "sinon",
}
WEAK_OPENER_BIGRAMS = {("du", "coup"), ("en", "fait"), ("par", "contre"),
                       ("c'est", "pour"), ("et", "donc"), ("et", "puis"),
                       ("en", "gros"), ("du", "coup,")}
# Bare references with no antecedent available to a cold viewer.
PRONOUN_OPENERS = {
    "ca", "ça", "cela", "ce", "cet", "cette", "ces", "celui", "celle", "ceux",
    "il", "elle", "ils", "elles", "lui", "leur", "eux", "y", "en", "la", "le",
    "les", "lui-meme", "ceci",
}
STOPWORDS = {
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "a", "à",
    "que", "qui", "dans", "pour", "sur", "avec", "au", "aux", "il", "elle",
    "ce", "cette", "ces", "son", "sa", "ses", "est", "sont", "plus", "pas",
    "the", "and", "of", "to", "in", "is", "for", "with", "on", "that",
}


def norm(text: str) -> str:
    """Lowercase, unify apostrophes, drop punctuation, collapse spaces."""
    t = text.replace("’", "'").replace("ʼ", "'").replace("`", "'")
    t = unicodedata.normalize("NFC", t).lower()
    t = re.sub(r"[^\w'\- ]+", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


class TranscriptIndex:
    """Word-level transcript with a normalized flat string for verbatim lookup."""

    def __init__(self, words: list[dict[str, Any]]) -> None:
        self.words = words
        self.tokens = [norm(w.get("word", "")) for w in words]
        self.starts = [float(w.get("start", 0.0)) for w in words]
        self.ends = [float(w.get("end", 0.0)) for w in words]
        offsets, buf = [], []
        pos = 0
        for tok in self.tokens:
            offsets.append(pos)
            buf.append(tok)
            pos += len(tok) + 1
        self.flat = " ".join(buf)
        self.offsets = offsets

    def find(self, quote: str) -> tuple[int, int] | None:
        """Return (first_token_idx, last_token_idx) of a verbatim quote, or None."""
        q = norm(quote)
        if not q:
            return None
        pos = self.flat.find(q)
        if pos < 0:
            return None
        # offsets is sorted; locate the token containing `pos`
        lo, hi = 0, len(self.offsets) - 1
        first = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.offsets[mid] <= pos:
                first, lo = mid, mid + 1
            else:
                hi = mid - 1
        n_tokens = len(q.split())
        last = min(first + n_tokens - 1, len(self.tokens) - 1)
        return first, last


def _first_words(arc: dict[str, Any], idx: TranscriptIndex) -> list[str]:
    """The words the viewer actually hears first: the resolved start anchor of
    segment 1, falling back to opening_words / the excerpt head."""
    segs = arc.get("segments") or []
    for candidate in (
        (segs[0].get("start_anchor") if segs else None),
        arc.get("opening_words"),
        (segs[0].get("transcript_excerpt") if segs else None),
    ):
        if candidate:
            return norm(candidate).split()
    return []


def _content_words(text: str) -> set[str]:
    return {w for w in norm(text).split() if len(w) >= 4 and w not in STOPWORDS}


def score_model(result: dict[str, Any], idx: TranscriptIndex) -> dict[str, Any]:
    if not result.get("ok"):
        return {"model": result["model"], "ok": False, "error": result.get("error"),
                "latency_seconds": result.get("latency_seconds")}

    arcs = result["arcs"]
    anchors_total = anchors_found = anchor_len_ok = 0
    drifts: list[float] = []
    weak_open = pronoun_open = 0
    bounds_arc_ko = bounds_seg_ko = seg_count_ko = 0
    multi = 0
    link_present = 0
    link_grounded = 0
    fits: list[int] = []
    arc_rows: list[dict[str, Any]] = []

    for arc in arcs:
        segs = arc.get("segments") or []
        total = sum((s["end"] - s["start"]) for s in segs)
        if not (MIN_CLIP_SECONDS - 1e-6 <= total <= MAX_CLIP_SECONDS + 1e-6):
            bounds_arc_ko += 1
        if len(segs) > MAX_SEGMENTS_PER_ARC:
            seg_count_ko += 1
        for s in segs:
            d = s["end"] - s["start"]
            if not (MIN_SEGMENT_SECONDS - 1e-6 <= d <= MAX_SEGMENT_SECONDS + 1e-6):
                bounds_seg_ko += 1
            for key in ("start_anchor", "end_anchor"):
                a = s.get(key)
                anchors_total += 1
                if not a:
                    continue
                n_words = len(norm(a).split())
                if 5 <= n_words <= 12:
                    anchor_len_ok += 1
                hit = idx.find(a)
                if hit is None:
                    continue
                anchors_found += 1
                if key == "start_anchor":
                    drifts.append(abs(idx.starts[hit[0]] - float(s["start"])))

        fw = _first_words(arc, idx)
        if fw:
            if fw[0] in WEAK_OPENERS or (len(fw) > 1 and (fw[0], fw[1]) in WEAK_OPENER_BIGRAMS):
                weak_open += 1
            elif fw[0] in PRONOUN_OPENERS:
                pronoun_open += 1

        if len(segs) > 1:
            multi += 1
            lr = arc.get("link_reason")
            if lr:
                link_present += 1
                lw = _content_words(lr)
                per_seg = [
                    bool(lw & _content_words(
                        (s.get("transcript_excerpt") or "") + " " + (s.get("why") or "")
                    ))
                    for s in segs
                ]
                if all(per_seg):
                    link_grounded += 1

        if arc.get("campaign_fit_llm") is not None:
            fits.append(int(arc["campaign_fit_llm"]))

        arc_rows.append({
            "title": arc.get("title"),
            "n_segments": len(segs),
            "total_seconds": round(total, 1),
            "campaign_fit_llm": arc.get("campaign_fit_llm"),
            "opens_on": " ".join(_first_words(arc, idx)[:8]),
            "link_reason": (arc.get("link_reason") or "")[:160],
        })

    n = len(arcs)
    return {
        "model": result["model"],
        "ok": True,
        "n_arcs": n,
        "latency_seconds": result.get("latency_seconds"),
        "tokens_total": result.get("tokens"),
        "anchors_total": anchors_total,
        "anchors_found": anchors_found,
        "anchors_found_pct": round(100 * anchors_found / anchors_total, 1) if anchors_total else 0.0,
        "anchor_len_ok_pct": round(100 * anchor_len_ok / anchors_total, 1) if anchors_total else 0.0,
        "drift_median": round(statistics.median(drifts), 2) if drifts else None,
        "drift_max": round(max(drifts), 2) if drifts else None,
        "weak_open": weak_open,
        "pronoun_open": pronoun_open,
        "multi_segment": multi,
        "link_present": link_present,
        "link_grounded": link_grounded,
        "campaign_fit_values": sorted(fits),
        "campaign_fit_distinct": len(set(fits)),
        "campaign_fit_stdev": round(statistics.pstdev(fits), 1) if len(fits) > 1 else 0.0,
        "bounds_arc_ko": bounds_arc_ko,
        "bounds_seg_ko": bounds_seg_ko,
        "seg_count_ko": seg_count_ko,
        "arcs": arc_rows,
    }


def parse_log(log_path: Path) -> dict[str, dict[str, Any]]:
    """Recover per-model parser rejections from the bench run log."""
    if not log_path.is_file():
        return {}
    out: dict[str, dict[str, Any]] = {}
    current = None
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = ansi.sub("", line)
        m = re.match(r"running (\S+) \.\.\.", line)
        if m:
            current = m.group(1)
            out.setdefault(current, {})
            continue
        if current and "story_arcs.rejected" in line:
            kept = re.search(r"kept=(\d+)", line)
            total = re.search(r"total=(\d+)", line)
            reasons = re.search(r"reasons=(\{[^}]*\})", line)
            out[current]["rejected_total"] = int(total.group(1)) if total else None
            out[current]["kept"] = int(kept.group(1)) if kept else None
            out[current]["reasons"] = reasons.group(1) if reasons else None
        if current and "story_arcs.video_read" in line:
            out[current]["video_read"] = True
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results-dir", required=True)
    p.add_argument("--log", default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    fixture = json.loads(Path(FIXTURE).read_text(encoding="utf-8"))
    idx = TranscriptIndex(fixture["transcript"]["words"])
    log_info = parse_log(Path(args.log)) if args.log else {}

    rows = []
    for f in sorted(Path(args.results_dir).glob("*.json")):
        result = json.loads(f.read_text(encoding="utf-8"))
        row = score_model(result, idx)
        row["parser"] = log_info.get(row["model"], {})
        rows.append(row)

    ok = [r for r in rows if r["ok"]]
    ko = [r for r in rows if not r["ok"]]

    hdr = (f"{'model':<32}{'arcs':>5}{'anch%':>7}{'len%':>6}{'drift_med':>10}"
           f"{'drift_max':>10}{'weak':>6}{'pron':>6}{'multi':>6}{'link_g':>7}"
           f"{'fit_dist':>9}{'fit_sd':>7}{'lat_s':>8}{'tokens':>8}")
    print(hdr)
    print("-" * len(hdr))
    for r in sorted(ok, key=lambda r: (-r["anchors_found_pct"], r["weak_open"])):
        print(f"{r['model']:<32}{r['n_arcs']:>5}{r['anchors_found_pct']:>7.1f}"
              f"{r['anchor_len_ok_pct']:>6.1f}{(r['drift_median'] or 0):>10.2f}"
              f"{(r['drift_max'] or 0):>10.2f}{r['weak_open']:>6}{r['pronoun_open']:>6}"
              f"{r['multi_segment']:>6}{r['link_grounded']:>7}"
              f"{r['campaign_fit_distinct']:>9}{r['campaign_fit_stdev']:>7.1f}"
              f"{r['latency_seconds']:>8.1f}{r['tokens_total']:>8}")
    for r in ko:
        print(f"{r['model']:<32}   KO  {r['error']}")

    print("\n--- parser rejections (from the run log) ---")
    for r in rows:
        pr = r.get("parser") or {}
        if pr:
            print(f"  {r['model']:<32} kept={pr.get('kept')} rejected={pr.get('rejected_total')} "
                  f"{pr.get('reasons')}")

    print("\n--- per-arc detail ---")
    for r in ok:
        print(f"\n{r['model']}  (fits={r['campaign_fit_values']})")
        for a in r["arcs"]:
            print(f"   [{a['n_segments']}seg {a['total_seconds']:>5.1f}s fit={a['campaign_fit_llm']}] "
                  f"opens_on={a['opens_on']!r}")
            if a["link_reason"]:
                print(f"        link: {a['link_reason']}")

    if args.out:
        Path(args.out).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwritten: {args.out}")


if __name__ == "__main__":
    main()
