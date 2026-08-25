# Inline Formula Components Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir criar e editar uma fórmula mestra com vários componentes na mesma tela do CRUD operacional.

**Architecture:** O CRUD genérico continua sendo a entrada única de criação/edição. Apenas o recurso `formulations/formulas` recebe um formset inline de `FormulaComponent`, validado e salvo em transação junto com `MasterFormula`.

**Tech Stack:** Python, Django, Django templates, Bootstrap 5, JavaScript leve.

## Global Constraints

- Preservar o CRUD genérico para os demais recursos.
- Não alterar schema de banco.
- Validar e salvar componentes com o mesmo tenant da fórmula.
- Permitir múltiplas linhas e remoção de componentes existentes na edição.
- Cobrir criação de fórmula com mais de 3 componentes em teste automatizado.

---

### Task 1: Teste de criação de fórmula com múltiplos componentes

**Files:**
- Create: `tests/test_formula_inline_components_ui.py`

**Interfaces:**
- Consumes: URL `app:resource_create` para `module_slug=formulations`, `resource_slug=formulas`.
- Produces: teste que exige persistência de uma `MasterFormula` com 4 `FormulaComponent`.

- [ ] Escrever teste que faz POST de uma fórmula com 4 linhas do formset.
- [ ] Rodar o teste e confirmar falha por ausência do formset.

### Task 2: Formset inline no CRUD de fórmulas

**Files:**
- Modify: `base/ui/views.py`
- Modify: `templates/app/resource_form.html`

**Interfaces:**
- Produces: contexto `inline_formsets` com metadados e formset renderizável.
- Produces: salvamento transacional de formulário principal e formset.

- [ ] Criar formset inline para `FormulaComponent`.
- [ ] Filtrar campos relacionais por tenant ativo.
- [ ] Validar `form` e `formset` antes de salvar.
- [ ] Salvar fórmula e componentes em `transaction.atomic()`.
- [ ] Renderizar formset no template com botão de adicionar linha e suporte a remoção.

### Task 3: Verificação

**Files:**
- Test: `tests/test_formula_inline_components_ui.py`
- Test: `tests/test_app_ui.py`

- [ ] Rodar o teste novo.
- [ ] Rodar testes relevantes de UI para garantir que a tela genérica não quebrou.
- [ ] Revisar `git diff` para confirmar escopo.
