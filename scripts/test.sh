#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_FILE="$ROOT_DIR/docker-compose.test.yml"
PYTHON="$ROOT_DIR/.venv/bin/python"
TEST_POSTGRES_PORT=${TEST_POSTGRES_PORT:-5433}
TEST_DATABASE_URL="postgresql://rgn_test:rgn_test@127.0.0.1:${TEST_POSTGRES_PORT}/rgn_test"

command -v docker >/dev/null 2>&1 || {
  echo "Erro: Docker não encontrado." >&2
  exit 127
}
docker compose version >/dev/null 2>&1 || {
  echo "Erro: Docker Compose v2 não está disponível." >&2
  exit 127
}
[[ -x "$PYTHON" ]] || {
  echo "Erro: virtualenv não encontrada em $PYTHON." >&2
  exit 127
}

export TEST_POSTGRES_PORT
export COMPOSE_PROJECT_NAME="rgnfarmasystem-test"
docker compose -f "$COMPOSE_FILE" up -d --wait postgres_test

export TEST_DATABASE_URL="$TEST_DATABASE_URL"
export DATABASE_URL="$TEST_DATABASE_URL"
export CSRF_TRUSTED_ORIGINS="http://localhost"
cd "$ROOT_DIR"
exec "$PYTHON" -m pytest "$@"
