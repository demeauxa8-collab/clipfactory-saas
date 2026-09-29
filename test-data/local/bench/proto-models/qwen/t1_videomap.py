#!/usr/bin/env python3
"""T1 — VIDEO MAP. Exact repo prompt (VIDEO_MAP_SYSTEM_PROMPT + video_map_user_prompt),
20 frames extracted with the repo's own ffmpeg settings (scale min(512,iw), -q:v 5),
spread over the whole 595 s source. Transcript compacted like _compact_transcript().
"""
import base64, json, os, pathlib, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).parent
D = HERE / "mapframes"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
ENV = pathlib.Path("/Users/augustindemeaux/clipfactory-saas/apps/worker/.env")
URL = "https://openrouter.ai/api/v1/chat/completions"
FIXTURE = pathlib.Path("/Users/augustindemeaux/clipfactory-data/bench/"
                       "fixture_2221f645-ed0e-47b2-8201-417d7c517a39.json")


def api_key():
    for line in ENV.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no key")


KEY = api_key()

VIDEO_MAP_SYSTEM_PROMPT = """\
You are a video understanding model. You receive a series of frames sampled
from a long video, plus a compact transcript summary. Your job is to produce a
JSON description of the video as a sequence of events.

You return ONE strict JSON object. No prose, no markdown.
"""


def video_map_user_prompt(*, duration_seconds, transcript_summary, frame_timestamps):
    ts_lines = "\n".join(f"- frame_{i:03d} @ {ts:.1f}s" for i, ts in enumerate(frame_timestamps))
    return f"""\
Source duration: {duration_seconds} seconds.

Transcript summary (compact, may not contain every word):
{transcript_summary}

Frames attached, in this order:
{ts_lines}

Return JSON with this shape:
{{
  "video_summary": "one-paragraph summary of what happens in the video, max 600 chars",
  "events": [
    {{
      "id": "evt_001",
      "start": <seconds in source>,
      "end":   <seconds in source>,
      "decor": "studio | car | desktop | outdoor | gaming | other",
      "people": "short description",
      "objects": ["string", "..."],
      "action": "short sentence — what happens visually",
      "transcript_summary": "what is being said during this event, max 200 chars",
      "visual_importance": 0..100,
      "narrative_role": "setup | payoff | neutral | transition"
    }}
  ]
}}

Constraints:
- Produce 15 to 35 events covering the whole video.
- Events should not overlap.
- An event covers a coherent visual moment (one decor, one action) — typically 15 to 60 seconds.
- `narrative_role` flags whether the event sets up something ("setup"), is a payoff
  ("payoff"), is filler ("neutral"), or is a visual cut between two themes ("transition").
- Be conservative: do not invent objects you cannot see.
"""


def compact_transcript(text, max_chars=4000):
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars // 2]}\n...\n{text[-max_chars // 2:]}"


TS = json.load(open(D / "ts.json"))
FX = json.load(open(FIXTURE))
TR = compact_transcript(FX["transcript"]["text"])

MODELS = [
    ("qwen/qwen3.7-flash", True),
    ("qwen/qwen3.5-flash-02-23", True),
    ("qwen/qwen3.5-9b", True),
    ("qwen/qwen3-vl-32b-instruct", False),
    ("qwen/qwen3-vl-8b-instruct", False),
    ("qwen/qwen3-vl-30b-a3b-instruct", False),
    ("qwen/qwen3.6-35b-a3b", True),
    ("qwen/qwen3.5-35b-a3b", True),
    ("qwen/qwen3.6-flash", True),
    ("qwen/qwen3.5-27b", True),
    ("qwen/qwen3.6-27b", True),
    ("qwen/qwen3-vl-235b-a22b-instruct", False),
    ("qwen/qwen2.5-vl-72b-instruct", False),
    ("qwen/qwen3.6-plus", True),
    ("qwen/qwen3.7-plus", True),
    ("qwen/qwen3.5-397b-a17b", True),
    ("google/gemini-2.5-flash", False),
    ("google/gemini-2.5-flash-lite", False),
]


def b64(p):
    return base64.b64encode(pathlib.Path(p).read_bytes()).decode()


def post(payload, timeout=600):
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


def run(model, reasoning_off):
    parts = [{"type": "text", "text": video_map_user_prompt(
        duration_seconds=595, transcript_summary=TR, frame_timestamps=TS)}]
    for i, ts in enumerate(TS):
        parts.append({"type": "text", "text": f"{ts:.1f}s"})
        parts.append({"type": "image_url",
                      "image_url": {"url": "data:image/jpeg;base64," + b64(D / f"map_{i:03d}.jpg")}})
    payload = {"model": model,
               "messages": [{"role": "system", "content": VIDEO_MAP_SYSTEM_PROMPT},
                            {"role": "user", "content": parts}],
               "max_tokens": 4096, "temperature": 0.2, "usage": {"include": True}}
    if reasoning_off:
        payload["reasoning"] = {"enabled": False}
    body, dt, err = post(payload)
    rec = {"model": model, "latency_s": round(dt, 1)}
    if err:
        rec["error"] = err
    else:
        rec["usage"] = body.get("usage")
        ch = (body.get("choices") or [{}])[0]
        rec["finish_reason"] = ch.get("finish_reason")
        rec["text"] = (ch.get("message") or {}).get("content")
        rec["provider"] = body.get("provider")
    (OUT / f"t1__{model.replace('/', '__')}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    u = rec.get("usage") or {}
    print(f"{model:38s} lat={rec['latency_s']:6.1f} in={u.get('prompt_tokens')} out={u.get('completion_tokens')} "
          f"cost=${u.get('cost')} fin={rec.get('finish_reason')} {str(rec.get('error'))[:150]}", flush=True)
    return rec


if __name__ == "__main__":
    sel = sys.argv[1:] or None
    jobs = [(m, r) for m, r in MODELS if not sel or any(s in m for s in sel)]
    with ThreadPoolExecutor(max_workers=5) as ex:
        list(ex.map(lambda j: run(*j), jobs))
