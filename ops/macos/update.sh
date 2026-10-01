#!/bin/bash
set -euo pipefail

repo="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo"
"$repo/apps/api/.venv/bin/python" "$repo/ops/macos/maintenance_guard.py"
restore_worker() {
  if ! launchctl print "gui/$(id -u)/com.clipfactory.worker" >/dev/null 2>&1; then
    launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.clipfactory.worker.plist"
  fi
}
trap restore_worker EXIT
# Leave new admissions queued while runtime files are updated.
launchctl bootout "gui/$(id -u)/com.clipfactory.worker" >/dev/null 2>&1 || true
git pull --ff-only
apps/api/.venv/bin/pip install -e 'apps/api[dev]'
apps/worker/.venv/bin/pip install -e 'apps/worker[dev,mlx]'
brew upgrade yt-dlp || test "$(brew outdated yt-dlp | wc -l | tr -d ' ')" = 0
"$repo/ops/macos/install.sh"
"$repo/ops/macos/doctor.sh"
