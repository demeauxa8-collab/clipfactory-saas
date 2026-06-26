#!/usr/bin/env bash
# Deploy the latest main on a VPS already provisioned with bootstrap-vps.sh.
# Runs as root via sudo. Re-installs Python deps only if pyproject.toml changed.
#
# Usage:
#   sudo /opt/clipfactory/clipfactory-saas/scripts/deploy.sh
#
# Optional flags:
#   --ref <branch|tag|sha>   Checkout something other than origin/main.

set -euo pipefail

APP_USER="${APP_USER:-clipfactory}"
APP_DIR="${APP_DIR:-/opt/clipfactory}"
REPO_DIR="${APP_DIR}/clipfactory-saas"
VENV_API="${APP_DIR}/venv-api"
VENV_WORKER="${APP_DIR}/venv-worker"

REF="origin/main"
while [[ $# -gt 0 ]]; do
	case "$1" in
		--ref) REF="$2"; shift 2 ;;
		*) echo "unknown flag: $1" >&2; exit 2 ;;
	esac
done

if [[ ${EUID} -ne 0 ]]; then
	echo "Need root. Re-run with sudo." >&2
	exit 1
fi

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

cd "${REPO_DIR}"

BEFORE_SHA=$(sudo -u "${APP_USER}" git rev-parse HEAD)
BEFORE_API=$(sha1sum apps/api/pyproject.toml | awk '{print $1}')
BEFORE_WORKER=$(sha1sum apps/worker/pyproject.toml | awk '{print $1}')

log "fetching ${REF}"
sudo -u "${APP_USER}" git fetch --prune origin
sudo -u "${APP_USER}" git reset --hard "${REF}"

AFTER_SHA=$(sudo -u "${APP_USER}" git rev-parse HEAD)
AFTER_API=$(sha1sum apps/api/pyproject.toml | awk '{print $1}')
AFTER_WORKER=$(sha1sum apps/worker/pyproject.toml | awk '{print $1}')

if [[ "${BEFORE_SHA}" == "${AFTER_SHA}" ]]; then
	log "already at ${AFTER_SHA}, nothing to deploy"
	exit 0
fi

log "deploying ${BEFORE_SHA:0:7} -> ${AFTER_SHA:0:7}"

# Re-install deps only when their lockfile changed — saves ~30s on doc-only deploys.
if [[ "${BEFORE_API}" != "${AFTER_API}" ]]; then
	log "apps/api deps changed, reinstalling"
	sudo -u "${APP_USER}" "${VENV_API}/bin/pip" install -e apps/api
fi
if [[ "${BEFORE_WORKER}" != "${AFTER_WORKER}" ]]; then
	log "apps/worker deps changed, reinstalling"
	sudo -u "${APP_USER}" "${VENV_WORKER}/bin/pip" install -e apps/worker
fi

# Bump systemd + Caddy config if they were edited in this deploy.
if git diff "${BEFORE_SHA}..${AFTER_SHA}" --name-only | grep -q '^infra/systemd/'; then
	log "systemd units changed, reinstalling"
	install -m 0644 infra/systemd/clipfactory-api.service /etc/systemd/system/clipfactory-api.service
	install -m 0644 infra/systemd/clipfactory-worker.service /etc/systemd/system/clipfactory-worker.service
	systemctl daemon-reload
fi
if git diff "${BEFORE_SHA}..${AFTER_SHA}" --name-only | grep -q '^infra/Caddyfile$'; then
	log "Caddyfile changed, reloading caddy"
	install -m 0644 infra/Caddyfile /etc/caddy/Caddyfile
	systemctl reload caddy
fi

log "restarting services"
systemctl restart clipfactory-api clipfactory-worker

# Smoke test: API should answer 200 on /health within 10 seconds.
for i in $(seq 1 10); do
	if curl -fsS -m 2 http://127.0.0.1:8000/health >/dev/null 2>&1; then
		log "deploy OK · ${AFTER_SHA:0:7} · API healthy"
		exit 0
	fi
	sleep 1
done

echo
echo "⚠️  API not responding on /health after 10s. Check:" >&2
echo "    journalctl -u clipfactory-api -n 80 --no-pager" >&2
exit 1
