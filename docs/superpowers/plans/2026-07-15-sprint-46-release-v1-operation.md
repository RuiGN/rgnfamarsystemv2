# Sprint 46 — Release v1 e operação assistida Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or **superpowers:executing-plans** to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar release versionada, gates reproduzíveis e runbook de rollback sem publicação externa.

**Architecture:** Um workflow GitHub Actions executa gates e valida tags; scripts locais reproduzem a validação e constroem a imagem com tag determinística. Documentação consolida promoção, rollback e evidências.

**Tech Stack:** GitHub Actions, Docker, Bash, Django management commands, pytest.

## Global Constraints

- Não publicar em registry externo.
- Não executar deploy real.
- Não usar credenciais ou segredos reais.
- Não alterar models ou gerar migrations.

### Task 1: Contrato de versão e gates

**Files:**
- Create: `scripts/release_gate.sh`
- Test: `tests/test_release_gate.py`

- [x] Testar aceitação de `vMAJOR.MINOR.PATCH` e rejeição de tags inválidas.
- [x] Testar que o script exige `GITHUB_SHA`/commit e executa gates configuráveis.
- [x] Implementar script seguro com `set -euo pipefail`.
- [x] Rodar testes e `bash -n`.

### Task 2: Workflow de release

**Files:**
- Create: `.github/workflows/release.yml`
- Test: `tests/test_release_workflow_contract.py`

- [x] Testar triggers manuais/tag e permissões mínimas.
- [x] Definir jobs para gates, build local e relatório sem push externo.
- [x] Validar YAML e contrato dos jobs.

### Task 3: Runbook e evidências

**Files:**
- Create: `docs/architecture/release-v1.md`
- Modify: `docs/deployment.md`
- Modify: `README.md`
- Modify: `PRD.md`

- [x] Documentar promoção, rollback por tag, pós-deploy, backup/restore e healthchecks.
- [x] Registrar Sprint 46 como executada somente após validações.
- [x] Rodar `git diff --check` e verificações de segredos.

### Task 4: Verificação

- [x] Executar gates locais e testes específicos.
- [x] Validar workflow e script.
- [x] Confirmar árvore limpa e registrar commit final.
