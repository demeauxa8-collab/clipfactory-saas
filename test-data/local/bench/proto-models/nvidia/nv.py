#!/usr/bin/env python3
"""NVIDIA + specialised-provider probe.
Phase 1 = deafness test (caption-free clip, word-for-word transcription)
Phase 2 = judge6 T3 benchmark
Phase 3 = T2 face_center_x
Writes ONLY inside proto-models/nvidia/.
"""
import base64, json, os, pathlib, re, subprocess, sys, tempfile, time

HERE = pathlib.Path(__file__).parent
JUDGE6 = pathlib.Path("/Users/augustindemeaux/clipfactory-data/bench/proto-video/judge6")
ENV = pathlib.Path("/Users/augustindemeaux/clipfactory-saas/apps/worker/.env")
URL = "https://openrouter.ai/api/v1/chat/completions"


def api_key():
    for line in ENV.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no key")


KEY = api_key()


def b64(p):
    return base64.b64encode(pathlib.Path(p).read_bytes()).decode()


def post(payload, timeout=900):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        bf = f.name
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
            return None, dt, f"non-json: {p.stdout[:500]}"
        if "error" in body and not body.get("choices"):
            return None, dt, f"API error: {json.dumps(body['error'])[:600]}"
        return body, dt, None
    finally:
        os.unlink(bf)


def vpart(path):
    return {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64(path)}"}}


def apart(path, fmt="mp3"):
    return {"type": "input_audio", "input_audio": {"data": b64(path), "format": fmt}}


def ipart(path):
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(path)}"}}


def call(model, parts, tag, outdir, max_tokens=3000, reasoning_off=True, temp=0.1):
    out = HERE / outdir
    out.mkdir(parents=True, exist_ok=True)
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
        msg = ch.get("message") or {}
        rec["text"] = msg.get("content")
        rec["reasoning"] = (msg.get("reasoning") or "")[:800]
        rec["provider"] = body.get("provider")
    (out / f"{model.replace('/','__').replace(':','_')}__{tag}.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1))
    u = rec.get("usage") or {}
    pd = u.get("prompt_tokens_details") or {}
    print(f"[{tag}] {model} lat={rec['latency_s']}s p={u.get('prompt_tokens')} "
          f"vid={pd.get('video_tokens')} aud={pd.get('audio_tokens')} img={pd.get('image_tokens')} "
          f"out={u.get('completion_tokens')} $={u.get('cost')} fin={rec.get('finish_reason')} "
          f"err={str(rec.get('error'))[:180]}", flush=True)
    if rec.get("text"):
        print("    >", rec["text"][:220].replace("\n", " "), flush=True)
    return rec


# ---------------- Phase 1: deafness ----------------
DEAF = """Ceci est un extrait video de 14 secondes d'un vlog francais.
Ta seule tache : TRANSCRIRE MOT A MOT ce que tu ENTENDS dans la bande son.
N'invente rien. Ne decris pas l'image. Ne lis pas le texte a l'ecran.
Si tu ne percois AUCUN son / si tu n'as pas acces a l'audio, reponds exactement : AUCUN_SON
Reponds en JSON strict : {"acces_audio": true/false, "transcription": "...", "langue": "..."}"""


def phase1(models):
    from concurrent.futures import ThreadPoolExecutor
    jobs = [(m, [{"type": "text", "text": DEAF}, vpart(HERE / "deaf_probe_14s.mp4")],
             f"deaf_{m.split('/')[-1][:28]}", "out_deaf", 1500, ro) for m, ro in models]
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda j: call(*j), jobs))


if __name__ == "__main__":
    pass


# ---------------- Phase 2: judge6 (T3) ----------------
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

CLIPS = ["j1_clean_intro", "j2_clean_google", "j3_clean_motsalea",
         "j4_bad_midsentence", "j5_bad_realmontage", "j6_bad_deadair"]


def phase2(models, outdir="out_judge"):
    from concurrent.futures import ThreadPoolExecutor
    jobs = []
    for m, ro, mt in models:
        for c in CLIPS:
            jobs.append((m, [{"type": "text", "text": JUDGE_V}, vpart(JUDGE6 / f"{c}.mp4")],
                         f"J_{c}", outdir, mt, ro))
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda j: call(*j), jobs))


# ---------------- Phase 3: T2 deep vision (face_center_x) ----------------
T2 = """Tu analyses 5 frames consecutives d'un segment de vlog FR destine a un clip vertical 9:16.
JSON strict, rien d'autre :
{"decor":"","person_visible":true/false,"face_center_x":0.0,"energy":0-10,"action":"",
 "proof_objects":[],"problems":[],"visual_score":0-10,"burned_captions":true/false}
face_center_x = position HORIZONTALE du centre du visage principal, 0.0 = bord GAUCHE de l'image,
0.5 = centre, 1.0 = bord DROIT. Sois precis a 0.05 pres : cette valeur sert a recadrer en 9:16."""


def phase3(models, framedirs, outdir="out_t2"):
    from concurrent.futures import ThreadPoolExecutor
    jobs = []
    for m, ro in models:
        for fd in framedirs:
            frames = sorted((HERE / fd).glob("*.jpg"))
            parts = [{"type": "text", "text": T2}] + [ipart(f) for f in frames]
            jobs.append((m, parts, f"T2_{fd}", outdir, 1200, ro))
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda j: call(*j), jobs))
