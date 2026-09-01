# Prontidão Operacional e Requisitos Não Funcionais

O avaliador `core.operational_readiness` e o comando
`check_operational_readiness` verificam os contratos de runtime, interface,
processamento assíncrono e implantação com Docker Compose na VPS.

## Comando

```bash
.venv/bin/python manage.py check_operational_readiness
.venv/bin/python manage.py check_operational_readiness --format json
.venv/bin/python manage.py check_operational_readiness --fail-on-error
```

O relatório cobre:

- `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` carregados por `.env`.
- `SECURE_PROXY_SSL_HEADER` e redirect seguro atrás do Nginx e do Cloudflare
  Tunnel.
- Startup ordenado do app com `wait_for_db`, `migrate_with_lock` e
  `collectstatic --noinput --clear`.
- Worker e beat aguardando banco e migrations sem executá-las.
- Janela mínima de 600 segundos para migrations iniciais.
- Healthcheck e `restart: unless-stopped` em todos os serviços da VPS.
- Banco, cache e filas sem portas publicadas no host.
- Nginx publicado exclusivamente em `127.0.0.1:8081`.
- Conector com endpoint `/ready` em `127.0.0.1:20241` e validação pública.
- `backup_scheduler` com banco privado, mídia somente leitura, lock e marcadores
  locais de saúde.
- Backup anterior à promoção e rollback automático apenas do código; dados só
  são restaurados mediante procedimento explícito.
- Serviços mínimos no Compose local, UI responsiva e Celery.

## Topologia de produção

`docker-compose.vps.yml` é a única fonte de orquestração da VPS. App, workers,
PostgreSQL, Redis, RabbitMQ e backup compartilham a rede privada `backend`.
Somente o Nginx publica uma porta, vinculada ao loopback do host. O conector
usa a rede do host para alcançar essa origem e expõe métricas/prontidão apenas
no loopback.

O script `scripts/deploy-vps.sh` valida o Compose, cria e confere o backup,
promove a revisão por fast-forward, aguarda healthchecks, testa origem,
conector e domínio público. Em falha, reimplanta o SHA anterior sem restaurar
banco ou mídia automaticamente.

## Critério de aceitação

- `check_operational_readiness --format json` retorna `passed=true`.
- `pytest tests/test_operational_readiness.py tests/test_vps_compose_contract.py`
  passa.
- `docker compose --env-file .env -f docker-compose.vps.yml config --quiet`
  passa com credenciais externas válidas.
- O smoke interno responde em `http://127.0.0.1:8081/health/`.
- O conector responde `200` em `http://127.0.0.1:20241/ready`.
- O domínio público responde `200` em `/health/`.
