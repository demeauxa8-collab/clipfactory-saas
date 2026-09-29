#!/usr/bin/env python3
"""Round 5: clip-judge discrimination. b_montage = truncated at the end (should FAIL),
h_clip_clean = sentence-aligned 0 -> 29.95 s ending on 'c'est pas tres grave' (should PASS)."""
import pathlib, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run_probe import HERE
import round3
from round3 import JUDGE, vpart

OUT = HERE / "out5"; OUT.mkdir(exist_ok=True)
round3.OUT = OUT

MODELS = [("google/gemini-3.1-flash-lite", 2500, True),
          ("google/gemini-3.5-flash-lite", 4000, False),
          ("google/gemini-3.6-flash", 4000, False)]
CLIPS = [("b_montage_concat.mp4", "judgeB_truncated"),
         ("h_clip_clean_30s.mp4", "judgeH_clean")]

JOBS = [(m, [{"type": "text", "text": JUDGE}, vpart(c)], tag, mt, ro)
        for (m, mt, ro) in MODELS for (c, tag) in CLIPS]

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda j: round3.call(*j), JOBS))
