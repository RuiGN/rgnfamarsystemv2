from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from procurement.models import PurchaseOrder, PurchaseReceipt, PurchaseReceiptItem
from reports.contracts import ReportColumn, ReportContext, ReportDataset
from reports.executors._filters import choice_filter, positive_integer_filter
from reports.filters import normalize_report_filters
from reports.registry import register_executor


PERCENT_SCALE = Decimal('0.0001')
PERCENT_BASE = Decimal('100.0000')
ZERO_DECIMAL = Decimal('0.0000')
OPEN_ORDER_STATUSES = (
    PurchaseOrder.Status.DRAFT,
    PurchaseOrder.Status.APPROVED,
    PurchaseOrder.Status.SENT,
    PurchaseOrder.Status.PARTIALLY_RECEIVED,
)


def _percentage(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == ZERO_DECIMAL:
        return ZERO_DECIMAL
    return ((numerator / denominator) * PERCENT_BASE).quantize(
        PERCENT_SCALE,
        rounding=ROUND_HALF_UP,
    )


@register_executor('procurement.open_delayed_orders')
def open_delayed_orders(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'supplier', 'product'),
    )
    reference_date = timezone.localdate()
    queryset = PurchaseOrder.objects.filter(status__in=OPEN_ORDER_STATUSES).select_related(
        'supplier'
    )
    if 'period_start' in filters:
        queryset = queryset.filter(issue_date__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(issue_date__lte=filters['period_end'])
    if 'status' in filters:
        queryset = queryset.filter(
            status=choice_filter(filters, 'status', PurchaseOrder.Status.choices)
        )
    if 'supplier' in filters:
        queryset = queryset.filter(supplier_id=positive_integer_filter(filters, 'supplier'))
    if 'product' in filters:
        queryset = queryset.filter(
            items__product_id=positive_integer_filter(filters, 'product')
        ).distinct()

    def order_rows():
        for item in queryset.order_by(
            'expected_delivery_date',
            'issue_date',
            'order_number',
            'pk',
        ):
            days_late = 0
            if item.expected_delivery_date:
                days_late = max((reference_date - item.expected_delivery_date).days, 0)
            yield {
                'order_number': item.order_number,
                'supplier': item.supplier.legal_name,
                'issue_date': item.issue_date,
                'expected_delivery_date': item.expected_delivery_date,
                'status': item.get_status_display(),
                'total_amount': item.total_amount,
                'days_late': days_late,
            }

    return ReportDataset(
        title='Pedidos de compra abertos ou atrasados',
        columns=(
            ReportColumn('order_number', 'Pedido'),
            ReportColumn('supplier', 'Fornecedor'),
            ReportColumn('issue_date', 'Emissão', 'date'),
            ReportColumn('expected_delivery_date', 'Entrega prevista', 'date'),
            ReportColumn('status', 'Situação', 'status'),
            ReportColumn('total_amount', 'Valor total', 'decimal'),
            ReportColumn('days_late', 'Dias de atraso', 'integer'),
        ),
        rows=order_rows(),
    )


@register_executor('procurement.receipt_supplier_performance')
def receipt_supplier_performance(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'supplier', 'product'),
    )
    queryset = PurchaseReceiptItem.objects.select_related(
        'receipt__order__supplier',
        'product',
    )
    if 'period_start' in filters:
        queryset = queryset.filter(receipt__physical_received_at__date__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(receipt__physical_received_at__date__lte=filters['period_end'])
    if 'status' in filters:
        queryset = queryset.filter(
            receipt__status=choice_filter(
                filters,
                'status',
                PurchaseReceipt.Status.choices,
            )
        )
    if 'supplier' in filters:
        queryset = queryset.filter(
            receipt__order__supplier_id=positive_integer_filter(filters, 'supplier')
        )
    if 'product' in filters:
        queryset = queryset.filter(product_id=positive_integer_filter(filters, 'product'))
    rows = (
        {
            'supplier': item.receipt.order.supplier.legal_name,
            'receipt': item.receipt.receipt_number,
            'product': f'{item.product.code} - {item.product.description}',
            'received': item.received_quantity,
            'accepted': item.accepted_quantity,
            'rejected': item.rejected_quantity,
            'acceptance_percent': _percentage(
                item.accepted_quantity,
                item.received_quantity,
            ),
        }
        for item in queryset.order_by(
            'receipt__order__supplier__legal_name',
            'receipt__receipt_number',
            'product__code',
            'pk',
        )
    )
    return ReportDataset(
        title='Divergências de recebimento e fornecedores',
        columns=(
            ReportColumn('supplier', 'Fornecedor'),
            ReportColumn('receipt', 'Recebimento'),
            ReportColumn('product', 'Produto'),
            ReportColumn('received', 'Recebido', 'decimal'),
            ReportColumn('accepted', 'Aceito', 'decimal'),
            ReportColumn('rejected', 'Rejeitado', 'decimal'),
            ReportColumn('acceptance_percent', 'Aceitação %', 'decimal'),
        ),
        rows=rows,
    )
