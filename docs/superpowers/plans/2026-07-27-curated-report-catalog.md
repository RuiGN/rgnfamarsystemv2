# Curated Report Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace simulated report execution with a secure real execution engine and deliver 15 system-managed financial, fiscal, inventory, procurement, and production reports in PDF, XLSX, and CSV.

**Architecture:** Resolve reports through an allow-listed Python registry rather than user-supplied model paths or SQL. Executors return a normalized tabular dataset; format renderers produce bytes; `ReportExecution` stores the artifact in `ProtectedFile` with hash, row count, audit metadata, and controlled download.

**Tech Stack:** Python 3.13, Django 5.2.16, Django REST Framework 3.17.1, PostgreSQL ORM, Celery 5.6.0, ReportLab 4.4.6, openpyxl 3.1.5, Bootstrap 5, pytest-django.

## Global Constraints

- Deliver exactly 15 initial reports from the approved specification.
- Do not execute arbitrary SQL, model paths, fields, imports, or expressions from database JSON.
- System-managed report technical configuration is immutable through operational APIs and UI.
- Enforce module/report permissions before querying or downloading.
- Store generated output as a protected file with SHA-256 hash and audit trail.
- Preserve existing report definitions, schedules, executions, and notifications.
- PDF, XLSX, and CSV output must contain real query results, not estimated row counts.
- Do not modify or delete user-owned untracked files.

---

## File Structure

- `reports/contracts.py`: immutable dataset, column, filter, and execution context types.
- `reports/registry.py`: explicit executor registration and resolution.
- `reports/filters.py`: shared typed date/status/entity filter parsing.
- `reports/executors/finance.py`: four financial datasets.
- `reports/executors/fiscal.py`: three fiscal datasets.
- `reports/executors/inventory.py`: three inventory/traceability datasets.
- `reports/executors/procurement.py`: two procurement datasets.
- `reports/executors/production.py`: three production/PCP datasets.
- `reports/apps.py`: deterministic executor registration at Django startup.
- `reports/renderers.py`: CSV, XLSX, and PDF byte renderers.
- `reports/services.py`: execution lifecycle, authorization, storage, and audit.
- `reports/catalog.py`: canonical metadata for all 15 reports.
- `reports/models.py`: system-managed/executor fields and protected result relation.
- `reports/migrations/0004_curated_report_catalog.py`: schema plus idempotent catalog seed.
- `reports/serializers.py`, `reports/views.py`, `reports/urls.py`: safe REST execution/download.
- `base/ui/urls.py`, `base/ui/views.py`: curated report catalog/filter form.
- `templates/app/report_catalog.html`, `templates/app/report_run.html`: operational UI.
- `requirements.txt`: pinned openpyxl dependency.
- `tests/test_report_engine.py`: registry, executors, formats, security, API, and UI.
- `docs/architecture/reports.md`, `docs/pdf/manual_usuario.md`: operating documentation.

### Task 1: Typed report contracts and allow-listed registry

**Files:**
- Create: `reports/contracts.py`
- Create: `reports/registry.py`
- Create: `reports/filters.py`
- Create: `reports/executors/__init__.py`
- Modify: `reports/apps.py`
- Test: `tests/test_report_engine.py`

**Interfaces:**
- Produces: `ReportColumn`, `ReportDataset`, `ReportContext`, `ReportExecutor`, `register_executor()`, `get_executor()`, and `normalize_report_filters()`.
- Consumes: only primitive filter values and authenticated Django users.

- [ ] **Step 1: Write failing contract and registry tests**

```python
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError


def test_report_registry_resolves_only_registered_keys():
    from reports.contracts import ReportColumn, ReportDataset
    from reports.registry import get_executor, register_executor

    @register_executor('tests.example')
    def example(context):
        return ReportDataset(
            title='Exemplo',
            columns=(ReportColumn('amount', 'Valor', 'decimal'),),
            rows=({'amount': Decimal('10.0000')},),
        )

    assert get_executor('tests.example').__name__ == 'example'
    with pytest.raises(ValidationError):
        get_executor('tests.unknown')


def test_filter_normalization_rejects_unknown_and_inverted_period():
    from reports.filters import normalize_report_filters

    with pytest.raises(ValidationError) as unknown:
        normalize_report_filters({'sql': 'select 1'}, allowed=('period_start',))
    assert 'filters' in unknown.value.message_dict

    with pytest.raises(ValidationError) as inverted:
        normalize_report_filters(
            {'period_start': '2026-07-31', 'period_end': '2026-07-01'},
            allowed=('period_start', 'period_end'),
        )
    assert 'period_end' in inverted.value.message_dict

    result = normalize_report_filters(
        {'period_start': '2026-07-01'},
        allowed=('period_start',),
    )
    assert result['period_start'] == date(2026, 7, 1)
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py -k "registry or filter_normalization"
```

Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement contracts**

Create `reports/contracts.py`:

```python
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from django.contrib.auth.base_user import AbstractBaseUser


ColumnKind = Literal['text', 'date', 'datetime', 'decimal', 'integer', 'status']


@dataclass(frozen=True, slots=True)
class ReportColumn:
    key: str
    label: str
    kind: ColumnKind = 'text'


@dataclass(frozen=True, slots=True)
class ReportDataset:
    title: str
    columns: tuple[ReportColumn, ...]
    rows: Iterable[Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class ReportContext:
    filters: Mapping[str, Any]
    user: AbstractBaseUser


class ReportExecutor(Protocol):
    def __call__(self, context: ReportContext) -> ReportDataset: ...
```

Create `reports/registry.py`:

```python
from django.core.exceptions import ValidationError

from reports.contracts import ReportExecutor


_EXECUTORS: dict[str, ReportExecutor] = {}


def register_executor(key: str):
    def decorator(executor: ReportExecutor) -> ReportExecutor:
        if not key or key in _EXECUTORS:
            raise RuntimeError(f'Executor de relatório duplicado: {key}')
        _EXECUTORS[key] = executor
        return executor
    return decorator


def get_executor(key: str) -> ReportExecutor:
    try:
        return _EXECUTORS[key]
    except KeyError as exc:
        raise ValidationError(
            {'executor_key': 'Executor de relatório não registrado.'}
        ) from exc
```

Create `reports/filters.py` with:

```python
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date


DATE_FILTERS = {'period_start', 'period_end', 'due_start', 'due_end'}


def normalize_report_filters(filters, *, allowed, required=()):
    if not isinstance(filters or {}, dict):
        raise ValidationError({'filters': 'Filtros devem ser um objeto.'})
    unknown = sorted(set(filters) - set(allowed))
    missing = sorted(set(required) - set(filters))
    errors = {}
    if unknown:
        errors['filters'] = f'Filtros não suportados: {", ".join(unknown)}.'
    if missing:
        errors['required_filters'] = f'Filtros obrigatórios ausentes: {", ".join(missing)}.'
    normalized = {}
    for key, value in filters.items():
        if key in DATE_FILTERS and value not in (None, ''):
            parsed = parse_date(str(value))
            if parsed is None:
                errors[key] = 'Informe uma data válida.'
            else:
                normalized[key] = parsed
        elif value not in (None, ''):
            normalized[key] = value
    start = normalized.get('period_start')
    end = normalized.get('period_end')
    if start and end and end < start:
        errors['period_end'] = 'Data final não pode ser anterior à inicial.'
    if errors:
        raise ValidationError(errors)
    return normalized
```

Import the five executor modules, once created, from
`reports/executors/__init__.py`; do not dynamically import a module name from
database content.

Load that package from `ReportsConfig.ready()`:

```python
def ready(self):
    from reports import executors  # noqa: F401
```

- [ ] **Step 4: Run tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py -k "registry or filter_normalization"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add reports/contracts.py reports/registry.py reports/filters.py reports/executors/__init__.py reports/apps.py tests/test_report_engine.py
git commit -m "feat: add safe report executor registry"
```

### Task 2: Fifteen real report executors

**Files:**
- Create: `reports/executors/finance.py`
- Create: `reports/executors/fiscal.py`
- Create: `reports/executors/inventory.py`
- Create: `reports/executors/procurement.py`
- Create: `reports/executors/production.py`
- Modify: `reports/executors/__init__.py`
- Test: `tests/test_report_engine.py`

**Interfaces:**
- Consumes: `ReportContext` with normalized `period_start`, `period_end`, `status`, `product`, `lot`, `supplier`, and `customer` filters.
- Produces: the 15 executor keys listed below, each returning `ReportDataset`.

- [ ] **Step 1: Write parameterized failing executor tests**

```python
@pytest.mark.django_db
@pytest.mark.parametrize(
    ('key', 'expected_title'),
    [
        ('finance.receivables_open_overdue', 'Contas a receber em aberto e vencidas'),
        ('finance.payables_open_overdue', 'Contas a pagar em aberto e vencidas'),
        ('finance.cash_flow', 'Fluxo de caixa realizado e projetado'),
        ('finance.period_result', 'Resultado financeiro por período'),
        ('fiscal.documents', 'Documentos fiscais por período e situação'),
        ('fiscal.tax_assessment', 'Apuração de tributos'),
        ('fiscal.books', 'Livro de entradas e saídas'),
        ('inventory.position', 'Posição de estoque'),
        ('inventory.expiry', 'Lotes próximos do vencimento ou vencidos'),
        ('inventory.genealogy', 'Genealogia e rastreabilidade de lotes'),
        ('procurement.open_delayed_orders', 'Pedidos de compra abertos ou atrasados'),
        ('procurement.receipt_supplier_performance', 'Divergências de recebimento e fornecedores'),
        ('production.orders_status_delay', 'Ordens de produção por situação e atraso'),
        ('production.consumption_variance', 'Consumo planejado versus realizado'),
        ('production.yield_loss_cost', 'Rendimento, perdas e custo por ordem'),
    ],
)
def test_curated_executor_returns_real_rows(key, expected_title, report_context, seeded_domains):
    import reports.executors  # noqa: F401
    from reports.registry import get_executor

    dataset = get_executor(key)(report_context)
    rows = list(dataset.rows)
    assert dataset.title == expected_title
    assert dataset.columns
    assert rows
```

- [ ] **Step 2: Verify failures**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py -k "curated_executor"
```

Expected: FAIL because the executor modules do not exist.

- [ ] **Step 3: Implement the shared executor pattern**

Every executor must:

1. call `normalize_report_filters()` with an explicit allow-list;
2. build a fixed ORM queryset;
3. apply only explicit `if filter_value` branches;
4. return dictionaries whose keys exactly match `ReportColumn.key`;
5. never call `apps.get_model()`, `raw()`, `extra()`, `eval()`, or `exec()`.

Use this complete pattern for the receivables executor:

```python
@register_executor('finance.receivables_open_overdue')
def receivables_open_overdue(context):
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'customer'),
    )
    queryset = FinancialTitle.objects.filter(
        title_type=FinancialTitle.TitleType.RECEIVABLE,
        status__in=(
            FinancialTitle.Status.PENDING,
            FinancialTitle.Status.APPROVED,
            FinancialTitle.Status.PARTIALLY_SETTLED,
            FinancialTitle.Status.OVERDUE,
        ),
    ).select_related('partner')
    if start := filters.get('period_start'):
        queryset = queryset.filter(due_date__gte=start)
    if end := filters.get('period_end'):
        queryset = queryset.filter(due_date__lte=end)
    if status := filters.get('status'):
        queryset = queryset.filter(status=status)
    if customer := filters.get('customer'):
        queryset = queryset.filter(partner_id=customer)
    rows = (
        {
            'title_number': item.title_number,
            'partner': item.partner.legal_name,
            'due_date': item.due_date,
            'status': item.get_status_display(),
            'original_amount': item.original_amount,
            'open_amount': item.open_amount,
        }
        for item in queryset.order_by('due_date', 'title_number')
    )
    return ReportDataset(
        title='Contas a receber em aberto e vencidas',
        columns=(
            ReportColumn('title_number', 'Título'),
            ReportColumn('partner', 'Cliente'),
            ReportColumn('due_date', 'Vencimento', 'date'),
            ReportColumn('status', 'Situação', 'status'),
            ReportColumn('original_amount', 'Valor original', 'decimal'),
            ReportColumn('open_amount', 'Valor em aberto', 'decimal'),
        ),
        rows=rows,
    )
```

Implement the other keys with these fixed sources and row contracts:

```python
EXECUTOR_ROW_CONTRACTS = {
    'finance.payables_open_overdue': (
        FinancialTitle,
        ('title_number', 'partner', 'due_date', 'status', 'original_amount', 'open_amount'),
    ),
    'finance.cash_flow': (
        CashFlowEntry,
        ('cash_date', 'flow_type', 'direction', 'account', 'description', 'amount'),
    ),
    'finance.period_result': (
        CashFlowEntry,
        ('period', 'inflow', 'outflow', 'net_result'),
    ),
    'fiscal.documents': (
        FiscalDocument,
        ('issue_date', 'number', 'series', 'direction', 'partner', 'status', 'total_amount'),
    ),
    'fiscal.tax_assessment': (
        TaxAssessmentPeriod,
        ('period', 'tax_kind', 'debit_amount', 'credit_amount', 'amount_due', 'status'),
    ),
    'fiscal.books': (
        FiscalBookEntry,
        ('entry_date', 'book_type', 'document', 'partner', 'tax_base', 'tax_amount'),
    ),
    'inventory.position': (
        StockBalance,
        ('product', 'lot', 'expiry_date', 'warehouse', 'location', 'quality_status', 'quantity', 'reserved', 'available'),
    ),
    'inventory.expiry': (
        StockLot,
        ('product', 'lot', 'expiry_date', 'days_to_expiry', 'quality_status', 'quantity'),
    ),
    'inventory.genealogy': (
        StockLotGenealogy,
        ('input_product', 'input_lot', 'output_product', 'output_lot', 'relation_type', 'quantity', 'production_order'),
    ),
    'procurement.open_delayed_orders': (
        PurchaseOrder,
        ('order_number', 'supplier', 'issue_date', 'expected_delivery_date', 'status', 'total_amount', 'days_late'),
    ),
    'procurement.receipt_supplier_performance': (
        PurchaseReceiptItem,
        ('supplier', 'receipt', 'product', 'received', 'accepted', 'rejected', 'acceptance_percent'),
    ),
    'production.orders_status_delay': (
        ProductionOrder,
        ('order_number', 'product', 'priority', 'responsible', 'scheduled_end', 'status', 'days_late'),
    ),
    'production.consumption_variance': (
        MaterialConsumption,
        ('order_number', 'material', 'lot', 'planned', 'actual', 'loss', 'returned', 'variance'),
    ),
    'production.yield_loss_cost': (
        ProductionOrder,
        ('order_number', 'product', 'planned', 'actual_yield', 'yield_percent', 'loss', 'rework', 'actual_cost', 'cost_variance'),
    ),
}
```

The constant belongs only in the test as a coverage oracle. Production files
define explicit functions and fixed columns; they do not dynamically construct
queries from this mapping.

- [ ] **Step 4: Add numeric aggregation tests**

```python
@pytest.mark.django_db
def test_period_result_aggregates_realized_inflow_and_outflow(report_context, cash_flow_entries):
    from reports.executors.finance import period_result

    dataset = period_result(report_context)
    row = list(dataset.rows)[0]
    assert row['inflow'] == Decimal('1000.0000')
    assert row['outflow'] == Decimal('300.0000')
    assert row['net_result'] == Decimal('700.0000')


@pytest.mark.django_db
def test_consumption_variance_uses_actual_minus_planned(report_context, material_consumption):
    from reports.executors.production import consumption_variance

    row = list(consumption_variance(report_context).rows)[0]
    assert row['variance'] == (
        material_consumption.actual_quantity - material_consumption.planned_quantity
    )
```

- [ ] **Step 5: Run all executor tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py -k "executor or period_result or consumption_variance"
```

Expected: PASS with all 15 parameter cases.

- [ ] **Step 6: Commit**

```bash
git add reports/executors tests/test_report_engine.py
git commit -m "feat: add fifteen curated report executors"
```

### Task 3: PDF, XLSX, and CSV rendering

**Files:**
- Create: `reports/renderers.py`
- Modify: `requirements.txt`
- Test: `tests/test_report_engine.py`

**Interfaces:**
- Consumes: `ReportDataset`.
- Produces: `RenderedReport(content: bytes, mime_type: str, extension: str)` through `render_report(dataset, export_format)`.

- [ ] **Step 1: Pin the XLSX dependency**

Add this alphabetically to `requirements.txt`:

```text
openpyxl==3.1.5
```

Install it into the active virtual environment:

```bash
.venv/bin/pip install openpyxl==3.1.5
```

Expected: installation exits 0.

- [ ] **Step 2: Write failing renderer tests**

```python
from io import BytesIO

from openpyxl import load_workbook
from pypdf import PdfReader


@pytest.mark.parametrize(
    ('export_format', 'signature'),
    [('csv', b'\xef\xbb\xbf'), ('xlsx', b'PK'), ('pdf', b'%PDF')],
)
def test_render_report_creates_valid_formats(sample_dataset, export_format, signature):
    from reports.renderers import render_report

    rendered = render_report(sample_dataset, export_format)
    assert rendered.content.startswith(signature)
    assert rendered.extension == export_format

    if export_format == 'xlsx':
        workbook = load_workbook(BytesIO(rendered.content), read_only=True)
        assert workbook.active['A1'].value == 'Título'
    if export_format == 'pdf':
        assert len(PdfReader(BytesIO(rendered.content)).pages) >= 1
```

- [ ] **Step 3: Verify failures**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py -k "valid_formats"
```

Expected: FAIL because `reports.renderers` does not exist.

- [ ] **Step 4: Implement renderers**

Create:

```python
import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO, StringIO

from django.core.exceptions import ValidationError
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle


@dataclass(frozen=True, slots=True)
class RenderedReport:
    content: bytes
    mime_type: str
    extension: str


def _cell(value):
    if value is None:
        return ''
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f'{value:.4f}'
    return str(value)


def render_report(dataset, export_format):
    rows = list(dataset.rows)
    matrix = [
        [column.label for column in dataset.columns],
        *[[_cell(row.get(column.key)) for column in dataset.columns] for row in rows],
    ]
    if export_format == 'csv':
        stream = StringIO()
        writer = csv.writer(stream, delimiter=';')
        writer.writerows(matrix)
        return RenderedReport(
            b'\xef\xbb\xbf' + stream.getvalue().encode('utf-8'),
            'text/csv; charset=utf-8',
            'csv',
        )
    if export_format == 'xlsx':
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet(title='Relatório')
        for row in matrix:
            sheet.append(row)
        stream = BytesIO()
        workbook.save(stream)
        return RenderedReport(
            stream.getvalue(),
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'xlsx',
        )
    if export_format == 'pdf':
        stream = BytesIO()
        document = SimpleDocTemplate(stream, pagesize=landscape(A4))
        table = Table(matrix, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#243447')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
        ]))
        document.build([table])
        return RenderedReport(stream.getvalue(), 'application/pdf', 'pdf')
    raise ValidationError({'export_format': 'Formato de exportação não suportado.'})
```

- [ ] **Step 5: Run renderer tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py -k "valid_formats"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt reports/renderers.py tests/test_report_engine.py
git commit -m "feat: render reports as pdf xlsx and csv"
```

### Task 4: Real execution lifecycle and protected artifacts

**Files:**
- Modify: `reports/models.py`
- Create: `reports/services.py`
- Create: `reports/migrations/0004_report_execution_engine.py`
- Modify: `reports/tasks.py`
- Test: `tests/test_report_engine.py`
- Test: `tests/test_reports.py`

**Interfaces:**
- Consumes: registry, executors, renderers, and `ProtectedFile.store_encrypted_content()`.
- Produces: `execute_report(execution, user) -> ReportExecution`, `ReportDefinition.executor_key`, `ReportDefinition.is_system_managed`, and `ReportExecution.result_file`.

- [ ] **Step 1: Write failing lifecycle tests**

```python
@pytest.mark.django_db
def test_execution_stores_real_protected_artifact(report_definition, report_user):
    from reports.services import execute_report

    execution = report_definition.create_execution(
        filters={'period_start': '2026-07-01', 'period_end': '2026-07-31'},
        export_format='csv',
        requested_by=report_user,
    )
    execute_report(execution, report_user)
    execution.refresh_from_db()

    assert execution.status == execution.Status.COMPLETED
    assert execution.result_file.file_type == execution.result_file.FileType.REPORT
    assert execution.content_hash == execution.result_file.content_hash
    assert execution.row_count > 0


@pytest.mark.django_db
def test_system_definition_rejects_technical_mutation(report_definition):
    report_definition.executor_key = 'tests.unknown'
    with pytest.raises(ValidationError):
        report_definition.full_clean()


@pytest.mark.django_db
def test_execution_requires_report_and_domain_permissions(
    report_definition, report_user_without_finance_permission
):
    from django.core.exceptions import PermissionDenied
    from reports.services import execute_report

    execution = report_definition.create_execution(
        filters={},
        export_format='csv',
        requested_by=report_user_without_finance_permission,
    )
    with pytest.raises(PermissionDenied):
        execute_report(execution, report_user_without_finance_permission)
    execution.refresh_from_db()
    assert execution.status == execution.Status.PENDING
```

- [ ] **Step 2: Verify failures**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py -k "protected_artifact or technical_mutation"
```

Expected: FAIL because fields and service are absent.

- [ ] **Step 3: Add schema fields and immutable validation**

Add:

```python
# ReportDefinition
executor_key = models.CharField('executor registrado', max_length=120, blank=True)
is_system_managed = models.BooleanField('gerenciado pelo sistema', default=False)
filter_schema = models.JSONField('esquema de filtros', default=dict, blank=True)
required_permission = models.CharField(
    'permissão de domínio exigida', max_length=120, blank=True
)

# ReportExecution
result_file = models.ForeignKey(
    'files.ProtectedFile',
    on_delete=models.PROTECT,
    related_name='report_executions',
    null=True,
    blank=True,
    verbose_name='arquivo gerado',
)
```

Add `PROCUREMENT = 'procurement', 'Compras'` to
`ReportDefinition.Module`. The migration must alter every report-module choice
field that reuses this enum.

In `ReportDefinition.clean()` require a registered executor for system-managed
definitions. In `ReportDefinitionSerializer`, expose technical fields as
read-only and reject updates to `code`, `executor_key`, `query_config`,
`filter_schema`, `required_permission`, and `is_system_managed` when the
instance is system-managed.

- [ ] **Step 4: Implement the execution service**

Create:

```python
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from files.models import ProtectedFile
from reports.contracts import ReportContext, ReportDataset
from reports.registry import get_executor
from reports.renderers import render_report


def execute_report(execution, user):
    if not user.has_perm('reports.add_reportexecution'):
        raise PermissionDenied
    with transaction.atomic():
        execution = execution.__class__.objects.select_for_update().select_related(
            'definition', 'requested_by', 'result_file'
        ).get(pk=execution.pk)
        if execution.status not in {execution.Status.PENDING, execution.Status.RUNNING}:
            raise ValidationError(
                {'status': 'A execução não pode ser processada neste estado.'}
            )
        if (
            execution.definition.required_permission
            and not user.has_perm(execution.definition.required_permission)
        ):
            raise PermissionDenied
        execution.status = execution.Status.RUNNING
        execution.started_at = execution.started_at or timezone.now()
        execution.save(update_fields=['status', 'started_at', 'updated_at'])
    protected_file = None
    try:
        executor = get_executor(execution.definition.executor_key)
        dataset = executor(ReportContext(filters=execution.filters, user=user))
        rows = tuple(dataset.rows)
        rendered = render_report(
            ReportDataset(title=dataset.title, columns=dataset.columns, rows=rows),
            execution.export_format,
        )
        protected_file = ProtectedFile.objects.create(
            source_module=ProtectedFile.SourceModule.OPERATIONAL,
            source_model='reports.ReportExecution',
            source_record_id=str(execution.pk),
            file_type=ProtectedFile.FileType.REPORT,
            origin=ProtectedFile.Origin.SYSTEM,
            criticality=ProtectedFile.Criticality.MEDIUM,
            confidentiality=ProtectedFile.Confidentiality.INTERNAL,
            title=execution.definition.title,
            file_name=f'{execution.execution_number}.{rendered.extension}',
            file_reference=f'reports/{execution.execution_number}.{rendered.extension}',
            mime_type=rendered.mime_type,
            file_size=0,
            content_hash='sha256:pending',
            responsible=user,
            uploaded_by=user,
        )
        protected_file.store_encrypted_content(
            rendered.content,
            file_name=protected_file.file_name,
            mime_type=rendered.mime_type,
            user=user,
        )
        with transaction.atomic():
            execution = execution.__class__.objects.select_for_update().get(pk=execution.pk)
            execution.result_file = protected_file
            execution.result_reference = protected_file.file_reference
            execution.content_hash = protected_file.content_hash
            execution.row_count = len(rows)
            execution.status = execution.Status.COMPLETED
            execution.completed_at = timezone.now()
            execution.error_message = ''
            execution.save()
        execution.notify_completion()
        return execution
    except Exception as exc:
        if protected_file and protected_file.status != protected_file.Status.DELETED:
            protected_file.delete_secure(
                reason='Artefato órfão após falha da execução.',
                user=user,
            )
        execution.__class__.objects.filter(pk=execution.pk).update(
            status=execution.Status.FAILED,
            completed_at=timezone.now(),
            error_message=str(exc)[:4000],
            updated_at=timezone.now(),
        )
        raise
```

Update `ReportExecution.run()` to delegate to this service, and keep the Celery
task calling `execution.run()`.

- [ ] **Step 5: Generate migration and run lifecycle regressions**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py makemigrations reports
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py tests/test_reports.py
```

Expected: migration created and tests PASS.

- [ ] **Step 6: Commit**

```bash
git add reports/models.py reports/services.py reports/tasks.py reports/migrations/0004_*.py tests/test_report_engine.py tests/test_reports.py
git commit -m "feat: execute reports into protected artifacts"
```

### Task 5: Idempotent curated catalog seed

**Files:**
- Create: `reports/catalog.py`
- Create: `reports/migrations/0005_seed_curated_report_catalog.py`
- Test: `tests/test_report_engine.py`

**Interfaces:**
- Consumes: executor keys from Task 2.
- Produces: `CURATED_REPORTS` and `sync_curated_report_catalog(ReportDefinition)`.

- [ ] **Step 1: Write failing catalog tests**

```python
@pytest.mark.django_db
def test_catalog_sync_creates_exactly_fifteen_system_reports():
    from reports.catalog import sync_curated_report_catalog
    from reports.models import ReportDefinition

    sync_curated_report_catalog(ReportDefinition)
    sync_curated_report_catalog(ReportDefinition)

    definitions = ReportDefinition.objects.filter(is_system_managed=True)
    assert definitions.count() == 15
    assert definitions.values('code').distinct().count() == 15
    assert all(definition.executor_key for definition in definitions)
```

- [ ] **Step 2: Verify failure**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py -k "catalog_sync"
```

Expected: FAIL because `reports.catalog` does not exist.

- [ ] **Step 3: Define canonical catalog entries**

Create `CURATED_REPORTS` as 15 dictionaries with these immutable
`code -> executor_key` pairs:

```python
CURATED_REPORT_KEYS = {
    'REL-FIN-001': 'finance.receivables_open_overdue',
    'REL-FIN-002': 'finance.payables_open_overdue',
    'REL-FIN-003': 'finance.cash_flow',
    'REL-FIN-004': 'finance.period_result',
    'REL-FIS-001': 'fiscal.documents',
    'REL-FIS-002': 'fiscal.tax_assessment',
    'REL-FIS-003': 'fiscal.books',
    'REL-EST-001': 'inventory.position',
    'REL-EST-002': 'inventory.expiry',
    'REL-EST-003': 'inventory.genealogy',
    'REL-COM-001': 'procurement.open_delayed_orders',
    'REL-COM-002': 'procurement.receipt_supplier_performance',
    'REL-PRO-001': 'production.orders_status_delay',
    'REL-PRO-002': 'production.consumption_variance',
    'REL-PRO-003': 'production.yield_loss_cost',
}
```

Define the remaining metadata explicitly:

```python
CURATED_REPORT_METADATA = {
    'REL-FIN-001': ('Contas a receber em aberto e vencidas', 'finance', 'operational', ()),
    'REL-FIN-002': ('Contas a pagar em aberto e vencidas', 'finance', 'operational', ()),
    'REL-FIN-003': ('Fluxo de caixa realizado e projetado', 'finance', 'management', ('period_start', 'period_end')),
    'REL-FIN-004': ('Resultado financeiro por período', 'finance', 'management', ('period_start', 'period_end')),
    'REL-FIS-001': ('Documentos fiscais por período e situação', 'fiscal', 'operational', ('period_start', 'period_end')),
    'REL-FIS-002': ('Apuração de tributos', 'fiscal', 'management', ('period_start', 'period_end')),
    'REL-FIS-003': ('Livro de entradas e saídas', 'fiscal', 'operational', ('period_start', 'period_end')),
    'REL-EST-001': ('Posição de estoque', 'inventory', 'operational', ()),
    'REL-EST-002': ('Lotes próximos do vencimento ou vencidos', 'inventory', 'operational', ('period_end',)),
    'REL-EST-003': ('Genealogia e rastreabilidade de lotes', 'traceability', 'audit', ()),
    'REL-COM-001': ('Pedidos de compra abertos ou atrasados', 'procurement', 'operational', ()),
    'REL-COM-002': ('Divergências de recebimento e fornecedores', 'procurement', 'management', ('period_start', 'period_end')),
    'REL-PRO-001': ('Ordens de produção por situação e atraso', 'production', 'operational', ()),
    'REL-PRO-002': ('Consumo planejado versus realizado', 'production', 'management', ('period_start', 'period_end')),
    'REL-PRO-003': ('Rendimento, perdas e custo por ordem', 'production', 'management', ('period_start', 'period_end')),
}

FILTER_SCHEMAS = {
    'period_start': {'type': 'date', 'label': 'Data inicial'},
    'period_end': {'type': 'date', 'label': 'Data final'},
    'status': {'type': 'text', 'label': 'Situação'},
    'product': {'type': 'integer', 'label': 'Produto'},
    'lot': {'type': 'text', 'label': 'Lote'},
    'customer': {'type': 'integer', 'label': 'Cliente'},
    'supplier': {'type': 'integer', 'label': 'Fornecedor'},
}

MODULE_REPORT_PERMISSIONS = {
    'finance': 'finance.view_financialtitle',
    'fiscal': 'fiscal.view_fiscaldocument',
    'inventory': 'inventory.view_stockbalance',
    'traceability': 'inventory.view_stocklotgenealogy',
    'procurement': 'procurement.view_purchaseorder',
    'production': 'production.view_productionorder',
}

EXECUTOR_ALLOWED_FILTERS = {
    'finance.receivables_open_overdue': ('period_start', 'period_end', 'status', 'customer'),
    'finance.payables_open_overdue': ('period_start', 'period_end', 'status', 'supplier'),
    'finance.cash_flow': ('period_start', 'period_end', 'status'),
    'finance.period_result': ('period_start', 'period_end'),
    'fiscal.documents': ('period_start', 'period_end', 'status', 'supplier', 'customer'),
    'fiscal.tax_assessment': ('period_start', 'period_end', 'status'),
    'fiscal.books': ('period_start', 'period_end', 'status', 'supplier', 'customer'),
    'inventory.position': ('product', 'lot', 'status'),
    'inventory.expiry': ('period_end', 'product', 'lot', 'status'),
    'inventory.genealogy': ('product', 'lot'),
    'procurement.open_delayed_orders': ('status', 'supplier'),
    'procurement.receipt_supplier_performance': (
        'period_start', 'period_end', 'supplier', 'product',
    ),
    'production.orders_status_delay': ('period_start', 'period_end', 'status', 'product'),
    'production.consumption_variance': ('period_start', 'period_end', 'product', 'lot'),
    'production.yield_loss_cost': ('period_start', 'period_end', 'product'),
}


def executor_allowed_filters(executor_key):
    try:
        return EXECUTOR_ALLOWED_FILTERS[executor_key]
    except KeyError as exc:
        raise RuntimeError(f'Filtros ausentes para {executor_key}.') from exc


CURATED_REPORTS = tuple(
    {
        'code': code,
        'title': CURATED_REPORT_METADATA[code][0],
        'module': CURATED_REPORT_METADATA[code][1],
        'category': CURATED_REPORT_METADATA[code][2],
        'required_permission': MODULE_REPORT_PERMISSIONS[
            CURATED_REPORT_METADATA[code][1]
        ],
        'executor_key': executor_key,
        'allowed_export_formats': ['pdf', 'xlsx', 'csv'],
        'required_filters': list(CURATED_REPORT_METADATA[code][3]),
        'filter_schema': {
            key: FILTER_SCHEMAS[key]
            for key in (
                'period_start', 'period_end', 'status', 'product',
                'lot', 'customer', 'supplier',
            )
            if key in executor_allowed_filters(executor_key)
        },
        'query_config': {'catalog_version': 1},
        'description': CURATED_REPORT_METADATA[code][0],
        'is_active': True,
        'is_system_managed': True,
    }
    for code, executor_key in CURATED_REPORT_KEYS.items()
)
```

Implement:

```python
def sync_curated_report_catalog(report_definition_model):
    for item in CURATED_REPORTS:
        code = item['code']
        defaults = {key: value for key, value in item.items() if key != 'code'}
        report_definition_model.objects.update_or_create(code=code, defaults=defaults)
```

- [ ] **Step 4: Add data migration**

The migration calls `sync_curated_report_catalog(apps.get_model('reports',
'ReportDefinition'))`. Its reverse function is a no-op so historical executions
and schedules are never deleted.

- [ ] **Step 5: Run catalog tests and migration checks**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py -k "catalog"
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py makemigrations --check
```

Expected: PASS and `No changes detected`.

- [ ] **Step 6: Commit**

```bash
git add reports/catalog.py reports/migrations/0005_seed_curated_report_catalog.py tests/test_report_engine.py
git commit -m "feat: seed curated operational report catalog"
```

### Task 6: Catalog UI, safe execution, and download

**Files:**
- Modify: `reports/serializers.py`
- Modify: `reports/views.py`
- Modify: `reports/urls.py`
- Modify: `base/ui/urls.py`
- Modify: `base/ui/views.py`
- Modify: `base/ui/registry.py`
- Create: `templates/app/report_catalog.html`
- Create: `templates/app/report_run.html`
- Test: `tests/test_report_engine.py`
- Test: `tests/test_app_ui.py`

**Interfaces:**
- Consumes: system-managed definitions and protected result files.
- Produces: `/app/reports/catalog/`, `/app/reports/catalog/<pk>/run/`, `POST /api/reports/definitions/<pk>/run/`, and `GET /api/reports/executions/<pk>/download/`.

- [ ] **Step 1: Write failing authorization and UI tests**

```python
@pytest.mark.django_db
def test_catalog_groups_system_reports_by_module(client, report_user, curated_catalog):
    client.force_login(report_user)
    response = client.get('/app/reports/catalog/')
    assert response.status_code == 200
    assert len(response.context['report_groups']) == 5
    assert b'Campos JSON' not in response.content


@pytest.mark.django_db
def test_download_requires_report_and_file_access(api_client, completed_execution, outsider):
    api_client.force_authenticate(outsider)
    response = api_client.get(
        f'/api/reports/executions/{completed_execution.pk}/download/'
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Verify failures**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py tests/test_app_ui.py -k "catalog_groups or download_requires"
```

Expected: FAIL with missing route/action.

- [ ] **Step 3: Add safe API behavior**

`ReportDefinitionViewSet.run` must ignore technical configuration from the
request and accept only:

```python
class RunReportSerializer(serializers.Serializer):
    export_format = serializers.ChoiceField(choices=ReportExecution.ExportFormat.choices)
    filters = serializers.JSONField(default=dict)
```

The download action must require `reports.view_reportexecution`,
`files.view_protectedfile`, ensure `result_file_id` exists, call the same
authorization path used by `ProtectedFileViewSet.download`, and return the
decrypted bytes with the stored MIME type and safe filename.

- [ ] **Step 4: Add catalog and dynamic filter form views**

The catalog view queries only
`ReportDefinition.objects.filter(is_system_managed=True, is_active=True)` and
groups by `module`. The run form builds fields from the server-owned
`filter_schema`; support only:

```python
FILTER_FIELD_TYPES = {
    'date': forms.DateField,
    'choice': forms.ChoiceField,
    'text': forms.CharField,
    'integer': forms.IntegerField,
}
```

Reject any schema type outside this map. On valid POST, create and run an
execution, then redirect to its detail/download action. Never render or accept
`query_config` or `executor_key`.

- [ ] **Step 5: Add templates and menu entry**

`report_catalog.html` renders module cards, report title/description, allowed
formats, and a “Executar” link. `report_run.html` uses the existing page header,
CSRF token, Bootstrap field errors, and submit/cancel actions. Replace the
operational “Definições de relatório” emphasis with “Catálogo de relatórios”;
keep definitions accessible only to administrators with change permission.

- [ ] **Step 6: Run API/UI tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py tests/test_reports.py tests/test_app_ui.py tests/test_action_registry.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add reports/serializers.py reports/views.py reports/urls.py base/ui/urls.py base/ui/views.py base/ui/registry.py templates/app/report_catalog.html templates/app/report_run.html tests/test_report_engine.py tests/test_app_ui.py
git commit -m "feat: add curated report catalog experience"
```

### Task 7: Documentation and report verification

**Files:**
- Modify: `docs/architecture/reports.md`
- Modify: `docs/pdf/especificacao_funcional.md`
- Modify: `docs/pdf/manual_usuario.md`
- Modify: `mkdocs.yml`

**Interfaces:**
- Consumes: all report tasks.
- Produces: operating documentation and final verification evidence.

- [ ] **Step 1: Document the security and execution model**

Document the 15 codes/titles, filter rules, async schedule behavior, file access,
hashing, failure state, and this invariant:

```text
Nenhuma definição operacional pode fornecer SQL, caminho de model, lista de
campos ou expressão executável. O código do executor é resolvido exclusivamente
em uma lista registrada no servidor.
```

- [ ] **Step 2: Run Django and migration checks**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py makemigrations --check
```

Expected: exit 0 and `No changes detected`.

- [ ] **Step 3: Run report, finance, fiscal, inventory, procurement, and production tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_report_engine.py tests/test_reports.py tests/test_finance.py tests/test_fiscal.py tests/test_inventory.py tests/test_procurement.py tests/test_production.py
```

Expected: PASS.

- [ ] **Step 4: Run lint**

Run:

```bash
.venv/bin/ruff check reports tests/test_report_engine.py
```

Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add docs/architecture/reports.md docs/pdf/especificacao_funcional.md docs/pdf/manual_usuario.md mkdocs.yml
git commit -m "docs: document curated report catalog"
```
