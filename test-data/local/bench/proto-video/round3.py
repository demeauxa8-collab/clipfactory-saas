#!/usr/bin/env python3
"""Round 3: quantitative timecode accuracy, audio-only full-length, clip-judge."""
import json, pathlib, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run_probe import b64, post, HERE

OUT = HERE / "out3"; OUT.mkdir(exist_ok=True)

# Anchors verified against the whisper word-level transcript (ground truth, seconds):
#  36.2 "TikTok" / 38.1 "je prefere faire du dropshipping sur Google"
#  57.3 "que je demande a ma meuf 100 euros"
#  85.1 "je finis par laver des voitures"
#  103.5 "je vais garder un chien 24 heures"
#  132.8 "mots aleatoires"
#  241.6 "on regarde sur Aliexpress"
#  275.3 "aller directement sur SEMrush"
ANCHOR = """REGARDE et ECOUTE cette video en entier. Pour chacune des phrases ci-dessous,
donne la SECONDE EXACTE (depuis le debut de la video) ou elle est prononcee.
Si une phrase n'apparait pas, mets -1. Ne devine pas, ecoute.
Phrases:
A. "je prefere faire du dropshipping sur Google"
B. "que je demande a ma meuf 100 euros"
C. "je finis par laver des voitures"
D. "je vais garder un chien 24 heures"
E. "mots aleatoires"
F. "on regarde sur Aliexpress"
G. "aller directement sur SEMrush"
Reponds en JSON strict: {"A":0.0,"B":0.0,"C":0.0,"D":0.0,"E":0.0,"F":0.0,"G":0.0,"duree_video_s":0.0}"""

AUDIO_LONG = """Tu es directeur artistique pour des clips verticaux TikTok/Reels a partir de vlogs FR.
ECOUTE cette piste audio complete. Retourne un JSON strict :
{"segments_clipables":[{"start_s":0,"end_s":0,"titre":"","hook_score":0-10,"pourquoi":"","energie":0-10,"debit":"lent|normal|rapide"}],
 "moments_morts":[[start,end]],
 "anchors":{"A_dropshipping_sur_Google":0.0,"B_demande_a_ma_meuf_100_euros":0.0,"C_laver_des_voitures":0.0,"D_garder_un_chien":0.0,"E_mots_aleatoires":0.0,"F_Aliexpress":0.0,"G_SEMrush":0.0},
 "meilleur_hook_absolu":{"start_s":0,"end_s":0,"pourquoi":""}}
Donne 6 a 10 segments. Timecodes en secondes reelles."""

JUDGE = """Tu es le juge final d'une chaine de montage automatique. On te donne UN clip vertical candidat
(deja monte, il peut contenir plusieurs plans colles bout a bout).
REGARDE-le et ECOUTE-le. Retourne un JSON strict :
{"publiable":true/false,
 "score_global":0-10,
 "hook_2s":0-10,
 "coherence_du_montage":{"score":0-10,"raccords_percus":[{"at_s":0,"type":"cut sec|transition|insert","ca_se_comprend":true/false,"pourquoi":""}]},
 "phrase_coupee_au_debut":true/false,
 "phrase_coupee_a_la_fin":true/false,
 "premier_mot_entendu":"",
 "dernier_mot_entendu":"",
 "correction_start_s":0.0,"correction_end_s":0.0,
 "raison_du_refus":""}
Sois severe : un clip dont la premiere ou la derniere phrase est tronquee n'est PAS publiable."""


def call(model, parts, tag, max_tokens=4000, reasoning_off=True, temp=0.1):
    payload = {"model": model, "messages": [{"role": "user", "content": parts}],
               "max_tokens": max_tokens, "temperature": temp, "usage": {"include": True}}
    if reasoning_off:
        payload["reasoning"] = {"enabled": False}
    body, dt, err = post(payload)
    rec = {"model": model, "tag": tag, "latency_s": round(dt, 1)}
    if err:
        rec["error"] = err
    else:
        rec["usage"] = body.get("usage")
        ch = (body.get("choices") or [{}])[0]
        rec["finish_reason"] = ch.get("finish_reason")
        rec["text"] = (ch.get("message") or {}).get("content")
    (OUT / f"{model.replace('/','__')}__{tag}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    u = rec.get("usage") or {}; pd = u.get("prompt_tokens_details") or {}
    print(f"[{tag}] {model} lat={rec['latency_s']}s prompt={u.get('prompt_tokens')} vid={pd.get('video_tokens')} "
          f"aud={pd.get('audio_tokens')} out={u.get('completion_tokens')} cost=${u.get('cost')} "
          f"finish={rec.get('finish_reason')} err={str(rec.get('error'))[:200]}")
    return rec


def vpart(path):
    return {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64(HERE / path)}"}}


def apart(path, fmt="mp3"):
    return {"type": "input_audio", "input_audio": {"data": b64(HERE / path), "format": fmt}}


JOBS = [
    # timecode accuracy on 300 s of video
    ("qwen/qwen3.7-flash", [{"type": "text", "text": ANCHOR}, vpart("d_long_300s.mp4")], "anchor300", 1200, True),
    ("google/gemini-3.1-flash-lite", [{"type": "text", "text": ANCHOR}, vpart("d_long_300s.mp4")], "anchor300", 1200, True),
    ("google/gemini-3.5-flash-lite", [{"type": "text", "text": ANCHOR}, vpart("d_long_300s.mp4")], "anchor300", 4000, False),
    # audio-only, full 595 s: the cheap alternative
    ("google/gemini-3.1-flash-lite", [{"type": "text", "text": AUDIO_LONG}, apart("full_audio_600s.mp3")], "audio_full", 5000, True),
    # clip-judge on the real assembled montage
    ("google/gemini-3.1-flash-lite", [{"type": "text", "text": JUDGE}, vpart("b_montage_concat.mp4")], "judge_b", 2500, True),
    ("google/gemini-3.6-flash", [{"type": "text", "text": JUDGE}, vpart("b_montage_concat.mp4")], "judge_b", 4000, False),
]

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda j: call(*j), JOBS))
