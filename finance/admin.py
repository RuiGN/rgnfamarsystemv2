from django.contrib import admin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from finance.models import (
    CashFlowEntry,
    ChartOfAccount,
    FinancialAccount,
    FinancialCategory,
    FinancialPeriodClosing,
    FinancialSettlement,
    FinancialTitle,
)


@admin.register(ChartOfAccount)
class ChartOfAccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'parent', 'is_active')
    list_filter = ('account_type', 'is_active')
    search_fields = ('code', 'name')
    autocomplete_fields = ('parent',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FinancialCategory)
class FinancialCategoryAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'category_type', 'chart_account', 'is_active')
    list_filter = ('category_type', 'is_active')
    search_fields = ('code', 'name', 'chart_account__code', 'chart_account__name')
    autocomplete_fields = ('chart_account',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FinancialAccount)
class FinancialAccountAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'bank_name', 'current_balance', 'is_active')
    list_filter = ('account_type', 'is_active')
    search_fields = ('code', 'name', 'bank_name', 'agency_number', 'account_number')
    autocomplete_fields = ()
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FinancialTitle)
class FinancialTitleAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        'title_number',
        'title_type',
        'source_type',
        'partner',
        'due_date',
        'original_amount',
        'open_amount',
        'status',
    )
    list_filter = ('title_type', 'source_type', 'status', 'due_date')
    search_fields = (
        'title_number',
        'partner__legal_name',
        'fiscal_document_number',
        'contract_reference',
        'sale_reference',
    )
    autocomplete_fields = (
        'partner',
        'category',
        'financial_account',
        'purchase_order',
        'approved_by',
    )
    readonly_fields = ('paid_amount', 'approved_by', 'approved_at', 'created_at', 'updated_at')


@admin.register(FinancialSettlement)
class FinancialSettlementAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'financial_account',
        'settlement_date',
        'method',
        'amount',
        'net_amount',
        'status',
    )
    list_filter = ('method', 'status', 'settlement_date')
    search_fields = ('title__title_number', 'reference', 'notes')
    autocomplete_fields = ('title', 'financial_account', 'reconciled_by', 'reversed_by')
    readonly_fields = (
        'net_amount',
        'reconciled_by',
        'reconciled_at',
        'reversed_by',
        'reversed_at',
        'created_at',
        'updated_at',
    )


@admin.register(CashFlowEntry)
class CashFlowEntryAdmin(admin.ModelAdmin):
    list_display = (
        'cash_date',
        'flow_type',
        'direction',
        'title',
        'financial_account',
        'amount',
        'status',
    )
    list_filter = ('flow_type', 'direction', 'status', 'cash_date')
    search_fields = ('title__title_number', 'description')
    autocomplete_fields = ('title', 'settlement', 'financial_account')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FinancialPeriodClosing)
class FinancialPeriodClosingAdmin(admin.ModelAdmin):
    list_display = ('period_year', 'period_month', 'status', 'closed_by', 'closed_at')
    list_filter = ('status', 'period_year', 'period_month')
    search_fields = ('validation_notes',)
    autocomplete_fields = ('closed_by',)
    readonly_fields = ('closed_by', 'closed_at', 'created_at', 'updated_at')
