# Assistente Regulatório em Modo Dual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disponibilizar modos funcional e regulatório isolados no chat RAG, com snapshots oficiais vigentes em 2 de setembro de 2026, citações, índices independentes e integração ao bootstrap de produção.

**Architecture:** Adicionar um discriminador de modo às fontes, sessões e gerações, mantendo uma geração PostgreSQL/Redis ativa por modo. O corpus regulatório será lido de snapshots versionados e validado por manifesto; recuperação, prompts, API e interface receberão o modo explícito e aplicarão filtros novamente no banco. O bootstrap só publicará o release após validar ambos os modos.

**Tech Stack:** Python 3.14, Django 6, Django REST Framework, PostgreSQL, Redis Search, OpenAI embeddings/Responses API, Bootstrap 5, JavaScript, pytest-django.

## Global Constraints

- Executar este plano depois de `2026-08-31-catalogos-referencia-producao.md` e `2026-08-31-corpus-funcional-ia-rag.md`, e antes das tarefas finais de `2026-08-31-bootstrap-deploy-producao.md`.
- Usar 2 de setembro de 2026 como data de corte regulatória do release.
- Consultar a rede somente no comando explícito de atualização; ingestão e deploy devem usar arquivos versionados locais.
- Aceitar no modo regulatório apenas fontes federais oficiais confirmadas e conteúdo permitido; ISO 22716 e GAMP 5 permanecem metadados sem texto integral.
- Manter o modo funcional restrito ao manual do ERP e o regulatório restrito às fontes oficiais elegíveis.
- Respostas são somente leitura, em pt-BR, com citações; o modo regulatório inclui aviso de limitação técnica/jurídica.
- Não ingerir `.env`, credenciais, logs, dumps, dados pessoais, registros operacionais nem o código-fonte integral.
- Não criar produtos, matérias-primas, fórmulas, parceiros, plantas, lotes, saldos, ordens, documentos GxP, usuários ou dados de demonstração.
- Não usar force-push e não restaurar banco ou mídia automaticamente em rollback.

## Execution Order Across Plans

1. Executar integralmente `docs/superpowers/plans/2026-08-31-catalogos-referencia-producao.md`.
2. Executar integralmente `docs/superpowers/plans/2026-08-31-corpus-funcional-ia-rag.md`.
3. Executar Tasks 1–7 deste plano.
4. Executar integralmente `docs/superpowers/plans/2026-08-31-bootstrap-deploy-producao.md`, aplicando as extensões da Task 7 deste plano.
5. Rodar o gate integrado, revisar o diff, fazer os commits restantes, push e deploy autorizado.

---

### Task 1: Persistir o modo das fontes, sessões e gerações

**Files:**
- Modify: `knowledge/models.py`
- Create: `knowledge/migrations/0004_dual_assistant_modes.py`
- Modify: `knowledge/admin.py`
- Modify: `tests/test_knowledge_models.py`
- Modify: `tests/test_knowledge_api.py`
- Modify: `tests/test_knowledge_indexing.py`

**Interfaces:**
- Produces: `KnowledgeSource.AssistantMode`, `KnowledgeSource.assistant_mode`, `RAGChatSession.mode`, `KnowledgeIndexGeneration.mode`.
- Produces: uma constraint ativa por par `(mode, status)` quando `status='active'`.
- Consumes: `KnowledgeDocument.is_current` e a migration `knowledge.0003`, criadas pelo plano do corpus funcional.

- [ ] **Step 1: Escrever os testes falhos dos modos e das constraints**

Adicionar testes que criem uma fonte funcional, uma regulatória, duas sessões em modos diferentes e duas gerações ativas, uma por modo:

```python
def test_dual_modes_are_persisted_and_one_generation_per_mode_can_be_active(db):
    functional = KnowledgeSource.objects.create(
        code='RGN-MANUAL',
        title='Manual',
        source_type=KnowledgeSource.SourceType.SYSTEM_MANUAL,
        publisher='RGN Farma System',
        assistant_mode=KnowledgeSource.AssistantMode.FUNCTIONAL,
        is_official=True,
    )
    regulatory = KnowledgeSource.objects.create(
        code='ANVISA-RDC-894-2024',
        title='RDC 894/2024',
        source_type=KnowledgeSource.SourceType.REGULATION,
        publisher='Anvisa',
        jurisdiction='BR',
        assistant_mode=KnowledgeSource.AssistantMode.REGULATORY,
        is_official=True,
    )
    first = KnowledgeIndexGeneration.objects.create(
        generation_id='functional-release',
        redis_index_name='idx:test:functional:functional-release',
        mode=KnowledgeSource.AssistantMode.FUNCTIONAL,
        status=KnowledgeIndexGeneration.Status.ACTIVE,
    )
    second = KnowledgeIndexGeneration.objects.create(
        generation_id='regulatory-release',
        redis_index_name='idx:test:regulatory:regulatory-release',
        mode=KnowledgeSource.AssistantMode.REGULATORY,
        status=KnowledgeIndexGeneration.Status.ACTIVE,
    )

    assert functional.assistant_mode == 'functional'
    assert regulatory.assistant_mode == 'regulatory'
    assert first.mode != second.mode


def test_two_active_generations_for_same_mode_are_rejected(db):
    values = {
        'mode': KnowledgeSource.AssistantMode.REGULATORY,
        'status': KnowledgeIndexGeneration.Status.ACTIVE,
    }
    KnowledgeIndexGeneration.objects.create(
        generation_id='regulatory-one',
        redis_index_name='idx:test:regulatory:one',
        **values,
    )
    with pytest.raises(IntegrityError):
        KnowledgeIndexGeneration.objects.create(
            generation_id='regulatory-two',
            redis_index_name='idx:test:regulatory:two',
            **values,
        )
```

Adicionar ao teste da API uma sessão sem modo explícito e verificar compatibilidade:

```python
session = RAGChatSession.objects.create(title='Histórica', created_by=owner)
assert session.mode == RAGChatSession.Mode.FUNCTIONAL
```

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_models.py tests/test_knowledge_api.py tests/test_knowledge_indexing.py -q`

Expected: FAIL porque os enums/campos `assistant_mode` e `mode` ainda não existem e a constraint continua global.

- [ ] **Step 3: Adicionar os enums, campos e validações**

Em `KnowledgeSource`, adicionar:

```python
class AssistantMode(models.TextChoices):
    NONE = 'none', 'Não elegível'
    FUNCTIONAL = 'functional', 'Ajuda do Sistema'
    REGULATORY = 'regulatory', 'Conformidade Regulatória'

assistant_mode = models.CharField(
    'modo do assistente',
    max_length=16,
    choices=AssistantMode.choices,
    default=AssistantMode.NONE,
)
```

Em `KnowledgeSource.clean()`, acrescentar:

```python
if self.assistant_mode == self.AssistantMode.FUNCTIONAL:
    if self.source_type != self.SourceType.SYSTEM_MANUAL:
        errors['assistant_mode'] = 'O modo funcional aceita somente manuais do sistema.'
if self.assistant_mode == self.AssistantMode.REGULATORY:
    if not self.is_official or self.jurisdiction != 'BR':
        errors['assistant_mode'] = (
            'O modo regulatório exige fonte oficial de jurisdição brasileira.'
        )
```

Em `RAGChatSession`, adicionar:

```python
class Mode(models.TextChoices):
    FUNCTIONAL = 'functional', 'Ajuda do Sistema'
    REGULATORY = 'regulatory', 'Conformidade Regulatória'

mode = models.CharField(
    'modo', max_length=16, choices=Mode.choices, default=Mode.FUNCTIONAL
)
```

Em `KnowledgeIndexGeneration`, adicionar `mode` usando as mesmas duas strings e substituir `unique_active_knowledge_generation` por:

```python
class Mode(models.TextChoices):
    FUNCTIONAL = 'functional', 'Ajuda do Sistema'
    REGULATORY = 'regulatory', 'Conformidade Regulatória'

mode = models.CharField(
    'modo',
    max_length=16,
    choices=Mode.choices,
    default=Mode.FUNCTIONAL,
)

models.UniqueConstraint(
    fields=['mode', 'status'],
    condition=models.Q(status='active'),
    name='unique_active_knowledge_generation_per_mode',
)
```

Atualizar `activate()` para desativar somente gerações do mesmo modo:

```python
type(self).objects.select_for_update().filter(
    mode=locked.mode,
    status=self.Status.ACTIVE,
).exclude(pk=locked.pk).update(status=self.Status.RETIRED)
```

- [ ] **Step 4: Criar e revisar a migration de compatibilidade**

Gerar `0004_dual_assistant_modes`. Inserir `RunPython` antes da troca de constraint:

```python
def classify_existing_rows(apps, schema_editor):
    Source = apps.get_model('knowledge', 'KnowledgeSource')
    Session = apps.get_model('knowledge', 'RAGChatSession')
    Generation = apps.get_model('knowledge', 'KnowledgeIndexGeneration')
    Source.objects.filter(
        source_type='system_manual', chat_eligible=True
    ).update(assistant_mode='functional')
    Session.objects.update(mode='functional')
    Generation.objects.update(mode='functional')
```

O `reverse_code` deve voltar `assistant_mode` para `none` e manter sessões/gerações como `functional`, pois os campos serão removidos pelo reverse das operações de schema.

- [ ] **Step 5: Atualizar administração e filtros somente leitura**

Adicionar `assistant_mode` aos `list_display`/`list_filter` de `KnowledgeSourceAdmin`, `mode` ao admin de sessões e gerações e aos `filterset_fields` dos viewsets de fonte e sessão.

- [ ] **Step 6: Executar GREEN e checks de migration**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_models.py tests/test_knowledge_api.py tests/test_knowledge_indexing.py -q`

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`

Expected: PASS e `No changes detected`.

- [ ] **Step 7: Commit**

```bash
git add knowledge/models.py knowledge/admin.py knowledge/migrations/0004_dual_assistant_modes.py tests/test_knowledge_models.py tests/test_knowledge_api.py tests/test_knowledge_indexing.py
git commit -m "feat(knowledge): persist functional and regulatory modes"
```

---

### Task 2: Criar o manifesto e snapshots regulatórios offline

**Files:**
- Create: `knowledge/regulatory_catalog.py`
- Create: `knowledge/regulatory_snapshots.py`
- Create: `knowledge/management/commands/refresh_regulatory_snapshots.py`
- Create: `reference_data/regulatory/manifest.json`
- Create: `reference_data/regulatory/snapshots/`
- Create: `tests/test_regulatory_catalog.py`
- Modify: `knowledge/source_catalog.py`

**Interfaces:**
- Produces: `REGULATORY_CUTOFF = date(2026, 9, 2)`.
- Produces: `RegulatoryRecord`, `load_regulatory_manifest()` e `regulatory_entries()`.
- Produces: comando online `refresh_regulatory_snapshots --cutoff 2026-09-02`.
- Consumes: `reference_data.manifest.canonical_hash` criado pelo plano de catálogos.

- [ ] **Step 1: Escrever testes falhos de cobertura, hash e licença**

Criar testes com o conjunto mínimo obrigatório:

```python
REQUIRED_CODES = {
    'ANVISA-RDC-19-2013',
    'ANVISA-RDC-48-2013',
    'ANVISA-RDC-16-2014',
    'ANVISA-RDC-250-2018',
    'ANVISA-IN-69-2020',
    'ANVISA-RDC-409-2020',
    'ANVISA-RDC-528-2021',
    'ANVISA-RDC-529-2021',
    'ANVISA-RDC-530-2021',
    'ANVISA-RDC-600-2022',
    'ANVISA-RDC-628-2022',
    'ANVISA-RDC-629-2022',
    'ANVISA-RDC-630-2022',
    'ANVISA-RDC-642-2022',
    'ANVISA-RDC-643-2022',
    'ANVISA-RDC-644-2022',
    'ANVISA-RDC-645-2022',
    'ANVISA-RDC-646-2022',
    'ANVISA-IN-124-2022',
    'ANVISA-RDC-752-2022',
    'ANVISA-RDC-894-2024',
    'ANVISA-RDC-907-2024',
    'ANVISA-RDC-1029-2026',
    'ANVISA-RDC-1030-2026',
    'BR-LEI-15154-2025',
    'BR-LEI-15183-2025',
}


def test_regulatory_manifest_has_required_scope_and_verified_hashes():
    manifest = load_regulatory_manifest()
    codes = {record.code for record in manifest.records}
    assert REQUIRED_CODES <= codes
    assert manifest.cutoff == date(2026, 9, 2)
    assert all(record.publisher == 'Anvisa' for record in manifest.records)
    assert all(record.official_url.startswith('https://') for record in manifest.records)
    assert all(record.sha256 == snapshot_hash(record.snapshot_path) for record in manifest.records)


def test_metadata_only_references_have_no_snapshot_text():
    entries = regulatory_entries()
    protected = [entry for entry in entries if entry['metadata'].get('metadata_only')]
    assert {entry['code'] for entry in protected} == {
        'ISO-22716-REFERENCE',
        'ISPE-GAMP-5-REFERENCE',
    }
    assert all('local_path' not in entry['metadata'] for entry in protected)
```

Adicionar um teste que rejeite item com `status='revoked'`, `effective_from` posterior à data de corte, hash divergente ou domínio oficial fora de `gov.br`, `in.gov.br`, `bvsms.saude.gov.br` e `iso.org` apenas para metadados.

- [ ] **Step 2: Executar RED**

Run: `.venv/bin/python -m pytest tests/test_regulatory_catalog.py -q`

Expected: ERROR de importação porque o catálogo regulatório e o manifesto ainda não existem.

- [ ] **Step 3: Implementar os tipos e validações do manifesto**

Em `knowledge/regulatory_catalog.py`, criar:

```python
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REGULATORY_CUTOFF = date(2026, 9, 2)
ALLOWED_OFFICIAL_HOSTS = frozenset(
    {
        'www.gov.br',
        'in.gov.br',
        'www.in.gov.br',
        'bvsms.saude.gov.br',
        'www.planalto.gov.br',
    }
)


@dataclass(frozen=True, slots=True)
class RegulatoryRecord:
    code: str
    title: str
    publisher: str
    official_url: str
    snapshot_path: Path
    source_type: str
    status: str
    published_on: date
    effective_from: date
    effective_to: date | None
    verified_on: date
    sha256: str
    supersedes: tuple[str, ...]
    related_codes: tuple[str, ...]
    normative: bool

    def is_current_at(self, value: date) -> bool:
        return (
            self.status == 'current'
            and self.effective_from <= value
            and (self.effective_to is None or self.effective_to >= value)
        )
```

`load_regulatory_manifest()` deve validar datas ISO, códigos únicos, arquivos sob `reference_data/regulatory/snapshots`, SHA-256, hosts permitidos e referências existentes em `supersedes`/`related_codes`. `regulatory_entries()` deve retornar somente registros correntes na data de corte e mapear cada item para `assistant_mode='regulatory'`, `is_official=True`, `jurisdiction='BR'`, `chat_eligible=True` e `metadata.local_path`.

- [ ] **Step 4: Implementar snapshots locais seguros**

Em `knowledge/regulatory_snapshots.py`, criar funções:

```python
def snapshot_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_official_text(value: str) -> str:
    text = BeautifulSoup(value, 'html.parser').get_text('\n')
    return '\n'.join(line.strip() for line in text.splitlines() if line.strip())


def write_snapshot(*, root: Path, code: str, content: str) -> Path:
    target = (root / f'{code.lower()}.txt').resolve()
    if root.resolve() not in target.parents:
        raise ValueError('Caminho de snapshot inválido.')
    target.write_text(normalize_official_text(content) + '\n', encoding='utf-8')
    return target
```

O comando de atualização deve usar `httpx` com redirect, timeout entre 1 e 300 segundos, verificar hostname final, rejeitar resposta vazia e gravar somente em diretório temporário. Para `text/html`, deve reutilizar `extract_html_text`; para `application/pdf`, deve reutilizar `extract_pdf_text` e rejeitar PDF sem texto extraível. A troca para o diretório versionado só ocorre após validar todos os hashes e o manifesto. O comando nunca será chamado pelo deploy.

- [ ] **Step 5: Gerar e revisar o snapshot de 2 de setembro de 2026**

Run: `.venv/bin/python manage.py refresh_regulatory_snapshots --cutoff 2026-09-02 --timeout 90`

Expected: criar o manifesto e snapshots para todos os códigos obrigatórios; imprimir somente código, status HTTP, bytes e hash, sem conteúdo integral.

Revisar cada item contra a publicação oficial. Marcar RDC 529/2021, RDC 530/2021 e qualquer outro ato revogado/substituído com datas e relações explícitas; manter seus metadados para rastreabilidade, porém `regulatory_entries()` não os torna elegíveis. Manter RDC 1.029/2026, RDC 1.030/2026, Lei 15.154/2025 e Lei 15.183/2025 como correntes somente se a fonte oficial confirmar vigência até a data de corte. Registrar no manifesto todos os atos encontrados no inventário oficial, mesmo quando excluídos do corpus corrente, com justificativa fechada `revoked`, `future`, `out_of_scope`, `metadata_only` ou `unverified`.

- [ ] **Step 6: Substituir o catálogo regulatório hardcoded**

Em `knowledge/source_catalog.py`, manter as referências protegidas e manuais internas, importar `regulatory_entries` e definir:

```python
SEED_SOURCES = [
    *regulatory_entries(),
    *PROTECTED_REFERENCE_SOURCES,
    *SYSTEM_HELP_SOURCES,
]
```

- [ ] **Step 7: Executar GREEN e busca de segurança**

Run: `.venv/bin/python -m pytest tests/test_regulatory_catalog.py tests/test_knowledge_ingestion.py -q`

Run: `git grep -nEi '(SECRET_KEY|OPENAI_API_KEY|TUNNEL_TOKEN|POSTGRES_PASSWORD)=' -- reference_data/regulatory knowledge || true`

Expected: testes PASS e nenhuma atribuição de segredo.

- [ ] **Step 8: Commit**

```bash
git add knowledge/regulatory_catalog.py knowledge/regulatory_snapshots.py knowledge/management/commands/refresh_regulatory_snapshots.py knowledge/source_catalog.py reference_data/regulatory tests/test_regulatory_catalog.py tests/test_knowledge_ingestion.py
git commit -m "feat(knowledge): version cosmetics regulatory corpus"
```

---

### Task 3: Isolar elegibilidade, índices e recuperação por modo

**Files:**
- Modify: `knowledge/eligibility.py`
- Modify: `knowledge/indexing.py`
- Modify: `knowledge/retrieval.py`
- Modify: `knowledge/services.py`
- Modify: `knowledge/redis_index.py`
- Modify: `tests/test_knowledge_retrieval.py`
- Modify: `tests/test_knowledge_indexing.py`
- Create: `tests/test_regulatory_retrieval.py`

**Interfaces:**
- Produces: `is_document_eligible(document, *, mode: str, as_of: date | None = None) -> bool`.
- Produces: `build_index_generation(*, mode: str, ...) -> KnowledgeIndexGeneration`.
- Produces: `retrieve_context(question, *, mode: str, filters=None, limit=8, as_of=None)`.
- Produces: aliases Redis `idx:<prefix>:functional:active` e `idx:<prefix>:regulatory:active`.

- [ ] **Step 1: Escrever testes falhos de isolamento e vigência**

Criar uma fonte manual e uma regulatória com texto coincidente. Verificar que cada modo retorna apenas sua fonte. Criar documentos regulatórios futuro, revogado, substituído e corrente; somente o corrente deve retornar em 2 de setembro de 2026.

```python
functional = retrieve_context(
    'Como registrar evento adverso?', mode='functional', as_of=date(2026, 9, 2)
)
regulatory = retrieve_context(
    'Como registrar evento adverso?', mode='regulatory', as_of=date(2026, 9, 2)
)
assert {item.source_type for item in functional} == {'system_manual'}
assert {item.source_type for item in regulatory} <= {
    'regulation', 'guideline', 'technical_reference', 'web'
}
assert {item.source_id for item in functional}.isdisjoint(
    {item.source_id for item in regulatory}
)
```

No teste do índice, construir duas gerações e verificar aliases independentes e rollback de uma sem alterar a outra.

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_retrieval.py tests/test_knowledge_indexing.py tests/test_regulatory_retrieval.py -q`

Expected: FAIL porque `mode` não é aceito e o alias ainda é global.

- [ ] **Step 3: Tornar elegibilidade explícita**

Implementar em `eligibility.py`:

```python
def is_document_eligible(document, *, mode, as_of=None):
    if document.status != KnowledgeDocument.Status.INGESTED:
        return False
    if not document.is_current or not document.source.is_active:
        return False
    if document.source.assistant_mode != mode:
        return False
    if mode == KnowledgeSource.AssistantMode.FUNCTIONAL:
        return _functional_document_is_current(document)
    if mode == KnowledgeSource.AssistantMode.REGULATORY:
        return _regulatory_document_is_current(document, as_of=as_of)
    return False
```

`_regulatory_document_is_current` deve ler datas já validadas dos metadados, exigir `status='current'`, `verified_on='2026-09-02'`, `effective_from <= as_of`, `effective_to` vazio ou maior/igual a `as_of`, fonte oficial e jurisdição `BR`.

- [ ] **Step 4: Parametrizar publicação Redis por modo**

Alterar `_eligible_chunks(mode)`, `_manifest_hash(..., mode=mode)`, `build_index_generation(mode=...)` e `reconcile_active_alias(mode=...)`. Nomes devem ser:

```python
alias = f'idx:{settings.KNOWLEDGE_REDIS_PREFIX}:{mode}:active'
redis_index_name = f'idx:{settings.KNOWLEDGE_REDIS_PREFIX}:{mode}:{generation_id}'
lock_key = f'{settings.KNOWLEDGE_REDIS_PREFIX}:publication-lock:{mode}'
```

Todas as consultas e locks PostgreSQL devem filtrar `mode`. Incluir `mode` no manifesto Redis e em cada row.

- [ ] **Step 5: Parametrizar recuperação e aplicar defesa em profundidade**

`retrieve_context()` deve exigir `mode`, selecionar a geração ativa correspondente, pesquisar o alias do modo e refiltrar hits no PostgreSQL por `source__assistant_mode=mode`, `document__is_current=True` e `is_document_eligible(..., mode=mode, as_of=as_of)`. Ignorar qualquer hit Redis que não corresponda ao modo solicitado.

Manter o fallback PostgreSQL com os mesmos filtros. `filters` externos nunca poderão sobrescrever `mode`, `is_active`, `is_current`, `status` ou vigência.

- [ ] **Step 6: Executar GREEN**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_retrieval.py tests/test_knowledge_indexing.py tests/test_regulatory_retrieval.py -q`

Expected: PASS com duas gerações/aliases e fontes disjuntas.

- [ ] **Step 7: Commit**

```bash
git add knowledge/eligibility.py knowledge/indexing.py knowledge/retrieval.py knowledge/services.py knowledge/redis_index.py tests/test_knowledge_retrieval.py tests/test_knowledge_indexing.py tests/test_regulatory_retrieval.py
git commit -m "feat(knowledge): isolate retrieval and indexes by mode"
```

---

### Task 4: Separar prompts, sessões e contrato da API

**Files:**
- Modify: `knowledge/services.py`
- Modify: `knowledge/serializers.py`
- Modify: `knowledge/views.py`
- Modify: `tests/test_knowledge_chat_service.py`
- Modify: `tests/test_knowledge_api.py`
- Create: `tests/test_regulatory_chat_service.py`

**Interfaces:**
- Produces: `answer_question(user, question, *, mode='functional', session_id=None, limit=5)`.
- Produces: `build_system_prompt(mode: str) -> str`, `build_prompt(question, context, *, mode: str) -> str` e `local_answer(question, context, *, mode: str, provider_fallback=False) -> str`.
- API POST `/api/knowledge/chat/`: aceita `question`, `mode` e `session_id`.

- [ ] **Step 1: Escrever testes falhos de sessão imutável e resposta regulatória**

Adicionar:

```python
def test_new_chat_requires_known_mode_and_persists_it(api_client, allowed_user):
    api_client.force_authenticate(allowed_user)
    response = api_client.post(
        '/api/knowledge/chat/',
        {'question': 'Como funciona a cosmetovigilância?', 'mode': 'regulatory'},
        format='json',
    )
    assert response.status_code == 200
    session = RAGChatSession.objects.get(pk=response.json()['session_id'])
    assert session.mode == 'regulatory'


def test_existing_session_rejects_mode_change(api_client, regulatory_session):
    response = api_client.post(
        '/api/knowledge/chat/',
        {
            'question': 'Continue',
            'mode': 'functional',
            'session_id': regulatory_session.pk,
        },
        format='json',
    )
    assert response.status_code == 400
    assert response.json()['mode'] == [
        'O modo informado não corresponde ao modo desta conversa.'
    ]


def test_regulatory_answer_contains_limitation_and_official_citation(user):
    result = answer_question(
        user,
        'Quais eventos devem ser tratados?',
        mode='regulatory',
    )
    assert 'responsável técnico' in result['answer'].lower()
    assert result['citations']
    assert all(item['url'].startswith('https://') for item in result['citations'])
```

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_chat_service.py tests/test_knowledge_api.py tests/test_regulatory_chat_service.py -q`

Expected: FAIL porque a API e o serviço não aceitam `mode`.

- [ ] **Step 3: Validar o modo no serializer**

Adicionar ao `RAGChatRequestSerializer`:

```python
mode = serializers.ChoiceField(
    choices=RAGChatSession.Mode.choices,
    default=RAGChatSession.Mode.FUNCTIONAL,
)
```

No `validate()`, se houver `session_id`, buscar somente sessão do usuário autenticado e aberta; rejeitar `mode` divergente com a mensagem testada. Passar `request.user` no contexto do serializer em `RAGChatAPIView`.

- [ ] **Step 4: Tornar sessão e recuperação dependentes do modo**

Alterar `_get_or_create_session(..., mode)` para criar a sessão com o modo e nunca atualizá-lo. `answer_question` deve obter a sessão primeiro, usar `session.mode` em todas as chamadas de recuperação/prompt e persistir `mode` dentro de `retrieved_context` para auditoria.

- [ ] **Step 5: Criar prompts separados e recusas seguras**

Definir `FUNCTIONAL_SYSTEM_PROMPT` preservando o contrato atual. Definir:

```python
REGULATORY_SYSTEM_PROMPT = (
    'Você é o assistente de consulta regulatória do RGN Farma System para a '
    'indústria brasileira de produtos de higiene pessoal, cosméticos e perfumes. '
    'Responda em português do Brasil somente com base nas fontes oficiais '
    'fornecidas. Diferencie obrigação normativa de guia ou orientação, mencione '
    'a norma e a data de corte quando relevantes e não invente vigência, '
    'interpretação, aprovação sanitária ou parecer jurídico. Não execute ações '
    'nem altere registros. Quando o contexto for insuficiente, declare a '
    'limitação e encaminhe a decisão ao responsável técnico, regulatório ou '
    'jurídico.'
)
REGULATORY_DISCLAIMER = (
    'Esta resposta auxilia a consulta e não substitui a avaliação do responsável '
    'técnico, regulatório ou jurídico.'
)
```

`build_prompt` deve usar o rótulo `Contexto do manual` no modo funcional e `Contexto regulatório oficial — corte em 02/09/2026` no regulatório. `local_answer` regulatório deve sempre terminar com `REGULATORY_DISCLAIMER`.

- [ ] **Step 6: Executar GREEN e schema DRF**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_knowledge_chat_service.py tests/test_knowledge_api.py tests/test_regulatory_chat_service.py -q`

Run: `.venv/bin/python manage.py spectacular --file /tmp/rgn-openapi-dual-mode.yml --validate`

Expected: PASS e schema válido com `mode` em `RAGChatRequest`.

- [ ] **Step 7: Commit**

```bash
git add knowledge/services.py knowledge/serializers.py knowledge/views.py tests/test_knowledge_chat_service.py tests/test_knowledge_api.py tests/test_regulatory_chat_service.py
git commit -m "feat(knowledge): add regulatory chat contract"
```

---

### Task 5: Expor o seletor acessível dos dois modos

**Files:**
- Modify: `templates/includes/rag_chat.html`
- Modify: `templates/app/resource_chat.html`
- Modify: `static/js/rag-chat.js`
- Modify: `static/css/app.css`
- Modify: `tests/test_rag_chat_frontend.py`
- Modify: `tests/test_knowledge_ui_registry.py`

**Interfaces:**
- Consumes: API `mode=functional|regulatory` da Task 4.
- Produces: controles `[data-rag-chat-mode]` e armazenamento por chave `rgn-rag-session:<mode>`.

- [ ] **Step 1: Escrever testes falhos do seletor e armazenamento isolado**

Adicionar contratos:

```python
def test_chat_exposes_accessible_dual_mode_selector():
    template = (ROOT / 'templates/includes/rag_chat.html').read_text(encoding='utf-8')
    assert 'aria-label="Modo do assistente"' in template
    assert 'value="functional"' in template
    assert 'value="regulatory"' in template
    assert 'Ajuda do Sistema' in template
    assert 'Conformidade Regulatória' in template


def test_chat_client_sends_mode_and_keeps_sessions_separate():
    script = (ROOT / 'static/js/rag-chat.js').read_text(encoding='utf-8')
    assert 'mode: activeMode' in script
    assert "'rgn-rag-session:' + activeMode" in script
    assert 'textContent = text' in script
    assert 'innerHTML' not in script
```

- [ ] **Step 2: Executar RED**

Run: `.venv/bin/python -m pytest tests/test_rag_chat_frontend.py tests/test_knowledge_ui_registry.py -q`

Expected: FAIL porque o seletor e o payload de modo não existem.

- [ ] **Step 3: Adicionar o seletor Bootstrap acessível**

Antes do log de mensagens, inserir um `fieldset` com `legend` visualmente oculta e dois radios Bootstrap. O funcional inicia marcado. Adicionar um texto de escopo com `aria-live="polite"`; ao selecionar regulatório, mostrar a data de corte e o aviso de consulta, sem prometer parecer ou atualização em tempo real.

- [ ] **Step 4: Isolar sessões no JavaScript**

Em `init`, calcular:

```javascript
var activeMode = 'functional';
function sessionKey() {
    return 'rgn-rag-session:' + activeMode;
}
function loadSession() {
    return sessionStorage.getItem(sessionKey());
}
```

O payload deve conter `mode: activeMode`. Ao trocar o radio, atualizar `activeMode`, recarregar o `sessionId` do modo, limpar apenas a apresentação corrente, alterar título/status e focar o campo. `Nova conversa` remove somente `sessionKey()` do modo ativo. Todo conteúdo remoto continua atribuído por `textContent`.

- [ ] **Step 5: Executar GREEN e contratos de acessibilidade**

Run: `.venv/bin/python -m pytest tests/test_rag_chat_frontend.py tests/test_knowledge_ui_registry.py -q`

Expected: PASS sem `innerHTML`, com radios nomeados e sessões separadas.

- [ ] **Step 6: Commit**

```bash
git add templates/includes/rag_chat.html templates/app/resource_chat.html static/js/rag-chat.js static/css/app.css tests/test_rag_chat_frontend.py tests/test_knowledge_ui_registry.py
git commit -m "feat(ui): add functional and regulatory chat modes"
```

---

### Task 6: Criar a carga offline e validar o corpus regulatório

**Files:**
- Create: `knowledge/regulatory_corpus.py`
- Create: `knowledge/management/commands/build_regulatory_corpus.py`
- Create: `tests/test_regulatory_corpus.py`
- Modify: `knowledge/management/commands/ingest_rag_sources.py`
- Modify: `knowledge/management/commands/rebuild_knowledge_index.py`
- Modify: `docs/architecture/knowledge.md`

**Interfaces:**
- Produces: `build_regulatory_corpus(*, release_sha: str, cutoff: date) -> RegulatoryCorpusResult`.
- Produces: `build_regulatory_corpus --release-sha <sha> --cutoff 2026-09-02 --rebuild-index`.
- Consumes: `regulatory_entries()`, `ingest_source()` e `build_index_generation(mode='regulatory')`.

- [ ] **Step 1: Escrever testes falhos de atomicidade lógica e auditoria**

Criar testes que comprovem:

```python
result = build_regulatory_corpus(
    release_sha='a' * 40,
    cutoff=date(2026, 9, 2),
)
assert result.release_sha == 'a' * 40
assert result.cutoff == date(2026, 9, 2)
assert result.source_count >= 17
assert result.document_count == result.source_count
assert result.chunk_count > result.document_count
assert result.manifest_hash
assert KnowledgeSource.objects.filter(
    assistant_mode='regulatory', is_active=True
).count() == result.source_count
```

Simular falha em uma fonte e verificar que nenhuma geração regulatória é ativada e que a geração funcional permanece inalterada. Rodar duas vezes e verificar mesmas contagens e hashes, sem duplicação.

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_regulatory_corpus.py -q`

Expected: ERROR de importação porque `build_regulatory_corpus` não existe.

- [ ] **Step 3: Implementar resultado e construção determinística**

Criar:

```python
@dataclass(frozen=True, slots=True)
class RegulatoryCorpusResult:
    release_sha: str
    cutoff: date
    source_count: int
    document_count: int
    chunk_count: int
    manifest_hash: str
    generation_id: str | None
```

Validar SHA hexadecimal com 7–64 caracteres e exigir `cutoff == REGULATORY_CUTOFF`. Ingerir cada entrada a partir de `metadata.local_path`; rejeitar rede, documento vazio, hash divergente, item não corrente e item sem URL oficial. Construir todos os documentos antes de chamar o índice. O `generation_id` regulatório deve ser `regulatory-<release_sha[:12]>`.

- [ ] **Step 4: Criar comando dedicado**

O comando deve exigir `--release-sha`, aceitar somente `--cutoff 2026-09-02` e `--rebuild-index`. A saída deve conter release, corte, quantidade de fontes/documentos/chunks, hash e geração; nunca imprimir conteúdo dos snapshots ou payload do provedor.

Deprecar o uso de `ingest_rag_sources` para o catálogo oficial no deploy: manter o comando para atualização manual compatível, mas adicionar mensagem que encaminha produção ao novo comando. `rebuild_knowledge_index` passa a exigir `--mode`.

- [ ] **Step 5: Documentar modos, fontes e atualização**

Em `docs/architecture/knowledge.md`, registrar os dois modos, data de corte, hosts oficiais permitidos, diferença entre norma/orientação/referência, comando de refresh online, comando offline de build, aliases por modo e recusa segura.

- [ ] **Step 6: Executar GREEN e idempotência**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_regulatory_catalog.py tests/test_regulatory_corpus.py tests/test_regulatory_retrieval.py tests/test_regulatory_chat_service.py -q`

Expected: PASS; a segunda construção produz as mesmas contagens e hash.

- [ ] **Step 7: Commit**

```bash
git add knowledge/regulatory_corpus.py knowledge/management/commands/build_regulatory_corpus.py knowledge/management/commands/ingest_rag_sources.py knowledge/management/commands/rebuild_knowledge_index.py tests/test_regulatory_corpus.py docs/architecture/knowledge.md
git commit -m "feat(knowledge): build audited regulatory corpus"
```

---

### Task 7: Integrar os dois modos ao bootstrap, rollback e gate

**Files:**
- Modify: `governance/release_bootstrap.py`
- Modify: `governance/management/commands/bootstrap_production_release.py`
- Modify: `scripts/deploy-vps.sh`
- Modify: `docker-compose.vps.yml`
- Modify: `tests/test_production_release_bootstrap.py`
- Modify: `tests/test_vps_compose_contract.py`
- Modify: `tests/test_native_postgres_deployment.py`
- Modify: `tests/test_single_domain_deployment.py`
- Modify: `docs/deployment.md`
- Modify: `docs/validation/requirements-matrix.yml`

**Interfaces:**
- Consumes: `build_erp_release_corpus(...)` do plano funcional.
- Consumes: `build_regulatory_corpus(release_sha=..., cutoff=date(2026, 9, 2))`.
- Produces: relatório de bootstrap com `functional_generation_id` e `regulatory_generation_id`.

- [ ] **Step 1: Escrever testes falhos do bootstrap dual**

Estender o teste do bootstrap para exigir a ordem:

```python
assert phases == [
    'validate_manifests',
    'load_reference_catalogs',
    'build_functional_corpus',
    'build_regulatory_corpus',
    'validate_functional_retrieval',
    'validate_regulatory_retrieval',
    'publish_generations',
]
assert result.functional_generation_id
assert result.regulatory_generation_id
assert result.regulatory_cutoff == '2026-09-02'
```

Simular falha regulatória e verificar que nenhuma das novas gerações é publicada. No teste de deploy, exigir captura/restauração dos IDs ativos dos dois modos e impedir `cloudflared` antes das duas validações.

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_production_release_bootstrap.py tests/test_vps_compose_contract.py tests/test_native_postgres_deployment.py tests/test_single_domain_deployment.py -q`

Expected: FAIL porque o bootstrap conhece somente o corpus funcional e o script captura uma geração global.

- [ ] **Step 3: Integrar o corpus regulatório ao serviço one-shot**

Adicionar `regulatory_cutoff`, contagens, hash e geração ao resultado/auditoria. Construir ambos os corpora antes de ativar aliases. Se o modo local estiver habilitado, executar perguntas fixas por modo e exigir pelo menos uma citação de `system_manual` no funcional e uma fonte oficial `BR` no regulatório.

- [ ] **Step 4: Tornar rollback e prontidão conscientes dos modos**

No shell, armazenar somente IDs validados:

```bash
PREVIOUS_FUNCTIONAL_GENERATION_ID=""
PREVIOUS_REGULATORY_GENERATION_ID=""
```

Consultar por modo, restaurar cada alias independentemente e verificar que ambos possuem geração ativa ou prova local válida antes de iniciar `cloudflared`. Não imprimir chaves, textos dos chunks ou conteúdo do `.env`.

- [ ] **Step 5: Atualizar Compose, runbook e matriz**

O serviço `release_bootstrap` deve receber `REGULATORY_CUTOFF=2026-09-02`. Documentar comandos, saída segura, atualização futura do snapshot, rollback dos dois aliases e distinção entre o conteúdo de consulta e parecer técnico/jurídico.

- [ ] **Step 6: Executar GREEN e gate integrado**

Run: `bash -n scripts/deploy-vps.sh scripts/backup.sh scripts/backup_scheduler.sh`

Run: `TUNNEL_TOKEN=compose-contract-validation POSTGRES_DB=contract POSTGRES_USER=contract POSTGRES_PASSWORD=contract RABBITMQ_DEFAULT_USER=contract RABBITMQ_DEFAULT_PASS=contract DATA_ENCRYPTION_KEYS=contract VPS_ENV_FILE=.env.example docker compose --env-file .env.example -f docker-compose.vps.yml config --quiet`

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_production_release_bootstrap.py tests/test_vps_compose_contract.py tests/test_native_postgres_deployment.py tests/test_single_domain_deployment.py tests/test_regulatory_catalog.py tests/test_regulatory_corpus.py tests/test_regulatory_retrieval.py tests/test_regulatory_chat_service.py -q`

Run: `.venv/bin/python manage.py check`

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`

Run: `git diff --check`

Expected: todos os comandos terminam com exit 0 e nenhum warning de migration pendente.

- [ ] **Step 7: Commit**

```bash
git add governance/release_bootstrap.py governance/management/commands/bootstrap_production_release.py scripts/deploy-vps.sh docker-compose.vps.yml tests/test_production_release_bootstrap.py tests/test_vps_compose_contract.py tests/test_native_postgres_deployment.py tests/test_single_domain_deployment.py docs/deployment.md docs/validation/requirements-matrix.yml
git commit -m "feat(release): gate deployment on both knowledge modes"
```

---

### Task 8: Executar verificação final, push e deploy autorizado

**Files:**
- Verify: repository and VPS state only.

**Interfaces:**
- Consumes: todos os planos e commits anteriores.
- Produces: SHA publicado, backup validado, contagens de produção e evidência dos dois modos.

- [ ] **Step 1: Executar o gate local completo do projeto**

Run: `bash scripts/test.sh`

Run: `bash scripts/release_gate.sh`

Run: `.venv/bin/python -m ruff check .`

Run: `.venv/bin/python -m mypy .`

Run: `.venv/bin/python -m bandit -r . -c pyproject.toml`

Run: `.venv/bin/pip-audit --strict`

Run: `.venv/bin/python -m mkdocs build --strict`

Run: `git diff --check`

Expected: todos exit 0. Se um comando não estiver instalado, registrar como não executado e usar o gate oficial equivalente; não declarar essa ferramenta aprovada sem saída completa.

- [ ] **Step 2: Revisar escopo, segredos e árvore Git**

Run: `git status --short`

Run: `git diff origin/main...HEAD --stat`

Run: `git grep -nEi '(SECRET_KEY|OPENAI_API_KEY|TUNNEL_TOKEN|POSTGRES_PASSWORD)=' -- ':!*.example*' ':!tests/*' || true`

Expected: worktree limpo após commits, nenhuma credencial versionada e somente arquivos do escopo.

- [ ] **Step 3: Publicar sem force-push**

Run: `git fetch origin`

Run: `git push origin main`

Expected: `origin/main` avança por fast-forward para o SHA local.

- [ ] **Step 4: Verificar pré-condições do VPS sem revelar segredos**

Confirmar caminho `/home/deploy/rgnfamarsystemv2`, owner, branch `main`, worktree limpo, `.env` modo `0600`, nomes das variáveis obrigatórias presentes, containers e volumes. Confirmar que `rgnfarmasystem_postgres_data` pertence ao PostgreSQL 15 do próprio projeto e não é `scsi_pg_data`.

- [ ] **Step 5: Executar deploy com backup obrigatório**

No VPS, executar como operador autorizado a partir do checkout real:

```bash
PROJECT_DIR=/home/deploy/rgnfamarsystemv2 \
TARGET_REF=origin/main \
COMPOSE_PROJECT_NAME=rgnfarmasystem \
bash scripts/deploy-vps.sh
```

Expected: backup PostgreSQL/mídia não vazios e validados, fast-forward, runtime privado, migrations, bootstrap dual, túnel e checks finais.

- [ ] **Step 6: Coletar evidência agregada de produção**

Sem imprimir registros empresariais ou segredos, registrar:

- SHA do checkout e `origin/main`;
- status/health dos oito serviços persistentes;
- diretório e hashes do backup;
- migrations pendentes igual a zero;
- contagens por model dos catálogos gerenciados;
- contagens de fontes, documentos e chunks por modo;
- IDs, hashes e contagens das gerações ativas funcional e regulatória;
- `DEBUG=False`, HTTPS redirect, cookies seguros e HSTS positivo;
- origem, `/ready` do túnel e HTTPS público com HTTP 200;
- uma consulta representativa por modo com quantidade de citações e tipos de fonte, sem registrar a resposta integral.

- [ ] **Step 7: Confirmar idempotência em produção**

Executar novamente apenas o comando one-shot de bootstrap com o mesmo SHA e data de corte. Confirmar mesmas contagens/hashes, zero duplicações e mesmas gerações ou reutilização explícita segura. Não reiniciar o domínio se a validação one-shot não exigir publicação.
