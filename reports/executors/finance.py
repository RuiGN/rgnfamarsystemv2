from decimal import Decimal

from django.db.models import Case, DecimalField, Q, Sum, Value, When
from django.db.models.functions import Coalesce, TruncMonth

from finance.models import CashFlowEntry, FinancialTitle
from reports.contracts import ReportColumn, ReportContext, ReportDataset
from reports.executors._filters import choice_filter, positive_integer_filter
from reports.filters import normalize_report_filters
from reports.registry import register_executor


OPEN_TITLE_STATUSES = (
    FinancialTitle.Status.PENDING,
    FinancialTitle.Status.APPROVED,
    FinancialTitle.Status.PARTIALLY_SETTLED,
    FinancialTitle.Status.OVERDUE,
)
MONEY_FIELD = DecimalField(max_digits=18, decimal_places=4)
ZERO_MONEY = Decimal('0.0000')


@register_executor('finance.receivables_open_overdue')
def receivables_open_overdue(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'customer'),
    )
    queryset = FinancialTitle.objects.filter(
        title_type=FinancialTitle.TitleType.RECEIVABLE,
        status__in=OPEN_TITLE_STATUSES,
        open_amount__gt=ZERO_MONEY,
    ).select_related('partner')
    if 'period_start' in filters:
        queryset = queryset.filter(due_date__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(due_date__lte=filters['period_end'])
    if 'status' in filters:
        queryset = queryset.filter(
            status=choice_filter(filters, 'status', FinancialTitle.Status.choices)
        )
    if 'customer' in filters:
        queryset = queryset.filter(partner_id=positive_integer_filter(filters, 'customer'))

    rows = (
        {
            'title_number': item.title_number,
            'partner': item.partner.legal_name,
            'due_date': item.due_date,
            'status': item.get_status_display(),
            'original_amount': item.original_amount,
            'open_amount': item.open_amount,
        }
        for item in queryset.order_by('due_date', 'title_number', 'pk')
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


@register_executor('finance.payables_open_overdue')
def payables_open_overdue(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'supplier'),
    )
    queryset = FinancialTitle.objects.filter(
        title_type=FinancialTitle.TitleType.PAYABLE,
        status__in=OPEN_TITLE_STATUSES,
        open_amount__gt=ZERO_MONEY,
    ).select_related('partner')
    if 'period_start' in filters:
        queryset = queryset.filter(due_date__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(due_date__lte=filters['period_end'])
    if 'status' in filters:
        queryset = queryset.filter(
            status=choice_filter(filters, 'status', FinancialTitle.Status.choices)
        )
    if 'supplier' in filters:
        queryset = queryset.filter(partner_id=positive_integer_filter(filters, 'supplier'))

    rows = (
        {
            'title_number': item.title_number,
            'partner': item.partner.legal_name,
            'due_date': item.due_date,
            'status': item.get_status_display(),
            'original_amount': item.original_amount,
            'open_amount': item.open_amount,
        }
        for item in queryset.order_by('due_date', 'title_number', 'pk')
    )
    return ReportDataset(
        title='Contas a pagar em aberto e vencidas',
        columns=(
            ReportColumn('title_number', 'Título'),
            ReportColumn('partner', 'Fornecedor'),
            ReportColumn('due_date', 'Vencimento', 'date'),
            ReportColumn('status', 'Situação', 'status'),
            ReportColumn('original_amount', 'Valor original', 'decimal'),
            ReportColumn('open_amount', 'Valor em aberto', 'decimal'),
        ),
        rows=rows,
    )


@register_executor('finance.cash_flow')
def cash_flow(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'customer', 'supplier'),
    )
    queryset = CashFlowEntry.objects.filter(
        Q(flow_type=CashFlowEntry.FlowType.PLANNED, status=CashFlowEntry.Status.FORECAST)
        | Q(flow_type=CashFlowEntry.FlowType.REALIZED, status=CashFlowEntry.Status.REALIZED)
    ).select_related('financial_account')
    if 'period_start' in filters:
        queryset = queryset.filter(cash_date__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(cash_date__lte=filters['period_end'])
    if 'status' in filters:
        queryset = queryset.filter(
            status=choice_filter(filters, 'status', CashFlowEntry.Status.choices)
        )
    if 'customer' in filters:
        queryset = queryset.filter(
            title__title_type=FinancialTitle.TitleType.RECEIVABLE,
            title__partner_id=positive_integer_filter(filters, 'customer'),
        )
    if 'supplier' in filters:
        queryset = queryset.filter(
            title__title_type=FinancialTitle.TitleType.PAYABLE,
            title__partner_id=positive_integer_filter(filters, 'supplier'),
        )
    rows = (
        {
            'cash_date': item.cash_date,
            'flow_type': item.get_flow_type_display(),
            'direction': item.get_direction_display(),
            'account': item.financial_account.name if item.financial_account else 'Não informada',
            'description': item.description,
            'amount': item.amount,
        }
        for item in queryset.order_by('cash_date', 'direction', 'pk')
    )
    return ReportDataset(
        title='Fluxo de caixa realizado e projetado',
        columns=(
            ReportColumn('cash_date', 'Data', 'date'),
            ReportColumn('flow_type', 'Tipo', 'status'),
            ReportColumn('direction', 'Direção', 'status'),
            ReportColumn('account', 'Conta'),
            ReportColumn('description', 'Descrição'),
            ReportColumn('amount', 'Valor', 'decimal'),
        ),
        rows=rows,
    )


@register_executor('finance.period_result')
def period_result(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'customer', 'supplier'),
    )
    queryset = CashFlowEntry.objects.filter(
        flow_type=CashFlowEntry.FlowType.REALIZED,
        status=CashFlowEntry.Status.REALIZED,
    )
    if 'period_start' in filters:
        queryset = queryset.filter(cash_date__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(cash_date__lte=filters['period_end'])
    if 'status' in filters:
        queryset = queryset.filter(
            status=choice_filter(filters, 'status', CashFlowEntry.Status.choices)
        )
    if 'customer' in filters:
        queryset = queryset.filter(
            title__title_type=FinancialTitle.TitleType.RECEIVABLE,
            title__partner_id=positive_integer_filter(filters, 'customer'),
        )
    if 'supplier' in filters:
        queryset = queryset.filter(
            title__title_type=FinancialTitle.TitleType.PAYABLE,
            title__partner_id=positive_integer_filter(filters, 'supplier'),
        )
    inflow_case = Case(
        When(direction=CashFlowEntry.Direction.INFLOW, then='amount'),
        default=Value(ZERO_MONEY),
        output_field=MONEY_FIELD,
    )
    outflow_case = Case(
        When(direction=CashFlowEntry.Direction.OUTFLOW, then='amount'),
        default=Value(ZERO_MONEY),
        output_field=MONEY_FIELD,
    )
    aggregates = (
        queryset.annotate(period=TruncMonth('cash_date'))
        .values('period')
        .annotate(
            inflow=Coalesce(Sum(inflow_case), Value(ZERO_MONEY), output_field=MONEY_FIELD),
            outflow=Coalesce(Sum(outflow_case), Value(ZERO_MONEY), output_field=MONEY_FIELD),
        )
        .order_by('period')
    )
    rows = (
        {
            'period': item['period'],
            'inflow': item['inflow'],
            'outflow': item['outflow'],
            'net_result': item['inflow'] - item['outflow'],
        }
        for item in aggregates
    )
    return ReportDataset(
        title='Resultado financeiro por período',
        columns=(
            ReportColumn('period', 'Período', 'date'),
            ReportColumn('inflow', 'Entradas', 'decimal'),
            ReportColumn('outflow', 'Saídas', 'decimal'),
            ReportColumn('net_result', 'Resultado líquido', 'decimal'),
        ),
        rows=rows,
    )
