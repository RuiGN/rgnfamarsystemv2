# Sprint 3 Complete Action Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cadastrar e validar as 253 ações POST DRF na interface HTML operacional.

**Architecture:** Cada app possui um módulo declarativo em `base/ui/actions/modules/`; uma fábrica reduz repetição, mas cada ação continua declarando recurso, nome, campos, estados, confirmação e cópia. Um teste compara chaves descobertas e registradas, incluindo rota, model, detalhe/coleção e permissão.

**Tech Stack:** Python, Django, DRF URL resolver, pytest parametrizado e catálogo Markdown gerado dos mesmos metadados.

## Global Constraints

- A união dos 27 módulos deve ter exatamente 253 ações: 247 de detalhe e seis de coleção.
- Nenhuma configuração pode usar texto inglês visível, permissão vazia, rota concatenada ou estado inexistente.
- Campos de motivo, comentário, evidência e confirmação indicados no inventário são obrigatórios quando a API/model exige valor não vazio.
- Ações destrutivas, aprovações, rejeições, liberações, encerramentos, obsolescência, revogações e reversões exigem confirmação.
- Estados permitidos devem reproduzir as precondições atuais do método de domínio no respectivo `models.py`.

---

## Inventário congelado

Legenda de campos: `t` texto curto, `T` texto longo, `i` inteiro, `d` decimal, `b` booleano, `D` data, `DT` data/hora, `c` choice, `r` relação, `j` JSON. Ausência de parênteses significa payload vazio.

- `ai_agents` (6): `profiles: run(source_module:c, source_model:t, source_record_id:t, input_payload:j, run_immediately:b, dispatch:b)`; `runs: enqueue(dispatch:b), execute`; `suggestions: apply(comments:T), approve(comments:T), reject(comments:T)`.
- `audits` (12): `programs: activate, close`; `plans: cancel(reason:T), close(summary:T), complete_execution, start, submit`; `checklist-items: answer(status:c, answer:T)`; `findings: close`; `actions: complete(completion_notes:T, evidence_reference:t, content_hash:t), start`; `reports: issue`.
- `capa` (11): `records: cancel(reason:T), close(summary:T), generate_notifications, start, submit`; `actions: complete(completion_notes:T), start`; `effectiveness-checks: verify(result:c, evidence_reference:t, effective:b)`; `approvals: approve(comments:T), reject(comments:T)`; `notifications: mark_sent`.
- `changes` (11): `controls: approve_for_implementation, cancel(reason:T), close(summary:T), start_implementation, submit`; `assessments: complete(impact_level:c, impact_description:T, required_actions:T)`; `actions: complete(completion_notes:T, evidence_reference:t, content_hash:t), start`; `approvals: approve(comments:T), reject(comments:T)`; `stock-assessments: complete(decision:c, assessment_summary:T)`.
- `compliance` (1, coleção): `checklist-items: evaluate_module(module:c)`.
- `costing` (8): `standard-costs: approve, recalculate`; `simulations: calculate`; `production-captures: calculate`; `monthly-closings: close, reopen(validation_notes:T), validate_period(validation_notes:T)`; `report-snapshots: calculate_margin`.
- `crm` (16): `opportunities: advance(stage:c), mark_lost(reason:T), mark_won`; `proposals: accept, recalculate, reject(reason:T), send`; `contracts: activate, cancel, suspend`; `orders: approve, cancel(reason:T), recalculate`; `complaints: cancel(reason:T), close(resolution:T), start_investigation`.
- `deviations` (7): `events: cancel(reason:T), close(summary:T), start_investigation`; `investigations: conclude(root_cause:T, impact_conclusion:T, conclusion:T)`; `impact-assessments: complete`; `approvals: approve(comments:T), reject(comments:T)`.
- `documents` (9): `controlled-documents: approve(comments:T), archive(reason:T), cancel(reason:T), create_revision(change_summary:T), obsolete(reason:T), publish, review(comments:T), submit_for_review`; `distributions: confirm_read(confirmation_text:T)`.
- `files` (7): `protected-files: delete_secure(reason:T), expire, generate_link(purpose:T, expires_in_minutes:i), record_view, replace(new_file_reference:t, new_file_name:t, content_hash:t, reason:T, file_size:i, mime_type:t)`; `secure-links: revoke(reason:T), use`.
- `finance` (10): `titles: approve, cancel, mark_overdue`; `settlements: reconcile, reverse(reversal_reason:T)`; `cash-flow` (coleção): `from_settlement(settlement:r), from_title(title:r)`; `period-closings: close, reopen(validation_notes:T), validate_period(validation_notes:T)`.
- `fiscal` (16): `tax-rules: approve`; `documents: approve, cancel(justification:T), check_status, create_financial_title(category:r, due_date:D), issue, post_entry, recalculate, review, send_email, submit_for_review`; `taxes: calculate`; `assessments: calculate, close`; `book-entries` (coleção): `from_document(document:r)`; `obligations: submit(protocol_number:t)`.
- `governance` (1): `demo-loads: run`.
- `integrations` (5): `connectors: activate, suspend(reason:T), test_failure(error_message:T, details:j), test_success(details:j)`; `api-clients: rotate_secret(secret:t)`.
- `maintenance` (8): `assets: block(reason:T), release`; `plans: generate_order(source_lot:r, due_date:D)`; `orders: cancel(reason:T), complete(summary:T, evidence_reference:t, content_hash:t), start`; `downtimes: close(ended_at:DT)`; `metric-reports: generate(content_reference:t)`.
- `pharmacovigilance` (8): `cases: cancel(reason:T), close(summary:T), start_investigation, start_triage`; `investigations: complete`; `actions: complete(completion_notes:T, evidence_reference:t, content_hash:t), start`; `reports: generate(content_reference:t)`.
- `planning` (1): `mrp-runs: calculate`.
- `procurement` (12): `requisitions: approve, cancel, reject(rejection_reason:T), submit`; `rfqs: approve, send`; `orders: approve, cancel, send`; `receipts: mark_received, post_stock, release_quality(quality_status:c)`.
- `production` (7): `orders: approve, cancel(cancel_reason:T), complete(actual_yield_quantity:d), pause, release, resume, start`.
- `qa` (13): `reviews: approve, reject(reason:T), submit`; `checklist-items: complete(evidence_reference:t, comments:T)`; `lot-releases: approve(decision:c), block(reason:T), reject(reason:T), unblock(reason:T)`; `blocks: apply, unblock(reason:T)`; `training-records: complete(evidence_reference:t), revoke(reason:T)`; `critical-activity-rules: authorize(user:r)`.
- `quality` (23): `specifications: approve, obsolete`; `samples: approve, cancel(reason:T), collect, create_analysis(method_reference:t), receive, reject(reason:T), review, start_analysis`; `analyses: approve, complete, reject(reason:T), review, start`; `results: evaluate`; `investigations: approve_repeat(justification:T), approve_resampling(justification:T), approve_retest(justification:T), conclude(root_cause:T, conclusion:T), start`; `documents: cancel(reason:T), issue`.
- `recalls` (19): `complaints: cancel(reason:T), close(summary:T), record_regulatory_communication(reference:t), start_investigation, start_triage`; `returns: authorize, cancel(reason:T), close(summary:T), inspect(disposition:c, notes:T), receive(quantity:d)`; `campaigns: approve, cancel(reason:T), close(summary:T), start`; `impacted-customers: record_response(status:c, notes:T), record_return(quantity:d, notes:T)`; `communications: acknowledge, send`; `reports: generate(content_reference:t)`.
- `reports` (4): `definitions: run(export_format:c, filters:j)`; `executions: cancel, run`; `schedules: trigger_now`.
- `regulatory` (10): `dossiers: cancel(reason:T), close(summary:T), submit`; `petitions: record_response(response_summary:T), submit(protocol_number:t)`; `requirements: answer(response_summary:T, evidence_reference:t, content_hash:t)`; `commitments: complete(completion_summary:T, evidence_reference:t, content_hash:t)`; `reports: generate(content_reference:t)`; `alerts` (coleção): `generate`; `alerts: acknowledge`.
- `risks` (10): `records: cancel(reason:T), close(summary:T), generate_alerts, start_monitoring, start_treatment`; `actions: complete(completion_notes:T, evidence_reference:t, content_hash:t), start`; `reviews: complete(result:c, next_review_date:D)`; `alerts` (coleção): `generate`; `alerts: acknowledge`.
- `training` (8): `sessions: convocate(user:r, due_date:D)`; `enrollments: approve(certificate_reference:t), complete(score:d, evidence_reference:t, content_hash:t), fail(reason:T), revoke(reason:T), start`; `critical-activity-rules: authorize(user:r)`; `indicator-reports: generate(content_reference:t)`.
- `workflow` (10): `notifications: archive, mark_read, send`; `tasks: approve(comments:T), cancel(comments:T), reject(comments:T)`; `async-jobs: complete(result_reference:t, message:T), fail(error_message:T, message:T), start(task_id:t), update_progress(progress_percent:i, message:T)`.

As seis ações de coleção são `compliance/checklist-items/evaluate_module`, `finance/cash-flow/from_settlement`, `finance/cash-flow/from_title`, `fiscal/book-entries/from_document`, `regulatory/alerts/generate` e `risks/alerts/generate`.

## Vocabulário pt-BR obrigatório

`base/ui/actions/copy.py` define rótulos estáveis para os 94 nomes: aceitar, reconhecer, ativar, avançar, responder, aplicar, aprovar, aprovar para implementação, aprovar repetição, aprovar nova amostragem, aprovar nova análise, arquivar, autorizar, bloquear, calcular, calcular margem, cancelar, consultar situação, encerrar, coletar, concluir, concluir execução, confirmar leitura, convocar, criar análise, criar título financeiro, criar revisão, excluir com segurança, enfileirar, avaliar, avaliar módulo, executar, expirar, reprovar, gerar a partir do documento, gerar a partir da liquidação, gerar a partir do título, gerar, gerar alertas, gerar link, gerar notificações, gerar ordem, inspecionar, emitir, marcar como perdida, marcar como vencido, marcar como lida, marcar como recebido, marcar como enviado, marcar como ganha, tornar obsoleto, pausar, contabilizar, lançar no estoque, publicar, recalcular, receber, conciliar, registrar comunicação regulatória, registrar resposta, registrar devolução, registrar visualização, rejeitar, liberar, liberar pela qualidade, reabrir, substituir, retomar, estornar, revisar, revogar, rotacionar segredo, executar, enviar, enviar por e-mail, iniciar, iniciar análise, iniciar implementação, iniciar investigação, iniciar monitoramento, iniciar tratamento, iniciar triagem, submeter, submeter para revisão, suspender, registrar falha no teste, registrar sucesso no teste, executar agora, desbloquear, atualizar progresso, utilizar, validar período e verificar.

Mensagens de sucesso seguem `“{Rótulo} concluído com sucesso.”`; descrições seguem `“Execute esta ação em {recurso}.”`; confirmações críticas seguem `“Confirme a ação {rótulo em minúsculas} para este registro.”`. Ajustar gênero somente nos rótulos “marcada/marcado” usando override na configuração.

### Task 1: Fábrica, vocabulário e gate de igualdade

**Files:**
- Create: `base/ui/actions/copy.py`
- Create: `base/ui/actions/factory.py`
- Modify: `base/ui/actions/registry.py`
- Create: `tests/test_action_catalog_completeness.py`
- Create: `tests/test_action_copy_ptbr.py`

**Interfaces:**
- Produces: `action_config(module_slug, resource_slug, action_name, *, fields=(), allowed_states=(), confirmation=None, **overrides)`.
- Consumes: descoberta da Sprint 2 para rota/model/permissão e vocabulário pt-BR.

- [ ] **Step 1: escrever o teste global vermelho**

```python
def test_html_catalog_exactly_matches_post_actions():
    discovered = {item.key: item for item in discover_post_actions()}
    registered = {
        (config.model._meta.label_lower, config.action_name, config.detail): config
        for config in action_registry.all()
    }
    assert registered.keys() == discovered.keys()
    for key, config in registered.items():
        endpoint = discovered[key]
        assert config.route_name == endpoint.route_name
        assert config.permissions == endpoint.permissions

def test_catalog_has_approved_cardinality():
    configs = action_registry.all()
    assert len(configs) == 253
    assert sum(not config.detail for config in configs) == 6
```

- [ ] **Step 2: executar e confirmar a diferença de 246 itens**

Run: `./scripts/test.sh tests/test_action_catalog_completeness.py -q`

Expected: FAIL mostrando 253 descobertas e sete registradas.

- [ ] **Step 3: implementar fábrica e cópia**

A fábrica localiza exatamente uma `DiscoveredAction` pelo model do recurso e `action_name`, preenche `route_name`, `detail` e `permissions`, aplica cópia do vocabulário e exige override quando o nome não estiver no dicionário. Não permitir fallback em inglês. O teste pt-BR percorre todos os textos, exige Unicode NFC, rejeita as formas sem acento da especificação e verifica que `templates/base.html` usa `lang="pt-BR"`.

- [ ] **Step 4: executar testes unitários**

Run: `./scripts/test.sh tests/test_action_discovery.py tests/test_action_registry.py tests/test_action_copy_ptbr.py -q`

Expected: PASS; o teste global continua vermelho até os três lotes.

### Task 2: Lote 1 — operações, comercial e finanças

**Files:**
- Create: `base/ui/actions/modules/ai_agents.py`
- Create: `base/ui/actions/modules/costing.py`
- Create: `base/ui/actions/modules/crm.py`
- Create: `base/ui/actions/modules/finance.py`
- Create: `base/ui/actions/modules/fiscal.py`
- Create: `base/ui/actions/modules/integrations.py`
- Create: `base/ui/actions/modules/maintenance.py`
- Create: `base/ui/actions/modules/planning.py`
- Create: `base/ui/actions/modules/procurement.py`
- Modify: `base/ui/actions/modules/production.py`
- Create: `base/ui/actions/modules/reports.py`
- Create: `tests/test_action_catalog_operations.py`

**Interfaces:**
- Produces: 93 configurações acumuladas neste lote, incluindo as sete já existentes de produção.

- [ ] **Step 1: parametrizar o inventário do lote**

O teste usa exatamente as linhas correspondentes do inventário congelado, verifica chaves/campos/tipos, choices do model/serializer, querysets de relação com permissão `view`, required conforme validação da API e estados conforme os métodos de domínio.

- [ ] **Step 2: executar o teste vermelho**

Run: `./scripts/test.sh tests/test_action_catalog_operations.py -q`

Expected: FAIL listando módulos ainda ausentes.

- [ ] **Step 3: cadastrar o lote**

Criar uma tupla `ACTION_CONFIGS` por arquivo usando `action_config()`. Relações usam factories que retornam somente objetos visíveis; `details` e `filters` usam textarea com validação de objeto JSON; `secret` usa `PasswordInput(render_value=False)` por override de widget seguro. Todas as ações com status declaram `allowed_states` literais existentes no `TextChoices` do model.

- [ ] **Step 4: validar e commit**

Run: `./scripts/test.sh tests/test_action_catalog_operations.py tests/test_costing.py tests/test_crm.py tests/test_finance.py tests/test_fiscal.py tests/test_integrations.py tests/test_maintenance.py tests/test_planning.py tests/test_procurement.py tests/test_production.py tests/test_reports.py -q`

Expected: PASS.

```bash
git add base/ui/actions tests/test_action_catalog_operations.py
git commit -m "feat: register operational action catalog batch 1"
```

### Task 3: Lote 2 — qualidade, GxP e regulatório

**Files:**
- Create: `base/ui/actions/modules/audits.py`
- Create: `base/ui/actions/modules/capa.py`
- Create: `base/ui/actions/modules/changes.py`
- Create: `base/ui/actions/modules/compliance.py`
- Create: `base/ui/actions/modules/deviations.py`
- Create: `base/ui/actions/modules/documents.py`
- Create: `base/ui/actions/modules/pharmacovigilance.py`
- Create: `base/ui/actions/modules/qa.py`
- Create: `base/ui/actions/modules/quality.py`
- Create: `base/ui/actions/modules/recalls.py`
- Create: `base/ui/actions/modules/regulatory.py`
- Create: `base/ui/actions/modules/risks.py`
- Create: `tests/test_action_catalog_gxp.py`

**Interfaces:**
- Produces: 134 configurações deste lote, com confirmação e evidência reforçadas.

- [ ] **Step 1: escrever teste vermelho do lote regulado**

Além do inventário, parametrizar um caso por app garantindo: permissão ausente oculta botão; estado inválido oculta botão; motivo/evidência obrigatórios geram erro; sucesso altera estado e cria/atualiza trilha de auditoria esperada pelo teste de domínio existente.

- [ ] **Step 2: executar o teste vermelho**

Run: `./scripts/test.sh tests/test_action_catalog_gxp.py -q`

Expected: FAIL listando os 12 módulos não cadastrados.

- [ ] **Step 3: cadastrar o lote GxP**

Usar o inventário congelado. `approve*`, `reject`, `release*`, `cancel`, `close`, `conclude`, `obsolete`, `archive`, `revoke`, `reverse` e ações de bloqueio exigem `ActionConfirmation`. Motivo, justificativa, conclusão, evidência e hash são obrigatórios exatamente quando o método de domínio os valida. Choices vêm dos `TextChoices` do model, sem listas duplicadas no frontend.

- [ ] **Step 4: validar e commit**

Run: `./scripts/test.sh tests/test_action_catalog_gxp.py tests/test_audits.py tests/test_capa.py tests/test_changes.py tests/test_compliance.py tests/test_deviations.py tests/test_documents.py tests/test_pharmacovigilance.py tests/test_qa.py tests/test_quality.py tests/test_recalls.py tests/test_regulatory.py tests/test_risks.py -q`

Expected: PASS.

```bash
git add base/ui/actions tests/test_action_catalog_gxp.py
git commit -m "feat: register operational action catalog batch 2"
```

### Task 4: Lote 3 — arquivos, governança, treinamento e workflow

**Files:**
- Create: `base/ui/actions/modules/files.py`
- Create: `base/ui/actions/modules/governance.py`
- Create: `base/ui/actions/modules/training.py`
- Create: `base/ui/actions/modules/workflow.py`
- Modify: `base/ui/actions/modules/__init__.py`
- Create: `tests/test_action_catalog_platform.py`

**Interfaces:**
- Produces: 26 configurações finais e agregação das 27 tuplas.

- [ ] **Step 1: escrever teste vermelho do lote**

Cobrir expiração/revogação/exclusão segura, carga demo, matrícula/treinamento e workflow assíncrono. Verificar limites `expires_in_minutes`, `score` e `progress_percent`, relation de usuário filtrada e mensagem segura de falha.

- [ ] **Step 2: cadastrar o lote e agregador explícito**

`modules/__init__.py` importa cada `ACTION_CONFIGS` com alias e concatena na ordem alfabética de app. Não fazer descoberta automática por filesystem. Configurar `delete_secure` e `revoke` como `danger`, `rotate_secret` já pertence ao lote 1 e permanece com campo password, e ações assíncronas usam reload sem polling adicional.

- [ ] **Step 3: executar igualdade global**

Run: `./scripts/test.sh tests/test_action_catalog_platform.py tests/test_action_catalog_completeness.py tests/test_action_copy_ptbr.py -q`

Expected: PASS com 253/253, seis ações de coleção, zero duplicadas e zero órfãs.

- [ ] **Step 4: commit**

```bash
git add base/ui/actions tests/test_action_catalog_platform.py tests/test_action_catalog_completeness.py tests/test_action_copy_ptbr.py
git commit -m "feat: register operational action catalog batch 3"
```

### Task 5: Gate da Sprint 3

**Files:**
- Test: `tests/test_action_*.py`
- Test: testes dos 27 apps com ações.

**Interfaces:**
- Produces: catálogo completo consumido pela documentação e pelo release.

- [ ] **Step 1: executar todos os testes de ação**

Run: `./scripts/test.sh tests/test_action_*.py -q`

Expected: PASS, 253 configurações.

- [ ] **Step 2: executar testes de domínio dos 27 apps**

Run: `./scripts/test.sh tests/test_ai_agents.py tests/test_audits.py tests/test_capa.py tests/test_changes.py tests/test_compliance.py tests/test_costing.py tests/test_crm.py tests/test_deviations.py tests/test_documents.py tests/test_files.py tests/test_finance.py tests/test_fiscal.py tests/test_governance.py tests/test_integrations.py tests/test_maintenance.py tests/test_pharmacovigilance.py tests/test_planning.py tests/test_procurement.py tests/test_production.py tests/test_qa.py tests/test_quality.py tests/test_recalls.py tests/test_regulatory.py tests/test_reports.py tests/test_risks.py tests/test_training.py tests/test_workflow.py -q`

Expected: todos PASS.

- [ ] **Step 3: lint e consistência**

Run: `.venv/bin/ruff check base/ui/actions tests/test_action_*.py && .venv/bin/ruff format --check base/ui/actions tests/test_action_*.py && git diff --check`

Expected: PASS e nenhum texto visível sem acentuação aprovada.
