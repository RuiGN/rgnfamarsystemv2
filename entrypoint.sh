#!/usr/bin/env sh
set -eu

python manage.py wait_for_db
python manage.py migrate_with_lock
python manage.py collectstatic --noinput --clear

exec "$@"
