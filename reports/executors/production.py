from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Prefetch
from django.utils import timezone

from costing.models import ProductionCostCapture
from production.models import (
    MaterialConsumption,
    ProductionOrder,
    ProductionOutput,
)
from reports.contracts import ReportColumn, ReportContext, ReportDataset
from reports.executors._filters import choice_filter, positive_integer_filter
from reports.filters import normalize_report_filters
from reports.registry import register_executor


ZERO_DECIMAL = Decimal('0.0000')
PERCENT_BASE = Decimal('100.0000')
PERCENT_SCALE = Decimal('0.0001')


def _percentage(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == ZERO_DECIMAL:
        return ZERO_DECIMAL
    return ((numerator / denominator) * PERCENT_BASE).quantize(
        PERCENT_SCALE,
        rounding=ROUND_HALF_UP,
    )


@register_executor('production.orders_status_delay')
def orders_status_delay(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'product'),
    )
    reference_date = timezone.localdate()
    report_timezone = timezone.get_current_timezone()
    queryset = ProductionOrder.objects.select_related('product', 'responsible')
    if 'period_start' in filters:
        queryset = queryset.filter(scheduled_end__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(scheduled_end__lte=filters['period_end'])
    if 'status' in filters:
        queryset = queryset.filter(
            status=choice_filter(filters, 'status', ProductionOrder.Status.choices)
        )
    if 'product' in filters:
        queryset = queryset.filter(product_id=positive_integer_filter(filters, 'product'))

    def order_rows():
        for item in queryset.order_by('scheduled_end', 'order_number', 'pk'):
            days_late = 0
            if item.scheduled_end:
                scheduled_end = item.scheduled_end
                if item.actual_end:
                    end_reference = timezone.localtime(
                        item.actual_end,
                        report_timezone,
                    ).date()
                elif item.status not in {
                    ProductionOrder.Status.COMPLETED,
                    ProductionOrder.Status.CANCELLED,
                    ProductionOrder.Status.CLOSED,
                }:
                    end_reference = reference_date
                else:
                    end_reference = scheduled_end
                days_late = max((end_reference - scheduled_end).days, 0)
            yield {
                'order_number': item.order_number,
                'product': f'{item.product.code} - {item.product.description}',
                'priority': item.get_priority_display(),
                'responsible': item.responsible.get_username() if item.responsible else '',
                'scheduled_end': item.scheduled_end,
                'status': item.get_status_display(),
                'days_late': days_late,
            }

    return ReportDataset(
        title='Ordens de produção por situação e atraso',
        columns=(
            ReportColumn('order_number', 'Ordem'),
            ReportColumn('product', 'Produto'),
            ReportColumn('priority', 'Prioridade', 'status'),
            ReportColumn('responsible', 'Responsável'),
            ReportColumn('scheduled_end', 'Fim previsto', 'date'),
            ReportColumn('status', 'Situação', 'status'),
            ReportColumn('days_late', 'Dias de atraso', 'integer'),
        ),
        rows=order_rows(),
    )


@register_executor('production.consumption_variance')
def consumption_variance(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'product', 'lot'),
    )
    queryset = MaterialConsumption.objects.select_related(
        'order',
        'material',
        'stock_lot',
    )
    if 'period_start' in filters:
        queryset = queryset.filter(order__scheduled_end__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(order__scheduled_end__lte=filters['period_end'])
    if 'status' in filters:
        queryset = queryset.filter(
            order__status=choice_filter(
                filters,
                'status',
                ProductionOrder.Status.choices,
            )
        )
    # In this material-level report, product identifies the consumed material.
    if 'product' in filters:
        queryset = queryset.filter(material_id=positive_integer_filter(filters, 'product'))
    if 'lot' in filters:
        queryset = queryset.filter(stock_lot_id=positive_integer_filter(filters, 'lot'))
    rows = (
        {
            'order_number': item.order.order_number,
            'material': f'{item.material.code} - {item.material.description}',
            'lot': item.stock_lot.lot_number if item.stock_lot else item.lot_number,
            'planned': item.planned_quantity,
            'actual': item.actual_quantity,
            'loss': item.loss_quantity,
            'returned': item.returned_quantity,
            'variance': item.actual_quantity - item.planned_quantity,
        }
        for item in queryset.order_by('order__order_number', 'material__code', 'pk')
    )
    return ReportDataset(
        title='Consumo planejado versus realizado',
        columns=(
            ReportColumn('order_number', 'Ordem'),
            ReportColumn('material', 'Material'),
            ReportColumn('lot', 'Lote'),
            ReportColumn('planned', 'Planejado', 'decimal'),
            ReportColumn('actual', 'Realizado', 'decimal'),
            ReportColumn('loss', 'Perda', 'decimal'),
            ReportColumn('returned', 'Devolvido', 'decimal'),
            ReportColumn('variance', 'Variação', 'decimal'),
        ),
        rows=rows,
    )


@register_executor('production.yield_loss_cost')
def yield_loss_cost(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'product'),
    )
    queryset = ProductionOrder.objects.select_related('product').prefetch_related(
        Prefetch(
            'outputs',
            queryset=ProductionOutput.objects.order_by('lot_number', 'sublot_number', 'pk'),
            to_attr='report_outputs',
        ),
        Prefetch(
            'cost_captures',
            queryset=ProductionCostCapture.objects.order_by(
                'period_start',
                'pk',
            ),
            to_attr='report_cost_captures',
        ),
    )
    if 'period_start' in filters:
        queryset = queryset.filter(scheduled_end__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(scheduled_end__lte=filters['period_end'])
    if 'status' in filters:
        queryset = queryset.filter(
            status=choice_filter(filters, 'status', ProductionOrder.Status.choices)
        )
    if 'product' in filters:
        queryset = queryset.filter(product_id=positive_integer_filter(filters, 'product'))

    def result_rows():
        for item in queryset.order_by('order_number', 'pk'):
            actual_yield = sum(
                (output.produced_quantity for output in item.report_outputs),
                ZERO_DECIMAL,
            )
            actual_cost = sum(
                (capture.total_actual_cost for capture in item.report_cost_captures),
                ZERO_DECIMAL,
            )
            cost_variance = sum(
                (capture.variance_amount for capture in item.report_cost_captures),
                ZERO_DECIMAL,
            )
            yield {
                'order_number': item.order_number,
                'product': f'{item.product.code} - {item.product.description}',
                'planned': item.planned_quantity,
                'actual_yield': actual_yield,
                'yield_percent': _percentage(actual_yield, item.planned_quantity),
                'loss': item.real_loss_quantity,
                'rework': item.rework_quantity,
                'actual_cost': actual_cost,
                'cost_variance': cost_variance,
            }

    return ReportDataset(
        title='Rendimento, perdas e custo por ordem',
        columns=(
            ReportColumn('order_number', 'Ordem'),
            ReportColumn('product', 'Produto'),
            ReportColumn('planned', 'Planejado', 'decimal'),
            ReportColumn('actual_yield', 'Rendimento real', 'decimal'),
            ReportColumn('yield_percent', 'Rendimento %', 'decimal'),
            ReportColumn('loss', 'Perda', 'decimal'),
            ReportColumn('rework', 'Retrabalho', 'decimal'),
            ReportColumn('actual_cost', 'Custo real', 'decimal'),
            ReportColumn('cost_variance', 'Variação de custo', 'decimal'),
        ),
        rows=result_rows(),
    )
