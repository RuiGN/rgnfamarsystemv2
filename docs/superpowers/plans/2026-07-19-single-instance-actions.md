# Single-Instance Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remover o Control Plane, manter o Django Admin em `/admin/`, publicar as 253 ações DRF no frontend operacional em pt-BR e concluir o deploy single-domain na VPS Contabo.

**Architecture:** O trabalho é dividido em quatro sprints ordenadas. O pacote `control_plane` torna-se um tombstone de migrations; a UI de ações usa metadados imutáveis e despacha para os callbacks DRF existentes; o catálogo é validado por igualdade de conjuntos; o release final publica somente o domínio principal.

**Tech Stack:** Python 3.13, Django 5.2, Django REST Framework, PostgreSQL 15, Redis 7, Celery, RabbitMQ 3.13, Docker Compose, Nginx, Cloudflare Tunnel, Bootstrap 5 e JavaScript.

## Global Constraints

- O sistema é single-instance e não pode reintroduzir segmentação ou domínio por cliente.
- O único domínio público é `rgnfarmasystem.rgnsystems.com.br`.
- O Django Admin permanece em `/admin/` com autenticação padrão `is_active` e `is_staff`.
- A API existente permanece como executora única de regras de domínio, transações e auditoria.
- O frontend deve cobrir exatamente as 253 ações POST DRF existentes e falhar no CI quando o conjunto mudar sem configuração HTML.
- Todo texto novo visível deve usar português brasileiro com acentuação UTF-8 correta e o HTML deve declarar `lang="pt-BR"`.
- Ações críticas exigem confirmação explícita; autorização, CSRF e estado são revalidados no servidor.
- PostgreSQL é obrigatório em desenvolvimento, testes e produção.
- Nenhum lote pode reduzir a cobertura total abaixo de 80%.
- Alterações locais preexistentes em `docker-compose.vps.yml` e `tests/test_operational_readiness.py` pertencem ao gate de saúde da Sprint 4 e devem ser preservadas.

---

## Ordem obrigatória

1. [Sprint 1 — remoção segura do Control Plane](2026-07-19-sprint-1-control-plane-removal.md)
2. [Sprint 2 — infraestrutura genérica das ações](2026-07-19-sprint-2-action-framework.md)
3. [Sprint 3 — catálogo completo das 253 ações](2026-07-19-sprint-3-action-catalog.md)
4. [Sprint 4 — runbook de deploy, Contabo e aceite final](../../DEPLOY_VPS.md)

Uma sprint somente avança após testes relevantes verdes, `git diff --check`, revisão de menus/permissões e commit próprio. O gate final da Sprint 4 executa toda a suíte e verifica o domínio público; saúde interna sem túnel estável não caracteriza deploy concluído.

## Interface compartilhada entre sprints

- Sprint 1 produz runtime single-domain, migrations `control_plane.0005` e `accounts.0012` e Admin padrão.
- Sprint 2 produz `ActionConfig`, `ActionField`, `ActionConfirmation`, descoberta DRF, registro, formulário, dispatcher HTML, templates e JavaScript.
- Sprint 3 consome essas interfaces sem alterar suas assinaturas e produz 27 módulos de catálogo cuja união possui 253 chaves.
- Sprint 4 consome o runtime e o catálogo completos, atualiza documentação/infra e gera evidências de release.

## Commits esperados

```text
test: specify control-plane evidence migration
feat: remove control-plane runtime
test: specify generic domain action registry
feat: add generic domain action interface
feat: register operational action catalog batch 1
feat: register operational action catalog batch 2
feat: register operational action catalog batch 3
docs: document single-instance action workflows
ops: publish single-domain Contabo release
```
