# Sprint 45 — Deploy local/staging e observabilidade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar um ambiente Docker Compose local reproduzível, observável e validado por smoke tests.

**Architecture:** Um Compose local autocontido usa infraestrutura oficial e uma imagem compartilhada da aplicação. Healthchecks Docker e um script de smoke test fornecem sinais independentes para operação e diagnóstico.

**Tech Stack:** Docker Compose, Python/Django, PostgreSQL, Redis, RabbitMQ, Celery, Bash, pytest.

## Global Constraints

- Não usar VPS, Swarm, Cloudflare, GHCR privado ou credenciais reais.
- Não criar models nem migrations.
- Não versionar `.env.local` nem segredos.
- Manter comandos e documentação em português quando forem voltados ao operador.

### Task 1: Compose local autocontido

**Files:**
- Create: `docker-compose.local.yml`
- Modify: `.env.local.example`
- Test: `tests/test_local_compose_contract.py`

- [x] Escrever testes para serviços, ausência de Cloudflare por padrão, healthchecks e referências de variáveis locais.
- [x] Executar os testes e confirmar falha por arquivo ausente.
- [x] Implementar Compose local com `app`, `celery_worker`, `celery_beat`, `db`, `redis` e `rabbitmq`, usando uma imagem compartilhada.
- [x] Executar `docker compose -f docker-compose.local.yml config`.
- [x] Executar testes do contrato.

### Task 2: Smoke test local

**Files:**
- Create: `scripts/smoke_local.sh`
- Test: `tests/test_smoke_local_script.py`

- [x] Escrever testes para sucesso HTTP, retry de healthcheck e falha de rota.
- [x] Confirmar falha inicial por script ausente.
- [x] Implementar script sem expor ambiente ou segredos.
- [x] Executar testes unitários do script.

### Task 3: Observabilidade e documentação

**Files:**
- Modify: `docs/deployment.md`
- Modify: `README.md`
- Modify: `PRD.md`

- [x] Documentar comandos de subida, status, logs, smoke test e limpeza.
- [x] Registrar critérios e resultado da Sprint 45 no PRD.
- [x] Executar verificações de links/texto e `git diff --check`.

### Task 4: Verificação integrada

- [x] Rodar Compose config e `manage.py check`.
- [ ] Subir o ambiente local e aguardar healthchecks (bloqueado pelo daemon Docker local).
- [ ] Rodar `scripts/smoke_local.sh` contra o ambiente iniciado (bloqueado pelo daemon Docker local).
- [x] Rodar testes específicos e a suíte completa com banco isolado.
- [x] Confirmar ausência de segredos e árvore limpa.
- [x] Commitar a Sprint 45.
