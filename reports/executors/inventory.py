from datetime import timedelta
from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from inventory.models import StockBalance, StockLot, StockLotGenealogy, StockQualityStatus
from reports.contracts import ReportColumn, ReportContext, ReportDataset
from reports.executors._filters import choice_filter, positive_integer_filter
from reports.filters import normalize_report_filters
from reports.registry import register_executor


ZERO_QUANTITY = Decimal('0.0000')
QUANTITY_FIELD = DecimalField(max_digits=18, decimal_places=4)
DEFAULT_EXPIRY_WINDOW_DAYS = 90


@register_executor('inventory.position')
def position(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('product', 'lot', 'status', 'supplier'),
    )
    queryset = StockBalance.objects.select_related(
        'product',
        'lot',
        'warehouse',
        'location',
    )
    if 'product' in filters:
        queryset = queryset.filter(product_id=positive_integer_filter(filters, 'product'))
    if 'lot' in filters:
        queryset = queryset.filter(lot_id=positive_integer_filter(filters, 'lot'))
    if 'status' in filters:
        queryset = queryset.filter(
            quality_status=choice_filter(
                filters,
                'status',
                StockQualityStatus.choices,
            )
        )
    if 'supplier' in filters:
        queryset = queryset.filter(lot__supplier_id=positive_integer_filter(filters, 'supplier'))
    rows = (
        {
            'product': f'{item.product.code} - {item.product.description}',
            'lot': item.lot.lot_number,
            'expiry_date': item.lot.expiry_date,
            'warehouse': item.warehouse.name,
            'location': item.location.code,
            'quality_status': item.get_quality_status_display(),
            'quantity': item.quantity,
            'reserved': item.reserved_quantity,
            'available': item.available_quantity,
        }
        for item in queryset.order_by(
            'product__code',
            'lot__lot_number',
            'warehouse__code',
            'location__code',
            'quality_status',
            'pk',
        )
    )
    return ReportDataset(
        title='Posição de estoque',
        columns=(
            ReportColumn('product', 'Produto'),
            ReportColumn('lot', 'Lote'),
            ReportColumn('expiry_date', 'Validade', 'date'),
            ReportColumn('warehouse', 'Almoxarifado'),
            ReportColumn('location', 'Localização'),
            ReportColumn('quality_status', 'Qualidade', 'status'),
            ReportColumn('quantity', 'Quantidade', 'decimal'),
            ReportColumn('reserved', 'Reservado', 'decimal'),
            ReportColumn('available', 'Disponível', 'decimal'),
        ),
        rows=rows,
    )


@register_executor('inventory.expiry')
def expiry(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'product', 'lot', 'status', 'supplier'),
    )
    reference_date = timezone.localdate()
    queryset = (
        StockLot.objects.filter(expiry_date__isnull=False)
        .select_related('product')
        .annotate(
            report_quantity=Coalesce(
                Sum('balances__quantity'),
                Value(ZERO_QUANTITY),
                output_field=QUANTITY_FIELD,
            )
        )
        .filter(report_quantity__gt=ZERO_QUANTITY)
    )
    if 'period_start' in filters:
        queryset = queryset.filter(expiry_date__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(expiry_date__lte=filters['period_end'])
    elif 'period_start' not in filters:
        queryset = queryset.filter(
            expiry_date__lte=reference_date + timedelta(days=DEFAULT_EXPIRY_WINDOW_DAYS)
        )
    if 'product' in filters:
        queryset = queryset.filter(product_id=positive_integer_filter(filters, 'product'))
    if 'lot' in filters:
        queryset = queryset.filter(pk=positive_integer_filter(filters, 'lot'))
    if 'status' in filters:
        queryset = queryset.filter(
            quality_status=choice_filter(
                filters,
                'status',
                StockQualityStatus.choices,
            )
        )
    if 'supplier' in filters:
        queryset = queryset.filter(supplier_id=positive_integer_filter(filters, 'supplier'))
    rows = (
        {
            'product': f'{item.product.code} - {item.product.description}',
            'lot': item.lot_number,
            'expiry_date': item.expiry_date,
            'days_to_expiry': (item.expiry_date - reference_date).days,
            'quality_status': item.get_quality_status_display(),
            'quantity': item.report_quantity,
        }
        for item in queryset.order_by('expiry_date', 'product__code', 'lot_number', 'pk')
    )
    return ReportDataset(
        title='Lotes próximos do vencimento ou vencidos',
        columns=(
            ReportColumn('product', 'Produto'),
            ReportColumn('lot', 'Lote'),
            ReportColumn('expiry_date', 'Validade', 'date'),
            ReportColumn('days_to_expiry', 'Dias para vencer', 'integer'),
            ReportColumn('quality_status', 'Qualidade', 'status'),
            ReportColumn('quantity', 'Quantidade em estoque', 'decimal'),
        ),
        rows=rows,
    )


@register_executor('inventory.genealogy')
def genealogy(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('product', 'lot'),
    )
    queryset = StockLotGenealogy.objects.select_related(
        'input_lot__product',
        'output_lot__product',
        'production_order',
    )
    if 'product' in filters:
        product = positive_integer_filter(filters, 'product')
        queryset = queryset.filter(
            Q(input_lot__product_id=product) | Q(output_lot__product_id=product)
        )
    if 'lot' in filters:
        lot = positive_integer_filter(filters, 'lot')
        queryset = queryset.filter(Q(input_lot_id=lot) | Q(output_lot_id=lot))
    rows = (
        {
            'input_product': item.input_lot.product.code,
            'input_lot': item.input_lot.lot_number,
            'output_product': item.output_lot.product.code,
            'output_lot': item.output_lot.lot_number,
            'relation_type': item.get_relation_type_display(),
            'quantity': item.quantity,
            'production_order': (
                item.production_order.order_number if item.production_order else ''
            ),
        }
        for item in queryset.order_by(
            'output_lot__product__code',
            'output_lot__lot_number',
            'input_lot__product__code',
            'input_lot__lot_number',
            'pk',
        )
    )
    return ReportDataset(
        title='Genealogia e rastreabilidade de lotes',
        columns=(
            ReportColumn('input_product', 'Produto de entrada'),
            ReportColumn('input_lot', 'Lote de entrada'),
            ReportColumn('output_product', 'Produto de saída'),
            ReportColumn('output_lot', 'Lote de saída'),
            ReportColumn('relation_type', 'Relação', 'status'),
            ReportColumn('quantity', 'Quantidade', 'decimal'),
            ReportColumn('production_order', 'Ordem de produção'),
        ),
        rows=rows,
    )
