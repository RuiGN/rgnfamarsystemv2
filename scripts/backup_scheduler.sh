#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
BACKUP_SCRIPT="$ROOT_DIR/scripts/backup.sh"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/rgnfarmasystem}"
LOG_DIR="${LOG_DIR:-${BACKUP_DIR}/logs}"
LOCK_FILE="${LOCK_FILE:-/tmp/rgnfarmasystem-backup-scheduler.lock}"
HEALTH_FILE="${HEALTH_FILE:-/tmp/backup_scheduler_ready}"
LAST_RUN_FILE="${LAST_RUN_FILE:-${BACKUP_DIR}/last_backup_ok}"
BACKUP_CRON_HOUR="${BACKUP_CRON_HOUR:-3}"
BACKUP_CRON_MINUTE="${BACKUP_CRON_MINUTE:-0}"
RUN_ONCE="${RUN_ONCE:-false}"

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
}

seconds_until_next_run() {
  local now_epoch target_epoch
  now_epoch=$(date +%s)
  target_epoch=$(date -d "today ${BACKUP_CRON_HOUR}:${BACKUP_CRON_MINUTE}:00" +%s)
  if (( target_epoch <= now_epoch )); then
    target_epoch=$(date -d "tomorrow ${BACKUP_CRON_HOUR}:${BACKUP_CRON_MINUTE}:00" +%s)
  fi
  printf '%s\n' "$((target_epoch - now_epoch))"
}

latest_new_artifact() {
  local marker="$1"
  local pattern="$2"
  find "$BACKUP_DIR" -maxdepth 1 -type f -name "$pattern" -newer "$marker" -size +0c \
    -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-
}

write_health_markers() {
  local timestamp="$1"
  local health_tmp="${HEALTH_FILE}.tmp.$$"
  local last_run_tmp="${LAST_RUN_FILE}.tmp.$$"
  printf '%s\n' "$timestamp" > "$health_tmp"
  printf '%s\n' "$timestamp" > "$last_run_tmp"
  mv -f -- "$health_tmp" "$HEALTH_FILE"
  mv -f -- "$last_run_tmp" "$LAST_RUN_FILE"
}

run_backup_cycle() {
  local cycle_marker postgres_artifact media_artifact completed_at
  mkdir -p -- "$BACKUP_DIR" "$LOG_DIR" "$(dirname -- "$HEALTH_FILE")" \
    "$(dirname -- "$LAST_RUN_FILE")" "$(dirname -- "$LOCK_FILE")"
  rm -f -- "$HEALTH_FILE"
  cycle_marker=$(mktemp "${BACKUP_DIR}/.backup-cycle.XXXXXX")
  trap "rm -f -- '$cycle_marker'" RETURN

  log 'Iniciando ciclo de backup local.'
  BACKUP_DIR="$BACKUP_DIR" bash "$BACKUP_SCRIPT"

  postgres_artifact=$(latest_new_artifact "$cycle_marker" 'postgres-*.sql.gz')
  media_artifact=$(latest_new_artifact "$cycle_marker" 'media-*.tar.gz')
  if [[ -z "$postgres_artifact" || -z "$media_artifact" ]]; then
    log 'Falha: o ciclo não produziu artefato novo e não vazio de PostgreSQL e mídia.'
    return 1
  fi

  completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  write_health_markers "$completed_at"
  log "Backup local concluído: $(basename -- "$postgres_artifact"), $(basename -- "$media_artifact")."
}

main() {
  command -v flock >/dev/null 2>&1 || {
    log 'Falha: o comando flock não está disponível.'
    return 127
  }
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log 'Outro ciclo de backup local já está em execução.'
    return 0
  fi

  if [[ "$RUN_ONCE" == 'true' ]]; then
    run_backup_cycle
    return
  fi

  touch -- "$HEALTH_FILE"
  while true; do
    sleep "$(seconds_until_next_run)"
    if ! run_backup_cycle; then
      log 'O ciclo falhou; o marcador de saúde permanecerá ausente.'
    fi
  done
}

main "$@"
