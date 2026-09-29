#!/usr/bin/env python3
"""T2b — DEEP VISION, decisive sets (face clearly OFF-CENTRE at 0.63, webcam inset
at 0.13, burned-in captions). Ground truth measured by hand on 20-column grids.
Same prompt as apps/worker/app/prompts.py, same ffmpeg frame settings.
"""
import base64, json, os, pathlib, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).parent
OUT = HERE / "outb"; OUT.mkdir(exist_ok=True)
ENV = pathlib.Path("/Users/augustindemeaux/clipfactory-saas/apps/worker/.env")
URL = "https://openrouter.ai/api/v1/chat/completions"


def api_key():
    for line in ENV.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no key")


KEY = api_key()

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

SETS = {
    "t2_head": dict(
        dir="t2_head",
        context="role=payoff, excerpt: cette boutique a fait 4500 euros sur 24 heures, "
                "et la-dessus je prends 45 pourcent de marge, presque 2000 euros de benefice en une journee",
    ),
    "t2_screen": dict(
        dir="t2_screen",
        context="role=proof, excerpt: on regarde les resultats de la campagne Google Ads, "
                "131 impressions, 11 clics, 3,18 dollars de cout, et 69 euros de ventes sur Shopify",
    ),
    "t2_caption": dict(
        dir="t2_caption",
        context="role=payoff, excerpt: on a depense 16 euros pour le nom de domaine, 1 euro pour Shopify, "
                "14 euros de produits, et on a fait 69 euros de ventes",
    ),
}

MODELS = [
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
    ("google/gemini-2.5-flash", False),
    ("google/gemini-2.5-flash-lite", False),
]


def b64(p):
    return base64.b64encode(pathlib.Path(p).read_bytes()).decode()


def post(payload, timeout=300):
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


def run(model, reasoning_off, setname):
    spec = SETS[setname]
    parts = [{"type": "text", "text": deep_vision_user_prompt(segment_context=spec["context"])}]
    for k in range(1, 6):
        parts.append({"type": "image_url",
                      "image_url": {"url": "data:image/jpeg;base64," + b64(HERE / spec["dir"] / f"f{k}.jpg")}})
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
    (OUT / f"t2b__{model.replace('/', '__')}__{setname}.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1))
    u = rec.get("usage") or {}
    print(f"[{setname}] {model:36s} lat={rec['latency_s']:6.1f} in={u.get('prompt_tokens')} "
          f"out={u.get('completion_tokens')} cost=${u.get('cost')} {str(rec.get('error'))[:100]}", flush=True)
    return rec


if __name__ == "__main__":
    jobs = [(m, r, s) for m, r in MODELS for s in SETS]
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda j: run(*j), jobs))
