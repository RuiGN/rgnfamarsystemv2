# Bootstrap e Deploy Seguro de Produção — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Multi-agent execution is not authorized for this task.

**Goal:** Orquestrar migration, catálogos reais e corpus funcional da IA como um bootstrap obrigatório, auditável e fail-closed antes de publicar cada release.

**Architecture:** Expor um único comando Django que coordena os serviços dos dois planos anteriores e grava evidência técnica saneada. Executá-lo em um container one-shot depois que a infraestrutura privada estiver saudável e enquanto o túnel público estiver fechado. Somente após checks locais o deploy inicia o Cloudflare e valida o domínio público; em falha posterior, restaura a geração RAG anterior e o código anterior.

**Tech Stack:** Bash, Docker Compose, Django 6 management commands, PostgreSQL, Redis, Cloudflare Tunnel, pytest.

## Prerequisites

- Concluir `2026-08-31-catalogos-referencia-producao.md`.
- Concluir `2026-08-31-corpus-funcional-ia-rag.md`.
- Não executar este plano em banco/VPS real sem autorização explícita do usuário.

## Global Constraints

- Backup verificado deve anteceder promoção de código e migration.
- O endpoint público deve permanecer indisponível durante migration e bootstrap.
- O bootstrap exige SHA do release e não aceita modo parcial.
- Catálogos e corpus devem ser idempotentes; nenhuma transação/demo pode ser criada.
- Logs, JSON de resultado e auditoria nunca podem conter segredo, DSN completo ou conteúdo de `.env`.
- Falha local impede a abertura do túnel; falha pública aciona rollback do código e da geração RAG.
- Migrations compatíveis não são revertidas automaticamente; o backup é preservado para recuperação controlada.
- Não executar commit, push ou deploy sem autorização explícita do usuário.

## File Map

- `base/management/commands/bootstrap_production_release.py`: comando coordenador.
- `base/release_bootstrap.py`: validação, execução e resultado saneado.
- `docker-compose.vps.yml`: serviço one-shot de bootstrap.
- `scripts/deploy-vps.sh`: sequência privada, publicação e rollback.
- `.env.example`: contratos de configuração documentados, sem segredos.
- `tests/test_production_release_bootstrap.py`: atomicidade lógica e auditoria.
- `tests/test_vps_compose_contract.py`: contrato do serviço one-shot.
- `tests/test_native_postgres_deployment.py`: ordem e fail-closed do script.
- `docs/deployment.md`: runbook e evidências.
- `docs/architecture/operational-readiness.md`: critérios de prontidão.

---

### Task 1: Criar o comando único de bootstrap do release

**Files:**
- Create: `base/release_bootstrap.py`
- Create: `base/management/commands/bootstrap_production_release.py`
- Create: `tests/test_production_release_bootstrap.py`

**Interfaces:**
- Produces: `bootstrap_production_release(release_sha: str) -> ProductionBootstrapResult`.
- Consumes: `seed_production_reference_data()`, `build_release_manual_corpus()` e `publish_release_knowledge()`.
- Audits: `GovernanceAuditLog.LogType.TECHNICAL` com contexto saneado.

- [ ] **Step 1: Escrever testes falhos do contrato completo**

Cobrir:

- SHA obrigatório e validado antes de qualquer mutação;
- ordem catálogos → corpus → publicação;
- interrupção imediata se qualquer fase falhar;
- resultado contendo hashes, contagens, modo RAG e gerações anterior/ativa;
- auditoria de sucesso e falha sem segredos;
- repetição do mesmo SHA sem duplicar registros gerenciados.

```python
def test_bootstrap_runs_all_mandatory_phases_in_order(mocker):
    calls = []
    mocker.patch('base.release_bootstrap.seed_production_reference_data', side_effect=lambda: calls.append('catalogs') or catalogs_result())
    mocker.patch('base.release_bootstrap.build_release_manual_corpus', side_effect=lambda sha: calls.append('corpus') or corpus_result(sha))
    mocker.patch('base.release_bootstrap.publish_release_knowledge', side_effect=lambda sha: calls.append('knowledge') or knowledge_result(sha))

    result = bootstrap_production_release('a' * 40)

    assert calls == ['catalogs', 'corpus', 'knowledge']
    assert result.release_sha == 'a' * 40
```

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_production_release_bootstrap.py -q`

Expected: ERROR de importação de `base.release_bootstrap`.

- [ ] **Step 3: Implementar resultado e validação**

```python
@dataclass(frozen=True)
class ProductionBootstrapResult:
    release_sha: str
    catalog_manifest_hash: str
    corpus_hash: str
    reference_counts: dict[str, int]
    module_count: int
    resource_count: int
    action_count: int
    document_count: int
    chunk_count: int
    rag_mode: Literal['vector', 'local']
    previous_generation_id: str
    active_generation_id: str
```

Validar `release_sha` antes de consultar banco/Redis. Saneie recursivamente os resultados para permitir somente chaves conhecidas e escalares não sensíveis.

- [ ] **Step 4: Coordenar as fases sem falsa atomicidade distribuída**

Cada serviço mantém sua própria transação PostgreSQL. O coordenador não deve manter uma transação aberta durante chamadas Redis/OpenAI. Se a publicação RAG falhar, catálogos e corpus válidos permanecem no banco, o deploy falha fechado e a geração anterior continua ativa.

Essa escolha deve ser explícita na documentação e no teste: “bootstrap integral” significa que o release não é publicado até todas as fases passarem, não que PostgreSQL e Redis compartilham uma transação impossível.

- [ ] **Step 5: Gravar auditoria saneada**

Em sucesso, gravar `action='production_release_bootstrap_succeeded'`; em falha, `action='production_release_bootstrap_failed'`. O contexto inclui apenas SHA, fase, hashes, contagens, IDs de geração e classe da exceção. Não persistir mensagem arbitrária de exceção se contiver configuração ou URL.

A auditoria de falha deve ser gravada fora da transação revertida pela fase que falhou.

- [ ] **Step 6: Criar a interface CLI**

O comando aceita `--release-sha` ou `RELEASE_SHA`, e `--json` para automação. O JSON vai para stdout; progresso e erros seguros vão para stderr. Código de saída diferente de zero em qualquer falha.

- [ ] **Step 7: Executar GREEN**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_production_release_bootstrap.py -q`

Expected: PASS com auditorias e saída determinística.

### Task 2: Adicionar serviço one-shot ao Compose

**Files:**
- Modify: `docker-compose.vps.yml`
- Modify: `tests/test_vps_compose_contract.py`
- Modify: `tests/test_single_domain_deployment.py`

**Interfaces:**
- Produces: serviço `release_bootstrap` no profile `release`.
- Consumes: imagem do release, `.env`, PostgreSQL e Redis privados.

- [ ] **Step 1: Escrever o teste falho do serviço one-shot**

Validar via YAML parseado:

```python
bootstrap = compose['services']['release_bootstrap']
assert bootstrap['profiles'] == ['release']
assert bootstrap['restart'] == 'no'
assert bootstrap['command'] == [
    'python', 'manage.py', 'bootstrap_production_release',
    '--release-sha', '${RELEASE_SHA:?RELEASE_SHA is required}',
    '--json',
]
assert 'cloudflared' not in bootstrap.get('depends_on', {})
```

Verificar que o serviço não publica portas, não monta o Docker socket e não possui healthcheck de daemon.

- [ ] **Step 2: Executar RED**

Run: `.venv/bin/python -m pytest tests/test_vps_compose_contract.py tests/test_single_domain_deployment.py -q`

Expected: FAIL porque `release_bootstrap` não existe.

- [ ] **Step 3: Definir o serviço**

Reutilizar a imagem, `env_file`, ambiente ancorado, rede e volumes estritamente necessários do `app`. Usar `entrypoint: []` para impedir que o entrypoint normal execute migration/collectstatic novamente. Dependências: `db` e `redis` saudáveis.

Não incluir `release_bootstrap` na lista de serviços persistentes que exigem `restart` e healthcheck; ajustar o teste existente para distinguir daemon de job one-shot.

- [ ] **Step 4: Validar Compose com placeholders efêmeros**

Run: `POSTGRES_DB=test POSTGRES_USER=test POSTGRES_PASSWORD=test RABBITMQ_DEFAULT_USER=test RABBITMQ_DEFAULT_PASS=test TUNNEL_TOKEN=test RELEASE_SHA=$(git rev-parse HEAD) VPS_ENV_FILE=.env.example docker compose -f docker-compose.vps.yml config --quiet`

Expected: código 0 sem imprimir os valores.

- [ ] **Step 5: Executar GREEN**

Run: `.venv/bin/python -m pytest tests/test_vps_compose_contract.py tests/test_single_domain_deployment.py -q`

Expected: PASS.

### Task 3: Tornar o deploy privado até o bootstrap passar

**Files:**
- Modify: `scripts/deploy-vps.sh`
- Modify: `tests/test_native_postgres_deployment.py`
- Modify: `tests/test_single_domain_deployment.py`

**Interfaces:**
- Produces: sequência backup → código → runtime privado → bootstrap → checks locais → túnel → checks públicos.
- Consumes: JSON do comando de bootstrap e ID da geração ativa anterior.

- [ ] **Step 1: Escrever testes falhos de ordem e rollback**

Testar o texto/AST shell e, quando viável, executar o script com binários fake em `PATH`. Exigir a ordem:

```text
create_release_backup
stop_publication
promote_revision
deploy_private_runtime
capture_active_generation
run_release_bootstrap
verify_private_readiness
start_publication
verify_public_readiness
```

Cenários obrigatórios:

- bootstrap falha: túnel não inicia;
- check local falha: túnel não inicia;
- check público falha: geração anterior é restaurada antes do código anterior;
- rollback só reabre o túnel antigo depois que a origem antiga responde saudável.

- [ ] **Step 2: Executar RED**

Run: `.venv/bin/python -m pytest tests/test_native_postgres_deployment.py tests/test_single_domain_deployment.py -q`

Expected: FAIL na ordem atual, que sobe `cloudflared` junto com os demais serviços.

- [ ] **Step 3: Separar as funções operacionais**

Implementar:

```bash
stop_publication() { compose stop cloudflared; }
deploy_private_runtime() { compose up -d --build --remove-orphans --wait app nginx celery_worker celery_beat db redis rabbitmq backup_scheduler; }
run_release_bootstrap() { RELEASE_SHA="$RELEASE_SHA" compose --profile release run --rm release_bootstrap; }
start_publication() { compose up -d --wait cloudflared; }
```

Calcular `RELEASE_SHA="$(git rev-parse HEAD)"` após promoção e validá-lo como hexadecimal. Não interpolar ou registrar o conteúdo de `.env`.

- [ ] **Step 4: Capturar e restaurar a geração anterior**

Depois que o runtime privado do candidato aplicar migrations e antes do bootstrap, consultar de forma read-only a geração ativa com `get_active_knowledge_generation` e guardar apenas seu ID validado. Se ocorrer falha depois de uma nova ativação, executar `restore_knowledge_generation --generation-id "$PREVIOUS_GENERATION_ID"` contra o runtime ainda disponível.

Se não havia geração anterior, reconciliar para ausência de alias somente se o próprio bootstrap tiver ativado uma nova geração; registrar o caso e manter o domínio fechado para intervenção.

- [ ] **Step 5: Dividir prontidão privada e pública**

`verify_private_readiness()` exige serviços persistentes internos, `curl` na origem com Host correto, `manage.py check --deploy`, migrations aplicadas, hashes do bootstrap e alias/modo local coerentes.

`verify_public_readiness()` exige health do túnel e `https://${PUBLIC_HOST}/health/`. Nenhuma prova isolada de DNS, redirect ou página HTML conta como deploy saudável.

- [ ] **Step 6: Implementar rollback ordenado e recuperável**

1. parar `cloudflared`;
2. restaurar geração anterior quando aplicável;
3. voltar ao SHA anterior sem apagar worktree/dados;
4. reconstruir/subir runtime privado anterior;
5. validar origem antiga;
6. reabrir túnel e validar domínio;
7. preservar caminho do backup e evidências.

Não restaurar banco/mídia automaticamente porque migrations deste pacote são aditivas e retrocompatíveis. Uma eventual restauração destrutiva exige decisão operacional explícita.

- [ ] **Step 7: Executar GREEN e validar shell**

Run: `bash -n scripts/deploy-vps.sh`

Run: `command -v shellcheck >/dev/null && shellcheck scripts/deploy-vps.sh || true`

Run: `.venv/bin/python -m pytest tests/test_native_postgres_deployment.py tests/test_single_domain_deployment.py -q`

Expected: sintaxe válida e testes PASS. Se `shellcheck` não estiver instalado, registrar “não executado”; não declarar essa verificação verde.

### Task 4: Documentar configuração e runbook

**Files:**
- Modify locally: `.env` (arquivo ignorado; nunca exibir ou versionar conteúdo)
- Modify: `.env.example`
- Modify: `docs/deployment.md`
- Modify: `docs/architecture/operational-readiness.md`
- Modify: `docs/validation/requirements-matrix.yml`

- [ ] **Step 1: Validar e configurar o `.env` local sem expor segredos**

Comparar apenas nomes de chaves entre `.env` e `.env.example`. Preservar todos os valores secretos existentes e preencher/ajustar somente as configurações não secretas necessárias ao container: `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `KNOWLEDGE_REDIS_URL`, `KNOWLEDGE_REDIS_PREFIX`, `KNOWLEDGE_REDIS_MAX_CONNECTIONS`, modelos/dimensões da IA e `RAG_CHAT_LOCAL_ONLY` conforme o modo aprovado. Se uma credencial obrigatória estiver ausente, interromper e informar o nome da variável, sem inventar ou imprimir valor.

Confirmar que `.env` permanece ignorado pelo Git e com permissão restrita. Não adicionar `RELEASE_SHA` permanentemente; o script injeta o SHA do checkout promovido.

- [ ] **Step 2: Documentar variáveis, sem valores reais**

Registrar `RAG_CHAT_LOCAL_ONLY`, configuração Redis/OpenAI já existente e o fato de `RELEASE_SHA` ser injetado pelo script, não armazenado permanentemente no `.env`. Não adicionar segredo ou credencial de produção ao repositório.

- [ ] **Step 3: Escrever o runbook normal e de falha**

Incluir pré-requisitos, comando autorizado, ordem das fases, tempo esperado, artefatos de evidência, leitura do JSON e diagnóstico de falhas por fase.

- [ ] **Step 4: Documentar rollback e restauração manual**

Explicar diferença entre rollback de código/índice e restore de banco/mídia. Registrar que o backup é criado e verificado antes do release, mas não é aplicado automaticamente.

- [ ] **Step 5: Atualizar matriz de requisitos**

Mapear catálogos reais, cobertura funcional, modo RAG, túnel fechado, auditoria e rollback aos testes correspondentes.

### Task 5: Executar o gate integrado sem tocar na VPS

**Files:**
- Verify only.

- [ ] **Step 1: Verificações estáticas**

Run: `git diff --check`

Run: `bash -n scripts/deploy-vps.sh scripts/backup.sh`

Run: `.venv/bin/python manage.py check`

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`

- [ ] **Step 2: Testes focados dos três planos**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_official_reference_snapshots.py tests/test_production_reference_catalogs.py tests/test_knowledge_manual.py tests/test_knowledge_ingestion.py tests/test_knowledge_indexing.py tests/test_knowledge_retrieval.py tests/test_release_knowledge.py tests/test_production_release_bootstrap.py tests/test_vps_compose_contract.py tests/test_native_postgres_deployment.py tests/test_single_domain_deployment.py -q`

Expected: todos PASS em banco PostgreSQL de teste isolado.

- [ ] **Step 3: Gate amplo proporcional ao risco**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_auxiliary_reference_data.py tests/test_normalized_locations.py tests/test_master_data.py tests/test_costing_migrations.py tests/test_crm.py tests/test_finance.py tests/test_fiscal.py tests/test_training.py tests/test_governance.py -q`

Expected: PASS sem regressões nos models populados.

- [ ] **Step 4: Revisar escopo e pendências**

Confirmar por busca negativa que nenhum seeder dos planos cria produtos, parceiros, plantas, fórmulas, lotes, documentos, ordens ou transações. Separar claramente falhas preexistentes do worktree de falhas introduzidas.

- [ ] **Step 5: Parar antes de operações externas**

Entregar resultados locais e solicitar autorização explícita antes de commit, push ou execução na VPS. O teste real de deploy só pode ser considerado concluído com evidência fresca da origem, túnel e domínio públicos.
