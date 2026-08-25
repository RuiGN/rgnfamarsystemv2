#!/usr/bin/env bash
# Orquestra o backup diario: dump PostgreSQL + midia, cifragem AES-256-GCM
# e upload para o Google Drive via Service Account.
#
# Variaveis de ambiente relevantes (definidas em .env):
#   BACKUP_GDRIVE_ENABLED         - "true" para habilitar upload (padrao: true)
#   BACKUP_GDRIVE_FOLDER_ID       - ID da pasta de destino no Drive
#   BACKUP_GDRIVE_CREDENTIALS_PATH - caminho do JSON da service account
#   BACKUP_CRON_HOUR              - hora local de execucao (padrao: 3)
#   BACKUP_CRON_MINUTE            - minuto da execucao (padrao: 0)
#   BACKUP_RETENTION_DAYS         - dias para manter arquivos locais (padrao: 14)
#   BACKUP_TRIGGERED_BY           - rotulo da origem (padrao: cron)
#   BACKUP_SKIP_UPLOAD_DURING_RESTORE - "true" para suprimir upload durante pre-restore
#
# O servico roda em loop: dorme ate a proxima janela 03:00 America/Recife,
# executa scripts/backup.sh e dispara o upload. Swarm envia SIGTERM em
# deploy/eviction; o trap garante flush de lock e saida limpa.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/rgnfarmasystem}"
LOG_DIR="${LOG_DIR:-/var/log/rgnfarmasystem}"
LOCK_FILE="${LOCK_FILE:-/var/lock/rgn_backup.lock}"
HEALTH_FILE="${HEALTH_FILE:-/tmp/last_backup_ok}"
LAST_RUN_FILE="${LAST_RUN_FILE:-/tmp/last_backup_run_at}"
RUN_ONCE="${RUN_ONCE:-false}"
STACK_NAME="${STACK_NAME:-rgnfarmasystem}"

BACKUP_GDRIVE_ENABLED="${BACKUP_GDRIVE_ENABLED:-true}"
BACKUP_CRON_HOUR="${BACKUP_CRON_HOUR:-3}"
BACKUP_CRON_MINUTE="${BACKUP_CRON_MINUTE:-0}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
BACKUP_TRIGGERED_BY="${BACKUP_TRIGGERED_BY:-cron}"
BACKUP_SKIP_UPLOAD_DURING_RESTORE="${BACKUP_SKIP_UPLOAD_DURING_RESTORE:-false}"
PYTHON_BIN="${PYTHON_BIN:-python}"

BACKUP_SCRIPT="${SCRIPT_DIR}/backup.sh"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"
LOG_FILE="${LOG_DIR}/backup-to-drive.log"

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG_FILE" >&2
}

fail() {
  log "ERRO: $*"
  exit 1
}

run_with_lock() {
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log "Outra execucao em andamento. Saindo."
    exit 0
  fi
  trap 'rc=$?; flock -u 9; rm -f "$LAST_RUN_FILE"; exit $rc' EXIT INT TERM
}

acquire_lock() {
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log "Outra execucao em andamento. Saindo."
    exit 0
  fi
  trap 'rc=$?; flock -u 9; exit $rc' EXIT INT TERM
}

seconds_until_next_run() {
  PYTHONPATH="${PROJECT_DIR}" TZ="${TZ:-America/Recife}" "$PYTHON_BIN" - <<'PY'
import datetime
import os
import sys

target_hour = int(os.environ.get("BACKUP_CRON_HOUR", "3"))
target_minute = int(os.environ.get("BACKUP_CRON_MINUTE", "0"))
tz_name = os.environ.get("TZ", "America/Recife")

try:
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(tz_name)
except Exception:
    tz = datetime.timezone.utc

now = datetime.datetime.now(tz=tz)
target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
if target <= now:
    target = target + datetime.timedelta(days=1)
delta = (target - now).total_seconds()
sys.stdout.write(str(int(delta) + 1))
PY
}

triggered_upload_enabled() {
  if [[ "${BACKUP_GDRIVE_ENABLED}" != "true" ]]; then
    return 1
  fi
  if [[ "${BACKUP_SKIP_UPLOAD_DURING_RESTORE}" == "true" ]]; then
    return 1
  fi
  if [[ -z "${BACKUP_GDRIVE_FOLDER_ID:-}" ]]; then
    return 1
  fi
  return 0
}

load_credentials() {
  if [[ -n "${BACKUP_GDRIVE_REFRESH_TOKEN:-}" ]]; then
    export BACKUP_GDRIVE_REFRESH_TOKEN
    export BACKUP_GDRIVE_OAUTH_CLIENT_ID
    export BACKUP_GDRIVE_OAUTH_CLIENT_SECRET
    return 0
  fi
  if [[ -n "${BACKUP_GDRIVE_CREDENTIALS_PATH:-}" && -f "${BACKUP_GDRIVE_CREDENTIALS_PATH}" ]]; then
    export BACKUP_GDRIVE_CREDENTIALS_PATH
    return 0
  fi
  local secret_path="/run/secrets/GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON"
  if [[ -f "$secret_path" ]]; then
    export BACKUP_GDRIVE_CREDENTIALS_PATH="$secret_path"
    return 0
  fi
  if [[ -n "${BACKUP_GDRIVE_CREDENTIALS_BASE64:-}" ]]; then
    export BACKUP_GDRIVE_CREDENTIALS_BASE64
    return 0
  fi
  return 1
}

upload_artifacts() {
  local kind="$1"
  local pattern="$2"
  local file
  local uploaded=0
  local skipped=0
  local failed=0

  for file in "${BACKUP_DIR}"/${pattern}; do
    [[ -f "$file" ]] || continue
    local target_name
    target_name="$(basename "$file")"

    log "Enviando $target_name para o Google Drive (kind=$kind)"
    if BACKUP_GDRIVE_ENABLED="$BACKUP_GDRIVE_ENABLED" \
       BACKUP_TRIGGERED_BY="$BACKUP_TRIGGERED_BY" \
       BACKUP_GDRIVE_FOLDER_ID="$BACKUP_GDRIVE_FOLDER_ID" \
       BACKUP_GDRIVE_REFRESH_TOKEN="${BACKUP_GDRIVE_REFRESH_TOKEN:-}" \
       BACKUP_GDRIVE_OAUTH_CLIENT_ID="${BACKUP_GDRIVE_OAUTH_CLIENT_ID:-}" \
       BACKUP_GDRIVE_OAUTH_CLIENT_SECRET="${BACKUP_GDRIVE_OAUTH_CLIENT_SECRET:-}" \
       BACKUP_GDRIVE_CREDENTIALS_PATH="${BACKUP_GDRIVE_CREDENTIALS_PATH:-}" \
       BACKUP_GDRIVE_CREDENTIALS_BASE64="${BACKUP_GDRIVE_CREDENTIALS_BASE64:-}" \
       "$PYTHON_BIN" "${PROJECT_DIR}/manage.py" upload_backup \
         --source "$file" --kind "$kind" \
         --target-name "$target_name" \
         --json >> "$LOG_FILE" 2>&1; then
      uploaded=$((uploaded + 1))
    else
      failed=$((failed + 1))
      log "Falha no upload de $file"
    fi
  done
  log "Resumo upload $kind: success=$uploaded failed=$failed"
  (( failed == 0 ))
}

run_backup_cycle() {
  local started_at
  started_at="$(date +%s)"

  log "Inicio do ciclo de backup (stack=$STACK_NAME dir=$BACKUP_DIR)"

  if [[ ! -x "$BACKUP_SCRIPT" ]]; then
    fail "Script de backup nao encontrado: $BACKUP_SCRIPT"
  fi

  STACK_NAME="$STACK_NAME" BACKUP_DIR="$BACKUP_DIR" RETENTION_DAYS="$BACKUP_RETENTION_DAYS" \
    "$BACKUP_SCRIPT" 2>&1 | tee -a "$LOG_FILE" || {
      log "Falha em scripts/backup.sh"
      return 1
    }

  if [[ "$BACKUP_GDRIVE_ENABLED" == "true" \
        && "$BACKUP_SKIP_UPLOAD_DURING_RESTORE" != "true" \
        && -z "${BACKUP_GDRIVE_FOLDER_ID:-}" ]]; then
    log "Falha no upload: BACKUP_GDRIVE_FOLDER_ID e obrigatorio quando Google Drive esta habilitado."
    return 1
  fi

  if triggered_upload_enabled; then
    if ! load_credentials; then
      log "Falha no upload: credenciais configuradas para Google Drive estao ausentes."
      return 1
    else
      local upload_failed=0
      upload_artifacts "postgres" "postgres-*.sql.gz" || upload_failed=1
      upload_artifacts "media" "media-*.tar.gz" || upload_failed=1
      if (( upload_failed != 0 )); then
        log "Falha no upload de um ou mais artefatos; ciclo marcado como erro."
        return 1
      fi
    fi
  else
    log "Upload para Google Drive desabilitado por configuracao."
  fi

  date -u +%Y-%m-%dT%H:%M:%SZ > "$HEALTH_FILE"
  echo "$started_at" > "$LAST_RUN_FILE"
  log "Ciclo de backup concluido em $(($(date +%s) - started_at))s"
}

main() {
  run_with_lock

  if [[ "$RUN_ONCE" == "true" ]]; then
    log "RUN_ONCE=true: executando um unico ciclo"
    run_backup_cycle
    exit $?
  fi

  while true; do
    local sleep_for
    sleep_for="$(seconds_until_next_run)"
    log "Proximo backup em ${sleep_for}s (janela ${BACKUP_CRON_HOUR}:$(printf '%02d' "$BACKUP_CRON_MINUTE"))"
    sleep "$sleep_for"
    if ! run_backup_cycle; then
      log "Ciclo terminou com erro; continuando loop."
    fi
  done
}

main "$@"
