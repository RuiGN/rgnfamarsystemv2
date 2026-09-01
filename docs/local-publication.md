# Publicação local com Docker e PostgreSQL

Este é o guia canônico de desenvolvimento. A aplicação e o PostgreSQL são
executados pelo Docker Compose, conforme `docs/architecture/single-instance.md`.

## Serviços

A topologia Docker local contém Nginx, Django/Gunicorn, PostgreSQL, Redis,
RabbitMQ, Celery Worker e Celery Beat.

## Inicialização

```bash
./scripts/prepare_local_publication.sh
docker compose --env-file .env.local -f docker-compose.local.yml up -d --build
docker compose --env-file .env.local -f docker-compose.local.yml ps
```

## Acesso

- ERP: `http://erp.localhost:4127/app/`
- Django Admin: `http://erp.localhost:4127/admin/`

Use o usuário criado por `manage.py createsuperuser`; a senha deve ser definida
fora do Git. ERP e Admin compartilham `/accounts/login/`, e o runtime usa
permissões Django.

Não existe hostname administrativo separado, MFA de plataforma ou rota de
Control Plane.

## Smoke test

```bash
./scripts/smoke_local.sh
```

Confirme o banco utilizado:

```bash
docker compose --env-file .env.local -f docker-compose.local.yml exec app python manage.py shell -c "from django.db import connection; print(connection.vendor)"
```

O resultado esperado é `postgresql`.

## Parada

```bash
docker compose --env-file .env.local -f docker-compose.local.yml down
```
