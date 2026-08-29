#!/usr/bin/env bash
set -euo pipefail

: "${TEST_DATABASE_URL:?TEST_DATABASE_URL is required}"

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-core.settings.test}"
STATIC_ANALYSIS_PACKAGES=(
  core
  accounts
  ai_agents
  audits
  auxiliary
  base
  capa
  changes
  compliance
  control_plane
  costing
  crm
  deviations
  documents
  files
  finance
  fiscal
  formulations
  governance
  integrations
  inventory
  knowledge
  masters
  pharmacovigilance
  planning
  procurement
  production
  qa
  quality
  recalls
  regulatory
  reports
  risks
  tenants
  training
  workflow
)

python manage.py check
python manage.py makemigrations --check --dry-run
ruff check .
ruff format --check .
mypy "${STATIC_ANALYSIS_PACKAGES[@]}"
bandit -r "${STATIC_ANALYSIS_PACKAGES[@]}" -q
pip-audit --strict
pytest --cov=. --cov-report=term-missing --cov-report=xml --cov-fail-under=80
python manage.py spectacular --file openapi-schema.yml --validate --fail-on-warn
python manage.py check_operational_readiness --fail-on-error
python manage.py check_backup_restore_readiness --fail-on-error
python manage.py check_product_acceptance --fail-on-error
python manage.py check_release_readiness --fail-on-error

DJANGO_SETTINGS_MODULE=core.settings.production python manage.py check --deploy --fail-level WARNING
