#!/usr/bin/env bash
# Bootstrap a fresh Ubuntu 24.04 host as ClipFactory API + worker.
# Idempotent: re-running on an already-set-up box only updates what changed.
#
# Usage (as root or via sudo):
#   curl -fsSL https://raw.githubusercontent.com/demeauxa8-collab/clipfactory-saas/main/scripts/bootstrap-vps.sh | sudo bash
#
# Or after cloning:
#   sudo ./scripts/bootstrap-vps.sh
#
# After this script finishes you still need to:
#   1. Fill /opt/clipfactory/clipfactory-saas/apps/api/.env
#   2. Fill /opt/clipfactory/clipfactory-saas/apps/worker/.env
#   3. Point DNS api.clipfactory.app -> this VPS IPv4
#   4. systemctl restart clipfactory-api clipfactory-worker caddy

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/demeauxa8-collab/clipfactory-saas.git}"
APP_USER="${APP_USER:-clipfactory}"
APP_DIR="${APP_DIR:-/opt/clipfactory}"
REPO_DIR="${APP_DIR}/clipfactory-saas"
VENV_API="${APP_DIR}/venv-api"
VENV_WORKER="${APP_DIR}/venv-worker"
LOG_DIR="/var/log/clipfactory"
TMP_DIR="/tmp/clipfactory"

if [[ ${EUID} -ne 0 ]]; then
	echo "This script needs root. Re-run with sudo." >&2
	exit 1
fi

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

log "1/8 apt update + base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
	ca-certificates curl git \
	python3 python3-venv python3-pip \
	ffmpeg \
	redis-server \
	caddy \
	ufw \
	unattended-upgrades

# yt-dlp from PyPI is fresher than the apt package — install it in the worker venv later.

log "2/8 unattended security upgrades"
dpkg-reconfigure -fnoninteractive unattended-upgrades >/dev/null 2>&1 || true

log "3/8 firewall (ufw)"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose

log "4/8 app user + directories"
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
	useradd --system --create-home --home-dir "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
fi
mkdir -p "${APP_DIR}" "${LOG_DIR}" "${TMP_DIR}"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}" "${LOG_DIR}" "${TMP_DIR}"

log "5/8 clone or update repo"
if [[ ! -d "${REPO_DIR}/.git" ]]; then
	sudo -u "${APP_USER}" git clone --depth 50 "${REPO_URL}" "${REPO_DIR}"
else
	sudo -u "${APP_USER}" git -C "${REPO_DIR}" fetch --prune origin
	sudo -u "${APP_USER}" git -C "${REPO_DIR}" checkout main
	sudo -u "${APP_USER}" git -C "${REPO_DIR}" reset --hard origin/main
fi

log "6/8 python venvs (api + worker)"
for VENV_PATH in "${VENV_API}" "${VENV_WORKER}"; do
	if [[ ! -d "${VENV_PATH}" ]]; then
		sudo -u "${APP_USER}" python3 -m venv "${VENV_PATH}"
	fi
	sudo -u "${APP_USER}" "${VENV_PATH}/bin/pip" install --upgrade pip wheel >/dev/null
done
sudo -u "${APP_USER}" "${VENV_API}/bin/pip" install -e "${REPO_DIR}/apps/api"
sudo -u "${APP_USER}" "${VENV_WORKER}/bin/pip" install -e "${REPO_DIR}/apps/worker"
sudo -u "${APP_USER}" "${VENV_WORKER}/bin/pip" install --upgrade yt-dlp

log "7/8 systemd units + Caddy config"
install -m 0644 "${REPO_DIR}/infra/systemd/clipfactory-api.service" /etc/systemd/system/clipfactory-api.service
install -m 0644 "${REPO_DIR}/infra/systemd/clipfactory-worker.service" /etc/systemd/system/clipfactory-worker.service
install -m 0644 "${REPO_DIR}/infra/Caddyfile" /etc/caddy/Caddyfile

systemctl daemon-reload
systemctl enable redis-server caddy clipfactory-api clipfactory-worker

# Seed empty .env files if missing — must be filled before first restart.
for SVC in api worker; do
	ENV_FILE="${REPO_DIR}/apps/${SVC}/.env"
	if [[ ! -f "${ENV_FILE}" ]]; then
		install -o "${APP_USER}" -g "${APP_USER}" -m 0600 \
			"${REPO_DIR}/apps/${SVC}/.env.example" "${ENV_FILE}"
		echo "  -> seeded ${ENV_FILE} from .env.example (FILL BEFORE STARTING)"
	fi
done

systemctl restart redis-server
systemctl restart caddy

log "8/8 done."
cat <<EOF

Next steps (do these by hand, the script will not):

  1. Edit ${REPO_DIR}/apps/api/.env     (Stripe, R2, Supabase, JWT...)
  2. Edit ${REPO_DIR}/apps/worker/.env  (OpenAI, OpenRouter, Anthropic, R2...)
  3. Point DNS A record  api.clipfactory.app  -> $(curl -fsS https://ifconfig.me 2>/dev/null || echo 'THIS-VPS-IP')
  4. systemctl restart clipfactory-api clipfactory-worker

Health check once DNS propagates:
  curl https://api.clipfactory.app/health

Logs:
  journalctl -u clipfactory-api    -f
  journalctl -u clipfactory-worker -f
  tail -f /var/log/caddy/clipfactory.log

EOF
