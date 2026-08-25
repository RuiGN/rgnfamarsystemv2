# PostgreSQL nativo na VPS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Executar a stack de produção contra o PostgreSQL nativo da VPS sem perder backup, restauração, criptografia, upload ao Google Drive ou evidências auditáveis.

**Architecture:** Django, Celery e o serviço de backup permanecem no Docker Swarm e alcançam o PostgreSQL nativo por `host.docker.internal`, mapeado para `host-gateway`. Os scripts de backup e restore recebem um modo explícito `DB_DEPLOYMENT=external`, usam `pg_dump`/`psql` via TCP nesse modo e preservam o modo `container` para desenvolvimento e transição.

**Tech Stack:** Bash, Docker Swarm, PostgreSQL client, Django 5, pytest, YAML, MkDocs.

## Global Constraints

- O banco e o usuário de produção serão `rgnfarmasystem`.
- A senha aprovada ficará somente no `.env` ignorado pelo Git e no PostgreSQL da VPS.
- Não registrar credenciais reais em commits, documentação, testes, logs ou saída de comandos.
- Não remover o volume `postgres_data` existente durante a migração; seu descarte será manual e posterior.
- Manter RPO de 24 horas, RTO técnico de 2 horas, retenção padrão de 14 dias e janela diária padrão de 03:00 em `America/Recife`.
- Preservar AES-256-GCM, sidecar SHA-256, Google Drive e registros `auxiliary.BackupRun`.
- A porta 5432 deve permanecer bloqueada para a Internet e liberada somente para a faixa Docker necessária.
- `docker-compose.yml` continuará usando PostgreSQL em container para desenvolvimento local.

---

## File Structure

- `tests/test_native_postgres_deployment.py`: contratos automatizados da imagem, stack, ambiente e scripts para PostgreSQL nativo.
- `Dockerfile`: instala os binários `pg_dump`, `pg_isready` e `psql` usados pelo backup/restore direto.
- `docker-stack.yml`: remove o PostgreSQL da stack de produção e entrega resolução do gateway aos consumidores do banco.
- `scripts/backup.sh`: seleciona explicitamente backup externo ou em container e publica artefatos apenas após sucesso.
- `scripts/restore.sh`: seleciona explicitamente restore externo ou em container, mantendo os controles pré-restore.
- `.env.example`: documenta as variáveis não secretas da topologia externa.
- `.env`: recebe os valores reais aprovados sem ser versionado.
- `scripts/deploy-vps.sh`: valida a topologia, os binários do host e a alcançabilidade do PostgreSQL antes do deploy.
- `docs/DEPLOY_VPS.md`: runbook de provisionamento e migração da VPS.
- `docs/deployment.md`: referência operacional resumida.
- `docs/architecture/backup-restore.md`: contrato canônico de backup/restore externo.
- `README.md`: comandos rápidos coerentes com o novo modo.

### Task 1: Contrato da imagem e da stack de produção

**Files:**
- Create: `tests/test_native_postgres_deployment.py`
- Modify: `Dockerfile`
- Modify: `docker-stack.yml`
- Modify: `.env.example`

**Interfaces:**
- Consumes: variáveis `DATABASE_URL`, `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD` já lidas pelos containers via `.env`.
- Produces: `DB_DEPLOYMENT=external`, `DB_HOST=host.docker.internal`, `DB_PORT=5432` e resolução `host.docker.internal:host-gateway` para `app`, `celery_worker`, `celery_beat` e `backup_uploader`.

- [ ] **Step 1: Escrever os testes de contrato que devem falhar**

```python
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_production_stack_uses_native_postgres():
    stack = yaml.safe_load((ROOT / 'docker-stack.yml').read_text(encoding='utf-8'))
    services = stack['services']
    assert 'db' not in services
    assert 'postgres_data' not in stack.get('volumes', {})
    for name in ('app', 'celery_worker', 'celery_beat', 'backup_uploader'):
        assert 'host.docker.internal:host-gateway' in services[name]['extra_hosts']


def test_production_image_contains_postgres_client():
    dockerfile = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
    assert 'postgresql-client' in dockerfile


def test_example_env_declares_external_database_without_real_secret():
    source = (ROOT / '.env.example').read_text(encoding='utf-8')
    assert 'DB_DEPLOYMENT=external' in source
    assert 'DB_HOST=host.docker.internal' in source
    assert 'DB_PORT=5432' in source
    assert '@host.docker.internal:5432/rgnfarmasystem' in source
    assert 'POSTGRES_PASSWORD=change-me' in source
```

- [ ] **Step 2: Executar os testes e confirmar a falha inicial**

Run: `.venv/bin/pytest tests/test_native_postgres_deployment.py -q`

Expected: FAIL porque `db` e `postgres_data` ainda existem, os consumidores não possuem `extra_hosts`, a imagem não instala `postgresql-client` e o exemplo ainda aponta para `db`.

- [ ] **Step 3: Instalar o cliente PostgreSQL na imagem**

Alterar o bloco de pacotes do `Dockerfile` para:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 4: Remover o banco da stack e mapear o gateway do host**

Excluir integralmente `services.db` e `volumes.postgres_data` de `docker-stack.yml`. Adicionar a cada um de `app`, `celery_worker`, `celery_beat` e `backup_uploader`:

```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Não alterar redes, secrets ou volumes do `backup_uploader`.

- [ ] **Step 5: Atualizar o exemplo de ambiente sem segredo real**

Substituir o bloco de banco de `.env.example` por:

```dotenv
DB_DEPLOYMENT=external
DB_HOST=host.docker.internal
DB_PORT=5432
POSTGRES_DB=rgnfarmasystem
POSTGRES_USER=rgnfarmasystem
POSTGRES_PASSWORD=change-me
DATABASE_URL=postgresql://rgnfarmasystem:change-me@host.docker.internal:5432/rgnfarmasystem
DATABASE_CONN_MAX_AGE=60
```

- [ ] **Step 6: Validar contratos e renderização da stack**

Run: `.venv/bin/pytest tests/test_native_postgres_deployment.py tests/test_local_compose_contract.py -q`

Expected: PASS; o contrato local continua apontando para `db` apenas em `docker-compose.yml`.

Run: `docker stack config -c docker-stack.yml >/tmp/rgnfarmasystem-stack.yml`

Expected: exit 0 e YAML renderizado sem serviço `db`.

- [ ] **Step 7: Commit**

```bash
git add tests/test_native_postgres_deployment.py Dockerfile docker-stack.yml .env.example
git commit -m "feat: connect production stack to native PostgreSQL"
```

### Task 2: Backup e restauração com alvo explícito

**Files:**
- Modify: `tests/test_native_postgres_deployment.py`
- Modify: `scripts/backup.sh`
- Modify: `scripts/restore.sh`

**Interfaces:**
- Consumes: `DB_DEPLOYMENT` com valores permitidos `external` ou `container`; `DB_HOST`, `DB_PORT`, `POSTGRES_USER`, `POSTGRES_DB` e `POSTGRES_PASSWORD`.
- Produces: dumps atômicos `postgres-YYYYmmdd-HHMMSS.sql.gz`; restore externo via `psql`; compatibilidade com `DB_DEPLOYMENT=container`.

- [ ] **Step 1: Acrescentar testes estáticos para seleção explícita e atomicidade**

Adicionar em `tests/test_native_postgres_deployment.py`:

```python
def test_backup_supports_explicit_external_database():
    source = (ROOT / 'scripts' / 'backup.sh').read_text(encoding='utf-8')
    assert 'DB_DEPLOYMENT' in source
    assert 'external)' in source
    assert 'container)' in source
    assert 'mktemp' in source
    assert 'PGPASSWORD=' in source
    assert 'pg_dump' in source


def test_restore_supports_external_database_and_keeps_safety_gates():
    source = (ROOT / 'scripts' / 'restore.sh').read_text(encoding='utf-8')
    assert 'DB_DEPLOYMENT' in source
    assert 'restore_external_postgres' in source
    assert 'PGPASSWORD=' in source
    assert 'psql' in source
    assert '--dry-run' in source
    assert '--yes' in source
    assert 'pre-restore-' in source


def test_scripts_reject_unknown_database_deployment():
    for name in ('backup.sh', 'restore.sh'):
        source = (ROOT / 'scripts' / name).read_text(encoding='utf-8')
        assert 'DB_DEPLOYMENT invalido' in source
```

- [ ] **Step 2: Executar os novos testes e confirmar a falha**

Run: `.venv/bin/pytest tests/test_native_postgres_deployment.py -q`

Expected: FAIL porque os scripts ainda inferem a topologia pela presença do Docker e o restore exige container.

- [ ] **Step 3: Tornar o backup explícito e atômico**

Em `scripts/backup.sh`, definir:

```bash
DB_DEPLOYMENT="${DB_DEPLOYMENT:-container}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
POSTGRES_TARGET="${BACKUP_DIR}/postgres-${TIMESTAMP}.sql.gz"
POSTGRES_TMP="$(mktemp "${BACKUP_DIR}/.postgres-${TIMESTAMP}.XXXXXX.sql.gz")"
trap 'rm -f "$POSTGRES_TMP"' EXIT
```

Substituir a inferência principal por:

```bash
case "$DB_DEPLOYMENT" in
  external)
    echo "Gerando dump do PostgreSQL externo em ${DB_HOST}:${DB_PORT}..."
    PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump \
      -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
      --no-owner --no-acl | gzip > "$POSTGRES_TMP"
    ;;
  container)
    command -v docker >/dev/null 2>&1 || {
      echo "Docker indisponivel para DB_DEPLOYMENT=container." >&2
      exit 1
    }
    DB_CONTAINER="$(docker ps --filter "name=${STACK_NAME}_db" --format '{{.ID}}' | head -n 1)"
    [[ -n "$DB_CONTAINER" ]] || {
      echo "Container do PostgreSQL nao encontrado." >&2
      exit 1
    }
    docker exec "$DB_CONTAINER" pg_dump \
      -U "$POSTGRES_USER" "$POSTGRES_DB" --no-owner --no-acl \
      | gzip > "$POSTGRES_TMP"
    ;;
  *)
    echo "DB_DEPLOYMENT invalido: ${DB_DEPLOYMENT}. Use external ou container." >&2
    exit 1
    ;;
esac
mv "$POSTGRES_TMP" "$POSTGRES_TARGET"
trap - EXIT
```

Manter o backup de mídia independente: usar Docker para copiar `/app/media` quando disponível e `MEDIA_DIR` quando executado dentro do `backup_uploader`.

- [ ] **Step 4: Implementar restore PostgreSQL externo**

Em `scripts/restore.sh`, adicionar `DB_DEPLOYMENT`, `DB_HOST` e `DB_PORT`, validar o enum e criar:

```bash
restore_external_postgres() {
  local source_path="$1"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY-RUN: PGPASSWORD=<redacted> psql -v ON_ERROR_STOP=1 -h ${DB_HOST} -p ${DB_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c 'DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;'"
    echo "DRY-RUN: gunzip -c ${source_path} | PGPASSWORD=<redacted> psql -v ON_ERROR_STOP=1 -h ${DB_HOST} -p ${DB_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB}"
    return
  fi
  PGPASSWORD="${POSTGRES_PASSWORD:-}" psql \
    -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -c 'DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;'
  gunzip -c "$source_path" | PGPASSWORD="${POSTGRES_PASSWORD:-}" psql \
    -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB"
}
```

No fluxo PostgreSQL, chamar `restore_external_postgres` para `external` e preservar os comandos `docker exec` para `container`. Só procurar `DB_CONTAINER` quando o modo for `container`; continuar procurando `APP_CONTAINER` separadamente quando houver restore de mídia.

- [ ] **Step 5: Executar os testes de scripts e prontidão**

Run: `.venv/bin/pytest tests/test_native_postgres_deployment.py tests/test_backup_to_drive_script.py tests/test_backup_restore_readiness.py -q`

Expected: PASS.

Run: `bash -n scripts/backup.sh scripts/restore.sh scripts/backup_to_drive.sh`

Expected: exit 0 sem saída.

- [ ] **Step 6: Commit**

```bash
git add tests/test_native_postgres_deployment.py scripts/backup.sh scripts/restore.sh
git commit -m "feat: support native PostgreSQL backup and restore"
```

### Task 3: Pré-flight seguro do deploy e ambiente real local

**Files:**
- Modify: `tests/test_native_postgres_deployment.py`
- Modify: `scripts/deploy-vps.sh`
- Modify: `.env` (ignorado; não adicionar ao Git)

**Interfaces:**
- Consumes: ambiente da Task 1 e PostgreSQL provisionado na VPS.
- Produces: `check_native_postgres()` bloqueando deploy quando a topologia ou conexão estiver inválida; `.env` real apontando ao host.

- [ ] **Step 1: Escrever teste de contrato do pré-flight**

Adicionar:

```python
def test_deploy_checks_native_postgres_without_printing_password():
    source = (ROOT / 'scripts' / 'deploy-vps.sh').read_text(encoding='utf-8')
    assert 'check_native_postgres' in source
    assert 'pg_isready' in source
    assert 'DB_DEPLOYMENT' in source
    assert 'host.docker.internal' in source
    assert '<redacted>' in source
```

- [ ] **Step 2: Executar o teste e confirmar a falha**

Run: `.venv/bin/pytest tests/test_native_postgres_deployment.py::test_deploy_checks_native_postgres_without_printing_password -q`

Expected: FAIL porque o deploy ainda não verifica o PostgreSQL nativo.

- [ ] **Step 3: Implementar o pré-flight**

Adicionar a `scripts/deploy-vps.sh` uma leitura de chaves que não execute o `.env` e uma função que valide `DB_DEPLOYMENT=external`, `DB_HOST=host.docker.internal`, `DB_PORT`, banco e usuário. Executar o teste de rede em container usando a própria imagem:

```bash
check_native_postgres() {
    local db_deployment db_host db_port postgres_db postgres_user postgres_password image_tag
    db_deployment=$(read_env_value DB_DEPLOYMENT)
    db_host=$(read_env_value DB_HOST)
    db_port=$(read_env_value DB_PORT)
    postgres_db=$(read_env_value POSTGRES_DB)
    postgres_user=$(read_env_value POSTGRES_USER)
    postgres_password=$(read_env_value POSTGRES_PASSWORD)
    image_tag=$(read_env_value IMAGE_TAG)

    [[ "$db_deployment" == "external" ]] || {
        log_error "DB_DEPLOYMENT deve ser external na VPS."
        exit 1
    }
    [[ "$db_host" == "host.docker.internal" ]] || {
        log_error "DB_HOST deve ser host.docker.internal na VPS."
        exit 1
    }
    log_info "Validando PostgreSQL nativo em ${db_host}:${db_port} com senha <redacted>..."
    docker run --rm --add-host host.docker.internal:host-gateway \
        -e PGPASSWORD="$postgres_password" \
        "ghcr.io/ruign/rgnfarmasystem:${image_tag:-latest}" \
        pg_isready -h "$db_host" -p "$db_port" -U "$postgres_user" -d "$postgres_db" || {
            log_error "PostgreSQL nativo indisponivel para a stack."
            exit 1
        }
}
```

Implementar `read_env_value()` com Python ou `awk` lendo exatamente `CHAVE=valor`, sem `source .env`, e chamar `check_native_postgres` depois de `check_env_file` e antes de `deploy_stack`.

- [ ] **Step 4: Atualizar o `.env` ignorado pelo Git**

Alterar apenas estas chaves, preservando todas as demais. Usar a senha aprovada
recebida na sessão como valor real das duas ocorrências indicadas; não copiá-la
para o plano, terminal ou saída de ferramentas:

```dotenv
DB_DEPLOYMENT=external
DB_HOST=host.docker.internal
DB_PORT=5432
POSTGRES_DB=rgnfarmasystem
POSTGRES_USER=rgnfarmasystem
POSTGRES_PASSWORD=[valor secreto fornecido na sessão]
DATABASE_URL=postgresql://rgnfarmasystem:[mesmo valor secreto codificado para URL]@host.docker.internal:5432/rgnfarmasystem
```

Confirmar que `git check-ignore .env` retorna sucesso. Não executar `git add -f .env` e não imprimir o arquivo.

- [ ] **Step 5: Validar sem revelar segredos**

Run: `.venv/bin/pytest tests/test_native_postgres_deployment.py -q`

Expected: PASS.

Run: `bash -n scripts/deploy-vps.sh && git check-ignore .env`

Expected: ambos retornam exit 0; nenhuma senha aparece na saída.

- [ ] **Step 6: Commit somente dos arquivos versionáveis**

```bash
git add tests/test_native_postgres_deployment.py scripts/deploy-vps.sh
git commit -m "feat: validate native PostgreSQL before deploy"
```

### Task 4: Runbook de provisionamento, migração e rollback

**Files:**
- Modify: `docs/DEPLOY_VPS.md`
- Modify: `docs/deployment.md`
- Modify: `docs/architecture/backup-restore.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `DB_DEPLOYMENT=external` e scripts das Tasks 1–3.
- Produces: procedimento operacional completo para configurar a VPS, migrar dados, validar e reverter.

- [ ] **Step 1: Acrescentar teste documental**

Adicionar a `tests/test_native_postgres_deployment.py`:

```python
def test_vps_docs_cover_native_postgres_security_migration_and_restore():
    sources = '\n'.join(
        (ROOT / path).read_text(encoding='utf-8')
        for path in (
            'docs/DEPLOY_VPS.md',
            'docs/deployment.md',
            'docs/architecture/backup-restore.md',
        )
    )
    for marker in (
        'host.docker.internal',
        'DB_DEPLOYMENT=external',
        'listen_addresses',
        'pg_hba.conf',
        'scram-sha-256',
        'pg_dump',
        'psql',
        'Google Drive',
        'rollback',
    ):
        assert marker in sources
```

- [ ] **Step 2: Executar o teste e confirmar a falha**

Run: `.venv/bin/pytest tests/test_native_postgres_deployment.py::test_vps_docs_cover_native_postgres_security_migration_and_restore -q`

Expected: FAIL com um ou mais marcadores ausentes.

- [ ] **Step 3: Documentar provisionamento seguro sem senha literal**

Em `docs/DEPLOY_VPS.md`, incluir comandos que solicitam a senha sem gravá-la no histórico:

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE rgnfarmasystem LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE rgnfarmasystem OWNER rgnfarmasystem;
SQL
sudo -u postgres psql -c '\password rgnfarmasystem'
```

Documentar `listen_addresses` restrito à interface necessária, `password_encryption = 'scram-sha-256'`, uma regra `pg_hba.conf` no formato:

Documentar a geração da regra com a subnet real, sem valor manual pendente:

```bash
DOCKER_GW_SUBNET=$(docker network inspect docker_gwbridge --format '{{(index .IPAM.Config 0).Subnet}}')
printf 'host  rgnfarmasystem  rgnfarmasystem  %s  scram-sha-256\n' "$DOCKER_GW_SUBNET"
```

Orientar o operador a copiar a linha produzida para `pg_hba.conf`, recarregar
PostgreSQL e manter 5432 bloqueada externamente.

- [ ] **Step 4: Documentar migração e rollback com comandos exatos**

Registrar a sequência:

```bash
DB_DEPLOYMENT=container BACKUP_DIR=/var/backups/rgnfarmasystem-migration bash scripts/backup.sh
MIGRATION_DUMP=$(find /var/backups/rgnfarmasystem-migration -maxdepth 1 -name 'postgres-*.sql.gz' -type f -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)
gunzip -t "$MIGRATION_DUMP"
DB_DEPLOYMENT=external bash scripts/restore.sh --postgres "$MIGRATION_DUMP" --dry-run
DB_DEPLOYMENT=external bash scripts/restore.sh --postgres "$MIGRATION_DUMP" --yes
./scripts/deploy-vps.sh
```

Como o formato atual é SQL comprimido, documentar que sua verificação efetiva
usa `gunzip -t` e restore isolado. No rollback, restaurar o `DATABASE_URL`
anterior, reimplantar a versão anterior de `docker-stack.yml` e preservar tanto
o volume antigo quanto o dump da migração.

- [ ] **Step 5: Atualizar o contrato canônico de backup/restore**

Em `docs/architecture/backup-restore.md`, substituir a premissa “PostgreSQL em Docker Swarm” por ambos os modos, tornar `external` o modo de produção, mostrar o fluxo TCP pelo gateway, e adicionar aos critérios de aceitação:

```markdown
- Produção usa `DB_DEPLOYMENT=external` e `host.docker.internal`.
- Backup e restore usam `pg_dump`/`psql` diretamente no modo externo.
- Credenciais nunca aparecem no log nem nos artefatos versionados.
- Um restore isolado comprova cada ciclo de backup antes da expiração da retenção.
```

Atualizar `docs/deployment.md` e `README.md` para apontar ao runbook canônico e usar `DB_DEPLOYMENT=external` nos comandos da VPS.

- [ ] **Step 6: Executar testes documentais e prontidão**

Run: `.venv/bin/pytest tests/test_native_postgres_deployment.py tests/test_backup_restore_readiness.py tests/test_operational_readiness.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tests/test_native_postgres_deployment.py docs/DEPLOY_VPS.md docs/deployment.md docs/architecture/backup-restore.md README.md
git commit -m "docs: add native PostgreSQL migration runbook"
```

### Task 5: Verificação integrada e evidência de implantação

**Files:**
- Modify only if a verification exposes a defect in an in-scope file from Tasks 1–4.

**Interfaces:**
- Consumes: todos os contratos e runbooks anteriores.
- Produces: evidência local de qualidade e checklist operacional para execução na VPS.

- [ ] **Step 1: Executar validações locais completas e corrigir apenas defeitos no escopo**

Run:

```bash
bash -n scripts/backup.sh scripts/restore.sh scripts/backup_to_drive.sh scripts/deploy-vps.sh
.venv/bin/pytest tests/test_native_postgres_deployment.py tests/test_local_compose_contract.py tests/test_backup_to_drive_script.py tests/test_backup_restore_readiness.py tests/test_operational_readiness.py -q
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py makemigrations --check --dry-run
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_backup_restore_readiness --fail-on-error
git diff --check
```

Expected: todos os comandos retornam exit 0; migrations informa `No changes detected`; nenhuma senha aparece na saída ou no diff.

- [ ] **Step 2: Validar a imagem e a stack**

Run:

```bash
docker build -t rgnfarmasystem:native-postgres-test .
docker run --rm --entrypoint sh rgnfarmasystem:native-postgres-test -c 'pg_dump --version && psql --version && pg_isready --version'
docker stack config -c docker-stack.yml >/tmp/rgnfarmasystem-stack.yml
```

Expected: build e comandos retornam exit 0; os três binários informam uma versão; a stack renderizada não contém serviço `db`.

- [ ] **Step 3: Executar checklist na VPS durante a janela aprovada**

Run na VPS, sem imprimir o `.env`:

```bash
sudo -u postgres pg_isready -d rgnfarmasystem
./scripts/deploy-vps.sh
docker service ls --filter name=rgnfarmasystem
curl -fsS https://rgnfarmasystem.rgnsystems.com.br/health/
docker service update --env-add RUN_ONCE=true --force rgnfarmasystem_backup_uploader
docker service logs rgnfarmasystem_backup_uploader --since 15m
```

Expected: PostgreSQL aceita conexões; serviços convergem; health retorna 2xx; logs mostram dump, cifragem e upload concluídos sem senha.

- [ ] **Step 4: Confirmar evidência auditável e recuperação**

Run na VPS:

```bash
docker exec "$(docker ps --filter name=rgnfarmasystem_app -q | head -n 1)" python manage.py shell -c "from auxiliary.models import BackupRun; print(BackupRun.objects.order_by('-started_at').values('kind','status','drive_file_id','sha256').first())"
LATEST_DUMP=$(find /var/backups/rgnfarmasystem -maxdepth 1 -name 'postgres-*.sql.gz' -type f -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)
DB_DEPLOYMENT=external bash scripts/restore.sh --postgres "$LATEST_DUMP" --dry-run
```

Expected: último `BackupRun` possui `status='success'`, `drive_file_id` e `sha256`; o dry-run mostra conexão externa com senha redigida. O restore real deve ocorrer em banco isolado, conforme runbook, nunca sobre produção durante essa verificação.

- [ ] **Step 5: Revisar o worktree e fazer commit corretivo somente se necessário**

Run: `git status --short && git diff --check`

Expected: `.env` não aparece; worktree limpo se nenhuma correção foi necessária.

Se houve correção dentro do escopo:

```bash
git add -u
git commit -m "fix: complete native PostgreSQL deployment verification"
```
