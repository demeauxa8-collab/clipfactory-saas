#!/usr/bin/env python3
"""Round 4: is the timecode drift caused by my re-encode (fps=5) or by the model?"""
import json, pathlib, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run_probe import b64, post, HERE
from round3 import ANCHOR, call, vpart, OUT as _o

OUT = HERE / "out4"; OUT.mkdir(exist_ok=True)
import round3
round3.OUT = OUT

ANCHOR90 = """REGARDE et ECOUTE cette video. Donne la SECONDE EXACTE ou chaque phrase est prononcee (-1 si absente).
A. "je prefere faire du dropshipping sur Google"
B. "que je demande a ma meuf 100 euros"
C. "je finis par laver des voitures"
JSON strict: {"A":0.0,"B":0.0,"C":0.0,"duree_video_s":0.0}"""

JOBS = [
    # same 300 s content, NATIVE 30 fps this time
    ("google/gemini-3.1-flash-lite", [{"type": "text", "text": ANCHOR}, vpart("f_long300_native30fps.mp4")], "anchor300_native", 1200, True),
    ("qwen/qwen3.7-flash", [{"type": "text", "text": ANCHOR}, vpart("f_long300_native30fps.mp4")], "anchor300_native", 1200, True),
    # the expensive tier on the same task
    ("google/gemini-3.6-flash", [{"type": "text", "text": ANCHOR}, vpart("f_long300_native30fps.mp4")], "anchor300_native", 4000, False),
    # short window: is accuracy fine at 90 s?
    ("google/gemini-3.1-flash-lite", [{"type": "text", "text": ANCHOR90}, vpart("g_90s_native.mp4")], "anchor90", 800, True),
    ("google/gemini-3.6-flash", [{"type": "text", "text": ANCHOR90}, vpart("g_90s_native.mp4")], "anchor90", 3000, False),
]

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda j: round3.call(*j), JOBS))
