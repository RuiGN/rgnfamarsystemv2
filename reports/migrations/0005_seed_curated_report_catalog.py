from django.db import IntegrityError, migrations, transaction


FILTER_SCHEMAS_V1 = {
    'period_start': {'type': 'date', 'label': 'Data inicial'},
    'period_end': {'type': 'date', 'label': 'Data final'},
    'status': {'type': 'text', 'label': 'Situação'},
    'product': {'type': 'integer', 'label': 'Produto'},
    'lot': {'type': 'text', 'label': 'Lote'},
    'customer': {'type': 'integer', 'label': 'Cliente'},
    'supplier': {'type': 'integer', 'label': 'Fornecedor'},
}

# Frozen version-1 values. Do not import reports.catalog here: migrations must
# replay the data contract that existed when this migration was released.
CURATED_REPORTS_V1 = (
    (
        'REL-FIN-001',
        'finance.receivables_open_overdue',
        'Contas a receber em aberto e vencidas',
        'finance',
        'operational',
        'finance.view_financialtitle',
        (),
        ('period_start', 'period_end', 'status', 'customer'),
    ),
    (
        'REL-FIN-002',
        'finance.payables_open_overdue',
        'Contas a pagar em aberto e vencidas',
        'finance',
        'operational',
        'finance.view_financialtitle',
        (),
        ('period_start', 'period_end', 'status', 'supplier'),
    ),
    (
        'REL-FIN-003',
        'finance.cash_flow',
        'Fluxo de caixa realizado e projetado',
        'finance',
        'management',
        'finance.view_financialtitle',
        ('period_start', 'period_end'),
        ('period_start', 'period_end', 'status', 'customer', 'supplier'),
    ),
    (
        'REL-FIN-004',
        'finance.period_result',
        'Resultado financeiro por período',
        'finance',
        'management',
        'finance.view_financialtitle',
        ('period_start', 'period_end'),
        ('period_start', 'period_end', 'status', 'customer', 'supplier'),
    ),
    (
        'REL-FIS-001',
        'fiscal.documents',
        'Documentos fiscais por período e situação',
        'fiscal',
        'operational',
        'fiscal.view_fiscaldocument',
        ('period_start', 'period_end'),
        ('period_start', 'period_end', 'status', 'supplier', 'customer'),
    ),
    (
        'REL-FIS-002',
        'fiscal.tax_assessment',
        'Apuração de tributos',
        'fiscal',
        'management',
        'fiscal.view_fiscaldocument',
        ('period_start', 'period_end'),
        ('period_start', 'period_end', 'status'),
    ),
    (
        'REL-FIS-003',
        'fiscal.books',
        'Livro de entradas e saídas',
        'fiscal',
        'operational',
        'fiscal.view_fiscaldocument',
        ('period_start', 'period_end'),
        ('period_start', 'period_end', 'status', 'supplier', 'customer'),
    ),
    (
        'REL-EST-001',
        'inventory.position',
        'Posição de estoque',
        'inventory',
        'operational',
        'inventory.view_stockbalance',
        (),
        ('product', 'lot', 'status', 'supplier'),
    ),
    (
        'REL-EST-002',
        'inventory.expiry',
        'Lotes próximos do vencimento ou vencidos',
        'inventory',
        'operational',
        'inventory.view_stockbalance',
        ('period_end',),
        ('period_start', 'period_end', 'product', 'lot', 'status', 'supplier'),
    ),
    (
        'REL-EST-003',
        'inventory.genealogy',
        'Genealogia e rastreabilidade de lotes',
        'traceability',
        'audit',
        'inventory.view_stocklotgenealogy',
        (),
        ('product', 'lot'),
    ),
    (
        'REL-COM-001',
        'procurement.open_delayed_orders',
        'Pedidos de compra abertos ou atrasados',
        'procurement',
        'operational',
        'procurement.view_purchaseorder',
        (),
        ('period_start', 'period_end', 'status', 'supplier', 'product'),
    ),
    (
        'REL-COM-002',
        'procurement.receipt_supplier_performance',
        'Divergências de recebimento e fornecedores',
        'procurement',
        'management',
        'procurement.view_purchaseorder',
        ('period_start', 'period_end'),
        ('period_start', 'period_end', 'status', 'supplier', 'product'),
    ),
    (
        'REL-PRO-001',
        'production.orders_status_delay',
        'Ordens de produção por situação e atraso',
        'production',
        'operational',
        'production.view_productionorder',
        (),
        ('period_start', 'period_end', 'status', 'product'),
    ),
    (
        'REL-PRO-002',
        'production.consumption_variance',
        'Consumo planejado versus realizado',
        'production',
        'management',
        'production.view_productionorder',
        ('period_start', 'period_end'),
        ('period_start', 'period_end', 'status', 'product', 'lot'),
    ),
    (
        'REL-PRO-003',
        'production.yield_loss_cost',
        'Rendimento, perdas e custo por ordem',
        'production',
        'management',
        'production.view_productionorder',
        ('period_start', 'period_end'),
        ('period_start', 'period_end', 'status', 'product'),
    ),
)


def _catalog_values(entry):
    (
        _code,
        executor_key,
        title,
        module,
        category,
        required_permission,
        required_filters,
        allowed_filters,
    ) = entry
    return {
        'title': title,
        'module': module,
        'category': category,
        'required_permission': required_permission,
        'executor_key': executor_key,
        'allowed_export_formats': ['pdf', 'xlsx', 'csv'],
        'required_filters': list(required_filters),
        'filter_schema': {key: dict(FILTER_SCHEMAS_V1[key]) for key in allowed_filters},
        'query_config': {'catalog_version': 1},
        'description': title,
        'is_active': True,
        'is_system_managed': True,
    }


def _seed_curated_report_catalog_once(manager, database):
    codes = tuple(entry[0] for entry in CURATED_REPORTS_V1)

    with transaction.atomic(using=database):
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
            raise RuntimeError(
                f'Código canônico {code} já pertence a uma definição não gerenciada pelo sistema.'
            )

        for entry in CURATED_REPORTS_V1:
            code = entry[0]
            values = _catalog_values(entry)
            definition = existing_by_code.get(code)
            if definition is None:
                manager.create(code=code, **values)
            else:
                manager.filter(pk=definition.pk, is_system_managed=True).update(**values)


def seed_curated_report_catalog(apps, schema_editor):
    ReportDefinition = apps.get_model('reports', 'ReportDefinition')
    database = schema_editor.connection.alias
    manager = ReportDefinition.objects.using(database)
    for attempt in range(2):
        try:
            return _seed_curated_report_catalog_once(manager, database)
        except IntegrityError:
            if attempt == 1:
                raise


class Migration(migrations.Migration):
    dependencies = [
        ('reports', '0004_report_execution_engine'),
    ]

    operations = [
        migrations.RunPython(
            seed_curated_report_catalog,
            migrations.RunPython.noop,
        ),
    ]
