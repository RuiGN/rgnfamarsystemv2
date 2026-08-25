#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:4127}"
RETRIES="${RETRIES:-30}"
WAIT_SECONDS="${WAIT_SECONDS:-2}"
SCHEMA_ROUTE="/api/schema/"

if [[ "${1:-}" == "--help" ]]; then
  echo "Uso: BASE_URL=http://127.0.0.1:4127 $0"
  exit 0
fi

check_route() {
  local host="$1"
  local route="$2"
  local expected_text="$3"
  local attempt
  local response
  for ((attempt = 1; attempt <= RETRIES; attempt++)); do
    if response=$(curl --fail --silent --show-error --location --max-time 5 \
      --header "Host: ${host}" "${BASE_URL}${route}"); then
      if [[ -z "${expected_text}" || "${response}" == *"${expected_text}"* ]]; then
        printf 'PASS %s%s\n' "${host}" "${route}"
        return 0
      fi
    fi
    sleep "${WAIT_SECONDS}"
  done
  printf 'FAIL %s%s\n' "${host}" "${route}" >&2
  return 1
}

check_route "erp.localhost" "/health/" '"status": "ok"'
check_route "control.localhost" "/health/" '"status": "ok"'
check_route "control.localhost" "/platform/" 'data-ui="platform-login"'
check_route "erp.localhost" "/accounts/login/" 'data-ui="auth-login"'
check_route "erp.localhost" "/" 'data-ui="auth-login"'
check_route "erp.localhost" "/api/docs/" 'SwaggerUIBundle'

printf 'INFO schema completo: valide separadamente em %s (geração não é lightweight)\n' "${SCHEMA_ROUTE}"
