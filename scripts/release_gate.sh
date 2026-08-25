#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-}"
COMMIT="${GITHUB_SHA:-$(git rev-parse HEAD 2>/dev/null || true)}"

if [[ ! "${VERSION}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo 'Versão inválida; use vMAJOR.MINOR.PATCH.' >&2
  exit 2
fi
if [[ ! "${COMMIT}" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'GITHUB_SHA ou commit Git de 40 caracteres é obrigatório.' >&2
  exit 2
fi

echo "release_version=${VERSION}"
echo "release_commit=${COMMIT}"
if [[ "${RUN_RELEASE_GATES:-false}" == 'true' ]]; then
  python manage.py check
  python manage.py makemigrations --check --dry-run
  python manage.py check_release_readiness --fail-on-error
fi
