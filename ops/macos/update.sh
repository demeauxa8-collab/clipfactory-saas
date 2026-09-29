#!/bin/bash
set -euo pipefail

repo="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo"
git pull --ff-only
apps/api/.venv/bin/pip install -e 'apps/api[dev]'
apps/worker/.venv/bin/pip install -e 'apps/worker[dev,mlx]'
brew upgrade yt-dlp || test "$(brew outdated yt-dlp | wc -l | tr -d ' ')" = 0
"$repo/ops/macos/install.sh"
"$repo/ops/macos/doctor.sh"
