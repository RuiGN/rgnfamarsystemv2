#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-rgnfarmasystem}"
IMAGE_NAME="${IMAGE_NAME:-ghcr.io/RuiGN/rgnfarmasystem}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ENV_FILE="${ENV_FILE:-.env}"
SKIP_BUILD="false"

if [[ "${1:-}" == "--skip-build" ]]; then
  SKIP_BUILD="true"
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Comando obrigatório ausente: $1" >&2
    exit 1
  }
}

read_env_value() {
  local key="$1"
  awk -F '=' -v search="$key" '
    $1 == search {
      value = substr($0, index($0, "=") + 1)
      gsub(/^"|"$/, "", value)
      gsub(/^'\''|'\''$/, "", value)
      print value
      exit
    }
  ' "$ENV_FILE"
}

require_command docker
require_command git

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Arquivo $ENV_FILE não encontrado." >&2
  exit 1
fi

if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q '^active$'; then
  echo "Docker Swarm não está ativo. Execute: docker swarm init" >&2
  exit 1
fi

if ! docker secret inspect CLOUDFLARE_DNS_API_TOKEN >/dev/null 2>&1; then
  echo "Docker Secret CLOUDFLARE_DNS_API_TOKEN não encontrado." >&2
  exit 1
fi

if ! docker network inspect traefik_public >/dev/null 2>&1; then
  echo "Rede traefik_public não encontrada." >&2
  exit 1
fi

if ! docker network inspect rgnfarmasystem_egress >/dev/null 2>&1; then
  echo "Rede rgnfarmasystem_egress não encontrada." >&2
  exit 1
fi

DEBUG_VALUE="$(read_env_value DEBUG)"
ALLOWED_HOSTS_VALUE="$(read_env_value ALLOWED_HOSTS)"

if [[ "$DEBUG_VALUE" != "False" ]]; then
  echo "Produção exige DEBUG=False no $ENV_FILE." >&2
  exit 1
fi

if [[ "$ALLOWED_HOSTS_VALUE" != *"localhost"* ]]; then
  echo "ALLOWED_HOSTS deve conter localhost para healthcheck interno." >&2
  exit 1
fi

git pull --ff-only

if [[ "$SKIP_BUILD" != "true" ]]; then
  docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
  docker push "${IMAGE_NAME}:${IMAGE_TAG}"
fi

IMAGE_TAG="$IMAGE_TAG" docker stack deploy --with-registry-auth -c docker-stack.yml "$STACK_NAME"
docker service update --force "${STACK_NAME}_app"
docker service update --force "${STACK_NAME}_celery_worker"
docker service update --force "${STACK_NAME}_celery_beat"
