#!/bin/bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd)"
exec "$repo/apps/api/.venv/bin/python" "$repo/ops/macos/doctor.py"
