# Chat RAG Global Somente Leitura Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incorporar ao projeto atual o chat RAG completo do projeto de origem, com widget global, tela dedicada, histórico, citações, Redis/PostgreSQL e modo local, sem qualquer capacidade de modificar dados do ERP.

**Architecture:** Criar um app Django `knowledge` com oito modelos somente leitura do ponto de vista conversacional. A API persistirá sessões e mensagens do próprio usuário, recuperará contexto elegível via Redis quando houver geração ativa e saudável, usará PostgreSQL como fallback e chamará a OpenAI apenas quando configurada; widget global e tela dedicada compartilharão o mesmo cliente JavaScript.

**Tech Stack:** Python 3.14, Django 6, Django REST Framework, PostgreSQL, Redis/RediSearch, OpenAI Responses API, Bootstrap 5, JavaScript, pytest-django.

## Global Constraints

- Projeto de destino: `/mnt/2c8d19a3-3bbb-4f90-b09f-9e17c780ce6a/Projects/rgnfarmasystem-main`.
- Projeto de origem: `/mnt/2c8d19a3-3bbb-4f90-b09f-9e17c780ce6a/Projects/rgnfarmasystem`.
- O assistente será estritamente somente leitura: nenhum arquivo de `knowledge/actions/`, model `Assistant*`, endpoint `actions/`, nonce, política ou executor será transportado.
- O contrato de autorização é `knowledge.view_ragchatsession` no template, na página dedicada e em `POST /api/knowledge/chat/`.
- Sessões e mensagens expostas pela API devem ficar limitadas ao usuário autenticado, inclusive quando o cliente informa `session_id`.
- Somente fontes ativas, `chat_eligible=True`, do tipo `system_manual`, com documento ingerido, podem fundamentar o chat.
- Redis só pode provocar geração de embedding quando existe geração ativa e a verificação de saúde foi bem-sucedida.
- A ausência de Redis, credencial OpenAI ou provedor externo não pode impedir a resposta local baseada no PostgreSQL.
- Nenhuma requisição web pode ingerir fontes ou reconstruir índices.
- Respostas e citações devem ser inseridas no DOM com `textContent`; conteúdo do modelo nunca pode ser passado a `innerHTML`.
- O projeto atual usa Django 6; a migration inicial deve ser gerada novamente no destino, não copiada da origem Django 5.2.
- Dependências necessárias (`httpx`, `beautifulsoup4`, `pypdf`, `numpy`, `redis`, `openai` e `PyYAML`) já existem em `requirements.txt`; não alterar versões durante esta funcionalidade.
- Usar `apply_patch` para todas as edições e preservar alterações não relacionadas no worktree.

---

## File Responsibility Map

### Domínio e persistência

- `knowledge/apps.py`: configuração do app.
- `knowledge/models.py`: os oito modelos RAG e utilitários determinísticos.
- `knowledge/migrations/0001_initial.py`: schema Django 6, sem tabelas de ações.
- `knowledge/admin.py`: operação administrativa das fontes, índice e registros imutáveis.

### Recuperação e provedor

- `knowledge/eligibility.py`: elegibilidade temporal/operacional do documento.
- `knowledge/openai_gateway.py`: única fronteira com a SDK OpenAI.
- `knowledge/redis_client.py`: conexão e health check do Redis de conhecimento.
- `knowledge/redis_index.py`: criação, publicação e consulta RediSearch.
- `knowledge/retrieval.py`: recuperação vetorial e revalidação dos hits no PostgreSQL.
- `knowledge/indexing.py`: construção atômica de gerações do índice.

### Ingestão e conversa

- `knowledge/services.py`: normalização, ingestão, fallback PostgreSQL, conversa e citações.
- `knowledge/manual_catalog.py`: corpus gerado a partir do catálogo real de módulos.
- `knowledge/step_by_step_manual.py`: instruções operacionais do ERP.
- `knowledge/source_catalog.py`: catálogo explícito de fontes externas não elegíveis ao chat por padrão.
- `knowledge/management/commands/*.py`: ingestão e manutenção explícitas.

### API e UI

- `knowledge/serializers.py`: contratos DRF somente leitura e requisição do chat.
- `knowledge/views.py`: viewsets de consulta e endpoint protegido.
- `knowledge/urls.py`: `/chat/` e rotas somente leitura; nunca registra `/actions/`.
- `templates/includes/rag_chat.html`: widget global acessível.
- `templates/base.html`: inclusão condicionada por permissão.
- `templates/app/resource_chat.html`: tela dedicada coerente com leitura documental.
- `static/js/rag-chat.js`: cliente compartilhado, sessão, retry, status e citações seguras.
- `static/css/app.css`: layout, estados e responsividade do widget.

### Integrações e documentação

- `core/settings/base.py`, `.env.example`: configuração do app e do runtime RAG.
- `core/urls.py`, `core/api_v1_urls.py`: publicação das APIs.
- `base/ui/views.py`, `base/ui/registry.py`: permissão da tela e módulo no menu.
- `docs/architecture/knowledge.md`, `README.md`: arquitetura e operação.

---

### Task 1: Criar o domínio RAG e a migration limpa

**Files:**
- Create: `knowledge/__init__.py`
- Create: `knowledge/apps.py`
- Create: `knowledge/models.py`
- Create: `knowledge/migrations/__init__.py`
- Create: `knowledge/migrations/0001_initial.py`
- Modify: `core/settings/base.py`
- Test: `tests/test_knowledge_models.py`

**Interfaces:**
- Produces: `content_hash(value: str) -> str`, `deterministic_embedding(value: str, dimensions: int = 64) -> list[float]`.
- Produces: `KnowledgeSource`, `KnowledgeDocument`, `KnowledgeChunk`, `KnowledgeIndexGeneration`, `RAGChatSession`, `RAGChatMessage`, `RAGCitation`, `KnowledgeIngestionLog`.
- Consumes: `base.models.SingleInstanceModel` e `settings.AUTH_USER_MODEL`.

- [ ] **Step 1: Escrever os testes falhando do domínio**

Crie `tests/test_knowledge_models.py` com factories locais e estes contratos:

```python
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User
from knowledge.models import (
    KnowledgeDocument,
    KnowledgeIndexGeneration,
    KnowledgeSource,
    RAGChatSession,
)


def create_user(username='rag.models'):
    return User.objects.create_user(username=username, email=f'{username}@example.com', password='test-pass')


def create_manual_source(code='ERP-MANUAL'):
    return KnowledgeSource.objects.create(
        code=code,
        title='Manual ERP',
        source_type=KnowledgeSource.SourceType.SYSTEM_MANUAL,
        publisher='RGN Farma System',
        is_official=True,
        is_active=True,
        chat_eligible=True,
    )


class KnowledgeModelTests(TestCase):
    def test_document_replaces_chunks_atomically(self):
        source = create_manual_source()
        document = KnowledgeDocument.objects.create(
            source=source,
            title='Fórmulas',
            document_type=KnowledgeDocument.DocumentType.TEXT,
            extracted_text='Cadastro de fórmula mestra.',
        )

        created = document.replace_chunks([
            {'content': 'Acesse Formulações e selecione Nova fórmula.', 'section_reference': 'Cadastro'},
            {'content': 'Salve a fórmula como rascunho.', 'section_reference': 'Estado'},
        ])

        assert len(created) == 2
        assert document.chunks.count() == 2
        assert document.status == KnowledgeDocument.Status.INGESTED
        assert all(chunk.source_id == source.pk for chunk in document.chunks.all())

    def test_only_ready_generation_can_be_activated(self):
        generation = KnowledgeIndexGeneration.objects.create(
            generation_id='g-1', redis_index_name='idx:rgn:knowledge:g-1'
        )
        with pytest.raises(ValidationError):
            generation.activate()

    def test_chat_session_belongs_to_creator(self):
        user = create_user()
        session = RAGChatSession.objects.create(title='Minha conversa', created_by=user)
        message = session.add_user_message('Como cadastrar um produto?')
        assert message.created_by == user
        assert message.session == session
        assert session.last_question_at is not None
```

- [ ] **Step 2: Executar o teste e confirmar a ausência do app**

Run: `.venv/bin/pytest tests/test_knowledge_models.py -q`

Expected: FAIL durante collection com `ModuleNotFoundError: No module named 'knowledge'`.

- [ ] **Step 3: Registrar o app e transportar somente os modelos permitidos**

Em `core/settings/base.py`, acrescente `'knowledge'` ao final de `LOCAL_APPS`.

Crie `knowledge/apps.py` exatamente com:

```python
from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge'
    verbose_name = 'Conhecimento RAG'
```

Use como base o trecho de `knowledge/models.py` da origem que começa nos imports e termina no fim de `KnowledgeIngestionLog`, imediatamente antes de `canonical_action_arguments_digest`. O arquivo de destino deve ter somente estes imports próprios:

```python
import hashlib
import math
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from base.models import SingleInstanceModel
```

Mantenha integralmente `_tokens`, `content_hash`, `deterministic_embedding` e os oito models listados em **Interfaces**. Remova `json`, `uuid`, `knowledge.actions.types`, `canonical_action_arguments_digest`, `_valid_sha256` e tudo que sucede essas funções na origem.

Verificação estrutural:

```bash
rg -n "Assistant|ActionRisk|ExecutionStatus|ProposalStatus|knowledge\.actions" knowledge/models.py
```

Expected: nenhuma saída.

- [ ] **Step 4: Gerar a migration sob Django 6**

Run: `.venv/bin/python manage.py makemigrations knowledge`

Expected: `knowledge/migrations/0001_initial.py` criando exatamente os oito models permitidos.

Run:

```bash
rg -n "CreateModel|Assistant|Action|RunSQL" knowledge/migrations/0001_initial.py
```

Expected: oito ocorrências de `CreateModel` e nenhuma ocorrência de `Assistant`, `Action` ou `RunSQL`.

- [ ] **Step 5: Validar models e migration**

Run: `.venv/bin/python manage.py check`

Expected: `System check identified no issues`.

Run: `.venv/bin/pytest tests/test_knowledge_models.py -q`

Expected: PASS.

- [ ] **Step 6: Commitar o domínio**

```bash
git add core/settings/base.py knowledge tests/test_knowledge_models.py
git commit -m "feat: add read-only RAG knowledge domain"
```

---

### Task 2: Incorporar OpenAI, Redis, recuperação e publicação atômica do índice

**Files:**
- Create: `knowledge/eligibility.py`
- Create: `knowledge/openai_gateway.py`
- Create: `knowledge/redis_client.py`
- Create: `knowledge/redis_index.py`
- Create: `knowledge/retrieval.py`
- Create: `knowledge/indexing.py`
- Modify: `core/settings/base.py`
- Modify: `.env.example`
- Test: `tests/test_knowledge_retrieval.py`

**Interfaces:**
- Produces: `OpenAIGateway.embed_texts(texts) -> EmbeddingBatch` e `OpenAIGateway.generate_text(*, instructions, input, model=None) -> TextGeneration`.
- Produces: `knowledge_redis_health() -> dict[str, object]`.
- Produces: `retrieve_context(question, *, filters=None, limit=8, as_of=None) -> list[RetrievedChunk]`.
- Produces: `build_index_generation(*, gateway=None, redis_index=None, generation_id=None) -> KnowledgeIndexGeneration`.
- Consumes: os models e utilitários criados na Task 1.

- [ ] **Step 1: Escrever testes falhando para o gateway e a recuperação vetorial**

Crie `tests/test_knowledge_retrieval.py` contendo:

```python
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import SimpleTestCase, TestCase, override_settings

from knowledge.openai_gateway import OpenAIGateway, OpenAIResponseError
from knowledge.retrieval import retrieve_context


class KnowledgeRetrievalTests(TestCase):
    def test_retrieval_returns_empty_without_active_generation(self):
        assert retrieve_context('Como informar lote?') == []


@override_settings(
    OPENAI_API_KEY='test-key',
    OPENAI_TIMEOUT_SECONDS=10,
    OPENAI_MODEL='test-model',
    OPENAI_EMBEDDING_MODEL='test-embedding',
    OPENAI_EMBEDDING_DIMENSIONS=3,
)
class KnowledgeProviderTests(SimpleTestCase):
    @patch('knowledge.openai_gateway.OpenAI')
    def test_gateway_rejects_response_without_text(self, openai):
        openai.return_value.responses.create.return_value = SimpleNamespace(
            output_text='', model='test-model', id='resp-1'
        )
        with pytest.raises(OpenAIResponseError):
            OpenAIGateway().generate_text(instructions='Use o manual.', input='Pergunta')
```

Acrescente ao mesmo arquivo os testes de ordenação dos embeddings e dimensão inválida de `KnowledgeProviderTests` da origem. Todos devem mockar `knowledge.openai_gateway.OpenAI` e não acessar a rede.

- [ ] **Step 2: Executar e observar os módulos ausentes**

Run: `.venv/bin/pytest tests/test_knowledge_retrieval.py -q`

Expected: FAIL por ausência das fronteiras Redis/OpenAI.

- [ ] **Step 3: Transportar as fronteiras independentes da origem**

Transcreva por `apply_patch`, sem alterações funcionais, estes arquivos da origem:

```text
knowledge/eligibility.py
knowledge/openai_gateway.py
knowledge/redis_client.py
knowledge/redis_index.py
knowledge/retrieval.py
knowledge/indexing.py
```

Não transporte `knowledge/actions/` nem imports que apontem para esse pacote. Os seis arquivos listados não devem possuir dependências de ações.

- [ ] **Step 4: Adicionar configuração explícita**

Após `OPENAI_MODEL` em `core/settings/base.py`, acrescente:

```python
OPENAI_TIMEOUT_SECONDS = env.int('OPENAI_TIMEOUT_SECONDS', default=120)
OPENAI_EMBEDDING_MODEL = env('OPENAI_EMBEDDING_MODEL', default='text-embedding-3-small')
OPENAI_EMBEDDING_DIMENSIONS = env.int('OPENAI_EMBEDDING_DIMENSIONS', default=1536)
KNOWLEDGE_REDIS_URL = env('KNOWLEDGE_REDIS_URL', default='redis://localhost:6379/0')
KNOWLEDGE_REDIS_PREFIX = env('KNOWLEDGE_REDIS_PREFIX', default='rgn:knowledge')
KNOWLEDGE_REDIS_MAX_CONNECTIONS = env.int('KNOWLEDGE_REDIS_MAX_CONNECTIONS', default=20)
RAG_CHAT_LOCAL_ONLY = env.bool('RAG_CHAT_LOCAL_ONLY', default=False)
```

Acrescente os mesmos nomes a `.env.example`, usando `redis://redis:6379/0` no ambiente Docker. Não adicione `OPENAI_TOOL_MODEL`, `KNOWLEDGE_ACTIONS_ENABLED` nem `KNOWLEDGE_ACTION_TTL_SECONDS`.

- [ ] **Step 5: Executar os testes unitários da infraestrutura**

Run: `.venv/bin/pytest tests/test_knowledge_retrieval.py -q`

Expected: PASS.

- [ ] **Step 6: Commitar infraestrutura de recuperação**

```bash
git add knowledge core/settings/base.py .env.example tests/test_knowledge_retrieval.py
git commit -m "feat: add RAG retrieval infrastructure"
```

---

### Task 3: Incorporar ingestão, corpus do manual e comandos operacionais

**Files:**
- Create: `knowledge/services.py`
- Create: `knowledge/manual_catalog.py`
- Create: `knowledge/step_by_step_manual.py`
- Create: `knowledge/source_catalog.py`
- Create: `knowledge/management/__init__.py`
- Create: `knowledge/management/commands/__init__.py`
- Create: `knowledge/management/commands/build_erp_manual_corpus.py`
- Create: `knowledge/management/commands/ingest_rag_sources.py`
- Create: `knowledge/management/commands/rebuild_knowledge_index.py`
- Create: `knowledge/management/commands/reconcile_knowledge_alias.py`
- Test: `tests/test_knowledge_ingestion.py`
- Test: `tests/test_knowledge_manual.py`

**Interfaces:**
- Produces: `normalize_text`, `chunk_text`, `source_from_entry`, `ingest_source`, `fetch_source_text`, `fetch_source_text_candidates`, `fetch_local_source_text`, `extract_pdf_text`, `extract_html_text`.
- Produces: `manual_entries() -> list[dict[str, object]]`.
- Consumes: models da Task 1 e indexação da Task 2.

- [ ] **Step 1: Transportar e ajustar os testes de ingestão/manual**

Use como base integral:

```text
/mnt/2c8d19a3-3bbb-4f90-b09f-9e17c780ce6a/Projects/rgnfarmasystem/tests/test_knowledge_ingestion.py
/mnt/2c8d19a3-3bbb-4f90-b09f-9e17c780ce6a/Projects/rgnfarmasystem/tests/test_knowledge_manual.py
```

No destino, remova do segundo arquivo somente imports/asserts de propostas de ação. Preserve estes contratos explícitos:

```python
def test_manual_catalog_covers_every_registered_module(self):
    entries = manual_entries()
    covered = {entry['metadata']['module_slug'] for entry in entries}
    assert covered == {module.slug for module in get_modules()}


def test_manual_source_is_the_only_chat_eligible_default(self):
    assert all(not entry.get('chat_eligible', False) for entry in SEED_SOURCES)
    assert all(entry['chat_eligible'] for entry in manual_entries())
```

- [ ] **Step 2: Executar os testes e confirmar falha por módulos ausentes**

Run: `.venv/bin/pytest tests/test_knowledge_ingestion.py tests/test_knowledge_manual.py -q`

Expected: FAIL durante import de `knowledge.manual_catalog` ou `knowledge.services`.

- [ ] **Step 3: Criar a parte de ingestão de `knowledge/services.py`**

Transcreva da origem os imports e as funções entre `normalize_text` e `extract_html_text`, inclusive. Mantenha o bloqueio de caminho em `fetch_local_source_text`: somente arquivos resolvidos dentro de `settings.BASE_DIR` e explicitamente declarados no catálogo podem ser lidos. Não inclua ainda as funções de conversa que começam em `retrieve_context`; elas entram na Task 4.

- [ ] **Step 4: Transportar o catálogo e comandos permitidos**

Transcreva por `apply_patch` estes arquivos da origem:

```text
knowledge/manual_catalog.py
knowledge/step_by_step_manual.py
knowledge/source_catalog.py
knowledge/management/commands/build_erp_manual_corpus.py
knowledge/management/commands/ingest_rag_sources.py
knowledge/management/commands/rebuild_knowledge_index.py
knowledge/management/commands/reconcile_knowledge_alias.py
```

Crie os três `__init__.py` vazios necessários. Não transporte:

```text
knowledge/management/commands/sync_assistant_action_policies.py
knowledge/data/assistant_action_overrides.yml
```

- [ ] **Step 5: Validar ingestão limitada e o corpus**

Run: `.venv/bin/pytest tests/test_knowledge_ingestion.py tests/test_knowledge_manual.py -q`

Expected: PASS.

Run: `.venv/bin/python manage.py build_erp_manual_corpus --module ai_agents`

Expected: saída `ai_agents: <N> chunks` com `N > 0` e `Manual ERP ingerido`.

- [ ] **Step 6: Commitar ingestão e corpus**

```bash
git add knowledge tests/test_knowledge_ingestion.py tests/test_knowledge_manual.py
git commit -m "feat: add explicit ERP manual ingestion"
```

---

### Task 4: Implementar conversa, fallback e citações sem mutações

**Files:**
- Modify: `knowledge/services.py`
- Modify: `tests/test_knowledge_retrieval.py`
- Create: `tests/test_knowledge_chat_service.py`

**Interfaces:**
- Produces: `retrieve_context(question: str, limit: int = 5) -> list[dict[str, object]]`.
- Produces: `answer_question(user, question: str, *, session_id: int | None = None, limit: int = 5) -> dict[str, object]`.
- Produces: `InvalidChatSession(ValueError)`.
- Consumes: `OpenAIGateway`, `knowledge_redis_health`, recuperação Redis e os models persistentes.

- [ ] **Step 1: Escrever testes falhando do serviço conversacional**

Crie `tests/test_knowledge_chat_service.py` com:

```python
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from knowledge.models import KnowledgeDocument, RAGChatMessage
from knowledge.services import InvalidChatSession, answer_question
from tests.test_knowledge_models import create_manual_source, create_user


class KnowledgeChatServiceTests(TestCase):
    def setUp(self):
        self.user = create_user('rag.owner')
        self.other = create_user('rag.other')
        source = create_manual_source()
        document = KnowledgeDocument.objects.create(
            source=source,
            title='Manual de produtos',
            document_type=KnowledgeDocument.DocumentType.TEXT,
            extracted_text='Cadastro de produto.',
        )
        document.replace_chunks([
            {'content': 'Acesse Cadastros, Produtos e selecione Adicionar.', 'section_reference': 'Produtos'}
        ])

    @override_settings(RAG_CHAT_LOCAL_ONLY=True)
    def test_local_answer_persists_history_and_public_citations(self):
        result = answer_question(self.user, 'Como cadastrar produto?')
        assert result.keys() == {'session_id', 'message_id', 'answer', 'citations'}
        assert result['citations'][0].keys() == {'title', 'section_reference', 'url', 'excerpt'}
        assert RAGChatMessage.objects.filter(session_id=result['session_id']).count() == 2

    @override_settings(RAG_CHAT_LOCAL_ONLY=True)
    def test_other_user_cannot_continue_session(self):
        first = answer_question(self.user, 'Como cadastrar produto?')
        with pytest.raises(InvalidChatSession):
            answer_question(self.other, 'Continue', session_id=first['session_id'])

    @patch('knowledge.services.invoke_openai', side_effect=RuntimeError('provider down'))
    def test_provider_failure_returns_local_answer_without_internal_error(self, _invoke):
        result = answer_question(self.user, 'Como cadastrar produto?')
        assert result['answer']
        assert 'provider down' not in result['answer']
        assert 'provider_payload' not in result
```

Amplie `tests/test_knowledge_retrieval.py` importando `KnowledgeDocument`,
`KnowledgeIndexGeneration` e `create_manual_source`, e acrescente:

```python
class KnowledgeServiceRetrievalTests(TestCase):
    def setUp(self):
        self.source = create_manual_source('ERP-STOCK-MANUAL')
        self.document = KnowledgeDocument.objects.create(
            source=self.source,
            title='Manual de estoque',
            document_type=KnowledgeDocument.DocumentType.TEXT,
            extracted_text='Entrada de estoque com lote.',
        )
        self.document.replace_chunks([
            {
                'content': 'Para dar entrada, informe produto, lote e quantidade.',
                'section_reference': 'Entrada',
            }
        ])

    @patch('knowledge.retrieval.OpenAIGateway')
    @patch('knowledge.services.knowledge_redis_health', return_value={'available': False})
    def test_unhealthy_redis_skips_embedding_and_uses_postgres(self, _health, gateway):
        KnowledgeIndexGeneration.objects.create(
            generation_id='g-active',
            redis_index_name='idx:rgn:knowledge:g-active',
            status=KnowledgeIndexGeneration.Status.ACTIVE,
        )
        from knowledge.services import retrieve_context

        context = retrieve_context('Como informar lote?', limit=5)

        assert context[0]['document_id'] == self.document.pk
        gateway.assert_not_called()
```

- [ ] **Step 2: Executar e confirmar as interfaces ausentes**

Run: `.venv/bin/pytest tests/test_knowledge_chat_service.py tests/test_knowledge_retrieval.py -q`

Expected: FAIL porque as funções conversacionais ainda não existem.

- [ ] **Step 3: Acrescentar a fachada Redis/PostgreSQL**

Acrescente a `knowledge/services.py` as funções da origem `_postgres_retrieve_context`, `_redis_retrieve_context`, `_redis_chunk_payload`, `_context_payload`, `_cosine_similarity` e esta fachada:

```python
def retrieve_context(question, limit=5):
    redis_context = _redis_retrieve_context(question, limit=limit)
    if redis_context is not None:
        return redis_context
    return _postgres_retrieve_context(question, limit=limit)
```

Importe `OpenAIGateway` e `knowledge_redis_health` no módulo para tornar o contrato de teste explícito. `_redis_retrieve_context` deve executar, nessa ordem: verificar geração ativa, verificar health, chamar recuperação vetorial. O PostgreSQL deve filtrar `INGESTED`, fonte ativa, elegível e `SYSTEM_MANUAL`, exigindo sobreposição lexical positiva antes de combinar o score vetorial determinístico.

- [ ] **Step 4: Acrescentar o serviço conversacional seguro**

Transcreva da origem `invoke_openai`, `build_system_prompt`, `build_prompt`, `_context_payload` e `_cosine_similarity`. Ajuste os demais contratos para:

```python
class InvalidChatSession(ValueError):
    pass


def _get_or_create_session(user, question, *, session_id=None):
    if session_id:
        session = RAGChatSession.objects.filter(
            created_by=user,
            pk=session_id,
            status=RAGChatSession.Status.OPEN,
        ).first()
        if session is None:
            raise InvalidChatSession('A conversa informada não existe ou não está disponível.')
        return session
    title = normalize_text(question)[:120] or 'Pergunta RAG'
    return RAGChatSession.objects.create(created_by=user, title=title)
```

`answer_question` deve executar dentro de `transaction.atomic`, persistir pergunta e resposta, fazer fallback local sem expor `str(error)` e retornar somente:

```python
return {
    'session_id': session.id,
    'message_id': assistant_message.id,
    'answer': answer,
    'citations': citations,
}
```

`create_citations` deve persistir todos os vínculos e expor a forma pública:

```python
{
    'title': citation.title,
    'section_reference': citation.section_reference,
    'url': citation.source_url,
    'excerpt': citation.excerpt,
}
```

Quando não houver contexto, `local_answer` deve informar que não há instrução validada no manual do ERP e orientar o usuário a refinar a pergunta ou procurar o responsável do processo. Não solicitar norma regulatória externa e não afirmar que executou ações.

- [ ] **Step 5: Validar fallback, isolamento e citações**

Run: `.venv/bin/pytest tests/test_knowledge_chat_service.py tests/test_knowledge_retrieval.py -q`

Expected: PASS.

- [ ] **Step 6: Commitar o serviço de conversa**

```bash
git add knowledge/services.py tests/test_knowledge_chat_service.py tests/test_knowledge_retrieval.py
git commit -m "feat: add read-only RAG conversation service"
```

---

### Task 5: Publicar a API protegida e isolada por usuário

**Files:**
- Create: `knowledge/serializers.py`
- Create: `knowledge/views.py`
- Create: `knowledge/urls.py`
- Modify: `core/urls.py`
- Modify: `core/api_v1_urls.py`
- Test: `tests/test_knowledge_api.py`

**Interfaces:**
- Consumes: `answer_question` e `InvalidChatSession` da Task 4.
- Produces: `POST /api/knowledge/chat/` e alias versionado `/api/v1/knowledge/chat/`.
- Produces: viewsets GET de `sources`, `documents`, `chunks`, `sessions`, `messages`, `ingestion-logs`.

- [ ] **Step 1: Escrever testes falhando de permissão e isolamento**

Crie `tests/test_knowledge_api.py` contendo:

```python
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from knowledge.models import RAGChatSession
from tests.test_knowledge_models import create_user


def grant_chat_permission(user):
    user.user_permissions.add(Permission.objects.get(codename='view_ragchatsession'))


class KnowledgeApiTests(TestCase):
    @override_settings(RAG_CHAT_LOCAL_ONLY=True)
    def test_chat_requires_explicit_permission(self):
        denied = create_user('rag.denied')
        allowed = create_user('rag.allowed')
        grant_chat_permission(allowed)
        client = APIClient()
        anonymous = client.post('/api/knowledge/chat/', {'question': 'Como usar o sistema?'}, format='json')
        client.force_authenticate(denied)
        forbidden = client.post('/api/knowledge/chat/', {'question': 'Como usar o sistema?'}, format='json')
        client.force_authenticate(allowed)
        success = client.post('/api/knowledge/chat/', {'question': 'Como usar o sistema?'}, format='json')
        assert anonymous.status_code in {401, 403}
        assert forbidden.status_code == 403
        assert success.status_code == 200

    @override_settings(RAG_CHAT_LOCAL_ONLY=True)
    def test_session_id_from_another_user_is_rejected(self):
        owner = create_user('rag.api.owner')
        attacker = create_user('rag.api.other')
        grant_chat_permission(attacker)
        session = RAGChatSession.objects.create(title='Privada', created_by=owner)
        client = APIClient()
        client.force_authenticate(attacker)
        response = client.post(
            '/api/knowledge/chat/',
            {'question': 'Continue', 'session_id': session.pk},
            format='json',
        )
        assert response.status_code == 400
        assert response.json() == {'session_id': ['A conversa informada não existe ou não está disponível.']}

    def test_actions_route_does_not_exist(self):
        user = create_user('rag.no.actions')
        client = APIClient()
        client.force_authenticate(user)
        assert client.get('/api/knowledge/actions/').status_code == 404
```

- [ ] **Step 2: Executar e confirmar 404 nas rotas**

Run: `.venv/bin/pytest tests/test_knowledge_api.py -q`

Expected: FAIL porque `/api/knowledge/` ainda não está registrada.

- [ ] **Step 3: Criar serializers sem tipos de ação**

Transcreva da origem `KnowledgeSourceSerializer`, `KnowledgeDocumentSerializer`, `KnowledgeChunkSerializer`, `RAGCitationSerializer`, `RAGChatMessageSerializer`, `RAGChatSessionSerializer` e `KnowledgeIngestionLogSerializer`. Crie a requisição exatamente assim:

```python
class RAGChatRequestSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=4000, trim_whitespace=True)
    session_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate_question(self, value):
        question = ' '.join(value.split())
        if not question:
            raise serializers.ValidationError('Informe uma pergunta.')
        return question
```

O arquivo não deve importar ou declarar nenhum serializer `Assistant*`.

- [ ] **Step 4: Criar views somente leitura e filtrar conversas**

Transcreva da origem `SingleInstanceKnowledgeReadOnlyViewSet`, os viewsets de fonte/documento/chunk/log e `CanUseRAGChat`. Para sessões e mensagens, use:

```python
class RAGChatSessionViewSet(SingleInstanceKnowledgeReadOnlyViewSet):
    serializer_class = RAGChatSessionSerializer
    filterset_fields = ('status',)
    search_fields = ('title',)
    ordering = ('-updated_at',)

    def get_queryset(self):
        return RAGChatSession.objects.filter(created_by=self.request.user)


class RAGChatMessageViewSet(SingleInstanceKnowledgeReadOnlyViewSet):
    serializer_class = RAGChatMessageSerializer
    filterset_fields = ('session', 'role', 'status')
    search_fields = ('content', 'model_name')
    ordering = ('-created_at',)

    def get_queryset(self):
        return RAGChatMessage.objects.filter(
            session__created_by=self.request.user
        ).select_related('session', 'created_by').prefetch_related('citations')
```

Importe `serializers` junto aos módulos do DRF (`from rest_framework import
filters, serializers, status, viewsets`). Em `RAGChatAPIView.post`, capture
`InvalidChatSession` e levante
`serializers.ValidationError({'session_id': [str(error)]})`. Não inclua imports,
mixins, decorators ou classes de ação.

- [ ] **Step 5: Registrar somente rotas permitidas**

Em `knowledge/urls.py`, registre os seis viewsets e:

```python
urlpatterns = [
    path('chat/', RAGChatAPIView.as_view(), name='chat'),
] + router.urls
```

Adicione a `core/urls.py`:

```python
path('api/knowledge/', include('knowledge.urls')),
```

Adicione a `core/api_v1_urls.py`:

```python
path('knowledge/', include('knowledge.urls', namespace='v1_knowledge')),
```

- [ ] **Step 6: Validar API e schema**

Run: `.venv/bin/pytest tests/test_knowledge_api.py -q`

Expected: PASS.

Run: `.venv/bin/python manage.py spectacular --file /tmp/rgn-knowledge-schema.yml --validate`

Expected: schema válido e nenhuma rota contendo `/knowledge/actions/`.

- [ ] **Step 7: Commitar a API**

```bash
git add knowledge/serializers.py knowledge/views.py knowledge/urls.py core/urls.py core/api_v1_urls.py tests/test_knowledge_api.py
git commit -m "feat: expose permissioned read-only RAG API"
```

---

### Task 6: Integrar administração, menu e permissões da página dedicada

**Files:**
- Create: `knowledge/admin.py`
- Modify: `base/ui/registry.py`
- Modify: `base/ui/views.py`
- Test: `tests/test_knowledge_ui_registry.py`
- Modify: `tests/test_additional_resource_views.py`

**Interfaces:**
- Produces: módulo `knowledge` no catálogo de UI.
- Produces: `ResourceChatView` protegido por `knowledge.view_ragchatsession`.
- Consumes: os oito models e a permissão criada pela migration.

- [ ] **Step 1: Escrever testes falhando de catálogo e página dedicada**

Crie `tests/test_knowledge_ui_registry.py`:

```python
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from ai_agents.models import AIAgentProfile
from base.ui.registry import get_module
from tests.test_knowledge_models import create_user


class KnowledgeUiRegistryTests(TestCase):
    def test_registry_exposes_only_read_only_conversation_resources(self):
        module = get_module('knowledge')
        assert {resource.slug for resource in module.resources} == {
            'sources', 'documents', 'chunks', 'sessions', 'messages', 'ingestion-logs'
        }
        assert all(resource.read_only for resource in module.resources)

    def test_agent_chat_requires_rag_permission(self):
        user = create_user('rag.page')
        profile = AIAgentProfile.objects.create(
            code='AI-RAG-PAGE',
            name='Assistente do manual',
            agent_type=AIAgentProfile.AgentType.SUMMARY,
            source_module=AIAgentProfile.SourceModule.DOCUMENTS,
            provider=AIAgentProfile.Provider.OPENAI,
            model_name='gpt-5.5-mini',
            system_prompt='Use apenas o manual.',
            allowed_source_modules=[AIAgentProfile.SourceModule.DOCUMENTS],
            created_by=user,
        )
        self.client.force_login(user)
        url = reverse('app:resource_chat', kwargs={
            'module_slug': 'ai_agents', 'resource_slug': 'profiles', 'pk': profile.pk
        })
        assert self.client.get(url).status_code == 403
        user.user_permissions.add(Permission.objects.get(codename='view_ragchatsession'))
        assert self.client.get(url).status_code == 200
```

- [ ] **Step 2: Executar e confirmar ausência do módulo/proteção**

Run: `.venv/bin/pytest tests/test_knowledge_ui_registry.py -q`

Expected: FAIL porque `knowledge` não está no registry e a página ainda aceita usuário sem permissão.

- [ ] **Step 3: Criar o admin sem ações mutáveis**

Use `knowledge/admin.py` da origem como base, mantendo apenas admins para os oito models. `KnowledgeChunk`, `RAGChatSession`, `RAGChatMessage`, `RAGCitation` e `KnowledgeIngestionLog` devem continuar usando `ImmutableAuditAdminMixin`. Remova todos os imports e registros `Assistant*`.

- [ ] **Step 4: Registrar o módulo somente leitura**

Em `base/ui/registry.py`, importe `KnowledgeChunk`, `KnowledgeDocument`,
`KnowledgeIngestionLog`, `KnowledgeSource`, `RAGChatMessage` e
`RAGChatSession`, e acrescente este bloco antes de governança:

```python
ModuleConfig(
    'knowledge',
    'Conhecimento RAG',
    'Manual do ERP, documentos, chunks e conversas do assistente.',
    'feather-message-square',
    (
        ResourceConfig(
            'sources',
            'Fontes RAG',
            KnowledgeSource,
            ('code', 'title', 'source_type', 'publisher', 'is_official', 'is_active'),
            ('code', 'title', 'publisher', 'url', 'jurisdiction'),
            read_only=True,
        ),
        ResourceConfig(
            'documents',
            'Documentos RAG',
            KnowledgeDocument,
            ('title', 'source', 'document_type', 'status', 'retrieved_at'),
            ('title', 'source__code', 'source__title', 'source_url', 'extracted_text'),
            read_only=True,
        ),
        ResourceConfig(
            'chunks',
            'Chunks RAG',
            KnowledgeChunk,
            ('document', 'chunk_index', 'section_reference', 'page_number', 'token_count'),
            ('title', 'section_reference', 'content', 'document__title', 'source__title'),
            read_only=True,
        ),
        ResourceConfig(
            'sessions',
            'Conversas RAG',
            RAGChatSession,
            ('title', 'created_by', 'status', 'last_question_at'),
            ('title', 'created_by__email'),
            read_only=True,
        ),
        ResourceConfig(
            'messages',
            'Mensagens RAG',
            RAGChatMessage,
            ('session', 'role', 'status', 'model_name', 'latency_ms', 'created_by'),
            ('content', 'model_name', 'error_message', 'created_by__email'),
            read_only=True,
        ),
        ResourceConfig(
            'ingestion-logs',
            'Logs de ingestão RAG',
            KnowledgeIngestionLog,
            ('source', 'document', 'status', 'chunks_created', 'started_at', 'completed_at'),
            ('source__code', 'source__title', 'error_message'),
            read_only=True,
        ),
    ),
)
```

Ingestão e alteração de corpus ocorrerão por admin/comandos controlados, não
pelo catálogo operacional genérico.

- [ ] **Step 5: Proteger a página dedicada no servidor**

Adicione `PermissionDenied` aos imports de `django.core.exceptions` e `Http404`
aos imports de `django.http` em `base/ui/views.py`, removendo o import local de
`Http404` apenas deste método. Altere `ResourceChatView.dispatch` para:

```python
def dispatch(self, request, *args, **kwargs):
    resource = self.get_resource()
    if not getattr(resource, 'has_chat_view', False):
        raise Http404('Resource does not support chat view')
    if not request.user.has_perm('knowledge.view_ragchatsession'):
        raise PermissionDenied
    return super().dispatch(request, *args, **kwargs)
```

- [ ] **Step 6: Atualizar testes legados da página**

Em `tests/test_additional_resource_views.py::test_chat_view_resolves_and_renders_properly`, conceda `view_ragchatsession` antes do GET. Preserve o teste de recurso sem `has_chat_view` retornando 404.

- [ ] **Step 7: Validar e commit**

Run: `.venv/bin/pytest tests/test_knowledge_ui_registry.py tests/test_additional_resource_views.py -q`

Expected: PASS.

```bash
git add knowledge/admin.py base/ui/registry.py base/ui/views.py tests/test_knowledge_ui_registry.py tests/test_additional_resource_views.py
git commit -m "feat: register governed RAG user interface"
```

---

### Task 7: Restaurar o widget global e unificar o cliente do chat

**Files:**
- Create: `templates/includes/rag_chat.html`
- Modify: `templates/base.html`
- Modify: `templates/app/resource_chat.html`
- Modify: `static/js/rag-chat.js`
- Modify: `static/css/app.css`
- Modify: `tests/test_app_ui.py`
- Create: `tests/test_rag_chat_frontend.py`

**Interfaces:**
- Consumes: `POST /api/knowledge/chat/` com `{question, session_id}`.
- Produces: widget global condicionado à permissão e cliente reutilizável por qualquer raiz `[data-rag-chat-endpoint]`.
- Produces: chave de sessão `rgn-farma-assistant-session-id` em `sessionStorage`.

- [ ] **Step 1: Inverter e ampliar os testes de layout**

Em `tests/test_app_ui.py`, substitua os testes que exigem ausência global por:

```python
def test_authenticated_layout_hides_global_rag_chat_without_permission(self):
    self.client.force_login(self.user)
    content = self.client.get('/app/').content.decode()
    assert 'id="rag-chat-root"' not in content
    assert 'rag-chat.js' not in content


def test_authenticated_layout_loads_global_rag_chat_with_permission(self):
    self.user.user_permissions.add(
        Permission.objects.get(codename='view_ragchatsession')
    )
    self.client.force_login(self.user)
    content = self.client.get('/app/').content.decode()
    assert 'id="rag-chat-root"' in content
    assert 'data-rag-chat-endpoint="/api/knowledge/chat/"' in content
    assert 'rag-chat.js' in content
```

Crie `tests/test_rag_chat_frontend.py` com verificações estáticas de segurança:

```python
from pathlib import Path


def test_chat_client_uses_safe_text_rendering_and_persistent_session():
    script = Path('static/js/rag-chat.js').read_text(encoding='utf-8')
    assert 'textContent = text' in script
    assert 'body.innerHTML' not in script
    assert 'sessionStorage.getItem' in script
    assert 'sessionStorage.setItem' in script
    assert 'data-rag-chat-retry' in script


def test_dedicated_chat_does_not_advertise_mutating_tools():
    template = Path('templates/app/resource_chat.html').read_text(encoding='utf-8')
    for forbidden in ('SQL Seguro ERP', 'Gerar Relatório CAPA', 'Propor Ishikawa', 'ações diretas'):
        assert forbidden not in template
```

- [ ] **Step 2: Executar e confirmar falha da restauração**

Run: `.venv/bin/pytest tests/test_app_ui.py tests/test_rag_chat_frontend.py -q`

Expected: FAIL porque o layout ainda omite o widget e a tela anuncia ferramentas inexistentes.

- [ ] **Step 3: Criar o widget acessível**

Crie `templates/includes/rag_chat.html` com uma única raiz. O endpoint deve
existir somente na raiz, nunca também no formulário:

```django
<section
    id="rag-chat-root"
    class="rag-chat"
    data-rag-chat-endpoint="/api/knowledge/chat/"
    aria-label="Assistente do manual RGN Farma System"
>
    <button
        type="button"
        class="rag-chat__toggle"
        aria-controls="rag-chat-panel"
        aria-expanded="false"
        aria-label="Abrir assistente do manual"
    >
        <i class="feather-message-circle" aria-hidden="true"></i>
    </button>
    <div id="rag-chat-panel" class="rag-chat__panel" aria-hidden="true" hidden>
        <header class="rag-chat__header">
            <div>
                <strong>Assistente RGN Farma System</strong>
                <span>Consulta ao manual do ERP — somente leitura</span>
            </div>
            <button type="button" class="rag-chat__close" aria-label="Fechar assistente">×</button>
        </header>
        <div class="rag-chat__messages" role="log" aria-live="polite" aria-relevant="additions"></div>
        <div class="rag-chat__composer">
            <p class="rag-chat__status" role="status" aria-live="polite" data-rag-chat-status></p>
            <button type="button" class="btn btn-light btn-sm" data-rag-chat-retry hidden>
                Tentar novamente
            </button>
            <form class="rag-chat__form no-loader">
                <label class="sr-only" for="rag-chat-question">Mensagem para o assistente</label>
                <textarea
                    id="rag-chat-question"
                    name="question"
                    class="form-control"
                    rows="3"
                    maxlength="4000"
                    placeholder="Ex.: Como cadastro uma fórmula mestra?"
                    required
                ></textarea>
                <div class="d-flex gap-2">
                    <button type="button" class="btn btn-light btn-sm" data-rag-chat-new>
                        Nova conversa
                    </button>
                    <button type="submit" class="btn btn-primary flex-fill">Enviar</button>
                </div>
            </form>
        </div>
    </div>
</section>
```

Essa estrutura reutiliza o painel já estilizado no destino e evita acoplamento
do cliente ao offcanvas do Bootstrap. Ícones em botões continuam permitidos;
o textarea não recebe ícone decorativo.

- [ ] **Step 4: Incluir widget/script por permissão e permitir supressão**

Antes dos scripts em `templates/base.html`, acrescente:

```django
{% block global_rag_chat %}
    {% if request.user.is_authenticated and perms.knowledge.view_ragchatsession %}
        {% include 'includes/rag_chat.html' %}
    {% endif %}
{% endblock %}
```

Carregue `rag-chat.js` somente na mesma condição. Em `templates/app/resource_chat.html`, acrescente um bloco vazio:

```django
{% block global_rag_chat %}{% endblock %}
```

Assim a página dedicada mantém uma única instância.

- [ ] **Step 5: Reescrever o cliente compartilhado com renderização segura**

Parta do `static/js/rag-chat.js` atual, que já usa `textContent`, e incorpore da origem: `SESSION_KEY`, leitura/gravação/limpeza em `sessionStorage`, mensagens de erro por status, estado de loading, status acessível, feedback de processamento, nova conversa e retry.

O renderer de citações deve usar o contrato aprovado:

```javascript
citations.forEach(function (citation) {
    var source = document.createElement('li');
    var label = citation.title || 'Fonte';
    if (citation.url) {
        var link = document.createElement('a');
        link.href = citation.url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = label;
        source.appendChild(link);
    } else {
        source.appendChild(document.createTextNode(label));
    }
    if (citation.section_reference) {
        source.appendChild(document.createTextNode(' · ' + citation.section_reference));
    }
    list.appendChild(source);
});
```

Nunca use `innerHTML` para texto da pergunta, resposta, erro, título ou seção.

- [ ] **Step 6: Alinhar a tela dedicada e estilos**

Em `templates/app/resource_chat.html`:

- mantenha nome do perfil e metadados do agente;
- altere o estado para “Assistente de consulta — somente leitura”;
- descreva revisão humana como necessária para validar orientações, não para confirmar ações;
- mantenha somente os badges “Busca no Manual ERP”, “Histórico” e “Citações”;
- remova botão de anexo, pois a API não aceita upload;
- use textarea de 4.000 caracteres, botão Nova conversa, status e retry com os mesmos data attributes do widget.

Em `static/css/app.css`, preserve o seletor `.rag-chat__panel[hidden] { display: none !important; }`, acrescente estilos de spinner/status/processamento e confirme `white-space: pre-wrap` na bolha.

- [ ] **Step 7: Validar interface e não regressão do command palette**

Run: `.venv/bin/pytest tests/test_app_ui.py tests/test_rag_chat_frontend.py tests/test_additional_resource_views.py tests/test_responsive_layout_css.py -q`

Expected: PASS.

Run:

```bash
rg -n "SQL Seguro ERP|Gerar Relatório CAPA|Propor Ishikawa|body\.innerHTML" templates static/js/rag-chat.js
```

Expected: nenhuma saída relacionada ao chat.

- [ ] **Step 8: Commitar a experiência global**

```bash
git add templates static/js/rag-chat.js static/css/app.css tests/test_app_ui.py tests/test_rag_chat_frontend.py
git commit -m "feat: restore global read-only RAG chat"
```

---

### Task 8: Documentar operação, segurança e rollout

**Files:**
- Create: `docs/architecture/knowledge.md`
- Modify: `README.md`
- Modify: `docs/pdf/especificacao_tecnica.md`
- Modify: `docs/pdf/especificacao_funcional.md`
- Modify: `docs/pdf/manual_usuario.md`
- Test: `tests/test_knowledge_documentation.py`

**Interfaces:**
- Consumes: comandos, settings, permissão e contrato HTTP das Tasks anteriores.
- Produces: procedimento operacional reproduzível para corpus, Redis, fallback e concessão de acesso.

- [ ] **Step 1: Escrever teste de documentação falhando**

Crie `tests/test_knowledge_documentation.py`:

```python
from pathlib import Path


def test_knowledge_runbook_documents_required_controls():
    content = Path('docs/architecture/knowledge.md').read_text(encoding='utf-8')
    for required in (
        'knowledge.view_ragchatsession',
        'build_erp_manual_corpus',
        'rebuild_knowledge_index',
        'reconcile_knowledge_alias',
        'RAG_CHAT_LOCAL_ONLY',
        'fallback PostgreSQL',
        'somente leitura',
    ):
        assert required in content
    assert 'sync_assistant_action_policies' not in content
```

- [ ] **Step 2: Executar e confirmar ausência do runbook**

Run: `.venv/bin/pytest tests/test_knowledge_documentation.py -q`

Expected: FAIL com `FileNotFoundError`.

- [ ] **Step 3: Criar a arquitetura e o runbook**

Use o documento `docs/architecture/knowledge.md` da origem como referência, mas descreva somente o desenho aprovado. Inclua estes comandos exatos:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py build_erp_manual_corpus
.venv/bin/python manage.py rebuild_knowledge_index
.venv/bin/python manage.py reconcile_knowledge_alias
```

Documente que a primeira validação deve ocorrer com `RAG_CHAT_LOCAL_ONLY=True`, depois com Redis desligado, e somente então com Redis/OpenAI habilitados. Explique que remover a permissão dos grupos oculta o widget e bloqueia a API sem apagar histórico.

- [ ] **Step 4: Corrigir documentação funcional existente**

Atualize README e os três documentos em `docs/pdf/` para:

- retirar afirmações de que `/api/knowledge/chat/` usa apenas autenticação;
- registrar a permissão funcional obrigatória;
- declarar isolamento por usuário e modo somente leitura;
- remover qualquer promessa de SQL, CAPA, Ishikawa ou mutação por chat;
- documentar citações e fallback operacional.

- [ ] **Step 5: Validar e commit**

Run: `.venv/bin/pytest tests/test_knowledge_documentation.py -q`

Expected: PASS.

```bash
git add docs README.md tests/test_knowledge_documentation.py
git commit -m "docs: add read-only RAG operations runbook"
```

---

### Task 9: Executar verificação integral e smoke test local

**Files:**
- Modify only if verification exposes a defect: files already listed in Tasks 1–8.
- Test: all knowledge/UI regression tests and complete suite.

**Interfaces:**
- Consumes: funcionalidade completa.
- Produces: evidência de migrations, segurança, regressão e execução local.

- [ ] **Step 1: Verificar exclusão física de mutações**

Run:

```bash
test ! -d knowledge/actions
! rg -n "AssistantAction|AssistantTool|KnowledgeToolCall|knowledge\.actions|KNOWLEDGE_ACTIONS|OPENAI_TOOL_MODEL" knowledge core templates static/js/rag-chat.js
```

Expected: exit code 0 e nenhuma ocorrência.

- [ ] **Step 2: Verificar migration e configuração Django**

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`

Expected: `No changes detected`.

Run: `.venv/bin/python manage.py migrate --plan`

Expected: plano válido contendo no máximo `knowledge.0001_initial` ainda não aplicada.

Run: `.venv/bin/python manage.py check --deploy`

Expected: nenhuma falha; warnings de segurança já conhecidos do perfil local devem ser registrados sem mascarar novos warnings.

- [ ] **Step 3: Executar a suíte focal**

Run:

```bash
.venv/bin/pytest \
  tests/test_knowledge_models.py \
  tests/test_knowledge_retrieval.py \
  tests/test_knowledge_ingestion.py \
  tests/test_knowledge_manual.py \
  tests/test_knowledge_chat_service.py \
  tests/test_knowledge_api.py \
  tests/test_knowledge_ui_registry.py \
  tests/test_rag_chat_frontend.py \
  tests/test_knowledge_documentation.py \
  tests/test_app_ui.py \
  tests/test_additional_resource_views.py \
  tests/test_responsive_layout_css.py -q
```

Expected: PASS.

- [ ] **Step 4: Executar a suíte completa**

Run: `.venv/bin/pytest -q`

Expected: PASS sem regressões.

- [ ] **Step 5: Aplicar migration e preparar corpus local**

Run:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py build_erp_manual_corpus --module ai_agents
```

Expected: migration aplicada e corpus `ai_agents` com ao menos um chunk.

- [ ] **Step 6: Conceder acesso ao superusuário já existente e executar smoke test**

O superusuário `master` já possui todas as permissões pelo comportamento padrão do Django. Inicie/reinicie o servidor na porta acordada do ambiente e valide:

1. login como `master`;
2. widget visível em `/app/`;
3. primeira pergunta cria sessão;
4. segunda pergunta reutiliza a sessão;
5. citação é exibida quando o corpus possui resultado;
6. `/app/ai_agents/profiles/<pk>/chat/` não duplica o widget;
7. Redis indisponível mantém resposta local/PostgreSQL;
8. `/api/knowledge/actions/` retorna 404.

- [ ] **Step 7: Revisar worktree e commit corretivo, se necessário**

Run: `git status --short && git diff --check`

Expected: worktree limpo. Se a verificação exigiu correção, execute novamente o teste que a revelou e faça um commit focal com a mensagem correspondente ao defeito antes de declarar conclusão.
