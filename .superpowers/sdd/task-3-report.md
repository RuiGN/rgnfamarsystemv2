# Task 3 — Layout 8+4 em telas de detalhe

## Status

Implementado e verificado no worktree `design-system-operational-components`.

## Evidência TDD

- **RED (layout):** `pytest -q tests/test_app_ui.py -k 'detail_layout or semantic_status_region'` retornou `2 failed, 1 passed`; os cenários falharam pela ausência de `data-ui="detail-layout"`.
- **GREEN (layout):** após a implementação, o mesmo comando retornou `3 passed, 101 deselected`.
- **RED (CSS):** `pytest -q tests/test_responsive_layout_css.py -k detail_summary` retornou `1 failed` depois da remoção temporária dos estilos `.detail-summary__*`.
- **GREEN final:** `pytest -q tests/test_app_ui.py tests/test_responsive_layout_css.py` retornou `125 passed, 7 subtests passed`.

## Implementação

- `base/ui/presentation.py`: contrato imutável `DetailSummaryItem` e `build_detail_summary(obj, status)`, limitado à allowlist de identificadores, pessoas e datas; datas são formatadas em pt-BR.
- `base/ui/views.py`: expõe `detail_summary` e `has_detail_sidebar`; a lateral só é aberta para status ou metadados operacionais além dos dados primários. Campos migrados para a lateral deixam de duplicar a tabela principal.
- `templates/app/resource_detail.html` e `templates/includes/components/detail_summary.html`: ações permanecem acima da grade, dados primários ocupam 8 colunas com lateral ou 12 sem lateral, e a trilha permanece abaixo dos dados primários.
- `static/css/app.css`: estilos escopados para legibilidade e quebra segura de valores longos.
- `tests/test_app_ui.py` e `tests/test_responsive_layout_css.py`: cobertura de ordem de produção com resumo e unidade simples sem lateral.

## Verificações

Executadas com `DATABASE_URL` e `TEST_DATABASE_URL` apontando para SQLite descartável:

- `pytest -q tests/test_app_ui.py tests/test_responsive_layout_css.py` — 125 passed, 7 subtests passed.
- `python manage.py check` — sem problemas (0 silenciados).
- `ruff check base/ui/presentation.py base/ui/views.py tests/test_app_ui.py tests/test_responsive_layout_css.py` — aprovado.
- `git diff --check` — aprovado.

## Autorrevisão e preocupações

- Não foram incluídas migrations, dados demonstrativos, mocks de negócio ou lógica futura de status/auditoria.
- A trilha de auditoria existente foi mantida, conforme escopo; sua adaptação para dados reais permanece para a tarefa própria.
- A suíte integral foi preservada para a Task 9; não foi executada nesta tarefa.
