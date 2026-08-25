# Sprint 4 Single-Domain Contabo Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Atualizar documentação e infraestrutura, publicar o release single-domain na Contabo e encerrar todos os gates técnicos verificáveis.

**Architecture:** Artefatos Docker/Nginx/Traefik/Cloudflare expõem somente o domínio principal. O release é precedido por backup e migrations verificadas, usa healthcheck interno e público e mantém rollback da imagem/commit anterior. Evidências externas do incidente de segurança permanecem explicitamente externas.

**Tech Stack:** MkDocs, Docker Compose, Docker Swarm/Traefik legado compatível, Nginx, Cloudflare Tunnel, SSH Ed25519 e PostgreSQL 15.

## Global Constraints

- VPS autorizada: `root@13.140.139.122`; projeto remoto: `/opt/rgnfarmasystem`.
- Não imprimir `.env`, tokens, senhas, chaves ou strings de conexão em logs.
- Fazer backup PostgreSQL e de mídia antes de migrations destrutivas.
- Preservar o commit anterior e os backups até o aceite público.
- `curl https://rgnfarmasystem.rgnsystems.com.br/health/` deve retornar `200`; 521, falha TLS ou cloudflared reiniciando bloqueiam conclusão.
- O domínio `control.rgnfarmasystem.rgnsystems.com.br` não é superfície da aplicação e deve ser removido de toda configuração vigente.

---

### Task 1: Contratos single-domain de infraestrutura

**Files:**
- Modify: `.env.example`
- Modify: `.env.development.example`
- Modify: `.env.local.example`
- Modify: `docker-compose.vps.yml`
- Modify: `docker-stack.yml`
- Modify: `deploy/nginx/local.conf`
- Modify: `deploy/nginx/rgnfarmasystem.conf`
- Modify: `deploy/traefik/dynamic.yml`
- Modify: `deploy/cloudflared/config.yml`
- Modify: `core/operational_readiness.py`
- Modify: `tests/test_operational_readiness.py`
- Modify: `tests/test_settings_profiles.py`
- Create: `tests/test_single_domain_deployment.py`

**Interfaces:**
- Produces: artefatos sem `CONTROL_PLANE_*`/host de controle e healthcheck inicial de 600 segundos.
- Consumes: alteração local preexistente `docker-compose.vps.yml:start_period=600s` e seu teste em `tests/test_operational_readiness.py`.

- [ ] **Step 1: escrever teste vermelho de domínio único**

```python
@pytest.mark.parametrize('path', TRACKED_RUNTIME_FILES)
def test_runtime_artifacts_do_not_publish_control_domain(path):
    source = (ROOT / path).read_text(encoding='utf-8')
    assert 'control.rgnfarmasystem.rgnsystems.com.br' not in source
    assert 'CONTROL_PLANE_' not in source

def test_vps_tunnel_targets_internal_nginx():
    compose = yaml.safe_load((ROOT / 'docker-compose.vps.yml').read_text())
    cloudflared = compose['services']['cloudflared']
    assert cloudflared['network_mode'] == 'host'
    assert compose['services']['nginx']['ports'] == ['127.0.0.1:8081:80']
    assert _duration_seconds(compose['services']['app']['healthcheck']['start_period']) >= 600
```

`TRACKED_RUNTIME_FILES` contém os três exemplos `.env`, três configs de deploy, os dois YAML Docker, settings vigentes e documentação operacional; specs/planos históricos são excluídos.

- [ ] **Step 2: executar e confirmar falhas**

Run: `./scripts/test.sh tests/test_single_domain_deployment.py tests/test_operational_readiness.py tests/test_settings_profiles.py -q`

Expected: FAIL nas referências do domínio e variáveis de controle.

- [ ] **Step 3: atualizar artefatos**

Remover router/labels/SAN do Control Plane em Traefik e Swarm; manter somente `Host(rgnfarmasystem.rgnsystems.com.br)`. Em exemplos `.env`, usar `ALLOWED_HOSTS=rgnfarmasystem.rgnsystems.com.br,localhost,127.0.0.1`, uma única origem HTTPS e `CUSTOMER_APP_BASE_URL=https://rgnfarmasystem.rgnsystems.com.br`. Em Nginx local, remover `control.localhost`. Manter cloudflared em rede host apontando, na configuração gerenciada do túnel, para `http://127.0.0.1:8081`.

- [ ] **Step 4: incorporar as alterações preexistentes de healthcheck**

Confirmar que o diff local existente altera somente `app.healthcheck.start_period` de 30 para 600 segundos em `docker-compose.vps.yml` e adiciona `test_vps_compose_allows_initial_migration_window`. Mantê-los no mesmo commit de infraestrutura, sem sobrescrever outras mudanças do usuário.

- [ ] **Step 5: validar YAML e testes**

Run: `docker compose -f docker-compose.vps.yml config --quiet`

Run: `docker compose -f docker-compose.yml config --quiet`

Run: `./scripts/test.sh tests/test_single_domain_deployment.py tests/test_operational_readiness.py tests/test_settings_profiles.py -q`

Expected: configs válidas e testes PASS.

### Task 2: Documentação funcional, técnica e regulatória

**Files:**
- Modify: `MODIFICACAGERAL.prd`
- Modify: `PRD.md`
- Modify: `TEMPLATES.md`
- Modify: `mkdocs.yml`
- Modify: `docs/index.md`
- Modify: `docs/architecture/auth-single-instance.md`
- Create: `docs/architecture/admin-single-instance.md`
- Delete: `docs/architecture/saas-control-plane.md`
- Create: `docs/architecture/domain-actions.md`
- Modify: `docs/architecture/templates.md`
- Modify: `docs/architecture/sidebar-permissions.md`
- Modify: `docs/deployment.md`
- Modify: `docs/DEPLOY_VPS.md`
- Modify: `deploy/vps/README.md`
- Modify: `docs/architecture/backup-restore.md`
- Modify: `docs/security/secrets-inventory.example.md`
- Modify: `docs/validation/requirements-matrix.yml`
- Modify: `docs/validation/evidence-catalog.yml`
- Modify: `docs/validation/known-pending-items.md`
- Create: `docs/validation/single-domain-actions-acceptance.md`
- Create: `tests/test_single_instance_documentation.py`

**Interfaces:**
- Produces: documentação vigente sem instruções de Control Plane/tenant e catálogo das 253 ações.
- Consumes: `action_registry.all()` para gerar tabela determinística por management command ou snippet documentado.

- [ ] **Step 1: escrever teste documental vermelho**

O teste exige navegação MkDocs para “Administração single-instance” e “Ações operacionais”, ausência de “Administração da plataforma”, domínio único nos runbooks, comando Contabo `docker compose -f docker-compose.vps.yml`, backup antes de migrate, matriz com requisitos `SIA-ADMIN`, `SIA-ACTION-253`, `SIA-PTBR` e evidências apontando para testes reais.

- [ ] **Step 2: atualizar PRDs e arquitetura**

Marcar os requisitos multitenant/Control Plane como substituídos pela decisão de 2026-07-19, sem apagar histórico. Documentar fluxo `/accounts/login/` → `/app/`, Admin padrão, Mermaid `HTML -> dispatcher -> DRF -> domínio -> auditoria`, extensão de `ActionConfig`, permissões e fallback sem JS. `TEMPLATES.md` deve incluir o procedimento exato para adicionar futura `@action`: config, campos, estados, cópia pt-BR e teste de igualdade.

- [ ] **Step 3: atualizar operação e validação**

Runbooks usam somente Contabo, domínio principal, Nginx `127.0.0.1:8081`, Cloudflare Tunnel, backup/restore e rollback. Atualizar pendências conhecidas com o usuário local real `Rui <ruign2015@gmail.com>` e declarar que sua senha deve ser definida fora do Git; manter INC-2026-001 aberto até evidências formais externas, sem simular aprovação. O documento de aceite registra commit, contagens 253/247/6, cobertura, migrations e resultados interno/público sem segredos.

- [ ] **Step 4: validar e commit de código/docs**

Run: `./scripts/test.sh tests/test_single_instance_documentation.py tests/test_single_domain_deployment.py tests/test_operational_readiness.py -q`

Run: `.venv/bin/mkdocs build --strict`

Expected: PASS.

```bash
git add .env.example .env.development.example .env.local.example docker-compose.vps.yml docker-stack.yml deploy core/operational_readiness.py tests MODIFICACAGERAL.prd PRD.md TEMPLATES.md mkdocs.yml docs
git commit -m "docs: document single-instance action workflows"
```

### Task 3: Gate técnico integral local

**Files:**
- Test: repositório completo.

**Interfaces:**
- Produces: commit candidato a release e evidências reproduzíveis.

- [ ] **Step 1: checks Django e migrations**

Run: `TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py check --settings=core.settings.test`

Run: `TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py makemigrations --check --dry-run --settings=core.settings.test`

Expected: zero problemas e nenhuma migration pendente.

- [ ] **Step 2: qualidade e segurança**

Run: `.venv/bin/ruff check . && .venv/bin/ruff format --check .`

Run: `.venv/bin/mypy .`

Run: `.venv/bin/bandit -q -r . -x './.venv/*,./.worktrees/*,./tests/*,*/migrations/*'`

Run: `.venv/bin/pip-audit -r requirements.txt`

Expected: todos com exit code 0.

- [ ] **Step 3: suíte completa com cobertura**

Run: `./scripts/test.sh --cov=. --cov-report=term-missing --cov-fail-under=80 -q`

Expected: todos PASS e cobertura ≥80%.

- [ ] **Step 4: OpenAPI, docs e secrets**

Run: `TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py spectacular --settings=core.settings.test --file /tmp/rgn-openapi.yml --validate`

Run: `.venv/bin/mkdocs build --strict`

Run: `./scripts/test.sh tests/test_secret_hygiene.py tests/test_release_gate.py -q`

Expected: PASS sem schema warnings bloqueantes, links quebrados ou segredo rastreado.

- [ ] **Step 5: revisar o candidato**

Run: `git diff --check && git status --short && git log --oneline -12`

Expected: worktree limpo e commits das quatro sprints presentes.

### Task 4: Backup e deploy transacional na Contabo

**Files:**
- Remote: `/opt/rgnfarmasystem`
- Remote backup: `/opt/rgnfarmasystem/backups/release-<timestamp>/`

**Interfaces:**
- Consumes: SSH `/home/rui/.ssh/id_ed25519`, candidato local aprovado e `.env` remoto existente.
- Produces: containers saudáveis no commit candidato e rollback verificável.

- [ ] **Step 1: registrar estado remoto sem expor secrets**

Run: `ssh -i /home/rui/.ssh/id_ed25519 root@13.140.139.122 'cd /opt/rgnfarmasystem && git rev-parse HEAD && docker compose -f docker-compose.vps.yml ps --format json'`

Expected: commit anterior registrado e serviços enumerados.

- [ ] **Step 2: criar backup antes do deploy**

No host remoto, criar diretório `0700`, executar `pg_dump` pelo container `db`, compactar mídia e gerar SHA-256. Validar `gzip -t` e `tar -tzf` antes de continuar. Nenhuma senha é interpolada no comando local; o container usa suas variáveis internas.

```bash
docker compose -f docker-compose.vps.yml exec -T db sh -c \
  'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$release_dir/postgres.sql.gz"
docker run --rm -v rgnfarmasystem_media:/source:ro -v "$release_dir":/backup alpine \
  tar -czf /backup/media.tar.gz -C /source .
sha256sum "$release_dir/postgres.sql.gz" "$release_dir/media.tar.gz" > "$release_dir/SHA256SUMS"
```

- [ ] **Step 3: atualizar código e construir imagem**

Fazer `git fetch --prune`, verificar que o SHA remoto desejado é exatamente o commit local aprovado, fazer fast-forward, executar `docker compose -f docker-compose.vps.yml config --quiet` e construir `app`. Não usar `git reset --hard` nem remover volumes.

- [ ] **Step 4: aplicar release e migrations**

Run remoto: `docker compose -f docker-compose.vps.yml up -d --build --remove-orphans`

Aguardar app healthy por até 15 minutos, confirmar migrations com `showmigrations --plan`, executar `check --deploy` no container e confirmar celery worker/beat, Redis, RabbitMQ, PostgreSQL e Nginx saudáveis.

- [ ] **Step 5: provisionar o administrador sem registrar senha**

Criar/atualizar `Rui <ruign2015@gmail.com>` com `is_active=True`, `is_staff=True`, `is_superuser=True`. A senha deve entrar por arquivo temporário `0600` fora do repositório, ser lida por processo one-shot e o arquivo deve ser destruído após `check_password()` retornar verdadeiro. Não mostrar a senha em terminal, Git, logs Docker ou documentação.

- [ ] **Step 6: validar superfícies internas**

Run remoto:

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' -H 'Host: rgnfarmasystem.rgnsystems.com.br' http://127.0.0.1:8081/health/
curl -fsS -o /dev/null -w '%{http_code}\n' -H 'Host: rgnfarmasystem.rgnsystems.com.br' http://127.0.0.1:8081/accounts/login/
curl -fsS -o /dev/null -w '%{http_code}\n' -H 'Host: rgnfarmasystem.rgnsystems.com.br' http://127.0.0.1:8081/admin/
```

Expected: `200`, `200`, `302` ou `200` conforme sessão; `/platform/` retorna `404`.

### Task 5: Cloudflare Tunnel e aceite público

**Files:**
- Remote: container `cloudflared` em `/opt/rgnfarmasystem`.
- Modify after evidence: `docs/validation/single-domain-actions-acceptance.md`.

**Interfaces:**
- Produces: TLS público estável e evidência final sem dados sensíveis.

- [ ] **Step 1: validar túnel estável**

Run remoto: `docker compose -f docker-compose.vps.yml ps cloudflared && docker compose -f docker-compose.vps.yml logs --since=10m cloudflared | tail -100`

Expected: container sem reinícios recentes e pelo menos uma conexão registrada; token, connector ID sensível e headers de autenticação não são copiados para documentação.

- [ ] **Step 2: corrigir origem gerenciada se necessário**

O hostname público do túnel deve apontar para `http://127.0.0.1:8081`, compatível com `network_mode: host`. Se o log indicar token revogado/inválido, interromper o gate público e solicitar um novo token no painel Cloudflare; não reutilizar, imprimir ou tentar adivinhar credenciais. Se indicar origem indisponível, corrigir a URL gerenciada e reiniciar apenas `cloudflared`.

- [ ] **Step 3: validar público de duas redes lógicas**

Run local:

```bash
curl --fail --silent --show-error --max-time 20 --retry 3 \
  -o /dev/null -w '%{http_code} %{ssl_verify_result}\n' \
  https://rgnfarmasystem.rgnsystems.com.br/health/
curl --fail --silent --show-error --max-time 20 \
  -o /dev/null -w '%{http_code}\n' \
  https://rgnfarmasystem.rgnsystems.com.br/accounts/login/
```

Expected: `200 0` e `200`; repetir dentro da VPS usando DNS público para detectar hairpin/configuração divergente.

- [ ] **Step 4: teste funcional mínimo do release**

Com sessão do administrador, verificar `/app/`, `/admin/`, `/api/docs/`, uma ação simples de produção pelo formulário HTML e seu registro de auditoria. Não usar dados reais regulados; criar fixture identificada como smoke e removê-la pela regra de retenção aplicável.

- [ ] **Step 5: rollback em qualquer falha bloqueante**

Voltar ao commit e imagem registrados, executar `docker compose ... up -d` e restaurar banco/mídia somente se migration incompatível tiver sido aplicada. Verificar os hashes antes de restore. Não apagar backups após rollback.

- [ ] **Step 6: registrar aceite e commit operacional**

Atualizar o documento de aceite com SHA, timestamps, contagem 253, cobertura, migrations, códigos HTTP interno/público e status do túnel. Manter INC-2026-001 como pendência externa até aprovação formal.

```bash
git add docs/validation/single-domain-actions-acceptance.md
git commit -m "ops: publish single-domain Contabo release"
```
