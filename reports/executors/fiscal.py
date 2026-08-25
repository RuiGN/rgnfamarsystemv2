from datetime import date
from typing import cast

from django.db.models import Q

from fiscal.models import FiscalBookEntry, FiscalDocument, TaxAssessmentPeriod
from reports.contracts import ReportColumn, ReportContext, ReportDataset
from reports.executors._filters import choice_filter, positive_integer_filter
from reports.filters import normalize_report_filters
from reports.registry import register_executor


@register_executor('fiscal.documents')
def documents(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'supplier', 'customer'),
    )
    queryset = FiscalDocument.objects.select_related('partner')
    if 'period_start' in filters:
        queryset = queryset.filter(issue_date__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(issue_date__lte=filters['period_end'])
    if 'status' in filters:
        queryset = queryset.filter(
            status=choice_filter(filters, 'status', FiscalDocument.Status.choices)
        )
    if 'supplier' in filters:
        queryset = queryset.filter(
            document_type=FiscalDocument.DocumentType.INBOUND,
            partner_id=positive_integer_filter(filters, 'supplier'),
        )
    if 'customer' in filters:
        queryset = queryset.filter(
            document_type=FiscalDocument.DocumentType.OUTBOUND,
            partner_id=positive_integer_filter(filters, 'customer'),
        )
    rows = (
        {
            'issue_date': item.issue_date,
            'number': item.number,
            'series': item.series,
            'direction': item.get_document_type_display(),
            'partner': item.partner.legal_name,
            'status': item.get_status_display(),
            'total_amount': item.total_amount,
        }
        for item in queryset.order_by('issue_date', 'number', 'series', 'pk')
    )
    return ReportDataset(
        title='Documentos fiscais por período e situação',
        columns=(
            ReportColumn('issue_date', 'Emissão', 'date'),
            ReportColumn('number', 'Número'),
            ReportColumn('series', 'Série'),
            ReportColumn('direction', 'Direção', 'status'),
            ReportColumn('partner', 'Parceiro'),
            ReportColumn('status', 'Situação', 'status'),
            ReportColumn('total_amount', 'Valor total', 'decimal'),
        ),
        rows=rows,
    )


@register_executor('fiscal.tax_assessment')
def tax_assessment(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status'),
    )
    queryset = TaxAssessmentPeriod.objects.all()
    if 'period_start' in filters:
        start = cast(date, filters['period_start'])
        queryset = queryset.filter(
            Q(period_year__gt=start.year) | Q(period_year=start.year, period_month__gte=start.month)
        )
    if 'period_end' in filters:
        end = cast(date, filters['period_end'])
        queryset = queryset.filter(
            Q(period_year__lt=end.year) | Q(period_year=end.year, period_month__lte=end.month)
        )
    if 'status' in filters:
        queryset = queryset.filter(
            status=choice_filter(filters, 'status', TaxAssessmentPeriod.Status.choices)
        )
    rows = (
        {
            'period': date(item.period_year, item.period_month, 1),
            'tax_kind': item.get_tax_kind_display(),
            'debit_amount': item.debit_amount,
            'credit_amount': item.credit_amount,
            'amount_due': item.balance_amount,
            'status': item.get_status_display(),
        }
        for item in queryset.order_by('period_year', 'period_month', 'tax_kind', 'pk')
    )
    return ReportDataset(
        title='Apuração de tributos',
        columns=(
            ReportColumn('period', 'Período', 'date'),
            ReportColumn('tax_kind', 'Tributo'),
            ReportColumn('debit_amount', 'Débitos', 'decimal'),
            ReportColumn('credit_amount', 'Créditos', 'decimal'),
            ReportColumn('amount_due', 'Saldo a recolher', 'decimal'),
            ReportColumn('status', 'Situação', 'status'),
        ),
        rows=rows,
    )


@register_executor('fiscal.books')
def books(context: ReportContext) -> ReportDataset:
    filters = normalize_report_filters(
        context.filters,
        allowed=('period_start', 'period_end', 'status', 'supplier', 'customer'),
    )
    queryset = FiscalBookEntry.objects.select_related('document__partner')
    if 'period_start' in filters:
        queryset = queryset.filter(entry_date__gte=filters['period_start'])
    if 'period_end' in filters:
        queryset = queryset.filter(entry_date__lte=filters['period_end'])
    if 'status' in filters:
        queryset = queryset.filter(
            document__status=choice_filter(
                filters,
                'status',
                FiscalDocument.Status.choices,
            )
        )
    if 'supplier' in filters:
        queryset = queryset.filter(
            document__document_type=FiscalDocument.DocumentType.INBOUND,
            document__partner_id=positive_integer_filter(filters, 'supplier'),
        )
    if 'customer' in filters:
        queryset = queryset.filter(
            document__document_type=FiscalDocument.DocumentType.OUTBOUND,
            document__partner_id=positive_integer_filter(filters, 'customer'),
        )
    rows = (
        {
            'entry_date': item.entry_date,
            'book_type': item.get_book_type_display(),
            'document': f'{item.document.number}/{item.document.series}',
            'partner': item.document.partner.legal_name,
            # FiscalBookEntry has no separate tax-base field; its persisted
            # total_amount is the authoritative book value for this contract.
            'tax_base': item.total_amount,
            'tax_amount': item.tax_amount,
        }
        for item in queryset.order_by('entry_date', 'document__number', 'book_type', 'pk')
    )
    return ReportDataset(
        title='Livro de entradas e saídas',
        columns=(
            ReportColumn('entry_date', 'Escrituração', 'date'),
            ReportColumn('book_type', 'Livro', 'status'),
            ReportColumn('document', 'Documento'),
            ReportColumn('partner', 'Parceiro'),
            ReportColumn('tax_base', 'Valor escriturado', 'decimal'),
            ReportColumn('tax_amount', 'Impostos', 'decimal'),
        ),
        rows=rows,
    )
