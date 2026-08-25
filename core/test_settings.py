from .settings import *  # noqa: F403


# Tests exercise requests in-process and must not inherit production-only
# transport enforcement from a local or container .env file.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Password strength is validated separately; a fast hasher keeps the complete
# application suite practical without changing production authentication.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Demo data must never rely on a shared production credential. This value is
# scoped to the disposable test database only.
DEMO_USER_PASSWORD = 'TestOnly-Demo-Password-2026!'  # nosec B105
