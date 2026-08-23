#!/usr/bin/env bash
set -Eeuo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DUMP_FILE="${1:-}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-youtube_language_learning}"

if [[ -z "${DUMP_FILE}" || ! -f "${DUMP_FILE}" ]]; then
  echo "Usage: RESTORE_LOCAL_DB_CONFIRM=YES $0 /path/to/mandarinflow-local.sql" >&2
  exit 1
fi

if [[ "${RESTORE_LOCAL_DB_CONFIRM:-}" != "YES" ]]; then
  echo "Refusing to overwrite database. Set RESTORE_LOCAL_DB_CONFIRM=YES explicitly." >&2
  exit 1
fi

docker compose -f "${COMPOSE_FILE}" stop backend go-api frontend caddy 2>/dev/null || true
docker compose -f "${COMPOSE_FILE}" up -d postgres redis

until docker compose -f "${COMPOSE_FILE}" exec -T postgres pg_isready -U "${DB_USER}" -d "${DB_NAME}" >/dev/null 2>&1; do
  sleep 2
done

docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U "${DB_USER}" -d "${DB_NAME}" \
  -v ON_ERROR_STOP=1 -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U "${DB_USER}" -d "${DB_NAME}" \
  -v ON_ERROR_STOP=1 < "${DUMP_FILE}"

docker compose -f "${COMPOSE_FILE}" up -d --force-recreate backend go-api frontend caddy
docker compose -f "${COMPOSE_FILE}" ps
