#!/usr/bin/env python3
"""T3 — clip-judge. Step 1: DEAFNESS TEST (ask for a verbatim transcript of what is
SPOKEN in a real clip; a deaf model returns only burned-in on-screen text or refuses).
Step 2: judge6 on the 6 hand-labelled clips, only for models that pass step 1.
"""
import base64, json, os, pathlib, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).parent
J6 = pathlib.Path("/Users/augustindemeaux/clipfactory-data/bench/proto-video/judge6")
OUT = HERE / "out3"; OUT.mkdir(exist_ok=True)
ENV = pathlib.Path("/Users/augustindemeaux/clipfactory-saas/apps/worker/.env")
URL = "https://openrouter.ai/api/v1/chat/completions"


def api_key():
    for line in ENV.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no key")


KEY = api_key()

DEAF_PROMPT = """Ce fichier est un extrait video avec une piste AUDIO (une personne parle en francais).
Ta seule tache : ECOUTER la piste audio et retranscrire MOT A MOT ce qui est DIT a l'oral.
N'ecris PAS le texte incruste a l'image. Si tu ne percois aucun son, reponds exactement AUCUN_SON.
Reponds en JSON strict : {"entends_le_son": true/false, "transcription_orale": "...", "texte_incruste_a_l_ecran": ["..."]}"""

JUDGE = """Tu es le juge final d'une chaine de montage automatique. On te donne UN clip vertical candidat
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

VIDEO_MODELS = [
    ("qwen/qwen3.7-flash", True),
    ("qwen/qwen3.5-flash-02-23", True),
    ("qwen/qwen3.6-flash", True),
    ("qwen/qwen3.5-9b", True),
    ("qwen/qwen3.5-27b", True),
    ("qwen/qwen3.5-35b-a3b", True),
    ("qwen/qwen3.6-35b-a3b", True),
    ("qwen/qwen3.6-27b", True),
    ("qwen/qwen3.5-122b-a10b", True),
    ("qwen/qwen3.5-397b-a17b", True),
    ("qwen/qwen3.5-plus-02-15", True),
    ("qwen/qwen3.5-plus-20260420", True),
    ("qwen/qwen3.6-plus", True),
    ("qwen/qwen3.8-max", False),
]


def b64(p):
    return base64.b64encode(pathlib.Path(p).read_bytes()).decode()


def post(payload, timeout=600):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f); bf = f.name
    t0 = time.time()
    try:
        p = subprocess.run(["curl", "-sS", "--max-time", str(timeout), URL,
                            "-H", f"Authorization: Bearer {KEY}",
                            "-H", "Content-Type: application/json",
                            "--data-binary", "@" + bf], capture_output=True, text=True)
        dt = time.time() - t0
        if p.returncode != 0:
            return None, dt, f"curl rc={p.returncode}: {p.stderr[:400]}"
        try:
            body = json.loads(p.stdout)
        except Exception:
            return None, dt, f"non-json: {p.stdout[:400]}"
        if "error" in body and not body.get("choices"):
            return None, dt, f"API error: {json.dumps(body['error'])[:500]}"
        return body, dt, None
    finally:
        os.unlink(bf)


def call(model, reasoning_off, prompt, media_path, tag, max_tokens=1500, kind="video"):
    if kind == "video":
        mp = {"type": "video_url", "video_url": {"url": "data:video/mp4;base64," + b64(media_path)}}
    else:
        mp = {"type": "input_audio", "input_audio": {"data": b64(media_path), "format": "mp3"}}
    payload = {"model": model,
               "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, mp]}],
               "max_tokens": max_tokens, "temperature": 0.1, "usage": {"include": True}}
    if reasoning_off:
        payload["reasoning"] = {"enabled": False}
    body, dt, err = post(payload)
    rec = {"model": model, "tag": tag, "kind": kind, "latency_s": round(dt, 1)}
    if err:
        rec["error"] = err
    else:
        rec["usage"] = body.get("usage")
        ch = (body.get("choices") or [{}])[0]
        rec["finish_reason"] = ch.get("finish_reason")
        rec["text"] = (ch.get("message") or {}).get("content")
        rec["provider"] = body.get("provider")
    (OUT / f"{model.replace('/', '__')}__{tag}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    u = rec.get("usage") or {}
    print(f"[{tag}] {model:34s} lat={rec['latency_s']:6.1f} in={u.get('prompt_tokens')} "
          f"out={u.get('completion_tokens')} $={u.get('cost')} fin={rec.get('finish_reason')} "
          f"{str(rec.get('error'))[:130]}", flush=True)
    return rec


def deafness():
    jobs = [(m, r, DEAF_PROMPT, str(J6 / "j1_clean_intro.mp4"), "deaf_j1") for m, r in VIDEO_MODELS]
    with ThreadPoolExecutor(max_workers=5) as ex:
        list(ex.map(lambda j: call(*j), jobs))


def judge(models):
    clips = ["j1_clean_intro", "j2_clean_google", "j3_clean_motsalea",
             "j4_bad_midsentence", "j5_bad_realmontage", "j6_bad_deadair"]
    jobs = [(m, r, JUDGE, str(J6 / f"{c}.mp4"), "judge_" + c) for m, r in models for c in clips]
    with ThreadPoolExecutor(max_workers=5) as ex:
        list(ex.map(lambda j: call(*j), jobs))


if __name__ == "__main__":
    if sys.argv[1] == "deaf":
        deafness()
    else:
        names = sys.argv[2:]
        judge([(m, r) for m, r in VIDEO_MODELS if m in names])
