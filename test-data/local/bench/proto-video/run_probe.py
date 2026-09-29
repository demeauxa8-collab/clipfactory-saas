#!/usr/bin/env python3
"""Probe OpenRouter video/audio-native models with real media from the ClipFactory bench source."""
import base64, json, mimetypes, os, pathlib, sys, time
import urllib.request, urllib.error

HERE = pathlib.Path(__file__).parent
ENV = pathlib.Path("/Users/augustindemeaux/clipfactory-saas/apps/worker/.env")

def api_key():
    for line in ENV.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no key")

KEY = api_key()
URL = "https://openrouter.ai/api/v1/chat/completions"

JUDGE_PROMPT = """Tu es directeur artistique pour une agence qui coupe des vlogs YouTube FR en clips verticaux TikTok/Reels.
On te donne UN extrait vidéo brut. REGARDE et ECOUTE-le vraiment.
Reponds UNIQUEMENT avec un objet JSON, sans texte autour, avec exactement ces cles :
{
 "hook_2s": {"score": 0-10, "why": "ce que l'on voit/entend precisement dans les 2 premieres secondes"},
 "speaker_energy": {"score": 0-10, "debit": "lent|normal|rapide", "why": ""},
 "prise_quality": {"score": 0-10, "issues": ["cadrage","lumiere","son","stabilite","autre"], "why": ""},
 "scene_description": "ce que tu vois: lieu, tenue, objets, incrustations de texte a l'ecran",
 "on_screen_text": ["textes exacts lus a l'ecran"],
 "recommended_cut": {"start_s": 0.0, "end_s": 0.0, "why": ""},
 "dead_air_s": [[start,end]],
 "cut_detected": {"count": 0, "timestamps_s": [], "description": "changements de plan/lieu que tu vois"},
 "raccord_understandable": {"verdict": "oui|non|na", "why": "si l'extrait saute d'un moment a un autre, est-ce que le lien se comprend ?"},
 "verdict": "publiable|a_retravailler|inutilisable"
}
Sois factuel et severe. Si tu ne peux pas percevoir quelque chose (ex. le son), dis-le explicitement dans le champ "why"."""

AUDIO_PROMPT = """Tu es monteur pour des clips verticaux TikTok/Reels a partir de vlogs FR.
On te donne UNIQUEMENT la piste AUDIO d'un extrait. ECOUTE-la.
Reponds UNIQUEMENT avec un objet JSON :
{
 "transcription": "ce que tu entends, mot a mot",
 "hook_2s": {"score": 0-10, "why": "ce qui est dit/entendu dans les 2 premieres secondes"},
 "debit": {"label": "lent|normal|rapide", "mots_par_minute_estimes": 0, "why": ""},
 "energy": {"score": 0-10, "why": "intonation, variation, conviction"},
 "audio_quality": {"score": 0-10, "issues": ["bruit","vent","echo","saturation","souffle","aucun"], "why": ""},
 "silences_s": [[start,end]],
 "recommended_cut": {"start_s": 0.0, "end_s": 0.0, "why": ""},
 "verdict": "publiable|a_retravailler|inutilisable"
}
Sois factuel. Si tu n'entends rien, dis-le."""


def b64(path):
    return base64.b64encode(pathlib.Path(path).read_bytes()).decode()


def post(payload, timeout=900):
    """curl instead of urllib: the system python has no CA bundle."""
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        body_file = f.name
    t0 = time.time()
    try:
        p = subprocess.run(
            ["curl", "-sS", "--max-time", str(timeout), URL,
             "-H", f"Authorization: Bearer {KEY}",
             "-H", "Content-Type: application/json",
             "--data-binary", "@" + body_file],
            capture_output=True, text=True)
        dt = time.time() - t0
        if p.returncode != 0:
            return None, dt, f"curl rc={p.returncode}: {p.stderr[:600]}"
        try:
            body = json.loads(p.stdout)
        except Exception:
            return None, dt, f"non-json: {p.stdout[:800]}"
        if "error" in body and not body.get("choices"):
            return None, dt, f"API error: {json.dumps(body['error'])[:900]}"
        return body, dt, None
    finally:
        os.unlink(body_file)


def run_video(model, video_path, extra="", fps=None, tag=""):
    parts = [{"type": "text", "text": JUDGE_PROMPT + ("\n\n" + extra if extra else "")}]
    vp = {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64(video_path)}"}}
    if fps:
        vp["video_url"]["fps"] = fps
    parts.append(vp)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": parts}],
        "max_tokens": 3000,
        "temperature": 0.2,
        "reasoning": {"enabled": False},
        "usage": {"include": True},
    }
    body, dt, err = post(payload)
    return record(model, tag or pathlib.Path(video_path).name, "video", body, dt, err, video_path)


def run_audio(model, audio_path, fmt, tag=""):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": AUDIO_PROMPT},
            {"type": "input_audio", "input_audio": {"data": b64(audio_path), "format": fmt}},
        ]}],
        "max_tokens": 3000,
        "temperature": 0.2,
        "reasoning": {"enabled": False},
        "usage": {"include": True},
    }
    body, dt, err = post(payload)
    return record(model, tag or pathlib.Path(audio_path).name, "audio", body, dt, err, audio_path)


def record(model, media, kind, body, dt, err, path):
    out = {"model": model, "media": media, "kind": kind, "latency_s": round(dt, 1),
           "file_bytes": os.path.getsize(path)}
    if err:
        out["error"] = err
    else:
        out["usage"] = body.get("usage")
        ch = (body.get("choices") or [{}])[0]
        out["finish_reason"] = ch.get("finish_reason")
        out["text"] = (ch.get("message") or {}).get("content")
        out["provider"] = body.get("provider")
    name = f"{model.replace('/','__')}__{kind}__{media.replace('.','_')}.json"
    (HERE / "out").mkdir(exist_ok=True)
    (HERE / "out" / name).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "text"}, ensure_ascii=False)[:600])
    if out.get("text"):
        print("   TEXT>", out["text"][:300].replace("\n", " "))
    print("---")
    return out


BATCH = [
    ("video", "qwen/qwen3.7-flash", "a_talkinghead_30s.mp4", None),
    ("video", "qwen/qwen3.7-flash", "b_montage_concat.mp4", None),
    ("video", "qwen/qwen3.7-flash", "c_screen_20s.mp4", None),
    ("video", "google/gemini-3.1-flash-lite", "a_talkinghead_30s.mp4", None),
    ("video", "google/gemini-3.1-flash-lite", "b_montage_concat.mp4", None),
    ("video", "google/gemini-3.1-flash-lite", "c_screen_20s.mp4", None),
    ("video", "google/gemini-3.5-flash-lite", "b_montage_concat.mp4", None),
    ("video", "minimax/minimax-m3", "b_montage_concat.mp4", None),
    ("audio", "google/gemini-3.1-flash-lite", "a_audio_30s.mp3", "mp3"),
    ("audio", "xiaomi/mimo-v2.5", "a_audio_30s.mp3", "mp3"),
]

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "batch":
        from concurrent.futures import ThreadPoolExecutor
        def go(j):
            kind, model, media, fmt = j
            try:
                if kind == "video":
                    return run_video(model, HERE / media)
                return run_audio(model, HERE / media, fmt)
            except Exception as e:
                print("FAIL", j, e)
        with ThreadPoolExecutor(max_workers=5) as ex:
            list(ex.map(go, BATCH))
    elif cmd == "video":
        run_video(sys.argv[2], HERE / sys.argv[3], extra=(sys.argv[4] if len(sys.argv) > 4 else ""))
    elif cmd == "audio":
        run_audio(sys.argv[2], HERE / sys.argv[3], sys.argv[4])
