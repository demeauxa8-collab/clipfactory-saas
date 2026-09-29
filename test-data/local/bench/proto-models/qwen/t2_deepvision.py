#!/usr/bin/env python3
"""T2 — DEEP VISION per segment, every Qwen vision model reachable on OpenRouter,
against the REAL repo prompt (apps/worker/app/prompts.py) and 3 hand-labelled
5-frame sets extracted with the pipeline's own ffmpeg settings.
"""
import base64, json, os, pathlib, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).parent
FRAMES = HERE / "frames"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
ENV = pathlib.Path("/Users/augustindemeaux/clipfactory-saas/apps/worker/.env")
URL = "https://openrouter.ai/api/v1/chat/completions"


def api_key():
    for line in ENV.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no key")


KEY = api_key()

# ---- EXACT prompts from apps/worker/app/prompts.py ----
DEEP_VISION_SYSTEM_PROMPT = """\
You are a visual analyst for short-form video. You receive 4 to 6 still frames
from a single candidate segment, plus a one-line description of what is being
said. You return ONE strict JSON object describing the visual quality of this
segment.

No prose. No markdown. JSON only.
"""


def deep_vision_user_prompt(*, segment_context: str) -> str:
    return f"""\
Context — what is being said during this segment:
{segment_context}

Return strict JSON:
{{
  "decor": "studio podcast | car | desktop screen | outdoor | gaming setup | other",
  "person_visible": true|false,
  "energy": 0..100,
  "action": "talking head | reaction | pointing at screen | demo | other",
  "proof_objects": ["string", ...],
  "problems": ["dark" | "no face" | "unreadable slide" | "blurry" | "low contrast", ...],
  "visual_score": 0..100,
  "face_center_x": 0.0..1.0 or null,
  "burned_captions": true|false
}}

Scoring rules:
- visual_score > 70 when a clear face is visible, lighting is good, and the
  moment has visible action or visible proof of what is being said.
- visual_score < 40 when the frames are dark, faceless, or unreadable.
- visual_score reflects how well this would perform as a vertical short.
- face_center_x is the average horizontal position of the main speaker's face
  across the frames (0.0 = far left edge, 0.5 = centre, 1.0 = far right edge),
  or null when no face is visible. It is used to re-crop the source to a
  full-height 9:16 vertical framing centred on the speaker.
- burned_captions is true when the source already has subtitles/captions burned
  into the picture (visible on-screen text tracking the speech), so we avoid
  adding a second caption layer.
"""


# ---- the 3 hand-labelled sets, context taken from the real fixture transcript ----
SETS = {
    "A_dubai": dict(
        context="role=hook, source_seconds=[4.0, 24.0], excerpt: partir de 1 euro et arriver le plus haut possible, "
                "je vais vous montrer comment je fais du dropshipping",
        truth=dict(decor_ok={"outdoor"}, person_visible=True, face=0.46, tol=0.10,
                   burned_captions=False, screen=False),
    ),
    "B_screen": dict(
        context="role=proof, source_seconds=[294.0, 306.0], excerpt: on regarde le volume de recherche sur montre gps, "
                "5400 recherches par mois, le CPC est de 17 centimes, et sur Google Trends la tendance",
        truth=dict(decor_ok={"desktop screen"}, person_visible=True, face=0.075, tol=0.10,
                   burned_captions=False, screen=True),
    ),
    "C_car": dict(
        context="role=payoff, source_seconds=[416.5, 425.5], excerpt: je prends la voiture pour aller chercher le colis, "
                "on va voir si la campagne a rapporte",
        truth=dict(decor_ok={"car"}, person_visible=True, face=0.42, tol=0.10,
                   burned_captions=False, screen=False),
    ),
    "E_mixed": dict(
        context="role=setup, source_seconds=[99.0, 111.0], excerpt: je trouve une annonce de garde de chien sur "
                "l'application, je vais garder un chien 24 heures pour 100 euros",
        truth=dict(decor_ok={"other"}, person_visible=True, face=0.44, tol=0.10,
                   burned_captions=True, screen=False),
    ),
}

MODELS = [
    # (id, reasoning_off)
    ("qwen/qwen3.7-flash", True),
    ("qwen/qwen3.5-flash-02-23", True),
    ("qwen/qwen3.5-9b", True),
    ("qwen/qwen3-vl-32b-instruct", False),
    ("qwen/qwen3-vl-8b-instruct", False),
    ("qwen/qwen3.6-35b-a3b", True),
    ("qwen/qwen3.5-35b-a3b", True),
    ("qwen/qwen3-vl-30b-a3b-instruct", False),
    ("qwen/qwen3-vl-8b-thinking", False),
    ("qwen/qwen3.6-flash", True),
    ("qwen/qwen3.5-27b", True),
    ("qwen/qwen3-vl-30b-a3b-thinking", False),
    ("qwen/qwen3-vl-235b-a22b-instruct", False),
    ("qwen/qwen2.5-vl-72b-instruct", False),
    ("qwen/qwen3.5-plus-02-15", True),
    ("qwen/qwen3.5-122b-a10b", True),
    ("qwen/qwen3.5-plus-20260420", True),
    ("qwen/qwen3.7-plus", True),
    ("qwen/qwen3.6-plus", True),
    ("qwen/qwen3.5-397b-a17b", True),
    ("qwen/qwen3-vl-235b-a22b-thinking", False),
    ("qwen/qwen3.6-27b", True),
    ("qwen/qwen3.8-max", True),
    # baselines
    ("google/gemini-2.5-flash", False),
    ("google/gemini-2.5-flash-lite", False),
]


def b64(p):
    return base64.b64encode(pathlib.Path(p).read_bytes()).decode()


def post(payload, timeout=300):
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
            return None, dt, f"non-json: {p.stdout[:400]}"
        if "error" in body and not body.get("choices"):
            return None, dt, f"API error: {json.dumps(body['error'])[:500]}"
        return body, dt, None
    finally:
        os.unlink(bf)


def run(model, reasoning_off, setname):
    spec = SETS[setname]
    parts = [{"type": "text", "text": deep_vision_user_prompt(segment_context=spec["context"])}]
    for k in range(5):
        parts.append({"type": "image_url",
                      "image_url": {"url": "data:image/jpeg;base64," + b64(FRAMES / f"{setname}_f{k}.jpg")}})
    payload = {"model": model,
               "messages": [{"role": "system", "content": DEEP_VISION_SYSTEM_PROMPT},
                            {"role": "user", "content": parts}],
               "max_tokens": 900, "temperature": 0.2, "usage": {"include": True}}
    if reasoning_off:
        payload["reasoning"] = {"enabled": False}
    body, dt, err = post(payload)
    rec = {"model": model, "set": setname, "latency_s": round(dt, 1)}
    if err:
        rec["error"] = err
    else:
        rec["usage"] = body.get("usage")
        ch = (body.get("choices") or [{}])[0]
        rec["finish_reason"] = ch.get("finish_reason")
        rec["text"] = (ch.get("message") or {}).get("content")
        rec["provider"] = body.get("provider")
    (OUT / f"t2__{model.replace('/', '__')}__{setname}.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1))
    u = rec.get("usage") or {}
    print(f"[{setname}] {model:38s} lat={rec['latency_s']:6.1f} in={u.get('prompt_tokens')} "
          f"out={u.get('completion_tokens')} cost=${u.get('cost')} {str(rec.get('error'))[:120]}", flush=True)
    return rec


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    jobs = [(m, r, s) for m, r in MODELS for s in SETS if (only is None or only in m)]
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(lambda j: run(*j), jobs))
