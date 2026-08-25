# Deploy single-domain

O runbook canônico é [`docs/DEPLOY_VPS.md`](DEPLOY_VPS.md). A produção autorizada
usa Docker Compose na Contabo, Nginx publicado somente em `127.0.0.1:8081` e
Cloudflare Tunnel para `https://rgnfarmasystem.rgnsystems.com.br`.

## Ordem obrigatória

1. Validar o candidato local, o diff e as migrations pendentes.
2. Registrar o SHA remoto e criar backup PostgreSQL e de mídia.
3. Validar `gzip`, `tar` e SHA-256 dos artefatos.
4. Promover o SHA aprovado por fast-forward.
5. Executar `docker compose -f docker-compose.vps.yml up -d --build --remove-orphans`.
6. Confirmar migrate, saúde dos serviços, login e endpoints internos.
7. Validar o domínio público e preservar backup/revisão anterior até o aceite.

O backup sempre ocorre antes de qualquer `migrate`. Não use `git reset --hard`,
não remova volumes e não carregue `.env` como código shell.

## Execução local sem HTTPS

O servidor de desenvolvimento atende somente em HTTP. Copie
`.env.development.example` e mantenha estas sobreposições locais, nunca no
perfil de produção:

```dotenv
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
```

Depois execute `migrate`, `check` e `runserver 127.0.0.1:8000` com o ambiente
virtual. Os testes usam o PostgreSQL isolado de `docker-compose.test.yml` pelo
perfil `core.settings.test`.

## Verificação da topologia

```bash
docker compose -f docker-compose.vps.yml config --quiet
docker compose -f docker-compose.vps.yml ps
curl -fsS -o /dev/null -w '%{http_code}\n' \
  -H 'Host: rgnfarmasystem.rgnsystems.com.br' \
  http://127.0.0.1:8081/health/
```

PostgreSQL, Redis e RabbitMQ permanecem apenas na rede `backend`. O container
`cloudflared` usa rede host e a origem gerenciada
`http://127.0.0.1:8081`.

## Backup, restauração e retenção

O Compose da Contabo faz o backup de release diretamente pelos serviços `db` e
pela volume de mídia, como descrito no runbook canônico. Para executar os
scripts portáveis contra um PostgreSQL externo, deixe o Docker interpretar o
dotenv sem `source` e sem imprimir credenciais:

```bash
APP_IMAGE=$(docker compose -f docker-compose.vps.yml images -q app)
docker run --rm --env-file .env --add-host host.docker.internal:host-gateway \
  -e DB_DEPLOYMENT=external -e BACKUP_DIR=/backups -e RETENTION_DAYS=14 \
  -v /var/backups/rgnfarmasystem:/backups \
  -v "$PWD:/workspace:ro" --entrypoint bash "$APP_IMAGE" \
  /workspace/scripts/backup.sh
docker run --rm --env-file .env --add-host host.docker.internal:host-gateway \
  -e DB_DEPLOYMENT=external -e BACKUP_DIR=/backups \
  -v /var/backups/rgnfarmasystem:/backups \
  -v "$PWD:/workspace:ro" --entrypoint bash "$APP_IMAGE" \
  /workspace/scripts/restore.sh --postgres /backups/postgres-AAAAmmdd-HHMMSS.sql.gz --dry-run
```

O restore real exige o mesmo artefato validado, um backup `pre-restore` e a
confirmação `--yes`. A política off-site pode usar Google Drive por meio de
`scripts/backup_to_drive.sh`; cada envio gera trilha `BackupRun` com SHA-256.

Agendamento alternativo no host, sempre com o dotenv de produção e o gateway
explícito:

```cron
15 2 * * * /bin/bash -c 'APP_IMAGE=$(docker compose -f /opt/rgnfarmasystem/docker-compose.vps.yml images -q app); docker run --rm --env-file /opt/rgnfarmasystem/.env --add-host host.docker.internal:host-gateway -e DB_DEPLOYMENT=external -e BACKUP_DIR=/backups -e RETENTION_DAYS=14 -v /var/backups/rgnfarmasystem:/backups -v /opt/rgnfarmasystem:/workspace:ro --entrypoint bash "$APP_IMAGE" /workspace/scripts/backup.sh' >> /var/log/rgnfarmasystem/backup.log 2>&1
```

Valide os contratos antes da promoção:

```bash
.venv/bin/python manage.py check_backup_restore_readiness --fail-on-error
.venv/bin/python manage.py check_operational_readiness --fail-on-error
.venv/bin/python manage.py check_product_acceptance --fail-on-error
.venv/bin/python manage.py check_release_readiness --fail-on-error
```

## Rollback

Reimplante o SHA e a imagem registrados antes da janela. Restaure banco ou
mídia somente quando uma migration incompatível tiver sido aplicada, depois de
validar os hashes. Backups não são apagados no rollback.
