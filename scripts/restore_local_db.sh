#!/usr/bin/env bash
set -Eeuo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DUMP_FILE="${1:-}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-youtube_language_learning}"
STATE_DIR="${STATE_DIR:-/var/lib/mandarinflow}"
BACKUP_DIR="${BACKUP_DIR:-${STATE_DIR}/backups}"
CURRENT_SHA_FILE="${STATE_DIR}/current_sha"
IMAGE_TAG="${DEPLOY_IMAGE_TAG:-}"

if [[ -z "${DUMP_FILE}" || ! -f "${DUMP_FILE}" ]]; then
  echo "Usage: RESTORE_LOCAL_DB_CONFIRM=YES $0 /path/to/mandarinflow-local.sql" >&2
  exit 1
fi

if [[ "${RESTORE_LOCAL_DB_CONFIRM:-}" != "YES" ]]; then
  echo "Refusing to overwrite database. Set RESTORE_LOCAL_DB_CONFIRM=YES explicitly." >&2
  exit 1
fi

if [[ -z "${IMAGE_TAG}" && -s "${CURRENT_SHA_FILE}" ]]; then
  IMAGE_TAG="$(tr -d '[:space:]' < "${CURRENT_SHA_FILE}")"
fi
if [[ ! "${IMAGE_TAG}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "A deployed image SHA is required. Set DEPLOY_IMAGE_TAG or deploy once with scripts/deploy_production.sh." >&2
  exit 1
fi
export IMAGE_TAG

install -d -m 700 "${BACKUP_DIR}"

docker compose -f "${COMPOSE_FILE}" stop backend go-api frontend caddy 2>/dev/null || true
docker compose -f "${COMPOSE_FILE}" up -d postgres redis

until docker compose -f "${COMPOSE_FILE}" exec -T postgres pg_isready -U "${DB_USER}" -d "${DB_NAME}" >/dev/null 2>&1; do
  sleep 2
done

backup_timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="${BACKUP_DIR}/pre-restore-${backup_timestamp}-${IMAGE_TAG}.dump"
install -m 600 /dev/null "${backup_file}"
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  pg_dump -U "${DB_USER}" -d "${DB_NAME}" -Fc > "${backup_file}"
docker compose -f "${COMPOSE_FILE}" exec -T postgres pg_restore -l < "${backup_file}" >/dev/null

docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U "${DB_USER}" -d "${DB_NAME}" \
  -v ON_ERROR_STOP=1 -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U "${DB_USER}" -d "${DB_NAME}" \
  -v ON_ERROR_STOP=1 < "${DUMP_FILE}"

docker compose -f "${COMPOSE_FILE}" up -d --no-build --pull never --force-recreate backend go-api frontend caddy
docker compose -f "${COMPOSE_FILE}" ps
