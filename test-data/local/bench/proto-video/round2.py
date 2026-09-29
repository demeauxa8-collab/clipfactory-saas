#!/usr/bin/env python3
"""Round 2: does video mode carry AUDIO? + token scaling on long video + fps knob + YouTube URL."""
import json, pathlib, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run_probe import b64, post, HERE

OUT = HERE / "out2"; OUT.mkdir(exist_ok=True)

# Decisive control: the answer can ONLY come from the audio track.
# Nothing in the frames spells these words out (verified on 1fps contact sheets).
AUDIO_CONTROL = """REGARDE ET ECOUTE cet extrait video. Reponds en JSON strict:
{
 "je_percois_le_son": true/false,
 "transcription_verbatim": "transcris MOT A MOT la parole que tu ENTENDS (pas ce qui est ecrit a l'ecran)",
 "premier_mot_prononce": "",
 "dernier_mot_prononce": "",
 "texte_incruste_a_l_ecran": ["uniquement les textes VISIBLES a l'ecran, pas la parole"]
}
Si tu n'as acces qu'aux images sans le son, mets je_percois_le_son=false et transcription_verbatim="".
Ne devine pas. L'honnetete prime."""

LONG_PROMPT = """Tu es directeur artistique. Voici une video complete. REGARDE-la et ECOUTE-la.
Retourne un JSON strict :
{"segments_clipables":[{"start_s":0,"end_s":0,"titre":"","hook_score":0-10,"pourquoi":"","energie":0-10}],
 "moments_morts":[[start,end]],
 "meilleur_hook_absolu":{"start_s":0,"end_s":0,"pourquoi":""}}
Donne 6 a 10 segments, timecodes en secondes reelles depuis le debut."""


def call(model, parts, tag, max_tokens=4000, reasoning_off=True):
    payload = {"model": model, "messages": [{"role": "user", "content": parts}],
               "max_tokens": max_tokens, "temperature": 0.1, "usage": {"include": True}}
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
        rec["provider"] = body.get("provider")
    (OUT / f"{model.replace('/','__')}__{tag}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    u = rec.get("usage") or {}
    pd = u.get("prompt_tokens_details") or {}
    print(f"[{tag}] {model} lat={rec['latency_s']}s prompt={u.get('prompt_tokens')} "
          f"vid={pd.get('video_tokens')} aud={pd.get('audio_tokens')} cost=${u.get('cost')} "
          f"finish={rec.get('finish_reason')} err={str(rec.get('error'))[:180]}")
    return rec


def vpart(path, fps=None):
    p = {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64(HERE / path)}"}}
    if fps:
        p["video_url"]["fps"] = fps
    return p


JOBS = []
# 1) audio-in-video control
for m in ["google/gemini-3.1-flash-lite", "qwen/qwen3.7-flash", "minimax/minimax-m3"]:
    JOBS.append((m, [{"type": "text", "text": AUDIO_CONTROL}, vpart("a_talkinghead_30s.mp4")], "ctrl_audio_a", 2500, True))
# 2) gemini-3.5-flash-lite with reasoning allowed (mandatory)
JOBS.append(("google/gemini-3.5-flash-lite",
             [{"type": "text", "text": AUDIO_CONTROL}, vpart("a_talkinghead_30s.mp4")], "ctrl_audio_a", 4000, False))
# 3) long video scaling: 300 s
JOBS.append(("google/gemini-3.1-flash-lite",
             [{"type": "text", "text": LONG_PROMPT}, vpart("d_long_300s.mp4")], "long300", 4000, True))
JOBS.append(("qwen/qwen3.7-flash",
             [{"type": "text", "text": LONG_PROMPT}, vpart("d_long_300s.mp4")], "long300", 4000, True))
# 4) fps knob
JOBS.append(("google/gemini-3.1-flash-lite",
             [{"type": "text", "text": AUDIO_CONTROL}, vpart("a_talkinghead_30s.mp4", fps=1)], "fps1_a", 2500, True))
# 5) YouTube URL direct
JOBS.append(("google/gemini-3.1-flash-lite",
             [{"type": "text", "text": "Decris en 3 phrases ce que montre cette video et donne sa duree."},
              {"type": "video_url", "video_url": {"url": "https://www.youtube.com/watch?v=aqz-KE-bpKQ"}}],
             "youtube_url", 800, True))

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda j: call(*j), JOBS))
