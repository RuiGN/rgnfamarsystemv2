#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-rgnfarmasystem}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/rgnfarmasystem}"
DB_DEPLOYMENT="${DB_DEPLOYMENT:-container}"
MEDIA_DEPLOYMENT="${MEDIA_DEPLOYMENT:-container}"
MEDIA_DIR="${MEDIA_DIR:-/app/media}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-rgnfarmasystem}"
POSTGRES_DB="${POSTGRES_DB:-rgnfarmasystem}"
POSTGRES_BACKUP=""
MEDIA_BACKUP=""
DRY_RUN="false"
YES="false"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
MEDIA_TMP="/tmp/rgnfarmasystem-media-restore.tar.gz"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup.sh" # scripts/backup.sh

usage() {
  cat <<'USAGE'
Uso:
  scripts/restore.sh --postgres /backup/postgres.sql.gz --media /backup/media.tar.gz --yes
  scripts/restore.sh --postgres /backup/postgres.sql.gz --dry-run
  scripts/restore.sh --media /backup/media.tar.gz --yes
  scripts/restore.sh --postgres /backup/postgres.sql.gz.enc --yes
  scripts/restore.sh --media /backup/media.tar.gz.enc --yes

Opcoes:
  --postgres CAMINHO  Arquivo .sql.gz (ou .enc) gerado por scripts/backup.sh.
  --media CAMINHO     Arquivo .tar.gz (ou .enc) de /app/media gerado por scripts/backup.sh.
  --backup-dir DIR    Diretorio para backup pre-restore. Padrao: BACKUP_DIR.
  --stack-name NOME   Nome da stack Docker Swarm. Padrao: STACK_NAME.
  --dry-run           Mostra as acoes sem alterar banco ou media.
  --yes               Confirma restore real. Obrigatorio sem --dry-run.
USAGE
}

fail() {
  echo "$1" >&2
  exit 1
}

decrypt_if_needed() {
  local source_path="$1"
  local kind="$2"
  if [[ "$source_path" != *.enc ]]; then
    echo "$source_path"
    return 0
  fi
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY-RUN: ${PYTHON_BIN} manage.py decrypt_backup --source ${source_path} --kind ${kind}" >&2
    echo "$source_path"
    return 0
  fi
  local output_path="${source_path%.enc}.dec.gz"
  (cd "$PROJECT_DIR" && BACKUP_GDRIVE_ENABLED=false "$PYTHON_BIN" manage.py decrypt_backup \
    --source "$source_path" \
    --destination "$output_path" \
    --kind "$kind" >&2) || fail "Falha ao decifrar ${source_path}"
  echo "$output_path"
}

validate_gzip() {
  local source_path="$1"
  local kind="$2"
  if [[ "$DRY_RUN" == "true" && "$source_path" == *.enc ]]; then
    echo "DRY-RUN: gzip -t -- <artefato ${kind} decifrado>"
    return 0
  fi
  gzip -t -- "$source_path" || fail "Artefato ${kind} nao e um gzip valido: ${source_path}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --postgres)
      [[ $# -ge 2 ]] || fail "Opcao --postgres exige caminho."
      POSTGRES_BACKUP="$2"
      shift 2
      ;;
    --media)
      [[ $# -ge 2 ]] || fail "Opcao --media exige caminho."
      MEDIA_BACKUP="$2"
      shift 2
      ;;
    --backup-dir)
      [[ $# -ge 2 ]] || fail "Opcao --backup-dir exige diretorio."
      BACKUP_DIR="$2"
      shift 2
      ;;
    --stack-name)
      [[ $# -ge 2 ]] || fail "Opcao --stack-name exige nome da stack."
      STACK_NAME="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    --yes)
      YES="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      fail "Opcao desconhecida: $1"
      ;;
  esac
done

if [[ -z "$POSTGRES_BACKUP" && -z "$MEDIA_BACKUP" ]]; then
  usage
  fail "Informe --postgres e/ou --media para restaurar."
fi

if [[ "$DRY_RUN" != "true" && "$YES" != "true" ]]; then
  fail "Restore real exige --yes. Execute antes com --dry-run para revisar as acoes."
fi

if [[ -n "$POSTGRES_BACKUP" && ! -f "$POSTGRES_BACKUP" ]]; then
  fail "Arquivo PostgreSQL nao encontrado: $POSTGRES_BACKUP"
fi

if [[ -n "$MEDIA_BACKUP" && ! -f "$MEDIA_BACKUP" ]]; then
  fail "Arquivo de media nao encontrado: $MEDIA_BACKUP"
fi

if [[ ! -x "$BACKUP_SCRIPT" ]]; then
  fail "Script de backup nao executavel: $BACKUP_SCRIPT"
fi

run() {
  if [[ "$DRY_RUN" == "true" ]]; then
    printf 'DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

lookup_container() {
  local suffix="$1"

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY_RUN_${suffix}_CONTAINER"
    return
  fi

  command -v docker >/dev/null 2>&1 || fail "Comando docker nao encontrado."
  docker ps --filter "name=${STACK_NAME}_${suffix}" --format '{{.ID}}' | head -n 1
}

restore_external_postgres() {
  local source_path="$1"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY-RUN: PGPASSWORD=<redacted> psql -v ON_ERROR_STOP=1 -h ${DB_HOST} -p ${DB_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c 'DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;'"
    echo "DRY-RUN: gunzip -c ${source_path} | PGPASSWORD=<redacted> psql -v ON_ERROR_STOP=1 -h ${DB_HOST} -p ${DB_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB}"
    return
  fi
  PGPASSWORD="${POSTGRES_PASSWORD:-}" psql \
    -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -c 'DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;'
  gunzip -c "$source_path" | PGPASSWORD="${POSTGRES_PASSWORD:-}" psql \
    -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB"
}

case "$DB_DEPLOYMENT" in
  external|container) ;;
  *) fail "DB_DEPLOYMENT invalido: ${DB_DEPLOYMENT}. Use external ou container." ;;
esac
case "$MEDIA_DEPLOYMENT" in
  external|container) ;;
  *) fail "MEDIA_DEPLOYMENT invalido: ${MEDIA_DEPLOYMENT}. Use external ou container." ;;
esac

DB_CONTAINER=""
APP_CONTAINER=""
POSTGRES_RESTORE_PATH=""
MEDIA_RESTORE_PATH=""

# Valide os artefatos (inclusive o resultado da decifragem) antes do backup
# pre-restore e, principalmente, antes de qualquer operacao destrutiva.
if [[ -n "$POSTGRES_BACKUP" ]]; then
  POSTGRES_RESTORE_PATH="$(decrypt_if_needed "$POSTGRES_BACKUP" postgres)"
  validate_gzip "$POSTGRES_RESTORE_PATH" postgres
fi

if [[ -n "$MEDIA_BACKUP" ]]; then
  MEDIA_RESTORE_PATH="$(decrypt_if_needed "$MEDIA_BACKUP" media)"
  validate_gzip "$MEDIA_RESTORE_PATH" media
  if [[ "$MEDIA_DEPLOYMENT" == "external" ]]; then
    if [[ "$DRY_RUN" != "true" || "$MEDIA_BACKUP" != *.enc ]]; then
      "$PYTHON_BIN" "$SCRIPT_DIR/restore_media.py" \
        --archive "$MEDIA_RESTORE_PATH" --destination "$MEDIA_DIR" --dry-run
    fi
  fi
fi

if [[ -n "$POSTGRES_BACKUP" && "$DB_DEPLOYMENT" == "container" ]]; then
  DB_CONTAINER="$(lookup_container db)"
fi

if [[ -n "$MEDIA_BACKUP" && "$MEDIA_DEPLOYMENT" == "container" ]]; then
  APP_CONTAINER="$(lookup_container app)"
fi

if [[ -n "$POSTGRES_BACKUP" && "$DB_DEPLOYMENT" == "container" && -z "$DB_CONTAINER" ]]; then
  fail "Container do PostgreSQL nao encontrado para stack ${STACK_NAME}."
fi

if [[ -n "$MEDIA_BACKUP" && "$MEDIA_DEPLOYMENT" == "container" && -z "$APP_CONTAINER" ]]; then
  fail "Container do app nao encontrado para stack ${STACK_NAME}."
fi

PRE_RESTORE_DIR="${BACKUP_DIR%/}/pre-restore-${TIMESTAMP}"

if [[ "$DRY_RUN" == "true" ]]; then
  echo "DRY-RUN: STACK_NAME=${STACK_NAME} BACKUP_DIR=${PRE_RESTORE_DIR} ${BACKUP_SCRIPT}"
else
  STACK_NAME="$STACK_NAME" BACKUP_DIR="$PRE_RESTORE_DIR" "$BACKUP_SCRIPT"
fi

if [[ -n "$POSTGRES_BACKUP" ]]; then
  if [[ "$DB_DEPLOYMENT" == "external" ]]; then
    restore_external_postgres "$POSTGRES_RESTORE_PATH"
  else
    if [[ "$DRY_RUN" == "true" ]]; then
      echo "DRY-RUN: docker exec -i \"${DB_CONTAINER}\" psql -v ON_ERROR_STOP=1 -U \"${POSTGRES_USER}\" \"${POSTGRES_DB}\" -c \"DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;\""
      echo "DRY-RUN: gunzip -c \"${POSTGRES_RESTORE_PATH}\" | docker exec -i \"${DB_CONTAINER}\" psql -v ON_ERROR_STOP=1 -U \"${POSTGRES_USER}\" \"${POSTGRES_DB}\""
    else
      docker exec -i "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB" -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
      gunzip -c "$POSTGRES_RESTORE_PATH" | docker exec -i "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB"
    fi
  fi
fi

if [[ -n "$MEDIA_BACKUP" ]]; then
  if [[ "$MEDIA_DEPLOYMENT" == "external" ]]; then
    if [[ "$DRY_RUN" == "true" ]]; then
      run "$PYTHON_BIN" "$SCRIPT_DIR/restore_media.py" \
        --archive "$MEDIA_RESTORE_PATH" --destination "$MEDIA_DIR" --dry-run
    else
      "$PYTHON_BIN" "$SCRIPT_DIR/restore_media.py" \
        --archive "$MEDIA_RESTORE_PATH" --destination "$MEDIA_DIR"
    fi
  else
    run docker cp "$MEDIA_RESTORE_PATH" "${APP_CONTAINER}:${MEDIA_TMP}"
    run docker exec "$APP_CONTAINER" sh -c "mkdir -p /app/media && tar -xzf ${MEDIA_TMP} -C / && rm -f /tmp/rgnfarmasystem-media-restore.tar.gz"
  fi
fi

echo "Restore finalizado."
