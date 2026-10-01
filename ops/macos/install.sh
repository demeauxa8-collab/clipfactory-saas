#!/bin/bash
set -euo pipefail

repo="$(cd "$(dirname "$0")/../.." && pwd)"
"$repo/apps/api/.venv/bin/python" "$repo/ops/macos/maintenance_guard.py"
launch_dir="$HOME/Library/LaunchAgents"
mkdir -p "$launch_dir" "$HOME/Library/Logs/ClipFactory"

for name in api worker; do
  label="com.clipfactory.$name"
  target="$launch_dir/$label.plist"
  sed -e "s|__HOME__|$HOME|g" -e "s|__REPO__|$repo|g" \
    "$repo/ops/macos/$label.plist" > "$target"
  plutil -lint "$target" >/dev/null
  launchctl bootout "gui/$(id -u)/$label" >/dev/null 2>&1 || true
  # launchd may take a moment to release a label after bootout.
  for attempt in 1 2 3 4 5; do
    if launchctl bootstrap "gui/$(id -u)" "$target"; then
      break
    fi
    if [ "$attempt" -eq 5 ]; then
      echo "Could not register $label" >&2
      exit 1
    fi
    sleep 1
  done
  launchctl kickstart -k "gui/$(id -u)/$label"
done
