# Corpus Funcional da IA e Publicação RAG — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Multi-agent execution is not authorized for this task.

**Goal:** Construir e publicar, a cada release, um corpus pt-BR auditável que cubra todas as funcionalidades registradas do ERP e permita à IA responder como usar o sistema.

**Architecture:** Gerar o manual a partir dos registries reais de módulos, recursos e ações, complementar com documentação funcional versionada e validar cobertura antes de qualquer gravação. Preservar documentos históricos, mas tornar elegível apenas a versão corrente de cada fonte. Publicar o índice vetorial por geração blue-green; no modo local, provar a recuperação PostgreSQL sem depender de API externa.

**Tech Stack:** Python 3.14, Django 6, PostgreSQL, Redis/RediSearch, OpenAI embeddings, pytest-django.

## Global Constraints

- O corpus deve cobrir 100% de `base.ui.registry.get_modules()` e `base.ui.actions.registry.action_registry.all()`.
- Todo conteúdo e metadado visível deve estar em pt-BR; identificadores técnicos permanecem estáveis.
- O corpus não pode copiar `.env`, segredos, logs, dumps, credenciais ou caminhos locais.
- Cada release deve possuir SHA válido, hash canônico do corpus, contagens e relatório de cobertura.
- Citações históricas permanecem resolvíveis; apenas documentos correntes entram em novas buscas e índices.
- O modo vetorial é obrigatório, exceto quando `RAG_CHAT_LOCAL_ONLY=true`.
- Uma falha nunca pode substituir a geração ativa nem deixar o alias Redis apontando para índice incompleto.
- Não executar commit, push ou deploy sem autorização explícita do usuário.

## File Map

- `knowledge/manual_coverage.py`: inventário e validação de cobertura funcional.
- `knowledge/manual_catalog.py`: documentos canônicos por módulo, recurso e ação.
- `knowledge/models.py`: versão corrente dos documentos preservando histórico.
- `knowledge/migrations/0003_current_manual_document.py`: constraint de documento corrente.
- `knowledge/services.py`: ingestão atômica e recuperação somente da versão corrente.
- `knowledge/indexing.py`: publicação determinística e restauração de geração.
- `knowledge/release_bootstrap.py`: build/publish/smoke da base de conhecimento.
- `knowledge/management/commands/build_erp_manual_corpus.py`: interface explícita por release.
- `knowledge/management/commands/restore_knowledge_generation.py`: rollback operacional do índice.
- `tests/test_knowledge_manual.py`: cobertura do catálogo e segurança do conteúdo.
- `tests/test_knowledge_ingestion.py`: histórico e unicidade da versão corrente.
- `tests/test_knowledge_indexing.py`: blue-green, falha segura e restauração.
- `tests/test_release_knowledge.py`: contratos dos modos vetorial e local.

---

### Task 1: Criar um manifesto completo das funcionalidades

**Files:**
- Create: `knowledge/manual_coverage.py`
- Modify: `knowledge/manual_catalog.py`
- Modify: `tests/test_knowledge_manual.py`

**Interfaces:**
- Produces: `build_functional_inventory() -> tuple[FunctionalCapability, ...]`.
- Produces: `validate_manual_coverage(entries, *, release_sha: str) -> CoverageReport`.
- Consumes: módulos/recursos registrados e `ActionConfig` do registry de ações.

- [ ] **Step 1: Escrever testes falhos para o inventário real**

Adicionar testes que comparem chaves exatas, sem contagem congelada:

```python
def test_functional_inventory_matches_runtime_registries():
    inventory = build_functional_inventory()
    expected_modules = {
        ('module', module.slug, '', '')
        for module in get_modules()
    }
    expected_resources = {
        ('resource', module.slug, resource.slug, '')
        for module in get_modules()
        for resource in module.resources
    }
    expected_actions = {
        ('action', action.module_slug, action.resource_slug, action.action_name)
        for action in action_registry.all()
    }
    assert {item.key for item in inventory} == (
        expected_modules | expected_resources | expected_actions
    )
```

Testar também SHA ausente/malformado, recurso sem manual, ação sem instruções e conteúdo com marcador sensível.

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_manual.py -q`

Expected: ERROR de importação de `knowledge.manual_coverage`.

- [ ] **Step 3: Implementar os tipos imutáveis de cobertura**

Criar:

```python
@dataclass(frozen=True, order=True)
class FunctionalCapability:
    kind: Literal['module', 'resource', 'action']
    module_slug: str
    resource_slug: str = ''
    action_name: str = ''
    label: str = ''

    @property
    def key(self):
        return self.kind, self.module_slug, self.resource_slug, self.action_name


@dataclass(frozen=True)
class CoverageReport:
    release_sha: str
    expected_modules: int
    expected_resources: int
    expected_actions: int
    covered_modules: int
    covered_resources: int
    covered_actions: int
    corpus_hash: str
```

Validar o SHA com `^[0-9a-f]{7,64}$`. Bloquear, de forma case-insensitive, `SECRET_KEY=`, `OPENAI_API_KEY=`, `POSTGRES_PASSWORD=`, `TUNNEL_TOKEN=`, `BEGIN PRIVATE KEY`, caminhos `/home/`, `/root/`, `/mnt/` e nomes de arquivos `.env`.

- [ ] **Step 4: Gerar entradas por módulo, recurso e ação**

Alterar a assinatura pública para `manual_entries(*, release_sha: str) -> tuple[dict, ...]`.

Para cada módulo, gerar uma visão geral. Para cada recurso, gerar um documento contendo finalidade, URL, permissão de consulta, modo somente leitura, campos de listagem/cadastro, inlines e fluxo CRUD aplicável. Para cada ação, incluir rótulo, descrição, permissões, campos e ajuda, estados permitidos, confirmação e mensagem de sucesso.

Todos os itens devem carregar:

```python
metadata = {
    'corpus': 'erp_manual',
    'language': 'pt-BR',
    'release_sha': release_sha,
    'module_slug': module_slug,
    'resource_slug': resource_slug,
    'action_names': action_names,
}
```

Cada entrada deve expor também `manual_sections`, uma tupla ordenada de objetos
`{'title', 'section_reference', 'content', 'metadata'}`. A ingestão usa essas
seções para preservar títulos e referências nas citações; `manual_content`
continua sendo a concatenação determinística para hash e compatibilidade.

Anexar a documentação `docs/architecture/<módulo>.md` somente à visão geral do módulo; não duplicá-la em cada recurso.

- [ ] **Step 5: Validar cobertura e determinismo**

Ordenar módulos, recursos, ações e chaves JSON por identificador estável. `validate_manual_coverage()` deve falhar antes da ingestão se qualquer capability estiver ausente, duplicada ou associada ao módulo/recurso errado.

- [ ] **Step 6: Executar GREEN**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_manual.py tests/test_action_discovery.py -q`

Expected: PASS sem alterar o contrato atual das 232 ações.

### Task 2: Preservar histórico e ativar somente o documento corrente

**Files:**
- Modify: `knowledge/models.py`
- Create: `knowledge/migrations/0003_current_manual_document.py`
- Modify: `knowledge/services.py`
- Modify: `knowledge/indexing.py`
- Modify: `knowledge/retrieval.py`
- Modify: `tests/test_knowledge_ingestion.py`
- Create: `tests/test_knowledge_indexing.py`

**Interfaces:**
- Produces: `KnowledgeDocument.is_current`.
- Guarantees: no máximo um documento corrente por fonte.
- Consumes: documentos históricos já existentes sem removê-los.

- [ ] **Step 1: Escrever o teste falho de sucessão documental**

```python
def test_reingestion_preserves_history_and_only_latest_is_searchable():
    first = ingest_source(entry(content='Fluxo antigo', release_sha='a' * 40))
    second = ingest_source(entry(content='Fluxo novo', release_sha='b' * 40))

    first['document'].refresh_from_db()
    assert first['document'].is_current is False
    assert second['document'].is_current is True
    eligible_document_ids = {chunk.document_id for chunk in _eligible_chunks()}
    assert first['document'].pk not in eligible_document_ids
```

Adicionar teste concorrente/constraint que rejeite dois documentos correntes da mesma fonte.

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_ingestion.py tests/test_knowledge_indexing.py -q`

Expected: FAIL porque `is_current` ainda não existe.

- [ ] **Step 3: Adicionar campo, índice e constraint condicional**

Adicionar `is_current = models.BooleanField('versão corrente', default=True)` e:

```python
models.UniqueConstraint(
    fields=['source'],
    condition=models.Q(is_current=True),
    name='unique_current_document_per_source',
)
```

A migration deve primeiro marcar como corrente apenas o documento elegível mais recente de cada fonte, ordenando por `retrieved_at`, `created_at` e `pk`; os demais tornam-se históricos. Só então adicionar a constraint.

- [ ] **Step 4: Tornar a ingestão uma troca atômica**

Dentro de `transaction.atomic()`:

1. bloquear a fonte com `select_for_update()`;
2. criar/reaproveitar o documento pelo hash ainda como `is_current=False`;
3. criar os chunks usando `manual_sections` quando fornecido e o chunker genérico nos demais casos;
4. marcar outros documentos da fonte como `is_current=False`;
5. marcar o novo documento como corrente somente após o chunking concluir.

Se o parsing/chunking falhar, a versão anterior deve continuar corrente.

- [ ] **Step 5: Filtrar todas as rotas de recuperação**

Adicionar `document__is_current=True` em `_eligible_chunks()`, na busca PostgreSQL e nos demais querysets que alimentam chat ou indexação. A página administrativa e a resolução de citações continuam mostrando documentos históricos.

- [ ] **Step 6: Executar GREEN e verificar migration**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_ingestion.py tests/test_knowledge_indexing.py tests/test_knowledge_retrieval.py -q`

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`

Expected: PASS e `No changes detected`.

### Task 3: Construir o corpus de release de forma atômica e auditável

**Files:**
- Create: `knowledge/release_bootstrap.py`
- Modify: `knowledge/management/commands/build_erp_manual_corpus.py`
- Create: `tests/test_release_knowledge.py`

**Interfaces:**
- Produces: `build_release_manual_corpus(release_sha: str) -> ManualCorpusResult`.
- Produces: `publish_release_knowledge(release_sha: str) -> KnowledgePublicationResult`.

- [ ] **Step 1: Escrever testes falhos para build e modos de publicação**

Cobrir:

- validação integral antes da primeira escrita;
- rollback do lote se a terceira entrada falhar;
- resultado com SHA, hash, módulos, recursos, ações, documentos e chunks;
- modo local recusando qualquer chamada ao gateway/Redis vetorial;
- modo vetorial falhando fechado sem configuração ou saúde necessárias.

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_release_knowledge.py -q`

Expected: ERROR de importação de `knowledge.release_bootstrap`.

- [ ] **Step 3: Implementar o resultado imutável e a construção do corpus**

```python
@dataclass(frozen=True)
class ManualCorpusResult:
    release_sha: str
    corpus_hash: str
    module_count: int
    resource_count: int
    action_count: int
    document_count: int
    chunk_count: int
```

Gerar e validar todas as entradas em memória; somente depois abrir uma transação e ingeri-las. O `corpus_hash` deve derivar de JSON canônico contendo SHA, códigos, hashes de conteúdo e metadados funcionais.

- [ ] **Step 4: Atualizar o comando existente**

Exigir `--release-sha` ou `RELEASE_SHA`; remover o valor genérico `generated`. Manter `--rebuild-index` apenas como compatibilidade, delegando a `publish_release_knowledge()`.

Saída de sucesso:

```text
Corpus funcional publicado: release=<sha> hash=<hash> módulos=<n> recursos=<n> ações=<n> documentos=<n> chunks=<n>
```

- [ ] **Step 5: Implementar os dois modos de publicação**

No modo vetorial:

- validar credenciais/configuração e saúde Redis;
- usar `generation_id=f'release-{release_sha[:12]}-{corpus_hash[:12]}'`;
- executar `build_index_generation()`;
- confirmar status `ACTIVE`, alias e hash do manifesto.

No modo `RAG_CHAT_LOCAL_ONLY=true`:

- não construir índice nem instanciar o gateway externo;
- executar perguntas representativas pela recuperação PostgreSQL;
- exigir citações correntes e cobertura de múltiplos módulos.

- [ ] **Step 6: Executar GREEN**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_release_knowledge.py tests/test_knowledge_manual.py -q`

Expected: PASS nos dois modos, com dependências externas substituídas por fakes determinísticos.

### Task 4: Permitir rollback explícito da geração ativa

**Files:**
- Modify: `knowledge/indexing.py`
- Create: `knowledge/management/commands/get_active_knowledge_generation.py`
- Create: `knowledge/management/commands/restore_knowledge_generation.py`
- Modify: `tests/test_knowledge_indexing.py`

**Interfaces:**
- Produces: `restore_index_generation(generation_id: str) -> KnowledgeIndexGeneration`.
- Produces: consulta CLI read-only que imprime somente o ID da geração ativa, ou uma linha vazia.
- Consumes: uma geração `RETIRED` cujo índice e manifesto Redis ainda existam.

- [ ] **Step 1: Escrever o teste falho de restauração blue-green**

```python
def test_restore_generation_reactivates_previous_index_atomically(redis_index):
    previous = active_generation('release-old')
    current = publish_generation('release-new')

    restored = restore_index_generation(previous.generation_id, redis_index=redis_index)

    current.refresh_from_db()
    assert restored.status == KnowledgeIndexGeneration.Status.ACTIVE
    assert current.status == KnowledgeIndexGeneration.Status.RETIRED
    assert redis_index.active_target() == previous.redis_index_name
```

Testar índice ausente, manifesto divergente, lock ocupado e perda do lock; em todos os casos a geração atual deve permanecer ativa.

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_indexing.py -q`

Expected: FAIL de importação da nova função.

- [ ] **Step 3: Implementar restauração com o lock de publicação existente**

Validar a existência do índice/manifesto antes de alterar o banco. Sob `RedisPublicationLock`, publicar primeiro o alias alvo e, na mesma seção crítica, atualizar os estados com transação e `select_for_update()`. Se a persistência falhar após troca do alias, reconciliar o alias com a geração ainda marcada como ativa.

- [ ] **Step 4: Criar comandos operacionais seguros**

`get_active_knowledge_generation` não recebe argumentos e imprime somente o ID validado. `restore_knowledge_generation` exige `--generation-id`, imprime geração anterior/nova e nunca aceita `BUILDING` ou `FAILED`. Nenhum dos comandos apaga índices.

- [ ] **Step 5: Executar GREEN**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_indexing.py -q`

Expected: PASS incluindo cenários de falha segura.

### Task 5: Documentar e fechar o gate do corpus

**Files:**
- Modify: `docs/architecture/ai-agents.md`
- Modify: `docs/architecture/foundation.md`
- Modify: `docs/pdf/manual_usuario.md`
- Modify: `docs/validation/requirements-matrix.yml`

- [ ] **Step 1: Documentar origem, cobertura e limites**

Registrar que o corpus explica uso do ERP, não executa operações em nome do usuário e não contém dados transacionais, segredos ou aconselhamento regulatório autônomo.

- [ ] **Step 2: Documentar os modos vetorial e local**

Explicar requisitos, smoke tests, geração ativa, rollback e evidências esperadas por release.

- [ ] **Step 3: Executar o gate focado**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_manual.py tests/test_knowledge_ingestion.py tests/test_knowledge_indexing.py tests/test_knowledge_retrieval.py tests/test_release_knowledge.py -q`

Run: `.venv/bin/python manage.py check`

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`

Expected: todos PASS, `System check identified no issues` e nenhuma migration pendente.

- [ ] **Step 4: Revisar o diff sem commit**

Run: `git diff --check`

Run: `git diff -- knowledge tests docs/architecture docs/pdf/manual_usuario.md docs/validation/requirements-matrix.yml`

Expected: somente mudanças previstas neste plano, preservando alterações preexistentes do usuário.
