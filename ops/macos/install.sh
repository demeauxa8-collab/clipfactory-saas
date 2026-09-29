#!/bin/bash
set -euo pipefail

repo="$(cd "$(dirname "$0")/../.." && pwd)"
launch_dir="$HOME/Library/LaunchAgents"
mkdir -p "$launch_dir" "$HOME/Library/Logs/ClipFactory"

for name in api worker; do
  label="com.clipfactory.$name"
  target="$launch_dir/$label.plist"
  sed -e "s|__HOME__|$HOME|g" -e "s|__REPO__|$repo|g" \
    "$repo/ops/macos/$label.plist" > "$target"
  plutil -lint "$target" >/dev/null
  launchctl bootout "gui/$(id -u)/$label" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$target"
  launchctl kickstart -k "gui/$(id -u)/$label"
done
