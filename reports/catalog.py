from copy import deepcopy

from django.db import IntegrityError, router, transaction

from reports.registry import get_executor


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

CURATED_REPORT_METADATA = {
    'REL-FIN-001': (
        'Contas a receber em aberto e vencidas',
        'finance',
        'operational',
        (),
    ),
    'REL-FIN-002': (
        'Contas a pagar em aberto e vencidas',
        'finance',
        'operational',
        (),
    ),
    'REL-FIN-003': (
        'Fluxo de caixa realizado e projetado',
        'finance',
        'management',
        ('period_start', 'period_end'),
    ),
    'REL-FIN-004': (
        'Resultado financeiro por período',
        'finance',
        'management',
        ('period_start', 'period_end'),
    ),
    'REL-FIS-001': (
        'Documentos fiscais por período e situação',
        'fiscal',
        'operational',
        ('period_start', 'period_end'),
    ),
    'REL-FIS-002': (
        'Apuração de tributos',
        'fiscal',
        'management',
        ('period_start', 'period_end'),
    ),
    'REL-FIS-003': (
        'Livro de entradas e saídas',
        'fiscal',
        'operational',
        ('period_start', 'period_end'),
    ),
    'REL-EST-001': (
        'Posição de estoque',
        'inventory',
        'operational',
        (),
    ),
    'REL-EST-002': (
        'Lotes próximos do vencimento ou vencidos',
        'inventory',
        'operational',
        ('period_end',),
    ),
    'REL-EST-003': (
        'Genealogia e rastreabilidade de lotes',
        'traceability',
        'audit',
        (),
    ),
    'REL-COM-001': (
        'Pedidos de compra abertos ou atrasados',
        'procurement',
        'operational',
        (),
    ),
    'REL-COM-002': (
        'Divergências de recebimento e fornecedores',
        'procurement',
        'management',
        ('period_start', 'period_end'),
    ),
    'REL-PRO-001': (
        'Ordens de produção por situação e atraso',
        'production',
        'operational',
        (),
    ),
    'REL-PRO-002': (
        'Consumo planejado versus realizado',
        'production',
        'management',
        ('period_start', 'period_end'),
    ),
    'REL-PRO-003': (
        'Rendimento, perdas e custo por ordem',
        'production',
        'management',
        ('period_start', 'period_end'),
    ),
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

# These lists mirror the explicit allow-lists in reports.executors. Keeping the
# complete runtime surface here prevents the persisted filter UI from drifting
# away from filters accepted by an executor.
EXECUTOR_ALLOWED_FILTERS = {
    'finance.receivables_open_overdue': (
        'period_start',
        'period_end',
        'status',
        'customer',
    ),
    'finance.payables_open_overdue': (
        'period_start',
        'period_end',
        'status',
        'supplier',
    ),
    'finance.cash_flow': (
        'period_start',
        'period_end',
        'status',
        'customer',
        'supplier',
    ),
    'finance.period_result': (
        'period_start',
        'period_end',
        'status',
        'customer',
        'supplier',
    ),
    'fiscal.documents': (
        'period_start',
        'period_end',
        'status',
        'supplier',
        'customer',
    ),
    'fiscal.tax_assessment': ('period_start', 'period_end', 'status'),
    'fiscal.books': (
        'period_start',
        'period_end',
        'status',
        'supplier',
        'customer',
    ),
    'inventory.position': ('product', 'lot', 'status', 'supplier'),
    'inventory.expiry': (
        'period_start',
        'period_end',
        'product',
        'lot',
        'status',
        'supplier',
    ),
    'inventory.genealogy': ('product', 'lot'),
    'procurement.open_delayed_orders': (
        'period_start',
        'period_end',
        'status',
        'supplier',
        'product',
    ),
    'procurement.receipt_supplier_performance': (
        'period_start',
        'period_end',
        'status',
        'supplier',
        'product',
    ),
    'production.orders_status_delay': (
        'period_start',
        'period_end',
        'status',
        'product',
    ),
    'production.consumption_variance': (
        'period_start',
        'period_end',
        'status',
        'product',
        'lot',
    ),
    'production.yield_loss_cost': (
        'period_start',
        'period_end',
        'status',
        'product',
    ),
}


class CuratedReportCatalogCollision(RuntimeError):
    """Raised when a canonical code is owned by a user-managed definition."""


def executor_allowed_filters(executor_key):
    try:
        return EXECUTOR_ALLOWED_FILTERS[executor_key]
    except KeyError as exc:
        raise RuntimeError(f'Filtros ausentes para {executor_key}.') from exc


def _build_curated_reports():
    reports = []
    for code, executor_key in CURATED_REPORT_KEYS.items():
        title, module, category, required_filters = CURATED_REPORT_METADATA[code]
        allowed_filters = executor_allowed_filters(executor_key)
        reports.append(
            {
                'code': code,
                'title': title,
                'module': module,
                'category': category,
                'required_permission': MODULE_REPORT_PERMISSIONS[module],
                'executor_key': executor_key,
                'allowed_export_formats': ['pdf', 'xlsx', 'csv'],
                'required_filters': list(required_filters),
                'filter_schema': {key: dict(FILTER_SCHEMAS[key]) for key in allowed_filters},
                'query_config': {'catalog_version': 1},
                'description': title,
                'is_active': True,
                'is_system_managed': True,
            }
        )
    return tuple(reports)


CURATED_REPORTS = _build_curated_reports()


def _validate_catalog(report_definition_model):
    codes = [item['code'] for item in CURATED_REPORTS]
    executor_keys = [item['executor_key'] for item in CURATED_REPORTS]
    if (
        len(CURATED_REPORTS) != 15
        or len(codes) != len(set(codes))
        or len(executor_keys) != len(set(executor_keys))
        or set(CURATED_REPORT_KEYS) != set(codes)
    ):
        raise RuntimeError('Catálogo curado de relatórios inválido ou duplicado.')

    module_values = {
        value for value, _label in report_definition_model._meta.get_field('module').choices
    }
    category_values = {
        value for value, _label in report_definition_model._meta.get_field('category').choices
    }
    for item in CURATED_REPORTS:
        get_executor(item['executor_key'])
        allowed_filters = set(executor_allowed_filters(item['executor_key']))
        if (
            item['module'] not in module_values
            or item['category'] not in category_values
            or set(item['filter_schema']) != allowed_filters
            or not set(item['required_filters']) <= allowed_filters
            or item['allowed_export_formats'] != ['pdf', 'xlsx', 'csv']
            or item['query_config'] != {'catalog_version': 1}
        ):
            raise RuntimeError(f'Entrada inválida no catálogo curado: {item["code"]}.')


def _sync_curated_report_catalog_once(
    report_definition_model,
    manager,
    write_alias,
):
    codes = tuple(CURATED_REPORT_KEYS)
    with transaction.atomic(using=write_alias):
        _validate_catalog(report_definition_model)
        existing_by_code = {
            definition.code: definition
            for definition in manager.select_for_update().filter(code__in=codes)
        }
        collisions = sorted(
            code
            for code, definition in existing_by_code.items()
            if definition.is_system_managed is not True
        )
        if collisions:
            code = collisions[0]
            raise CuratedReportCatalogCollision(
                f'Código canônico {code} já pertence a uma definição não gerenciada pelo sistema.'
            )

        for item in CURATED_REPORTS:
            values = deepcopy(item)
            code = values.pop('code')
            definition = existing_by_code.get(code)
            if definition is None:
                manager.create(code=code, **values)
            else:
                manager.filter(pk=definition.pk, is_system_managed=True).update(**values)


def sync_curated_report_catalog(report_definition_model):
    write_alias = router.db_for_write(report_definition_model)
    manager = report_definition_model._default_manager.using(write_alias)
    for attempt in range(2):
        try:
            return _sync_curated_report_catalog_once(
                report_definition_model,
                manager,
                write_alias,
            )
        except IntegrityError:
            if attempt == 1:
                raise
