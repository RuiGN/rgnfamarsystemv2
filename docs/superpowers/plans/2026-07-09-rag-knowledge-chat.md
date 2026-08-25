# RAG Knowledge Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-oriented RAG knowledge base and floating chat assistant for the pharmaceutical ERP.

**Architecture:** Create a focused `knowledge` Django app for corpus storage, ingestion, retrieval, chat orchestration and audit. Use tenant-scoped DRF endpoints, deterministic local retrieval vectors for portability, OpenCode as the configured LLM provider, and a safe local fallback when the provider is unavailable.

**Tech Stack:** Django 6, Django REST Framework, PostgreSQL-compatible models, Celery-ready ingestion command, `httpx`, `beautifulsoup4`, `pypdf`, Bootstrap-compatible HTML/CSS/JS.

## Global Constraints

- Do not store API keys in source code or committed env files.
- Use `OPENCODE_API_KEY`, `OPENCODE_BASE_URL`, `OPENCODE_MODEL` and `OPENCODE_TIMEOUT_SECONDS`.
- Keep all RAG records tenant scoped unless the record is a global public source mirrored into the current tenant during ingestion.
- Store commercial protected books as metadata only unless content usage is explicitly authorized.
- Include Farmacopeia Brasileira 8a edicao in the seed corpus.
- Preserve existing local user changes in shared files.

---

### Task 1: Dependencies And Settings

**Files:**
- Modify: `requirements.txt`
- Modify: `core/settings.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `settings.OPENCODE_API_KEY`, `settings.OPENCODE_BASE_URL`, `settings.OPENCODE_MODEL`, `settings.OPENCODE_TIMEOUT_SECONDS`.

- [ ] Add `httpx`, `beautifulsoup4` and `pgvector` to requirements.
- [ ] Add `knowledge` to `LOCAL_APPS`.
- [ ] Add OpenCode settings loaded from environment.
- [ ] Install dependencies in `.venv`.

### Task 2: Knowledge Models

**Files:**
- Create: `knowledge/apps.py`
- Create: `knowledge/models.py`
- Create: `knowledge/admin.py`
- Create: `knowledge/migrations/0001_initial.py`
- Test: `tests/test_knowledge.py`

**Interfaces:**
- Produces: `KnowledgeSource`, `KnowledgeDocument`, `KnowledgeChunk`, `RAGChatSession`, `RAGChatMessage`, `RAGCitation`, `KnowledgeIngestionLog`.
- Produces methods: `KnowledgeDocument.replace_chunks(chunks)`, `KnowledgeChunk.match_score(query)`, `RAGChatSession.add_user_message(text)`.

- [ ] Write failing model tests for tenant isolation, chunk replacement and source metadata.
- [ ] Implement models with indexes and validation.
- [ ] Run `makemigrations knowledge`.
- [ ] Run model tests until green.

### Task 3: Ingestion And Retrieval Services

**Files:**
- Create: `knowledge/services.py`
- Create: `knowledge/source_catalog.py`
- Create: `knowledge/management/commands/ingest_rag_sources.py`
- Test: `tests/test_knowledge.py`

**Interfaces:**
- Produces: `ingest_source_for_tenant(source, tenant, max_chunks=None)`, `retrieve_context(tenant, question, limit=5)`, `answer_question(tenant, user, question)`.

- [ ] Write failing tests for chunking, deterministic retrieval and fallback answer with citations.
- [ ] Implement source catalog with Anvisa, Farmacopeia Brasileira, ICH, PIC/S, WHO and FDA/eCFR.
- [ ] Implement HTML/PDF extraction, text normalization, hashing, chunking and ingestion logs.
- [ ] Implement retrieval score and answer orchestration.
- [ ] Run service tests until green.

### Task 4: API

**Files:**
- Create: `knowledge/serializers.py`
- Create: `knowledge/views.py`
- Create: `knowledge/urls.py`
- Modify: `core/urls.py`
- Modify: `core/api_v1_urls.py`
- Test: `tests/test_knowledge.py`

**Interfaces:**
- Produces: `POST /api/knowledge/chat/`
- Produces: read-only endpoints for sources, documents, chunks, sessions and messages.

- [ ] Write failing API tests for authenticated chat, tenant isolation and cited sources.
- [ ] Implement serializers and viewsets using `IsTenantMember`.
- [ ] Register URLs under `/api/knowledge/` and `/api/v1/knowledge/`.
- [ ] Run API tests until green.

### Task 5: Floating Chat UI

**Files:**
- Create: `static/js/rag-chat.js`
- Modify: `templates/base.html`
- Modify: `static/css/app.css`
- Test: `tests/test_app_ui.py`

**Interfaces:**
- Consumes: `POST /api/knowledge/chat/`.
- Produces: floating chat widget rendered for authenticated users.

- [ ] Write failing UI tests for widget markup and script inclusion.
- [ ] Add widget markup to `templates/base.html`.
- [ ] Add scoped CSS and JS for chat behavior, loading, errors and citations.
- [ ] Run UI tests until green.

### Task 6: Docs, Seed, Database And Verification

**Files:**
- Modify: `README.md`
- Create: `docs/architecture/knowledge.md`
- Modify: `base/ui/registry.py`
- Modify: `templates/base.html`

**Interfaces:**
- Produces command: `.venv/bin/python manage.py ingest_rag_sources --tenant-slug <slug> --max-chunks-per-source <n>`.

- [ ] Register knowledge resources in app UI registry and navigation.
- [ ] Update README and architecture docs.
- [ ] Run migrations on the local development database.
- [ ] Ingest the official seed corpus for an available tenant with a bounded chunk limit.
- [ ] Run relevant tests and Django checks.
