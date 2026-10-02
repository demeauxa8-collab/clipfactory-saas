# B0 private golden harness

The harness invokes the unchanged `app.pipeline.runner.run_job` against its own
short-lived PostgreSQL cluster. It does not accept a database URL and never uses
production credits, Redis, storage, subscriptions or model overrides. Only the
three provider API keys are read from the supplied ignored credentials file.

Source URLs, briefs, source media, rendered clips, reports and human ratings must
remain outside this public repository. Validate the private reference list before
the full run; a provisional mini run can be explicitly authorized separately.

## Commands

Run from the repository root with the worker's Python environment and media tools
on PATH. PostgreSQL binaries must already be available. No services are installed
or started at login by the harness.

```sh
PYTHONPATH=apps/worker python apps/worker/scripts/golden_sources.py \
  --config "$HOME/clipfactory-golden/sources.toml" \
  --root "$HOME/clipfactory-golden/sources"

PYTHONPATH=apps/worker python apps/worker/scripts/golden_run.py \
  --config "$HOME/clipfactory-golden/sources.toml" \
  --root "$HOME/clipfactory-golden" --budget 3.00 --judge \
  --credentials-file /absolute/private/worker.env \
  --catalog /absolute/private/openrouter-model-catalog.json \
  --pg-bin /absolute/path/to/postgresql/bin

PYTHONPATH=apps/worker python apps/worker/scripts/golden_review.py \
  /absolute/private/path/to/run
```

`--sources` accepts comma-separated IDs from the private config; `--no-judge`
disables the separate observation pass. The mini run must use `--budget 1.50`.
If an interrupted attempt was made, `--prior-ledger /private/prior-attempt-ledger.json`
carries its costs and conservative reserves into that same mission cap.
The code must be committed before a paid run. Run identities contain UTC date,
code commit and the models-lock hash; the full hashes are in `report.json`.
Runtime API/DB package versions must match `requirements.lock` before a paid
request. Both httpx and newer SDK httpx2 transports are guarded when present.

The TOML contains `[[sources]]` entries with `id`, `voices`, `voices_basis`, then
`[sources.campaign]` with `audience`, `niche`, `tone`, `goal`, `example_hooks`
(exactly three). Downloaded media is capped at 720p, hashed, and made read-only.
Existing frozen sources are verified, never overwritten. The runner's attempt
journal preloads the original media and heatmap cache before the job is claimed.

## Accounting

The benchmark intercepts HTTP requests in its own process. Each actual attempt,
including internal SDK retries, reserves a conservative cost ceiling before it
can be sent. OpenRouter responses settle to `usage.cost`, even if their answer is
discarded by the parser. OpenAI ASR uses returned duration at the Whisper tariff
(rounded up to whole seconds). Anthropic uses returned usage at lock tariffs.
Ambiguous failures and missing usage retain their reservation. Unknown models or
endpoints fail closed. The ledger survives interruptions and cannot be reused or
overwritten for a second paid run.

Input ceilings count UTF-8 bytes as text tokens, 4,096 tokens per image and 4,096
per second of known native-video duration, plus overhead and a 10% price margin.
Output ceilings include the actual request's `max_tokens`, including any raised
retry ceiling. A provider cost that violates a reserved ceiling is recorded and
halts further requests: it must never be reported as a successful budget check.
Catalog prices are checked against the model lock before the run. Provider billing
invoices are not reconciled; reports distinguish usage, tariff calculation and
conservative uncertain reservations. Budget enforcement is local, not a change to
the shared provider account's spending limit.

## Interpretation

Closed connector and pronoun flags are deterministic heuristics, not semantic
proof. Articles alone are not marked dependent. Sentence-end tolerance is 0.5s
against ASR segment ends with terminal punctuation; word-boundary tolerance is 1ms. Target
duration is 15-60s. Noir/silence reuses actual render QC. Missing heatmaps are N/A.
Audience overlap uses the top 10% of buckets by value, counts repeated shots in playback duration,
and 1,000 seeded random windows of equal duration.

Native-video judge verdicts are separate artifacts. They never affect delivery,
ranking, retries or credits. Judge errors remain visible as missing verdicts.
Model publishability must not be presented as human publishability.
Clips exceeding the 18 MB inline limit receive a judge-only 720p compressed proxy
with the full original audio and duration. Its use is recorded in the verdict;
compression may affect caption/framing judgments. Delivered clips stay untouched.

The portable review folder needs no server, CDN, sign-in or API. It includes only
opaque shuffled clip identities, media and excerpts. The private identity mapping
and judge verdicts are outside the review folder. Ratings are stored per run in
the browser and exported as UTF-8 CSV. Copy the **whole** review folder to another
Mac; local browser storage does not travel with it, so export ratings before moving.

## Offline verification

Unit tests mock HTTP providers. The PostgreSQL integration test uses a generated
34-second source, fake ASR/LLM providers, actual selection anchoring, vision frame
extraction, scoring, FFmpeg captions/render, QC, local delivery and artifact export.
No paid requests are made by these tests. CI runs them against disposable PostgreSQL.
The B0 branch explicitly disables its Vercel Git auto-deployment.

Section 6 (human yield and judge agreement) remains pending human ratings.

`golden_report.py RUN --sources-root /private/sources` recomputes only free
measurements from retained manifests/transcripts. It records the measurement-code
revision separately from the original paid runner revision, which stays unchanged.
