#!/usr/bin/env bash
set -euo pipefail

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-rgnfarmasystem}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/rgnfarmasystem}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

DB_DEPLOYMENT="${DB_DEPLOYMENT:-container}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-rgnfarmasystem}"
POSTGRES_DB="${POSTGRES_DB:-rgnfarmasystem}"
MEDIA_DIR="${MEDIA_DIR:-/app/media}"

mkdir -p "$BACKUP_DIR"

find_service_container() {
  local service="$1"
  local container
  container="$(docker ps \
    --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" \
    --filter "label=com.docker.compose.service=${service}" \
    --format '{{.ID}}' | head -n 1)"
  if [[ -z "$container" ]]; then
    container="$(docker ps --filter "name=${COMPOSE_PROJECT_NAME}_${service}" --format '{{.ID}}' | head -n 1)"
  fi
  printf '%s' "$container"
}

POSTGRES_TARGET="${BACKUP_DIR}/postgres-${TIMESTAMP}.sql.gz"
POSTGRES_TMP="$(mktemp "${BACKUP_DIR}/.postgres-${TIMESTAMP}.XXXXXX.sql.gz")"
MEDIA_TARGET="${BACKUP_DIR}/media-${TIMESTAMP}.tar.gz"
MEDIA_TMP="$(mktemp "${BACKUP_DIR}/.media-${TIMESTAMP}.XXXXXX.tar.gz")"
trap 'rm -f "$POSTGRES_TMP" "$MEDIA_TMP"' EXIT

case "$DB_DEPLOYMENT" in
  external)
    echo "Gerando dump do PostgreSQL externo em ${DB_HOST}:${DB_PORT}..."
    PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump \
      -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
      --no-owner --no-acl | gzip > "$POSTGRES_TMP"
    ;;
  container)
    command -v docker >/dev/null 2>&1 || {
      echo "Docker indisponivel para DB_DEPLOYMENT=container." >&2
      exit 1
    }
    DB_CONTAINER="$(find_service_container db)"
    [[ -n "$DB_CONTAINER" ]] || {
      echo "Container do PostgreSQL nao encontrado." >&2
      exit 1
    }
    docker exec "$DB_CONTAINER" pg_dump \
      -U "$POSTGRES_USER" "$POSTGRES_DB" --no-owner --no-acl \
      | gzip > "$POSTGRES_TMP"
    ;;
  *)
    echo "DB_DEPLOYMENT invalido: ${DB_DEPLOYMENT}. Use external ou container." >&2
    exit 1
    ;;
esac

mv "$POSTGRES_TMP" "$POSTGRES_TARGET"

# O backup de mídia independe da topologia do PostgreSQL.
APP_CONTAINER=""
if command -v docker >/dev/null 2>&1 && [[ -S /var/run/docker.sock ]]; then
  APP_CONTAINER="$(find_service_container app)"
fi

if [[ -n "$APP_CONTAINER" ]]; then
  docker exec "$APP_CONTAINER" tar -czf - /app/media > "$MEDIA_TMP"
elif [[ -d "$MEDIA_DIR" ]]; then
  tar -czf "$MEDIA_TMP" -C "$MEDIA_DIR" .
else
  echo "Backup de midia indisponivel: container do app ausente e MEDIA_DIR invalido (${MEDIA_DIR})." >&2
  exit 1
fi

if [[ ! -s "$MEDIA_TMP" ]]; then
  echo "Backup de midia vazio; artefato nao sera publicado." >&2
  exit 1
fi

mv "$MEDIA_TMP" "$MEDIA_TARGET"
trap - EXIT

find "$BACKUP_DIR" -type f -mtime "+${RETENTION_DAYS}" -delete
