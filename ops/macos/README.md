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
- Stop the worker for maintenance: `launchctl bootout gui/$(id -u)/com.clipfactory.worker`.
  A running job receives cancellation and is marked failed with its reserved
  credits refunded; restart does not automatically resume that attempt. A
  queued job stays in Redis unless it was already popped by the worker.
- After a power loss: if FileVault prevents automatic login, unlock the Mac,
  then run `ops/macos/doctor.sh`.

Delivered clips live in `STORAGE_LOCAL_DIR`. Keep at least 40 GB free. No
automatic retention or backup is installed; connect an external disk and
configure a backup before relying on this as the only copy. When the Mac or
home Internet is offline, clients cannot download clips. `yt-dlp` needs regular
updates as YouTube changes.
