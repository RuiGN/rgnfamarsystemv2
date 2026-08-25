"""Perfil de settings para rodar localmente com SQLite.

Usado quando se quer executar o projeto sem Postgres, Redis nem RabbitMQ:

    DJANGO_SETTINGS_MODULE=core.settings.sqlite python manage.py migrate
    DJANGO_SETTINGS_MODULE=core.settings.sqlite python manage.py runserver

- Banco: SQLite em BASE_DIR/db.sqlite3
- Cache: LocMemCache (em memoria, sem Redis)
- Celery: modo eager (tarefas rodam sincronas, sem broker)
- E-mail: console

Os perfis de producao (core.settings.production) e de teste
(core.settings.test) continuam exigindo PostgreSQL por design e nao
sao afetados por este perfil.
"""

from .base import *  # noqa: F403

# Banco de dados SQLite local.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),  # noqa: F405
        "CONN_MAX_AGE": 0,
        "OPTIONS": {},
    }
}

# Cache em memoria (sem Redis).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "rgnfarmasystem-sqlite-local",
    }
}

# Celery sincrono: sem RabbitMQ/Redis.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# E-mail no console para desenvolvimento local.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Midia local.
MEDIA_ROOT = BASE_DIR / "media"  # noqa: F405

# Desenvolvimento local: cookies/SSL sem exigencias de producao.
DEBUG = True
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
