#!/usr/bin/env python3
"""Round 6 (independent verification):
 A. real cost of the STATUS QUO (qwen3-vl-flash on 20 pipeline-identical 512px frames)
 B. token/cost law on the FULL 595 s video sent natively
 C. YouTube URL of the REAL source video, no upload
 D. clip-judge discrimination on 6 labelled clips x {video cheap, video reasoning, audio-only}
"""
import base64, json, os, pathlib, sys, time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run_probe import b64, post, HERE

OUT = HERE / "out6"; OUT.mkdir(exist_ok=True)
YT = "https://www.youtube.com/watch?v=TTDtkgCpyUk"

# ---- prompts ----
MAP_SYS = """You are a video understanding model. You receive a series of frames sampled
from a long-form French vlog, with their timestamps, plus the transcript.
Return a JSON list of 20-80 events: {start,end,decor,people,action,objects,
narrative_role,visual_importance,transcript_summary}. JSON only."""

SEGMENT = """Tu es directeur artistique pour des clips verticaux TikTok/Reels a partir de vlogs FR.
REGARDE et ECOUTE cette video en entier. Retourne un JSON strict :
{"segments_clipables":[{"start_s":0,"end_s":0,"titre":"","hook_score":0-10,"energie":0-10,
  "phrase_complete":true,"pourquoi":""}],
 "moments_morts":[[start,end]],
 "meilleur_hook_absolu":{"start_s":0,"end_s":0,"pourquoi":""}}
Donne 6 a 10 segments. Les timecodes doivent etre les SECONDES REELLES depuis le debut.
Chaque segment doit commencer et finir sur une phrase complete."""

JUDGE_V = """Tu es le juge final d'une chaine de montage automatique. On te donne UN clip vertical candidat
(il peut contenir plusieurs plans colles bout a bout). REGARDE-le et ECOUTE-le.
JSON strict :
{"publiable":true/false,"score_global":0-10,"hook_2s":0-10,
 "phrase_coupee_au_debut":true/false,"phrase_coupee_a_la_fin":true/false,
 "premier_mot_entendu":"","dernier_mot_entendu":"",
 "raccords":[{"at_s":0,"ca_se_comprend":true/false,"pourquoi":""}],
 "moment_mort":true/false,
 "raison_du_refus":""}
Sois severe : un clip dont la premiere ou la derniere phrase est tronquee n'est PAS publiable,
ni un clip qui n'est qu'un temps mort sans idee."""

JUDGE_A = JUDGE_V.replace("REGARDE-le et ECOUTE-le", "ECOUTE-le (tu n'as que le son)").replace(
    '"raccords":[{"at_s":0,"ca_se_comprend":true/false,"pourquoi":""}],', '')


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
        rec["provider"] = body.get("provider")
    (OUT / f"{model.replace('/','__')}__{tag}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    u = rec.get("usage") or {}; pd = u.get("prompt_tokens_details") or {}
    print(f"[{tag}] {model} lat={rec['latency_s']}s prompt={u.get('prompt_tokens')} "
          f"vid={pd.get('video_tokens')} aud={pd.get('audio_tokens')} img={pd.get('image_tokens')} "
          f"out={u.get('completion_tokens')} cost=${u.get('cost')} fin={rec.get('finish_reason')} "
          f"err={str(rec.get('error'))[:200]}", flush=True)
    return rec


def vpart(path):
    return {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64(HERE / path)}"}}


def apart(path, fmt="mp3"):
    return {"type": "input_audio", "input_audio": {"data": b64(HERE / path), "format": fmt}}


def ipart(path):
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(path)}"}}


def job_A():
    """Status quo: 20 x 512px frames + transcript to qwen3-vl-flash, exactly like the pipeline batch."""
    fx = json.load(open("/Users/augustindemeaux/clipfactory-data/bench/"
                        "fixture_2221f645-ed0e-47b2-8201-417d7c517a39.json"))
    tr = fx["transcript"]["text"][:4000]
    frames = sorted((HERE / "mapframes").glob("*.jpg"))
    parts = [{"type": "text", "text": MAP_SYS + f"\n\nDuration: 595 s.\nTranscript:\n{tr}\n\nFrames:"}]
    for i, f in enumerate(frames):
        parts.append({"type": "text", "text": f"frame at t={3 + i * 6}s"})
        parts.append(ipart(f))
    with ThreadPoolExecutor(max_workers=3) as ex:
        return list(ex.map(lambda m: call(m[0], parts, "statusquo_20frames", 4000, m[1]), [
            ("qwen/qwen3.7-flash", True),
            ("google/gemini-3.1-flash-lite", True),
            ("qwen/qwen3-vl-30b-a3b-instruct", True),
        ]))


JOBS = [
    # B. full 595 s native video
    ("google/gemini-3.1-flash-lite", [{"type": "text", "text": SEGMENT}, vpart("e_full_595s.mp4")], "full595_lite", 4000, True),
    ("google/gemini-3.6-flash", [{"type": "text", "text": SEGMENT}, vpart("e_full_595s.mp4")], "full595_36", 6000, False),
    # C. YouTube URL of the real source
    ("google/gemini-3.1-flash-lite", [{"type": "text", "text": SEGMENT},
                                      {"type": "video_url", "video_url": {"url": YT}}], "full595_youtube_lite", 4000, True),
]

CLIPS = ["j1_clean_intro", "j2_clean_google", "j3_clean_motsalea",
         "j4_bad_midsentence", "j5_bad_realmontage", "j6_bad_deadair"]

JUDGE_JOBS = []
for c in CLIPS:
    JUDGE_JOBS.append(("google/gemini-3.6-flash", [{"type": "text", "text": JUDGE_V}, vpart(f"judge6/{c}.mp4")], f"J36_{c}", 4000, False))
    JUDGE_JOBS.append(("google/gemini-3.1-flash-lite", [{"type": "text", "text": JUDGE_V}, vpart(f"judge6/{c}.mp4")], f"J31_{c}", 2500, True))
    JUDGE_JOBS.append(("google/gemini-3.1-flash-lite", [{"type": "text", "text": JUDGE_A}, apart(f"judge6/{c}.mp3")], f"A31_{c}", 2500, True))
    JUDGE_JOBS.append(("google/gemini-3.6-flash", [{"type": "text", "text": JUDGE_A}, apart(f"judge6/{c}.mp3")], f"A36_{c}", 4000, False))

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    with ThreadPoolExecutor(max_workers=4) as ex:
        if which in ("all", "a"):
            ex.submit(job_A)
        if which in ("all", "b"):
            list(ex.map(lambda j: call(*j), JOBS))
        if which in ("all", "j"):
            list(ex.map(lambda j: call(*j), JUDGE_JOBS))
