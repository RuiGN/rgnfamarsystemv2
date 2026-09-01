# Programa de Prontidão CSV e Validação GxP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar os riscos técnicos e regulatórios do RGN Farma System, atingir prontidão formal para CSV e validar incrementalmente o uso GxP por IQ/OQ/PQ.

**Architecture:** O programa usa gates G0–G4 e separa controles transversais dos pacotes de validação por domínio. Evidências são vinculadas bidirecionalmente a requisitos, riscos, especificações, execuções e desvios; nenhum pacote de módulo avança sem aprovação de Qualidade e sem os controles transversais dos quais depende.

**Tech Stack:** Python, Django, Django REST Framework, PostgreSQL, Redis, Celery, RabbitMQ, Docker Compose, Nginx, Cloudflare Tunnel, Bootstrap 5, pytest, GitHub Actions, Ruff, mypy, Bandit, pip-audit, Gitleaks, drf-spectacular e MkDocs. As versoes vigentes sao definidas pelos manifests do repositorio.

## Global Constraints

- Preservar a arquitetura modular e a segregação de funções existentes.
- PostgreSQL é obrigatório nos testes de integração e validação; SQLite não comprova compatibilidade de produção.
- Nenhum segredo real pode existir em Git, imagem, log, fixture, evidência ou documentação.
- Toda mudança de regra de negócio começa com teste reprovado e termina com teste aprovado.
- Todo modelo novo deve possuir migration, integridade referencial e índices para consultas frequentes.
- Requisitos críticos exigem 100% de rastreabilidade e execução aprovada.
- Vulnerabilidade crítica, teste mandatório reprovado ou desvio crítico/maior aberto bloqueia o gate.
- Dados de validação devem ser sintéticos ou anonimizados.
- DEV, TEST/VALIDATION e PROD não compartilham banco, fila, cache, bucket, chaves ou credenciais.
- Ações externas irreversíveis, como revogação de credenciais, reescrita de histórico e deploy, exigem janela e autorização registradas.
- A especificação normativa é `docs/superpowers/specs/2026-07-14-programa-validacao-gxp-design.md`.

---

## Estrutura de arquivos planejada

| Unidade | Responsabilidade |
|---|---|
| `core/settings/{base,test,production}.py` | Configuração segregada e fail-fast |
| `.github/workflows/quality.yml` | Quality gate técnico reproduzível |
| `compliance/validation_models.py` | Requisitos, riscos, testes, execuções, evidências e desvios |
| `compliance/validation_services.py` | Gates, rastreabilidade, aprovação e imutabilidade |
| `compliance/management/commands/check_gxp_readiness.py` | Avaliação automatizada G0–G4 |
| `governance/e_signatures.py` | Reautenticação e assinatura eletrônica |
| `governance/audit.py` | Serviço único de audit trail encadeado |
| `docs/validation/` | VMP, inventário, URS, riscos, matriz, protocolos, relatórios e SOPs |
| `validation/evidence/` | Manifestos de evidência sem dados sensíveis; binários ficam em storage protegido |
| `scripts/validation/` | Coleta determinística de evidências IQ/OQ/PQ |

## Planos derivados obrigatórios

Este plano mestre não autoriza implementar todos os domínios em um único lote. Antes de cada grupo da Onda 4, criar e aprovar um plano em `docs/superpowers/plans/`:

1. `2026-11-03-gxp-plataforma-identidade.md`;
2. `2026-12-01-gxp-auditoria-workflow-documentos.md`;
3. `2027-01-05-gxp-mestres-treinamento.md`;
4. `2027-02-02-gxp-estoque-lotes-genealogia.md`;
5. `2027-03-02-gxp-sistema-qualidade.md`;
6. `2027-05-04-gxp-producao-planejamento-manutencao.md`;
7. `2027-07-06-gxp-regulatorio-pos-mercado.md`;
8. `2027-09-01-gxp-administrativo-integracoes-ia.md`.

Cada plano derivado deve listar URS exatas, riscos, arquivos de código, testes automatizados, casos OQ/PQ, dados sintéticos, aprovadores e critérios de rollback.

---

### Task 1: Conter o incidente de segredos e fechar G0

**Files:**
- Modify: `.gitignore`
- Modify: `.dockerignore`
- Create: `docs/security/INC-2026-001-secrets-exposure.md`
- Create: `docs/security/secrets-inventory.example.md`
- Create: `.gitleaks.toml`
- Test: `tests/test_secret_hygiene.py`

**Interfaces:**
- Consumes: histórico Git e inventário de credenciais mantido fora do repositório.
- Produces: gate G0 aprovado, padrões preventivos e registro de incidente sem valores secretos.

- [ ] **Step 1: Registrar o incidente sem copiar valores sensíveis**

Criar `docs/security/INC-2026-001-secrets-exposure.md` com seções: detecção, intervalo de exposição, classes de segredo, sistemas afetados, análise de logs, impacto GxP/LGPD, contenção, erradicação, recuperação, CAPA, responsáveis e aprovações.

- [ ] **Step 2: Escrever o teste preventivo inicialmente reprovado**

```python
from pathlib import Path
import subprocess


def test_sensitive_runtime_artifacts_are_not_tracked():
    tracked = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
    forbidden = [
        path for path in tracked
        if path.startswith(".playwright-mcp/") or path.startswith(".env.backup")
    ]
    assert forbidden == []


def test_ignore_rules_cover_sensitive_artifacts():
    source = Path(".gitignore").read_text(encoding="utf-8")
    assert ".env.backup*" in source
    assert ".playwright-mcp/" in source
```

- [ ] **Step 3: Confirmar a reprovação**

Run: `.venv/bin/pytest tests/test_secret_hygiene.py -q`
Expected: FAIL listando o backup de ambiente e os artefatos Playwright rastreados.

- [ ] **Step 4: Revogar e rotacionar credenciais em janela aprovada**

Rotacionar, nesta ordem, acesso Google OAuth/Drive, chaves de criptografia com plano de recriptografia, banco, RabbitMQ, SMTP, Cloudflare, provedores de IA e demais tokens inventariados. Registrar somente identificador, proprietário, data, evidência de revogação e novo `key_id` no inventário externo.

- [ ] **Step 5: Remover artefatos do índice e preparar saneamento do histórico**

Run: `git rm --cached .env.backup.20260713-090837 .playwright-mcp/client-secret-*.json .playwright-mcp/*.yml .playwright-mcp/*.log`

Adicionar `.env.backup*`, `.playwright-mcp/`, `validation/evidence/private/` e arquivos de chaves aos ignores. Executar a reescrita do histórico apenas depois de comunicar todos os colaboradores, congelar pushes, criar backup e obter aprovação do responsável pelo repositório.

- [ ] **Step 6: Ativar Gitleaks e verificar todo o histórico saneado**

Run: `gitleaks git --config .gitleaks.toml --redact --exit-code 1`
Expected: exit 0, sem achados não justificados.

- [ ] **Step 7: Reexecutar o teste e obter aprovação G0**

Run: `.venv/bin/pytest tests/test_secret_hygiene.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add .gitignore .dockerignore .gitleaks.toml docs/security tests/test_secret_hygiene.py
git commit -m "security: contain exposed credentials and enforce secret hygiene"
```

---

### Task 2: Segregar settings e tornar testes reproduzíveis

**Files:**
- Create: `core/settings/__init__.py`
- Create: `core/settings/base.py`
- Create: `core/settings/test.py`
- Create: `core/settings/production.py`
- Delete: `core/settings.py`
- Modify: `pytest.ini`
- Modify: `.env.example`
- Test: `tests/test_settings_profiles.py`

**Interfaces:**
- Consumes: variáveis de ambiente documentadas em `.env.example`.
- Produces: `core.settings.test` para CI e `core.settings.production` com validação fail-fast.

- [ ] **Step 1: Escrever testes de perfil reprovados**

```python
import pytest
from django.core.exceptions import ImproperlyConfigured


def test_test_profile_uses_postgresql(settings):
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ImproperlyConfigured):
        __import__("core.settings.production")
```

- [ ] **Step 2: Confirmar reprovação**

Run: `DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest tests/test_settings_profiles.py -q`
Expected: FAIL porque os perfis ainda não existem.

- [ ] **Step 3: Extrair base e criar perfis**

Mover configuração compartilhada para `base.py`. Em `test.py`, exigir `TEST_DATABASE_URL` PostgreSQL, usar cache local e Celery eager. Em `production.py`, rejeitar `DEBUG=True`, chave default, hosts vazios, HTTP nas URLs públicas e ausência das chaves de criptografia.

- [ ] **Step 4: Configurar pytest para o perfil de teste**

Definir `DJANGO_SETTINGS_MODULE = core.settings.test` e documentar `TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test`.

- [ ] **Step 5: Verificar perfis e migrations**

Run: `DJANGO_SETTINGS_MODULE=core.settings.test TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python manage.py check`
Expected: `System check identified no issues`.

Run: `DJANGO_SETTINGS_MODULE=core.settings.test TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python manage.py makemigrations --check --dry-run`
Expected: `No changes detected`.

- [ ] **Step 6: Executar testes**

Run: `DJANGO_SETTINGS_MODULE=core.settings.test TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/pytest tests/test_settings_profiles.py tests/test_foundation.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/settings pytest.ini .env.example tests/test_settings_profiles.py
git commit -m "refactor: segregate Django settings by environment"
```

---

### Task 3: Implantar o quality gate CI/CD do G1

**Files:**
- Create: `.github/workflows/quality.yml`
- Create: `pyproject.toml`
- Create: `requirements-dev.txt`
- Create: `scripts/ci/quality-gate.sh`
- Modify: `requirements.txt`
- Modify: `docs/deployment.md`
- Test: `tests/test_ci_contract.py`

**Interfaces:**
- Consumes: `core.settings.test` e serviços PostgreSQL/Redis/RabbitMQ.
- Produces: artefatos `openapi-schema.yml`, `coverage.xml`, SBOM e relatórios de segurança ligados ao SHA.

- [ ] **Step 1: Criar teste do contrato da pipeline**

O teste deve carregar `.github/workflows/quality.yml` e afirmar presença de PostgreSQL, Redis, RabbitMQ, Gitleaks, `check --deploy`, migrations, pytest com cobertura, Ruff, mypy, Bandit, pip-audit, `spectacular --validate`, build Docker e upload de evidências.

- [ ] **Step 2: Confirmar reprovação**

Run: `.venv/bin/pytest tests/test_ci_contract.py -q`
Expected: FAIL porque o workflow não existe.

- [ ] **Step 3: Implementar `quality.yml` e script fail-fast**

O script executará exatamente:

```bash
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
ruff check .
ruff format --check .
mypy core accounts governance compliance
bandit -r core accounts governance compliance -q
pip-audit --strict
pytest --cov=. --cov-report=term-missing --cov-report=xml --cov-fail-under=80
python manage.py spectacular --file openapi-schema.yml --validate --fail-on-warn
python manage.py check_operational_readiness --fail-on-error
python manage.py check_backup_restore_readiness --fail-on-error
python manage.py check_product_acceptance --fail-on-error
python manage.py check_release_readiness --fail-on-error
```

- [ ] **Step 4: Corrigir os 36 avisos de deploy/OpenAPI sem silenciá-los**

Adicionar tipos ou `@extend_schema_field` em `accounts/serializers.py`, serializer explícito a `knowledge/views.py`, `ENUM_NAME_OVERRIDES` estáveis e HSTS parametrizado no perfil de produção.

- [ ] **Step 5: Executar o gate local contra PostgreSQL**

Run: `DJANGO_SETTINGS_MODULE=core.settings.test TEST_DATABASE_URL="$TEST_DATABASE_URL" bash scripts/ci/quality-gate.sh`
Expected: exit 0 e nenhum warning do OpenAPI/check deploy.

- [ ] **Step 6: Commit**

```bash
git add .github pyproject.toml requirements-dev.txt requirements.txt scripts/ci docs/deployment.md accounts/serializers.py knowledge/views.py core/settings tests/test_ci_contract.py
git commit -m "ci: establish reproducible G1 quality gate"
```

---

### Task 4: Endurecer artefatos, containers e borda

**Files:**
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.vps.yml`
- Modify: `deploy/nginx/rgnfarmasystem.conf`
- Create: `docs/architecture/adr/ADR-0001-edge-proxy.md`
- Create: `docs/architecture/container-hardening.md`
- Test: `tests/test_deployment_hardening.py`

**Interfaces:**
- Consumes: imagem identificada por SHA/tag imutável e secrets do orquestrador.
- Produces: runtime sem root, imagens pinadas, healthchecks e TLS/headers com Nginx e Cloudflare Tunnel.

- [ ] **Step 1: Testar o contrato de hardening**

Verificar por leitura que o Dockerfile define `USER`, usa base por digest, que manifests não contêm `latest`, credenciais default ou publicação direta desnecessária, e que o proxy define redirect HTTPS, HSTS, CSP, `X-Content-Type-Options` e `Referrer-Policy`.

- [ ] **Step 2: Implementar imagem multi-stage e usuário sem privilégios**

Criar usuário `rgn` com UID/GID fixos, copiar apenas artefatos necessários, tornar filesystem read-only onde possível e montar somente diretórios graváveis declarados.

- [ ] **Step 3: Aprovar ADR de borda**

Formalizar Nginx e Cloudflare Tunnel como borda autorizada. O ADR registrará contexto, ameaças, TLS, headers, healthcheck, logs, rollback, responsável e aprovação.

- [ ] **Step 4: Gerar SBOM e assinar imagem**

Run: `syft "${IMAGE_REF}" -o cyclonedx-json > sbom.cdx.json`

Run: `cosign sign --yes "${IMAGE_REF}@${IMAGE_DIGEST}"`
Expected: assinatura verificável pelo gate de deploy.

- [ ] **Step 5: Verificar manifests e imagem**

Run: `.venv/bin/pytest tests/test_deployment_hardening.py -q`
Expected: PASS.

Run: `docker build --pull -t rgnfarmasystem:validation .`
Expected: exit 0; processo da aplicação executa como UID não zero.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml docker-compose.vps.yml deploy docs/architecture tests/test_deployment_hardening.py
git commit -m "security: harden container supply chain and edge"
```

---

### Task 5: Criar o pacote documental de prontidão CSV

**Files:**
- Create: `docs/validation/VMP.md`
- Create: `docs/validation/system-inventory.md`
- Create: `docs/validation/intended-use.md`
- Create: `docs/validation/URS.md`
- Create: `docs/validation/functional-specification.md`
- Create: `docs/validation/configuration-specification.md`
- Create: `docs/validation/risk-assessment.md`
- Create: `docs/validation/traceability-matrix.csv`
- Create: `docs/validation/test-strategy.md`
- Create: `docs/validation/supplier-assessment.md`
- Modify: `mkdocs.yml`
- Modify: `docs/index.md`
- Test: `tests/test_validation_documentation.py`

**Interfaces:**
- Consumes: uso pretendido e inventário aprovados por PO, QA e donos de processo.
- Produces: baseline documental aprovada para autorizar G2.

- [ ] **Step 1: Testar completude e identificadores**

O teste deve exigir todos os arquivos, aprovações, versão, estado, proprietário e IDs nos formatos `URS-AUD-001`, `RISK-AUD-001`, `FS-AUD-001` e `TEST-AUD-001`, generalizados pela expressão `^(URS|RISK|FS|TEST)-[A-Z][A-Z0-9_]{1,11}-[0-9]{3}$`.

- [ ] **Step 2: Classificar sistema e componentes**

Registrar impacto GxP, dados regulados, categoria GAMP, fornecedores, infraestrutura, integrações, IA, criticidade, proprietários e justificativa de inclusão/exclusão.

- [ ] **Step 3: Elaborar URS e avaliação de risco**

Cada URS deve ter processo, ator, precondição, comportamento, dado, criticidade e aceite. Cada risco deve registrar severidade, probabilidade, detectabilidade, controle, risco residual e aprovador.

- [ ] **Step 4: Preencher matriz bidirecional**

Usar cabeçalho fixo:

```csv
urs_id,risk_id,spec_id,component,test_id,evidence_id,deviation_id,status,owner,qa_approval
```

- [ ] **Step 5: Publicar navegação e validar documentos**

Run: `.venv/bin/pytest tests/test_validation_documentation.py -q`
Expected: PASS, sem identificadores duplicados ou links quebrados.

- [ ] **Step 6: Obter assinaturas de PO, QA e patrocinador e criar baseline**

Marcar versão documental aprovada e tag Git assinada `csv-baseline-v1` somente após aprovação registrada.

- [ ] **Step 7: Commit**

```bash
git add docs/validation docs/index.md mkdocs.yml tests/test_validation_documentation.py
git commit -m "docs: establish CSV validation baseline"
```

---

### Task 6: Implementar rastreabilidade, evidências e gates GxP

**Files:**
- Create: `compliance/validation_models.py`
- Create: `compliance/validation_services.py`
- Create: `compliance/migrations/0005_validation_lifecycle.py`
- Create: `compliance/management/commands/check_gxp_readiness.py`
- Modify: `compliance/admin.py`
- Modify: `compliance/serializers.py`
- Modify: `compliance/urls.py`
- Modify: `compliance/views.py`
- Test: `tests/test_gxp_validation_lifecycle.py`

**Interfaces:**
- Produces: `evaluate_gxp_gate(gate: str) -> GateReport` e registros imutáveis de requisito, risco, caso, execução, evidência, desvio e aprovação.

- [ ] **Step 1: Escrever testes de integridade e bloqueio**

Cobrir unicidade de IDs, segregação de funções, proibição de alterar evidência aprovada, bloqueio por desvio crítico/maior, rastreabilidade crítica incompleta e aprovação de risco residual apenas por papel autorizado.

- [ ] **Step 2: Confirmar reprovação**

Run: `.venv/bin/pytest tests/test_gxp_validation_lifecycle.py -q`
Expected: FAIL porque o ciclo ainda não existe.

- [ ] **Step 3: Implementar modelos e constraints**

Todos os registros usam UUID, `SingleInstanceModel`, estado, versão, timestamps, autor e hash SHA-256. Evidência aprovada é append-only; correção cria nova revisão ligada por `supersedes`.

- [ ] **Step 4: Implementar o avaliador de gates**

`evaluate_gxp_gate` retorna checks com código, status, evidência e bloqueadores. O comando aceita `--gate G0|G1|G2|G3|G4`, `--format json` e `--fail-on-error`.

- [ ] **Step 5: Expor API autenticada e protegida por permissões Django**

Permitir leitura aos papéis de validação, execução aos testadores designados e aprovação somente a QA. Não expor binários diretamente; usar download protegido e auditado.

- [ ] **Step 6: Verificar migrations, testes e gate**

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`
Expected: `No changes detected`.

Run: `.venv/bin/pytest tests/test_gxp_validation_lifecycle.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add compliance tests/test_gxp_validation_lifecycle.py
git commit -m "feat: add GxP validation lifecycle and gate evaluator"
```

---

### Task 7: Qualificar identidade, assinatura e audit trail transversal

**Files:**
- Create: `governance/e_signatures.py`
- Create: `governance/audit.py`
- Create: `governance/migrations/0005_electronic_signature_audit_chain.py`
- Modify: `governance/models.py`
- Modify: `accounts/services.py`
- Modify: `core/middleware.py`
- Modify: `compliance/services.py`
- Test: `tests/test_electronic_signatures.py`
- Test: `tests/test_audit_trail_integrity.py`
- Test: `tests/test_authorization_isolation.py`

**Interfaces:**
- Produces: `require_electronic_signature(request, meaning, object_ref)` e `record_audit_event(...)`.

- [ ] **Step 1: Criar testes adversariais**

Cobrir senha/MFA inválidos, sessão expirada, assinatura reutilizada, significado ausente, alteração de evento, quebra da cadeia de hashes, exclusão, timestamp inconsistente e leitura/escrita sem a permissão exigida.

- [ ] **Step 2: Confirmar reprovação**

Run: `.venv/bin/pytest tests/test_electronic_signatures.py tests/test_audit_trail_integrity.py tests/test_authorization_isolation.py -q`
Expected: FAIL nos controles ainda ausentes.

- [ ] **Step 3: Implementar assinatura de uso único**

Vincular identidade, MFA/reautenticação, significado controlado, objeto, hash do estado assinado, timestamp do servidor, IP/request ID e expiração. Nunca armazenar senha ou OTP.

- [ ] **Step 4: Implementar audit trail encadeado e append-only**

Registrar valor anterior/posterior para campos críticos, motivo, ator, objeto, origem, request ID, `previous_hash` e `event_hash`. Bloquear update/delete na aplicação e retirar permissões de banco do usuário runtime.

- [ ] **Step 5: Integrar primeiro nas ações transversais críticas**

Aplicar a mudança de permissão, suporte com escrita, aprovação QA, liberação/bloqueio de lote, publicação documental e aceitação de risco. Os planos derivados enumerarão as demais ações.

- [ ] **Step 6: Verificar controles**

Run: `.venv/bin/pytest tests/test_electronic_signatures.py tests/test_audit_trail_integrity.py tests/test_authorization_isolation.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add governance accounts/services.py core/middleware.py compliance/services.py tests/test_electronic_signatures.py tests/test_audit_trail_integrity.py tests/test_authorization_isolation.py
git commit -m "feat: enforce electronic signatures and immutable audit trail"
```

---

### Task 8: Qualificar arquivos, criptografia, backup e recuperação

**Files:**
- Modify: `files/models.py`
- Modify: `files/views.py`
- Modify: `core/crypto.py`
- Modify: `scripts/backup.sh`
- Modify: `scripts/restore.sh`
- Create: `scripts/validation/execute-dr-test.sh`
- Create: `docs/validation/protocols/IQ-INFRA-001.md`
- Create: `docs/validation/protocols/OQ-DR-001.md`
- Modify: `docs/architecture/backup-restore.md`
- Test: `tests/test_file_retention.py`
- Test: `tests/test_key_rotation.py`
- Test: `tests/test_disaster_recovery.py`

**Interfaces:**
- Produces: arquivos versionados com hash/retention lock, rotação de chave rastreável e exercício DR com RPO/RTO medidos.

- [ ] **Step 1: Escrever testes de retenção, rotação e restore**

Cobrir download auditado, alteração detectada por hash, exclusão antes da retenção, chave antiga/nova, recriptografia idempotente, backup cifrado, restore em ambiente isolado e reconciliação de contagens/hashes.

- [ ] **Step 2: Implementar storage protegido e ciclo de chaves**

Persistir `key_id`, algoritmo, nonce, hash, tamanho, versão, retenção e legal hold. Chaves ficam em secret manager; banco armazena apenas referências.

- [ ] **Step 3: Tornar backup verificável**

Cada execução gera manifesto assinado com SHA-256, contagens, tamanho, início/fim, versão, resultado e local. Falha de upload ou verificação deve gerar alerta e status reprovado.

- [ ] **Step 4: Executar IQ e OQ de DR**

Run: `bash scripts/validation/execute-dr-test.sh --environment validation --evidence-dir validation/evidence/DR-001`
Expected: restore isolado aprovado, checks funcionais aprovados e RPO/RTO medidos no manifesto.

- [ ] **Step 5: Executar testes automatizados**

Run: `.venv/bin/pytest tests/test_file_retention.py tests/test_key_rotation.py tests/test_disaster_recovery.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add files core/crypto.py scripts docs/validation/protocols docs/architecture/backup-restore.md tests/test_file_retention.py tests/test_key_rotation.py tests/test_disaster_recovery.py
git commit -m "feat: qualify protected storage key lifecycle and disaster recovery"
```

---

### Task 9: Aprovar G2 e preparar os oito pacotes IQ/OQ/PQ

**Files:**
- Create: `docs/validation/templates/iq-protocol.md`
- Create: `docs/validation/templates/oq-protocol.md`
- Create: `docs/validation/templates/pq-protocol.md`
- Create: `docs/validation/templates/validation-report.md`
- Create: `docs/validation/templates/deviation.md`
- Create: os oito planos derivados listados neste documento, com datas reais no momento da criação
- Test: `tests/test_validation_packages.py`

**Interfaces:**
- Consumes: G1 aprovado, controles transversais testados e baseline CSV.
- Produces: oito pacotes independentes autorizados por QA para execução sequencial.

- [ ] **Step 1: Criar templates com metadados obrigatórios**

Exigir protocolo, versão, ambiente, build, precondições, dados, passos, esperado, obtido, evidência, executor, revisor, desvio, conclusão e assinaturas.

- [ ] **Step 2: Escrever teste de completude dos pacotes**

Validar que cada plano derivado contém todos os URS do grupo, riscos críticos, testes negativos, PQ de ponta a ponta, rollback e aprovadores.

- [ ] **Step 3: Avaliar G2**

Run: `.venv/bin/python manage.py check_gxp_readiness --gate G2 --format json --fail-on-error > validation/evidence/G2-report.json`
Expected: exit 0, todos os checks aprovados e hash do relatório registrado.

- [ ] **Step 4: Aprovar os planos derivados em ordem**

Somente criar baseline do próximo grupo quando suas dependências estiverem aprovadas. IA permanece consultiva até possuir avaliação e validação específicas.

- [ ] **Step 5: Commit**

```bash
git add docs/validation/templates docs/superpowers/plans tests/test_validation_packages.py
git commit -m "docs: prepare risk-based IQ OQ PQ validation packages"
```

---

### Task 10: Executar validação incremental e liberar G3

**Files:**
- Modify: `docs/validation/traceability-matrix.csv`
- Create: `docs/validation/reports/PLATFORM-validation-report.md`, `AUDDOC-validation-report.md`, `MASTERTRAIN-validation-report.md`, `INVENTORY-validation-report.md`, `QMS-validation-report.md`, `MANUFACTURING-validation-report.md`, `POSTMARKET-validation-report.md` e `ADMINAI-validation-report.md`
- Create: `validation/evidence/EXEC-YYYYMMDD-NNN/manifest.json`, onde o coletor substitui `YYYYMMDD-NNN` automaticamente pela data UTC e sequência transacional
- Modify: arquivos de código e testes enumerados em cada plano derivado

**Interfaces:**
- Consumes: planos derivados aprovados e build imutável do ambiente VALIDATION.
- Produces: relatórios IQ/OQ/PQ aprovados e gate G3 por grupo.

- [ ] **Step 1: Executar cada plano derivado com TDD e gate técnico**

Para cada mudança: teste reprovado, implementação mínima, teste aprovado, regressão do módulo, quality gate integral e revisão independente.

- [ ] **Step 2: Congelar o build candidato**

Registrar digest da imagem, SHA Git, migrations, SBOM, configuração e datasets sintéticos. Nenhuma mudança é permitida durante a execução sem abrir desvio e novo build.

- [ ] **Step 3: Executar IQ, OQ e PQ**

IQ confirma ambiente/configuração; OQ cobre requisitos, limites e falhas; PQ é executado por usuários-chave no processo real representativo. Cada resultado recebe hash e aprovação.

- [ ] **Step 4: Tratar desvios**

Desvio crítico/maior bloqueia o grupo. Registrar causa, impacto, correção, CAPA, novo teste e aprovação. Nunca editar a evidência original.

- [ ] **Step 5: Avaliar G3 do grupo**

Run:

```bash
for GROUP_CODE in PLATFORM AUDDOC MASTERTRAIN INVENTORY QMS MANUFACTURING POSTMARKET ADMINAI; do
  .venv/bin/python manage.py check_gxp_readiness --gate G3 --scope "$GROUP_CODE" --format json --fail-on-error
done
```

Expected: oito execuções com exit 0, 100% dos requisitos críticos aprovados, rastreabilidade completa e nenhum desvio bloqueador.

- [ ] **Step 6: Emitir e aprovar relatório de validação**

O relatório declara versão, uso pretendido, escopo incluído/excluído, execuções, desvios, riscos residuais, conclusão e aprovadores.

- [ ] **Step 7: Criar tag assinada da liberação validada**

Run:

```bash
GROUP_CODE=PLATFORM
RELEASE_VERSION=1.0.0
git tag -s "gxp-${GROUP_CODE}-v${RELEASE_VERSION}" -m "Validated GxP release ${GROUP_CODE} ${RELEASE_VERSION}"
git tag -v "gxp-${GROUP_CODE}-v${RELEASE_VERSION}"
```

Repetir com o código e a versão aprovados de cada grupo. Expected: `git tag -v` confirma assinatura válida.

---

### Task 11: Instituir SOPs e operação validada G4

**Files:**
- Create: `docs/validation/sops/SOP-ACCESS.md`
- Create: `docs/validation/sops/SOP-CHANGE-CONTROL.md`
- Create: `docs/validation/sops/SOP-INCIDENT-DEVIATION-CAPA.md`
- Create: `docs/validation/sops/SOP-BACKUP-RESTORE-DR.md`
- Create: `docs/validation/sops/SOP-TRAINING.md`
- Create: `docs/validation/sops/SOP-PERIODIC-REVIEW.md`
- Create: `docs/validation/sops/SOP-DATA-RETENTION-DECOMMISSION.md`
- Create: `compliance/tasks.py`
- Modify: `core/celery.py`
- Test: `tests/test_validated_operations.py`

**Interfaces:**
- Produces: recertificação, revisão periódica, DR, treinamento e avaliação de mudança agendados e auditados.

- [ ] **Step 1: Criar SOPs controladas**

Cada SOP define objetivo, escopo, papéis, entradas, passos, registros, exceções, escalonamento, periodicidade, retenção, treinamento e aprovação.

- [ ] **Step 2: Escrever testes das rotinas periódicas**

Cobrir alerta de recertificação vencida, revisão periódica, restore test, treinamento expirado, vulnerabilidade vencida e mudança sem avaliação de impacto.

- [ ] **Step 3: Implementar tarefas Celery idempotentes**

As tarefas criam registros de compliance e notificações sem duplicar ocorrências, registram request/run ID e falham de forma observável.

- [ ] **Step 4: Verificar operação validada**

Run: `.venv/bin/pytest tests/test_validated_operations.py -q`
Expected: PASS.

Run: `.venv/bin/python manage.py check_gxp_readiness --gate G4 --format json --fail-on-error`
Expected: exit 0 depois que as execuções reais e aprovações estiverem registradas.

- [ ] **Step 5: Commit**

```bash
git add docs/validation/sops compliance/tasks.py core/celery.py tests/test_validated_operations.py
git commit -m "feat: establish validated operations and periodic controls"
```

---

### Task 12: Verificação final e handoff regulatório

**Files:**
- Create: `docs/validation/reports/final-validation-summary.md`
- Create: `docs/validation/reports/validated-state-inventory.md`
- Modify: `README.md`
- Modify: `docs/index.md`

**Interfaces:**
- Consumes: G0–G4 e relatórios dos oito grupos.
- Produces: declaração inequívoca do estado validado, exclusões e responsabilidades operacionais.

- [ ] **Step 1: Executar verificação integral no build liberado**

Run: `DJANGO_SETTINGS_MODULE=core.settings.test TEST_DATABASE_URL="$TEST_DATABASE_URL" bash scripts/ci/quality-gate.sh`
Expected: exit 0.

- [ ] **Step 2: Verificar todos os gates**

```bash
for gate in G0 G1 G2 G3 G4; do
  python manage.py check_gxp_readiness --gate "$gate" --format json --fail-on-error
done
```

Expected: cinco execuções com exit 0 e manifestos com hash.

- [ ] **Step 3: Revisar rastreabilidade e desvios**

Confirmar 100% dos requisitos críticos aprovados, nenhum desvio crítico/maior aberto, riscos residuais assinados, treinamentos vigentes e exercício DR aprovado.

- [ ] **Step 4: Emitir resumo final**

O documento lista versão, uso pretendido, módulos validados, itens explicitamente não validados, infraestrutura qualificada, resultados, desvios, riscos, SOPs e aprovações.

- [ ] **Step 5: Aprovação e handoff**

QA, donos de processo e patrocinador assinam o resumo. Operações aceita calendário de revisão, DR, recertificação, treinamento e revalidação.

- [ ] **Step 6: Commit documental final**

```bash
git add docs/validation/reports README.md docs/index.md
git commit -m "docs: approve validated GxP operating state"
```
