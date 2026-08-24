#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${REPO_URL:-https://github.com/datnguyen305/mandarin_flow.git}"
APP_DIR="${APP_DIR:-/root/mandarin_flow}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

systemctl enable --now docker

if [[ -e "${APP_DIR}" ]]; then
  echo "Refusing to overwrite ${APP_DIR}. Remove it explicitly after confirming this is the intended VPS." >&2
  exit 1
fi

git clone --branch main --single-branch "${REPO_URL}" "${APP_DIR}"
install -d -m 700 "${APP_DIR}/cookies"

cat <<EOF
Bootstrap complete: ${APP_DIR}
Next steps:
  1. Upload and configure ${APP_DIR}/.env manually, then chmod 600 it.
  2. Configure the GitHub production environment SSH and GHCR secrets.
  3. Configure NEXT_PUBLIC_API_BASE_URL and NEXT_PUBLIC_FEEDBACK_EMAIL as GitHub environment variables.
  4. Run the Build and deploy workflow.
EOF
