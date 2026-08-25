#!/usr/bin/env sh
set -eu

python manage.py wait_for_db
python manage.py wait_for_migrations --timeout "${MIGRATION_WAIT_TIMEOUT:-900}" --interval "${MIGRATION_WAIT_INTERVAL:-2}"

exec "$@"
