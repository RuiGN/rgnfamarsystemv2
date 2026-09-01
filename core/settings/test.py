"""Deterministic PostgreSQL settings for automated tests and validation pipelines."""

import environ

from .base import *  # noqa: F403


test_env = environ.Env()
TEST_DATABASE_URL = test_env('TEST_DATABASE_URL', default='')
if not TEST_DATABASE_URL or not TEST_DATABASE_URL.startswith(('postgresql://', 'postgres://')):
    raise environ.ImproperlyConfigured(
        'TEST_DATABASE_URL must reference an isolated PostgreSQL database.'
    )

DATABASES = {'default': test_env.db_url_config(TEST_DATABASE_URL)}
DATABASES['default']['CONN_MAX_AGE'] = 0
DATABASES['default']['TEST'] = {'NAME': f'test_{DATABASES["default"]["NAME"]}'}

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
DATA_ENCRYPTION_KEY_ID = 'test'
DATA_ENCRYPTION_KEYS = 'test:cmduLWZhcm1hLXRlc3Qta2V5LTAxMjM0NTY3ODlhYmM='
MIDDLEWARE = [
    middleware
    for middleware in MIDDLEWARE
    if middleware != 'whitenoise.middleware.WhiteNoiseMiddleware'
]

DEBUG = False
CSRF_TRUSTED_ORIGINS = ['https://testserver']
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
