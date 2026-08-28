# Componentes operacionais do design system — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar os padrões operacionais aprovados do design system aos dashboards, workspaces, listagens e detalhes do RGN Farma System, com dados reais, permissões Django, acessibilidade e textos em português do Brasil.

**Architecture:** Contratos imutáveis em `base/ui/presentation.py` normalizam KPIs, prazos, notificações, estados e auditoria. Construtores Django consultam dados e permissões; templates compartilhados em `templates/includes/components/` somente apresentam o contexto. A entrega não cria tabelas novas e reutiliza `WorkflowNotification`, `DocumentAuditTrail` e `RecordStatusHistory`.

**Tech Stack:** Python 3.13+, Django, Django Templates, Bootstrap 5/Duralux, Feather Icons, ApexCharts, CSS3 e pytest-django.

## Global Constraints

- Executar as tarefas na ordem numerada.
- Escrever testes antes do código de produção e observar a falha esperada.
- Usar português do Brasil com acentuação em todo texto visível novo.
- Não adicionar textos demonstrativos, dados simulados ou links `javascript:void(0)` como ações de negócio.
- Cor nunca será a única indicação de estado; combinar texto, ícone e atributos ARIA.
- Filtrar objetos e links por permissões Django antes de entregá-los aos templates.
- Não criar migrations nesta entrega.
- Preservar as alterações locais preexistentes em `base/automatic_fields.py`, `crm/admin.py`, `docs/architecture/foundation.md`, `docs/architecture/inventory.md`, `finance/admin.py` e `tests/test_automatic_fields.py`.

---

## Estrutura de arquivos

- Criar `base/ui/presentation.py`: contratos imutáveis e resolvedor semântico.
- Criar `base/ui/deadlines.py`: fontes autorizadas de prazos por workspace.
- Criar `base/ui/audit.py`: adaptadores de auditoria persistida.
- Criar `base/templatetags/__init__.py` e `base/templatetags/ui_query.py`: query string segura para paginação.
- Criar `templates/includes/components/progress_metric_card.html`.
- Criar `templates/includes/components/deadline_list.html`.
- Criar `templates/includes/components/status_badge.html`.
- Criar `templates/includes/components/notification_dropdown.html`.
- Modificar `base/ui/workspaces.py`, `base/ui/context_processors.py`, `base/ui/registry.py` e `base/ui/views.py`.
- Modificar `templates/workspaces/workspace.html`, `templates/dashboards/hub.html`, `templates/base.html`, `templates/app/resource_list.html`, `templates/app/resource_detail.html`, `templates/app/includes/search_filters.html`, `templates/app/includes/pagination.html` e `templates/app/includes/audit_trail.html`.
- Modificar `static/css/app.css` e `static/js/dashboard-hub.js` apenas para os comportamentos visuais aprovados.
- Criar `tests/test_design_system_components.py` e ampliar testes específicos existentes.

---

### Task 1: KPI reutilizável com progresso

**Files:**
- Create: `base/ui/presentation.py`
- Create: `templates/includes/components/progress_metric_card.html`
- Create: `tests/test_design_system_components.py`
- Modify: `base/ui/workspaces.py`
- Modify: `base/ui/views.py:358-565`
- Modify: `templates/workspaces/workspace.html:20-49`
- Modify: `templates/dashboards/hub.html:30-53`
- Test: `tests/test_workspace_ui.py`
- Test: `tests/test_dashboard_hub.py`

**Interfaces:**
- Produces: `ProgressMetric`, com propriedades `has_progress: bool` e `percent: int`.
- Consumers: workspaces, dashboards e `progress_metric_card.html`.

- [ ] **Step 1: Write the failing contract tests**

```python
from base.ui.presentation import ProgressMetric


def test_progress_metric_normalizes_percent_and_handles_zero_target():
    metric = ProgressMetric('Concluídas', 12, 'feather-check', 'success', 'Produção', '/app/', 20)
    overflow = ProgressMetric('Concluídas', 30, 'feather-check', 'success', 'Produção', '/app/', 20)
    no_target = ProgressMetric('Pendentes', 4, 'feather-clock', 'warning', 'Qualidade', '/app/')

    assert metric.has_progress is True
    assert metric.percent == 60
    assert overflow.percent == 100
    assert no_target.has_progress is False
    assert no_target.percent == 0
```

Add response assertions that workspace and dashboard HTML contain `data-ui="progress-metric"`, `role="progressbar"`, `aria-valuenow` and the visible text `Ver detalhes` when a target exists.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_design_system_components.py tests/test_workspace_ui.py tests/test_dashboard_hub.py`

Expected: failure because `base.ui.presentation.ProgressMetric` and the shared include do not exist.

- [ ] **Step 3: Implement the immutable KPI contract**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressMetric:
    label: str
    value: int | float
    icon: str
    tone: str
    badge: str
    url: str
    target: int | float | None = None
    helper: str = ''
    required_permission: str = ''

    @property
    def has_progress(self) -> bool:
        return self.target is not None and self.target > 0

    @property
    def percent(self) -> int:
        if not self.has_progress:
            return 0
        return max(0, min(100, round(float(self.value) / float(self.target) * 100)))

    def can_view(self, user) -> bool:
        return not self.required_permission or user.has_perm(self.required_permission)
```

Replace `WorkspaceMetric` with an imported alias to `ProgressMetric`, preserving positional fields and `can_view`. In dashboard data, add a trustworthy `target` only when the same queryset provides the denominator; metrics without denominator remain simple.

- [ ] **Step 4: Implement the shared template**

Render icon, value, target, label, badge and link. When `metric.has_progress`, render:

```html
<div class="progress mt-2 ht-3" aria-hidden="true">
    <div class="progress-bar bg-{{ metric.tone }}" style="width: {{ metric.percent }}%"></div>
</div>
<span class="visually-hidden" role="progressbar"
      aria-label="Progresso de {{ metric.label }}"
      aria-valuemin="0" aria-valuemax="100"
      aria-valuenow="{{ metric.percent }}">{{ metric.percent }}%</span>
```

Use `{% include 'includes/components/progress_metric_card.html' %}` from both consumers.

- [ ] **Step 5: Run GREEN and refactor**

Run: `pytest -q tests/test_design_system_components.py tests/test_workspace_ui.py tests/test_dashboard_hub.py`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the task**

```bash
git add base/ui/presentation.py base/ui/workspaces.py base/ui/views.py templates/includes/components/progress_metric_card.html templates/workspaces/workspace.html templates/dashboards/hub.html tests/test_design_system_components.py tests/test_workspace_ui.py tests/test_dashboard_hub.py
git commit -m "feat: adicionar indicadores operacionais com progresso"
```

---

### Task 2: Prazos e eventos operacionais

**Files:**
- Create: `base/ui/deadlines.py`
- Create: `templates/includes/components/deadline_list.html`
- Modify: `base/ui/presentation.py`
- Modify: `base/ui/workspaces.py`
- Modify: `base/ui/views.py:576-608`
- Modify: `templates/workspaces/workspace.html`
- Modify: `static/css/app.css`
- Test: `tests/test_design_system_components.py`
- Test: `tests/test_workspace_ui.py`

**Interfaces:**
- Produces: `DeadlineItem` and `build_workspace_deadlines(request, workspace_slug, limit=5)`.
- Consumer: `WorkspaceView` exposes `deadlines` to `deadline_list.html`.

- [ ] **Step 1: Write failing tests for order, labels and authorization**

Create dates for a nonterminal `ProductionOrder`, an assigned `ApprovalTask` and a notification with `due_at`. Assert overdue items precede future items, terminal orders are absent, approval tasks are scoped to `assigned_to=request.user`, and a user without the model view permission receives an empty tuple.

```python
def test_deadline_item_uses_ptbr_temporal_labels():
    overdue = DeadlineItem('OP-001', '', timezone.now() - timedelta(days=1), 'danger', 'feather-alert-triangle', '/app/')
    today = DeadlineItem('OP-002', '', timezone.now(), 'warning', 'feather-clock', '/app/')
    assert overdue.temporal_label == 'Vencido'
    assert today.temporal_label == 'Vence hoje'
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_design_system_components.py tests/test_workspace_ui.py`

Expected: failure because the deadline contract and builder are absent.

- [ ] **Step 3: Implement the deadline contract and builders**

Use `ProductionOrder.scheduled_end` for operation, `BatchRecordChecklistItem.due_date` for quality when `qa.view_batchrecordchecklistitem` is granted, and `ApprovalTask.due_at` plus `WorkflowNotification.due_at` for workflow. Exclude completed/cancelled/closed states and limit after sorting.

```python
@dataclass(frozen=True)
class DeadlineItem:
    title: str
    description: str
    due_at: date | datetime
    tone: str
    icon: str
    url: str

    @property
    def temporal_label(self) -> str:
        due_date = self.due_at.date() if isinstance(self.due_at, datetime) else self.due_at
        today = timezone.localdate()
        if due_date < today:
            return 'Vencido'
        if due_date == today:
            return 'Vence hoje'
        return f'Vence em {date_format(due_date, "d/m/Y")}'
```

- [ ] **Step 4: Render the operational deadline list**

Use a semantic `<ol>` with a visible vertical accent, icon, title, description, `<time>` and `temporal_label`. Empty output must say `Nenhum prazo operacional encontrado.` Add CSS scoped under `.operational-deadlines` and a reduced-motion rule.

- [ ] **Step 5: Run GREEN**

Run: `pytest -q tests/test_design_system_components.py tests/test_workspace_ui.py tests/test_responsive_layout_css.py`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the task**

```bash
git add base/ui/deadlines.py base/ui/presentation.py base/ui/workspaces.py base/ui/views.py templates/includes/components/deadline_list.html templates/workspaces/workspace.html static/css/app.css tests/test_design_system_components.py tests/test_workspace_ui.py tests/test_responsive_layout_css.py
git commit -m "feat: exibir prazos operacionais autorizados"
```

---

### Task 3: Layout 8+4 em telas de detalhe

**Files:**
- Modify: `base/ui/presentation.py`
- Modify: `base/ui/views.py:920-952`
- Modify: `templates/app/resource_detail.html:75-113`
- Create: `templates/includes/components/detail_summary.html`
- Modify: `static/css/app.css`
- Test: `tests/test_app_ui.py`
- Test: `tests/test_responsive_layout_css.py`

**Interfaces:**
- Produces: `build_detail_summary(obj, status)` retornando itens reais de identificação, responsável, datas e estado.
- Consumer: `ResourceDetailView` exposes `detail_summary` and `has_detail_sidebar`.

- [ ] **Step 1: Write failing response tests**

Assert a `ProductionOrder` detail renders `data-ui="detail-layout"`, `col-xl-8`, `col-xl-4`, `Responsável`, `Fim previsto` and the visible status. Assert a simple unit without summary metadata renders `col-12` and no empty sidebar.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_app_ui.py -k 'detail_layout or semantic_status_region'`

Expected: failure because no detail summary/layout contract exists.

- [ ] **Step 3: Implement summary extraction**

Inspect only an allowlist of model attributes: identifiers (`code`, `order_number`, `batch_number`, `document_number`), people (`responsible`, `owner`, `assigned_to`) and dates (`due_date`, `due_at`, `scheduled_end`, `valid_until`, `expiry_date`, `created_at`, `updated_at`). Use model verbose names and formatted values; never iterate arbitrary model fields.

- [ ] **Step 4: Implement responsive 8+4 presentation**

Wrap the current detail card and audit region in `.row.g-4`. Use `col-xl-8` plus `col-xl-4` only when `has_detail_sidebar`; otherwise use `col-12`. Render actions above the grid and keep the audit section below the primary record data.

- [ ] **Step 5: Run GREEN and responsive checks**

Run: `pytest -q tests/test_app_ui.py tests/test_responsive_layout_css.py`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the task**

```bash
git add base/ui/presentation.py base/ui/views.py templates/app/resource_detail.html templates/includes/components/detail_summary.html static/css/app.css tests/test_app_ui.py tests/test_responsive_layout_css.py
git commit -m "feat: organizar detalhes em layout operacional responsivo"
```

---

### Task 4: Filtros avançados configuráveis

**Files:**
- Create: `base/templatetags/__init__.py`
- Create: `base/templatetags/ui_query.py`
- Modify: `base/ui/registry.py:320-370`
- Modify: `base/ui/views.py:737-862`
- Modify: `templates/app/includes/search_filters.html`
- Modify: `templates/app/includes/pagination.html`
- Test: `tests/test_app_ui.py`
- Test: `tests/test_responsive_layout_css.py`

**Interfaces:**
- `ResourceConfig.advanced_filter_fields: tuple[str, ...]` allowlists model fields.
- `build_advanced_filters()` emits controls of kind `choice`, `date` or `datetime`.
- `{% query_transform page=number %}` preserves authorized GET parameters.

- [ ] **Step 1: Write failing filter and query-string tests**

Configure production orders with `('priority', 'scheduled_end')`, quality events with `('severity', 'criticality')`, CAPA records with `('due_date',)` and workflow tasks with `('criticality', 'due_at')`. Assert valid filters affect the queryset, undeclared keys do not, active filter count is correct, and pagination preserves every declared value without duplicating `page`.

```python
def test_query_transform_replaces_page_and_keeps_authorized_filters(rf):
    request = rf.get('/app/?status=pending&priority=urgent&page=2')
    context = {
        'request': request,
        'allowed_query_params': ('status', 'priority', 'page'),
    }
    assert query_transform(context, page=3) == 'status=pending&priority=urgent&page=3'
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_app_ui.py -k 'filter or pagination' tests/test_responsive_layout_css.py -k filters`

Expected: failure because advanced definitions and `query_transform` are absent.

- [ ] **Step 3: Implement safe filter configuration**

Add `advanced_filter_fields` to the frozen resource dataclass. Validate each name with `_meta.get_field`. Choice fields accept only declared choice values. Date/datetime fields accept `<name>_from` and `<name>_to` parsed with Django helpers. Ignore unsupported types and never pass raw parameter names to `QuerySet.filter`.

- [ ] **Step 4: Implement the query template tag**

```python
@register.simple_tag(takes_context=True)
def query_transform(context, **updates):
    source = context['request'].GET
    query = QueryDict(mutable=True)
    for key in context.get('allowed_query_params', ()):
        query.setlist(key, source.getlist(key))
    for key, value in updates.items():
        if value in (None, ''):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()
```

Use it for previous, numeric and next pagination links. Remove the repeated manual parameter concatenation.

- [ ] **Step 5: Implement the collapsible panel**

Keep search and status visible. Add a real Bootstrap button with `aria-expanded`, `aria-controls="filtros-avancados"` and text `Filtros avançados`. Show `{{ active_filter_count }}` when nonzero. Advanced labels derive from model verbose names and preserve submitted values.

- [ ] **Step 6: Run GREEN**

Run: `pytest -q tests/test_app_ui.py tests/test_responsive_layout_css.py tests/test_template_language.py`

Expected: all selected tests pass.

- [ ] **Step 7: Commit the task**

```bash
git add base/templatetags/__init__.py base/templatetags/ui_query.py base/ui/registry.py base/ui/views.py templates/app/includes/search_filters.html templates/app/includes/pagination.html tests/test_app_ui.py tests/test_responsive_layout_css.py tests/test_template_language.py
git commit -m "feat: adicionar filtros avançados seguros"
```

---

### Task 5: Prévia autorizada de notificações

**Files:**
- Modify: `base/ui/presentation.py`
- Modify: `base/ui/context_processors.py`
- Create: `templates/includes/components/notification_dropdown.html`
- Modify: `templates/base.html:87-96`
- Modify: `static/css/app.css`
- Test: `tests/test_workspace_ui.py`

**Interfaces:**
- Produces: `NotificationPreview.from_model(notification)`.
- Context: `workflow_notification_previews`, `can_preview_workflow_notifications` and existing unread count.

- [ ] **Step 1: Write failing permission and scoping tests**

Create notifications for two users. Assert the dropdown contains only the authenticated recipient's titles, at most five items, newest first, and the text `Ver todas as notificações`. Patch the manager to assert no notification query occurs without `workflow.view_workflownotification`.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_workspace_ui.py -k notification`

Expected: failure because the current bell is a plain link.

- [ ] **Step 3: Implement the scoped context**

Require both workflow workspace visibility and `user.has_perm('workflow.view_workflownotification')`. Query `WorkflowNotification.objects.filter(recipient=user).order_by('-created_at')[:5]`. Build detail URLs with the registered workflow notification resource.

- [ ] **Step 4: Render the Bootstrap dropdown**

Use a `<button>` toggle, list items with criticality icon/text, `<time>`, unread marker and a footer link. If preview permission is absent but workspace access exists, retain the original direct link without dropdown. Empty state: `Nenhuma notificação recente.`

- [ ] **Step 5: Run GREEN**

Run: `pytest -q tests/test_workspace_ui.py tests/test_template_language.py tests/test_responsive_layout_css.py`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the task**

```bash
git add base/ui/presentation.py base/ui/context_processors.py templates/includes/components/notification_dropdown.html templates/base.html static/css/app.css tests/test_workspace_ui.py tests/test_template_language.py tests/test_responsive_layout_css.py
git commit -m "feat: exibir prévia autorizada de notificações"
```

---

### Task 6: Estados e ícones centralizados

**Files:**
- Modify: `base/ui/presentation.py`
- Modify: `base/ui/views.py:174-206,842-852,932-940`
- Create: `templates/includes/components/status_badge.html`
- Modify: `templates/app/resource_list.html:73-80`
- Modify: `templates/app/resource_detail.html`
- Remove: `templates/includes/status_badge.html`
- Test: `tests/test_design_system_components.py`
- Test: `tests/test_app_ui.py`

**Interfaces:**
- Produces: `StatusPresentation(label, tone, icon)` and `resolve_status(value)`.
- Compatibility: `_status_tone(value)` delegates to `resolve_status(value).tone` until all internal callers migrate.

- [ ] **Step 1: Write failing semantic mapping tests**

```python
@pytest.mark.parametrize(
    ('label', 'tone', 'icon'),
    [
        ('Liberado', 'success', 'feather-check-circle'),
        ('Em análise', 'warning', 'feather-clock'),
        ('OOS', 'danger', 'feather-alert-triangle'),
        ('Em processamento', 'info', 'feather-loader'),
        ('Arquivado', 'secondary', 'feather-archive'),
    ],
)
def test_status_resolution_is_accent_insensitive_and_semantic(label, tone, icon):
    result = resolve_status(label)
    assert (result.tone, result.icon) == (tone, icon)
```

Add HTML assertions that status badges contain visible labels, icons with `aria-hidden="true"` and never rely on a color-only circle.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_design_system_components.py tests/test_app_ui.py -k status`

Expected: failure because the resolved icon contract does not exist.

- [ ] **Step 3: Implement normalized precedence rules**

Normalize with `unicodedata.normalize('NFKD', value)`, remove combining marks and lowercase. Check danger tokens before success tokens so `não aprovado` cannot become success. Return a frozen `StatusPresentation` with the original visible label.

- [ ] **Step 4: Migrate list/detail templates**

Each status cell receives `status = resolve_status(value)`. Include the single component with `status.label`, `status.tone` and `status.icon`. Remove the duplicate legacy include after `rg` confirms no remaining consumer.

- [ ] **Step 5: Run GREEN**

Run: `pytest -q tests/test_design_system_components.py tests/test_app_ui.py tests/test_template_language.py`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the task**

```bash
git add base/ui/presentation.py base/ui/views.py templates/includes/components/status_badge.html templates/app/resource_list.html templates/app/resource_detail.html tests/test_design_system_components.py tests/test_app_ui.py tests/test_template_language.py
git rm templates/includes/status_badge.html
git commit -m "refactor: centralizar estados visuais e ícones"
```

---

### Task 7: Dashboards e gráficos acessíveis

**Files:**
- Modify: `base/ui/views.py:318-574`
- Modify: `templates/dashboards/hub.html`
- Modify: `static/js/dashboard-hub.js`
- Modify: `static/css/app.css`
- Test: `tests/test_dashboard_hub.py`
- Test: `tests/test_design_system_components.py`

**Interfaces:**
- Dashboard context adds `generated_at` and `chart_rows` pairing label/value.
- Existing `dashboard_data.chart` JSON contract remains stable for ApexCharts.

- [ ] **Step 1: Write failing dashboard accessibility tests**

Assert the response contains `<time datetime=`, `Atualizado em`, `Resumo textual do gráfico`, all chart labels and values, and does not contain `Atualizado agora`. Assert the chart container has `role="img"` and a dashboard-specific accessible label.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_dashboard_hub.py tests/test_design_system_components.py -k dashboard`

Expected: failure because timestamp and accessible chart rows are absent.

- [ ] **Step 3: Build timestamp and accessible rows server-side**

Set `generated_at = timezone.localtime()` in context. After `_build_data`, create `chart_rows = tuple(zip(chart['labels'], chart['series'], strict=False))`. Preserve the JSON payload unchanged.

- [ ] **Step 4: Render and initialize the accessible chart**

Replace fixed copy with `<time datetime="{{ generated_at|date:'c' }}">Atualizado em {{ generated_at|date:'d/m/Y H:i' }}</time>`. Add a compact table under `<details>` labelled `Resumo textual do gráfico`. In JavaScript, preserve the empty-state behavior and set chart locale-visible series name to `Registros`.

- [ ] **Step 5: Run GREEN**

Run: `pytest -q tests/test_dashboard_hub.py tests/test_design_system_components.py tests/test_template_language.py`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the task**

```bash
git add base/ui/views.py templates/dashboards/hub.html static/js/dashboard-hub.js static/css/app.css tests/test_dashboard_hub.py tests/test_design_system_components.py tests/test_template_language.py
git commit -m "feat: tornar dashboards operacionais e acessíveis"
```

---

### Task 8: Trilha de auditoria persistida

**Files:**
- Create: `base/ui/audit.py`
- Modify: `base/ui/presentation.py`
- Modify: `base/ui/views.py:920-952`
- Modify: `templates/app/includes/audit_trail.html`
- Modify: `templates/app/resource_detail.html`
- Test: `tests/test_app_ui.py`
- Test: `tests/test_documents.py`

**Interfaces:**
- Produces: `AuditEntry` and `get_audit_entries(obj, limit=25)`.
- `ControlledDocument` adapter uses `obj.audit_trail.select_related('actor')`.
- Generic adapter uses `RecordStatusHistory` by app label, class name and primary key.

- [ ] **Step 1: Write failing persisted-audit tests**

Create a `ControlledDocument` and two real `DocumentAuditTrail` rows. Request `/app/documents/controlled-documents/<pk>/` and assert both actions, actor, snapshot, reason and persisted timestamps are rendered newest first. Assert `Operador Sistema`, `2026-07-19 14:30:22`, `{% now` and `Exportar relatório` are absent from the template.

Create a `CapaRecord` plus `RecordStatusHistory.record_transition(...)`; assert the CAPA detail shows previous/new status and real actor. A resource with no history must show `Nenhum evento de auditoria disponível para este registro.`

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_app_ui.py -k audit tests/test_documents.py -k audit`

Expected: failure because the include still contains fixed rows.

- [ ] **Step 3: Implement immutable audit adapters**

```python
@dataclass(frozen=True)
class AuditEntry:
    occurred_at: datetime
    actor_label: str
    action_label: str
    details: str
    reason: str
    status: StatusPresentation
```

For documents, map `get_action_display()`, `snapshot`, `reason`, actor full name/email and `created_at`. For generic histories, map `action`, `previous_status → new_status`, `reason`, actor and `occurred_at`. Return a tuple ordered descending and limited to 25.

- [ ] **Step 4: Replace the demonstrative include**

Render a captioned responsive table with `<time datetime>`, actor, action/status component, details and reason. Render `—` for absent actor/reason and the approved empty state for no entries. Keep the region read-only and remove the fake export button.

- [ ] **Step 5: Run GREEN and regulatory regression**

Run: `pytest -q tests/test_app_ui.py tests/test_documents.py tests/test_compliance.py tests/test_template_language.py`

Expected: all selected tests pass and no demonstrative row remains.

- [ ] **Step 6: Commit the task**

```bash
git add base/ui/audit.py base/ui/presentation.py base/ui/views.py templates/app/includes/audit_trail.html templates/app/resource_detail.html tests/test_app_ui.py tests/test_documents.py tests/test_compliance.py tests/test_template_language.py
git commit -m "feat: apresentar trilha de auditoria persistida"
```

---

### Task 9: Documentação, inspeção visual e verificação final

**Files:**
- Modify: `TEMPLATES.md`
- Modify: `docs/architecture/templates.md`
- Modify: `docs/architecture/workflow.md`
- Modify: `docs/architecture/audits.md`
- Test: `tests/test_template_language.py`
- Test: relevant suite

**Interfaces:**
- Documents the reusable component contract, permission boundaries and real audit sources.

- [ ] **Step 1: Write the failing documentation assertions**

Add assertions that `TEMPLATES.md` names `ProgressMetric`, `DeadlineItem`, `advanced_filter_fields`, `NotificationPreview`, `StatusPresentation` and `AuditEntry`, and states that all visible copy must use Portuguese with correct accents.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_template_language.py tests/test_workspace_ui.py -k 'documentation or ptbr'`

Expected: failure because the new contracts are undocumented.

- [ ] **Step 3: Update documentation**

Document component purpose, input contract, permission ownership, empty states, audit source mapping and examples of PT-BR copy. Do not modify the user's dirty architecture files `foundation.md` and `inventory.md`.

- [ ] **Step 4: Run static and automated verification**

```bash
python manage.py check
ruff check base/ui tests/test_design_system_components.py
pytest -q tests/test_design_system_components.py tests/test_workspace_ui.py tests/test_dashboard_hub.py tests/test_app_ui.py tests/test_responsive_layout_css.py tests/test_template_language.py tests/test_documents.py tests/test_compliance.py
```

Expected: Django check reports no issues, Ruff exits 0 and all selected tests pass.

- [ ] **Step 5: Inspect UI visually**

Run the SQLite development profile, authenticate with a local test account and capture desktop/mobile screenshots of:

- cockpit operacional;
- cockpit de qualidade;
- central de workflow;
- lista de ordens com filtros avançados;
- detalhe de ordem com layout 8+4;
- dashboard executivo;
- detalhe de documento com auditoria real.

Verify light/dark themes, 1440 px, 768 px and 375 px widths, keyboard focus, Portuguese accents, empty states and absence of horizontal overflow. Correct visual defects with scoped CSS and rerun responsive tests.

- [ ] **Step 6: Run the broader regression suite**

Run: `pytest -q`

Expected: complete suite passes. If an unrelated preexisting failure appears, record the exact test and prove it also fails on the pre-task commit before classifying it as unrelated.

- [ ] **Step 7: Review the final diff and commit documentation**

```bash
git diff --check
git status --short
git add TEMPLATES.md docs/architecture/templates.md docs/architecture/workflow.md docs/architecture/audits.md tests/test_template_language.py
git commit -m "docs: documentar componentes operacionais do design system"
```

Expected: only the user's previously dirty files remain uncommitted; every file created or changed by this plan is committed.
