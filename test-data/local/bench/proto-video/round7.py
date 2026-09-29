#!/usr/bin/env python3
"""Round 7: at FULL length (595 s), how accurate are timecodes, and is audio-only enough?
Anchors verified against the whisper word-level transcript of the fixture:
 A 37.62  B 56.96  C 85.10  D 103.06  E 132.44  F 241.64  G 275.32
"""
import json, pathlib, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run_probe import HERE
from round6 import call, vpart, apart, SEGMENT

import round6
round6.OUT = HERE / "out7"; round6.OUT.mkdir(exist_ok=True)

ANCHOR = """REGARDE et ECOUTE cette video/audio en entier. Pour chacune des phrases ci-dessous,
donne la SECONDE EXACTE (depuis le debut) ou elle est prononcee. -1 si absente. N'estime pas au jugé, repere-la.
A. "je prefere faire du dropshipping sur Google"
B. "que je demande a ma meuf 100 euros"
C. "je finis par laver des voitures"
D. "je vais garder un chien 24 heures"
E. "mots aleatoires"
F. "on regarde sur Aliexpress"
G. "aller directement sur SEMrush"
JSON strict: {"A":0.0,"B":0.0,"C":0.0,"D":0.0,"E":0.0,"F":0.0,"G":0.0,"duree_video_s":0.0}"""

JOBS = [
    ("google/gemini-3.6-flash", [{"type": "text", "text": SEGMENT}, apart("full_audio_600s.mp3")], "audio595_segments_36", 6000, False),
    ("google/gemini-3.6-flash", [{"type": "text", "text": ANCHOR}, apart("full_audio_600s.mp3")], "audio595_anchor_36", 4000, False),
    ("google/gemini-3.6-flash", [{"type": "text", "text": ANCHOR}, vpart("e_full_595s.mp4")], "video595_anchor_36", 4000, False),
    ("google/gemini-3.1-flash-lite", [{"type": "text", "text": ANCHOR}, vpart("e_full_595s.mp4")], "video595_anchor_31", 1500, True),
    ("google/gemini-3.1-flash-lite", [{"type": "text", "text": ANCHOR}, apart("full_audio_600s.mp3")], "audio595_anchor_31", 1500, True),
]

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda j: call(*j), JOBS))
