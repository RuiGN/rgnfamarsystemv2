# Deploy na VPS Contabo

Use `/opt/rgnfarmasystem`, Docker Compose v2 e `.env` com permissão `0600`.
Somente `rgnfarmasystem.rgnsystems.com.br` é público; Nginx escuta no host em
`127.0.0.1:8081` e o Cloudflare Tunnel aponta para essa origem.
O Compose impõe `core.settings.production`; mantenha no dotenv os valores HSTS
documentados em `.env.example`.

## Atualização segura

Crie e valide o backup antes de `migrate` ou da substituição dos containers:

```bash
cd /opt/rgnfarmasystem
release_dir="backups/release-$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 0700 "$release_dir"
docker compose -f docker-compose.vps.yml exec -T db sh -c \
  'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$release_dir/postgres.sql.gz"
docker run --rm -v rgnfarmasystem_media:/source:ro \
  -v "$PWD/$release_dir":/backup alpine \
  tar -czf /backup/media.tar.gz -C /source .
gzip -t "$release_dir/postgres.sql.gz"
tar -tzf "$release_dir/media.tar.gz" >/dev/null
sha256sum "$release_dir/postgres.sql.gz" "$release_dir/media.tar.gz" \
  > "$release_dir/SHA256SUMS"
```

Depois promova somente o SHA aprovado:

```bash
docker compose -f docker-compose.vps.yml config --quiet
docker compose -f docker-compose.vps.yml up -d --build --remove-orphans
docker compose -f docker-compose.vps.yml ps
curl -fsS -H 'Host: rgnfarmasystem.rgnsystems.com.br' \
  http://127.0.0.1:8081/health/
```

O procedimento completo, incluindo rollback e aceite público, está em
[`docs/DEPLOY_VPS.md`](../../docs/DEPLOY_VPS.md).
