"""Deterministic settings for automated tests and validation pipelines.

Aceita PostgreSQL (quando ``TEST_DATABASE_URL`` aponta para um banco Postgres
isolado, usado em CI) ou SQLite (default local quando ``TEST_DATABASE_URL``
nao e definido). String vazia continua sendo rejeitada com erro.
"""

import environ

from .base import *  # noqa: F403


test_env = environ.Env()
# Default SQLite local permite rodar a suite sem Postgres. Em CI, scripts/test.sh
# exporta TEST_DATABASE_URL apontando para um Postgres isolado.
TEST_DATABASE_URL = test_env('TEST_DATABASE_URL', default='sqlite:///test_db.sqlite3')
if not TEST_DATABASE_URL or not TEST_DATABASE_URL.startswith(
    ('postgresql://', 'postgres://', 'sqlite://')
):
    raise environ.ImproperlyConfigured(
        'TEST_DATABASE_URL must reference an isolated PostgreSQL or SQLite database.'
    )

DATABASES = {'default': test_env.db_url_config(TEST_DATABASE_URL)}
DATABASES['default']['CONN_MAX_AGE'] = 0
DATABASES['default']['TEST'] = {'NAME': DATABASES['default']['NAME']}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'rgnfarmasystem-tests',
    }
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
DEMO_USER_PASSWORD = 'TestOnly-Demo-Password-2026!'  # nosec B105
MIDDLEWARE = [
    middleware
    for middleware in MIDDLEWARE
    if middleware != 'whitenoise.middleware.WhiteNoiseMiddleware'
]

DEBUG = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
