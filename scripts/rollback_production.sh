#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/root/mandarin_flow}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
STATE_DIR="${STATE_DIR:-/var/lib/mandarinflow}"
READY_URL="${READY_URL:-https://mandarinflow.online/ready}"
CURRENT_SHA_FILE="${STATE_DIR}/current_sha"
PREVIOUS_SHA_FILE="${STATE_DIR}/previous_sha"
TARGET_SHA="${1:-}"

if [[ -z "${TARGET_SHA}" && -s "${PREVIOUS_SHA_FILE}" ]]; then
  TARGET_SHA="$(tr -d '[:space:]' < "${PREVIOUS_SHA_FILE}")"
fi
[[ "${TARGET_SHA}" =~ ^[0-9a-f]{40}$ ]] || {
  echo "Provide a full rollback SHA or configure ${PREVIOUS_SHA_FILE}." >&2
  exit 2
}

cd "${APP_DIR}"
[[ -s .env ]] || { echo "Missing ${APP_DIR}/.env" >&2; exit 2; }
current_sha=""
[[ -s "${CURRENT_SHA_FILE}" ]] && current_sha="$(tr -d '[:space:]' < "${CURRENT_SHA_FILE}")"

for image in mandarin-flow-backend mandarin-flow-api mandarin-flow-frontend; do
  docker pull "ghcr.io/datnguyen305/${image}:${TARGET_SHA}"
done
IMAGE_TAG="${TARGET_SHA}" docker compose -f "${COMPOSE_FILE}" up -d --no-build --pull never backend go-api frontend caddy
curl --fail --silent --show-error --retry 6 --retry-delay 5 "${READY_URL}" >/dev/null

if [[ "${current_sha}" =~ ^[0-9a-f]{40}$ && "${current_sha}" != "${TARGET_SHA}" ]]; then
  printf '%s\n' "${current_sha}" > "${PREVIOUS_SHA_FILE}"
  chmod 600 "${PREVIOUS_SHA_FILE}"
fi
printf '%s\n' "${TARGET_SHA}" > "${CURRENT_SHA_FILE}"
chmod 600 "${CURRENT_SHA_FILE}"
echo "Rollback to ${TARGET_SHA} completed successfully."
