#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_SHA="${1:-}"
APP_DIR="${APP_DIR:-/root/mandarin_flow}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
STATE_DIR="${STATE_DIR:-/var/lib/mandarinflow}"
BACKUP_DIR="${BACKUP_DIR:-${STATE_DIR}/backups}"
READY_URL="${READY_URL:-https://mandarinflow.online/ready}"
SITE_URL="${SITE_URL:-https://mandarinflow.online/}"
BACKUP_RETENTION="${BACKUP_RETENTION:-7}"
EXPECTED_PUBLIC_API_URL="${EXPECTED_PUBLIC_API_URL:-https://mandarinflow.online}"
CURRENT_SHA_FILE="${STATE_DIR}/current_sha"
PREVIOUS_SHA_FILE="${STATE_DIR}/previous_sha"
APP_SWITCH_STARTED=0
PREVIOUS_SHA=""

require_sha() {
  [[ "$1" =~ ^[0-9a-f]{40}$ ]] || {
    echo "A full 40-character commit SHA is required." >&2
    exit 2
  }
}

require_env_value() {
  local key="$1"
  grep -Eq "^${key}=.*[^[:space:]]" .env || {
    echo "Missing required production environment value: ${key}" >&2
    exit 2
  }
}

env_value() {
  local key="$1"
  sed -n "s/^${key}=//p" .env | head -n 1
}

compose() {
  IMAGE_TAG="${IMAGE_TAG}" docker compose -f "${COMPOSE_FILE}" "$@"
}

wait_for_healthy() {
  local service="$1"
  local container_id status
  container_id="$(compose ps -q "${service}")"
  [[ -n "${container_id}" ]] || return 1
  for _ in $(seq 1 30); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}")"
    [[ "${status}" == "healthy" || "${status}" == "running" ]] && return 0
    [[ "${status}" == "unhealthy" || "${status}" == "exited" || "${status}" == "dead" ]] && return 1
    sleep 2
  done
  return 1
}

verify_image_sha() {
  local service="$1" expected_image="$2" container_id actual_image
  container_id="$(compose ps -q "${service}")"
  actual_image="$(docker inspect --format '{{.Config.Image}}' "${container_id}")"
  [[ "${actual_image}" == "${expected_image}:${DEPLOY_SHA}" ]] || {
    echo "${service} is running unexpected image: ${actual_image}" >&2
    return 1
  }
}

telegram_preflight() {
  compose exec -T backend python - <<'PY'
import asyncio
import sys

from app.core.config import settings
from app.services.telegram_service import TelegramService


async def main() -> int:
    service = TelegramService()
    if not service.enabled:
        return 1
    bot = await service._call("getMe", {})
    webhook = await service._call("getWebhookInfo", {})
    expected = f"{str(settings.frontend_url).rstrip('/')}/api/agent/integrations/telegram/webhook"
    return 0 if bot and webhook and webhook.get("url") == expected else 1


sys.exit(asyncio.run(main()))
PY
}

rollback_on_error() {
  local exit_code=$?
  trap - ERR
  set +e
  echo "Deployment ${DEPLOY_SHA} failed; collecting diagnostics." >&2
  compose ps >&2
  compose logs --no-color --tail=180 backend go-api frontend >&2
  if [[ "${APP_SWITCH_STARTED}" == "1" && "${PREVIOUS_SHA}" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Rolling application services back to ${PREVIOUS_SHA}." >&2
    IMAGE_TAG="${PREVIOUS_SHA}" docker compose -f "${COMPOSE_FILE}" pull backend go-api frontend
    IMAGE_TAG="${PREVIOUS_SHA}" docker compose -f "${COMPOSE_FILE}" up -d --no-build --pull never backend go-api frontend caddy
    curl --fail --silent --show-error --retry 6 --retry-delay 5 "${READY_URL}" >/dev/null
  else
    echo "No previous immutable deployment is available for automatic rollback." >&2
  fi
  exit "${exit_code}"
}

require_sha "${DEPLOY_SHA}"
[[ "${BACKUP_RETENTION}" =~ ^[1-9][0-9]*$ ]] || {
  echo "BACKUP_RETENTION must be a positive integer." >&2
  exit 2
}
cd "${APP_DIR}"
[[ -s .env ]] || { echo "Missing ${APP_DIR}/.env" >&2; exit 2; }
chmod 600 .env
for key in \
  FRONTEND_URL NEXT_PUBLIC_API_BASE_URL POSTGRES_PASSWORD POSTGRES_PASSWORD_URLENCODED DEV_ACCESS_TOKEN \
  OPENAI_TRANSLATION_API_KEY OPENAI_ASR_API_KEY OPENAI_CHAT_API_KEY \
  TELEGRAM_BOT_TOKEN TELEGRAM_ADMIN_CHAT_ID TELEGRAM_ALLOWED_USER_ID TELEGRAM_WEBHOOK_SECRET; do
  require_env_value "${key}"
done
[[ "$(env_value NEXT_PUBLIC_API_BASE_URL)" == "${EXPECTED_PUBLIC_API_URL}" ]] || {
  echo "NEXT_PUBLIC_API_BASE_URL does not match the production frontend build URL." >&2
  exit 2
}

install -d -m 700 "${STATE_DIR}" "${BACKUP_DIR}"
if [[ -s "${CURRENT_SHA_FILE}" ]]; then
  PREVIOUS_SHA="$(tr -d '[:space:]' < "${CURRENT_SHA_FILE}")"
fi
if [[ ! "${PREVIOUS_SHA}" =~ ^[0-9a-f]{40}$ ]]; then
  backend_container="$(docker ps -q --filter 'name=mandarin_flow-backend-1' | head -n 1)"
  if [[ -n "${backend_container}" ]]; then
    running_image="$(docker inspect --format '{{.Config.Image}}' "${backend_container}")"
    candidate_sha="${running_image##*:}"
    [[ "${candidate_sha}" =~ ^[0-9a-f]{40}$ ]] && PREVIOUS_SHA="${candidate_sha}" || PREVIOUS_SHA=""
  fi
fi

export IMAGE_TAG="${DEPLOY_SHA}"
trap rollback_on_error ERR

docker pull "ghcr.io/datnguyen305/mandarin-flow-backend:${DEPLOY_SHA}"
docker pull "ghcr.io/datnguyen305/mandarin-flow-api:${DEPLOY_SHA}"
docker pull "ghcr.io/datnguyen305/mandarin-flow-frontend:${DEPLOY_SHA}"
compose config --quiet
compose up -d --no-build --pull never postgres redis
wait_for_healthy postgres
wait_for_healthy redis

backup_timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_tmp="${BACKUP_DIR}/predeploy-${backup_timestamp}-${DEPLOY_SHA}.dump.tmp"
backup_file="${backup_tmp%.tmp}"
install -m 600 /dev/null "${backup_tmp}"
compose exec -T postgres sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "${backup_tmp}"
compose exec -T postgres pg_restore -l < "${backup_tmp}" >/dev/null
mv "${backup_tmp}" "${backup_file}"
mapfile -t backups < <(find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'predeploy-*.dump' -printf '%T@ %p\n' | sort -rn | cut -d' ' -f2-)
for ((index=BACKUP_RETENTION; index<${#backups[@]}; index++)); do
  rm -- "${backups[index]}"
done

compose run --rm --no-deps backend alembic upgrade head
APP_SWITCH_STARTED=1
compose up -d --no-build --pull never backend go-api frontend caddy
wait_for_healthy backend
wait_for_healthy go-api
verify_image_sha backend ghcr.io/datnguyen305/mandarin-flow-backend
verify_image_sha go-api ghcr.io/datnguyen305/mandarin-flow-api
verify_image_sha frontend ghcr.io/datnguyen305/mandarin-flow-frontend
curl --fail --silent --show-error --retry 6 --retry-delay 5 "${READY_URL}" >/dev/null
curl --fail --silent --show-error --retry 3 --retry-delay 3 "${SITE_URL}" >/dev/null
telegram_preflight

if [[ "${PREVIOUS_SHA}" =~ ^[0-9a-f]{40}$ && "${PREVIOUS_SHA}" != "${DEPLOY_SHA}" ]]; then
  printf '%s\n' "${PREVIOUS_SHA}" > "${PREVIOUS_SHA_FILE}.tmp"
  chmod 600 "${PREVIOUS_SHA_FILE}.tmp"
  mv "${PREVIOUS_SHA_FILE}.tmp" "${PREVIOUS_SHA_FILE}"
fi
printf '%s\n' "${DEPLOY_SHA}" > "${CURRENT_SHA_FILE}.tmp"
chmod 600 "${CURRENT_SHA_FILE}.tmp"
mv "${CURRENT_SHA_FILE}.tmp" "${CURRENT_SHA_FILE}"
trap - ERR
echo "Deployment ${DEPLOY_SHA} completed successfully."
