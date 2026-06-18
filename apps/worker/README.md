# ClipFactory worker

Pulls clipping jobs from Redis and runs the 17-step pipeline (see `docs/pipeline.md`).

## Install

```bash
cd apps/worker
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fill values
```

System binaries required on the host:

```bash
brew install ffmpeg yt-dlp   # macOS dev
# or apt install ffmpeg yt-dlp on a Linux host
```

## Run

```bash
python -m app.main
```

The worker connects to:
- Postgres (`DATABASE_URL`)
- Redis (`REDIS_URL`)
- Cloudflare R2 (`R2_*`)
- OpenAI gpt-4o-mini-transcribe API (transcription)
- OpenRouter (DeepSeek text + Gemini/Qwen vision) — primary
- Anthropic Claude Haiku — fallback

It then `BLPOP`s the queue key `clipfactory:jobs:queue` and runs `run_job` for each entry.

## Pipeline summary

See `docs/pipeline.md` for the 17 ordered steps. Logging is JSON via `structlog`.

## Cost accounting

Each finished job writes the following columns into `jobs`:
- `transcription_cost_cents`
- `analysis_tokens`
- `vision_frames_count`
- `render_seconds`
- `storage_bytes`
- `total_cost_estimate_cents`

V1 estimates are model-based (see `app/settings.py`). Wire to real provider invoices in V2.
