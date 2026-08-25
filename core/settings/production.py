"""Fail-fast settings profile for production deployments."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


def require_production(condition, message):
    if not condition:
        raise ImproperlyConfigured(message)


require_production(
    bool(SECRET_KEY) and SECRET_KEY != DEVELOPMENT_SECRET_KEY_DEFAULT,
    'SECRET_KEY must be explicitly configured with a non-default production value.',
)
require_production(DEBUG is False, 'DEBUG must be False in production.')
require_production(ALLOWED_HOSTS, 'ALLOWED_HOSTS must not be empty in production.')
require_production(
    DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql',
    'DATABASE_URL must reference PostgreSQL in production.',
)
require_production(
    CUSTOMER_APP_BASE_URL.startswith('https://'),
    'CUSTOMER_APP_BASE_URL must use HTTPS in production.',
)
require_production(
    bool(DATA_ENCRYPTION_KEYS or DATA_ENCRYPTION_KEY),
    'DATA_ENCRYPTION_KEYS must be configured in production.',
)

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=False)
