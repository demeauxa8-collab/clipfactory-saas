# ClipFactory on the Mac Studio

Run `ops/macos/install.sh` after placing private `.env` files in both apps.
The API and worker run as user LaunchAgents. Redis is a separate Homebrew
service. The API listens on `127.0.0.1:8000`; Tailscale Funnel exposes only
that port.

## Operations

- Check health: `ops/macos/doctor.sh`.
- Restart a service: `launchctl kickstart -k gui/$(id -u)/com.clipfactory.worker`
  (replace `worker` with `api` as needed).
- Logs: `tail -f ~/Library/Logs/ClipFactory/worker.err.log`.
- Update code and yt-dlp: `ops/macos/update.sh`.
  Update/install scripts refuse maintenance while an attempt is active.
- Stop the worker for maintenance: `launchctl bootout gui/$(id -u)/com.clipfactory.worker`.
  A running job receives cancellation and is marked failed with its reserved
  credits refunded; restart does not automatically resume that attempt. A
  Queued jobs are recovered from Postgres even if the Redis delivery was lost.
  A durable journal in `WORKER_STATE_DIR` (default: `WORKER_TMP_DIR/.state`)
  also refunds an owned interrupted attempt after an abrupt process crash or
  power loss. It never re-bills or refunds an already completed job.
- After a power loss: if FileVault prevents automatic login, unlock the Mac,
  then run `ops/macos/doctor.sh`.

Delivered clips live in `STORAGE_LOCAL_DIR`. Keep at least 40 GB free. No
automatic retention or backup is installed; connect an external disk and
configure a backup before relying on this as the only copy. When the Mac or
home Internet is offline, clients cannot download clips. `yt-dlp` needs regular
updates as YouTube changes.

## Browser access and local ASR

Browser API calls use the site's `/api/backend` rewrite to the public Funnel
URL. For signed media, set `MEDIA_BASE_URL` in the API to the production site's
`https://<site>/api/backend` URL. This keeps browsers from needing permission
to reach a local network directly. `API_BASE_URL` remains the Funnel URL.

Measure local ASR before switching production:
`apps/worker/.venv/bin/python ops/macos/benchmark_asr.py /absolute/source.mp4 /absolute/report.json`.
The comparison uses the first 180 seconds, the fixed local model, raw zero-length
word rates, cleaned/normalized difflib word alignment and matching word starts.
Keep OpenAI if any acceptance gate fails. The benchmark does not change settings.
