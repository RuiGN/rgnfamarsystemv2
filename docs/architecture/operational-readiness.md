# Prontidão Operacional e Requisitos Não Funcionais

O projeto inclui o avaliador `core.operational_readiness` e o comando
`check_operational_readiness` para verificar requisitos não funcionais de
runtime, UI, processamento assíncrono e Docker Swarm.

## Comando

```bash
.venv/bin/python manage.py check_operational_readiness
.venv/bin/python manage.py check_operational_readiness --format json
.venv/bin/python manage.py check_operational_readiness --fail-on-error
```

O relatório cobre:

- `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` carregados por `.env`.
- `SECURE_PROXY_SSL_HEADER` e redirect seguro para operação atrás do Traefik.
- Startup ordenado do app com `wait_for_db`, `migrate_with_lock` e
  `collectstatic --noinput --clear`.
- Worker e beat aguardando banco e migrations aplicadas sem executar
  migrations nem collectstatic.
- Janela mínima de 600 segundos nos healthchecks de primeira inicialização do
  app e workers, com espera de migrations por até 900 segundos nos workers.
- Docker Swarm com healthchecks, `restart_policy`, `resources` e
  `update_config.failure_action=rollback` em todos os serviços.
- Isolamento de rede para manter workers fora da `traefik_public`.
- Traefik com Cloudflare DNS-01 sem `tlschallenge` simultâneo.
- Serviços locais mínimos no Docker Compose.
- Shell responsivo com classes do design system Duralux.
- Celery worker e beat para processos pesados assíncronos.
- `worker-entrypoint.sh` usa `wait_for_migrations` para evitar que o beat
  consulte tabelas do `django_celery_beat` antes do app concluir as migrations.
- `start_period: 600s` evita marcação prematura de `unhealthy` enquanto o app
  executa a primeira carga de migrations em banco limpo.
- Documentação e scripts de deploy e backup.

## Docker Swarm

O `docker-stack.yml` declara healthchecks para Traefik, app, worker, beat,
PostgreSQL, Redis e RabbitMQ. Todos os serviços também possuem política de
restart, limites/reservas de recurso e rollback em atualização.

Os workers usam apenas as redes internas/egress. Somente Traefik e app ficam na
rede pública.

## Critério de Aceitação

A sprint operacional é aceita quando:

- `check_operational_readiness --format json` retorna `passed=true`.
- `pytest tests/test_operational_readiness.py` passa.
- `mkdocs build` inclui esta página.
- O smoke HTTP do servidor local responde `/health/`, `/` e `/api/schema/`.
