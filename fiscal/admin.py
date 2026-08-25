from django.contrib import admin
from base.admin_mixins import ImmutableAuditAdminMixin
from fiscal.models import (
    FiscalAuditTrail,
    FiscalBookEntry,
    FiscalCompany,
    FiscalDocument,
    FiscalDocumentItem,
    FiscalEmailDelivery,
    FiscalEmissionEvent,
    FiscalMunicipality,
    FiscalNCM,
    FiscalObligation,
    FiscalOperationCode,
    FiscalTax,
    FiscalUnit,
    TaxAssessmentPeriod,
    TaxRule,
    TaxSituation,
)


@admin.register(FiscalCompany)
class FiscalCompanyAdmin(admin.ModelAdmin):
    list_display = ('legal_name', 'document', 'tax_regime', 'city_ref', 'state_ref', 'is_active')
    list_filter = ('tax_regime', 'state_ref', 'is_active')
    search_fields = (
        'legal_name',
        'document',
        'state_registration',
        'municipal_registration',
        'city_ref__name',
        'state_ref__name',
        'state_ref__name',
    )
    autocomplete_fields = ('city_ref', 'state_ref')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FiscalMunicipality)
class FiscalMunicipalityAdmin(admin.ModelAdmin):
    list_display = ('ibge_code', 'name', 'city_ref', 'state_ref', 'is_active')
    list_filter = ('state_ref', 'is_active')
    search_fields = ('ibge_code', 'name', 'city_ref__name', 'state_ref__name')
    autocomplete_fields = ('city_ref', 'state_ref')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FiscalUnit)
class FiscalUnitAdmin(admin.ModelAdmin):
    list_display = ('code', 'description', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'description')
    autocomplete_fields = ()
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FiscalNCM)
class FiscalNCMAdmin(admin.ModelAdmin):
    list_display = ('code', 'description', 'cest', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'description', 'cest')
    autocomplete_fields = ()
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FiscalOperationCode)
class FiscalOperationCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'description', 'direction', 'is_active')
    list_filter = ('direction', 'is_active')
    search_fields = ('code', 'description')
    autocomplete_fields = ()
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TaxSituation)
class TaxSituationAdmin(admin.ModelAdmin):
    list_display = ('tax_kind', 'regime_kind', 'code', 'description', 'is_active')
    list_filter = ('tax_kind', 'regime_kind', 'is_active')
    search_fields = ('code', 'description')
    autocomplete_fields = ()
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'tax_kind', 'ncm', 'cfop', 'tax_situation', 'rate_percent', 'status')
    list_filter = ('tax_kind', 'status', 'effective_from')
    search_fields = ('name', 'ncm__code', 'cfop__code', 'tax_situation__code')
    autocomplete_fields = (
        'company',
        'product',
        'partner',
        'ncm',
        'cfop',
        'tax_situation',
        'approved_by',
    )
    readonly_fields = ('approved_by', 'approved_at', 'created_at', 'updated_at')


@admin.register(FiscalDocument)
class FiscalDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'number',
        'series',
        'document_type',
        'operation_type',
        'partner',
        'issue_date',
        'total_amount',
        'status',
        'emission_status',
    )
    list_filter = (
        'document_type',
        'operation_type',
        'status',
        'emission_status',
        'environment',
        'issue_date',
    )
    search_fields = (
        'number',
        'series',
        'access_key',
        'authorization_protocol',
        'partner__legal_name',
    )
    autocomplete_fields = (
        'company',
        'partner',
        'purchase_order',
        'purchase_receipt',
        'financial_title',
        'reviewed_by',
        'approved_by',
        'posted_by',
    )
    readonly_fields = (
        'total_products',
        'total_taxes',
        'retained_taxes',
        'total_amount',
        'reviewed_by',
        'reviewed_at',
        'approved_by',
        'approved_at',
        'posted_by',
        'posted_at',
        'emission_status',
        'access_key',
        'authorization_protocol',
        'authorization_at',
        'cancel_protocol',
        'cancelled_at',
        'rejection_code',
        'rejection_reason',
        'created_at',
        'updated_at',
    )


@admin.register(FiscalDocumentItem)
class FiscalDocumentItemAdmin(admin.ModelAdmin):
    list_display = (
        'document',
        'line_number',
        'product',
        'ncm',
        'cfop',
        'quantity',
        'unit_price',
        'line_total',
    )
    list_filter = ('ncm', 'cfop')
    search_fields = (
        'document__number',
        'product__code',
        'product__description',
        'ncm__code',
        'cfop__code',
    )
    autocomplete_fields = ('document', 'product', 'fiscal_unit', 'ncm', 'cfop', 'tax_situation')
    readonly_fields = ('line_subtotal', 'line_total', 'created_at', 'updated_at')


@admin.register(FiscalTax)
class FiscalTaxAdmin(admin.ModelAdmin):
    list_display = (
        'document',
        'item',
        'tax_kind',
        'base_amount',
        'rate_percent',
        'tax_amount',
        'is_retained',
    )
    list_filter = ('tax_kind', 'is_retained')
    search_fields = ('document__number', 'tax_kind')
    autocomplete_fields = ('document', 'item', 'tax_rule')
    readonly_fields = ('tax_amount', 'created_at', 'updated_at')


@admin.register(TaxAssessmentPeriod)
class TaxAssessmentPeriodAdmin(admin.ModelAdmin):
    list_display = (
        'period_year',
        'period_month',
        'tax_kind',
        'debit_amount',
        'credit_amount',
        'balance_amount',
        'status',
    )
    list_filter = ('tax_kind', 'status', 'period_year', 'period_month')
    search_fields = ('notes',)
    autocomplete_fields = ('closed_by',)
    readonly_fields = (
        'debit_amount',
        'credit_amount',
        'retained_amount',
        'balance_amount',
        'calculated_at',
        'closed_by',
        'closed_at',
        'created_at',
        'updated_at',
    )


@admin.register(FiscalBookEntry)
class FiscalBookEntryAdmin(admin.ModelAdmin):
    list_display = ('document', 'book_type', 'entry_date', 'total_amount', 'tax_amount')
    list_filter = ('book_type', 'entry_date')
    search_fields = ('document__number', 'notes')
    autocomplete_fields = ('document',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FiscalObligation)
class FiscalObligationAdmin(admin.ModelAdmin):
    list_display = ('obligation_type', 'period_year', 'period_month', 'due_date', 'status')
    list_filter = ('obligation_type', 'status', 'due_date')
    search_fields = ('protocol_number', 'notes')
    autocomplete_fields = ('submitted_by',)
    readonly_fields = ('submitted_by', 'submitted_at', 'created_at', 'updated_at')


@admin.register(FiscalAuditTrail)
class FiscalAuditTrailAdmin(ImmutableAuditAdminMixin, admin.ModelAdmin):
    list_display = ('entity_name', 'object_id', 'action', 'actor', 'created_at')
    list_filter = ('entity_name', 'action', 'created_at')
    search_fields = ('entity_name', 'object_id', 'action')
    autocomplete_fields = ('actor',)
    readonly_fields = (
        'actor',
        'entity_name',
        'object_id',
        'action',
        'details',
        'created_at',
        'updated_at',
    )


@admin.register(FiscalEmissionEvent)
class FiscalEmissionEventAdmin(ImmutableAuditAdminMixin, admin.ModelAdmin):
    list_display = (
        'document',
        'event_type',
        'provider',
        'status',
        'access_key',
        'protocol',
        'actor',
        'created_at',
    )
    list_filter = ('event_type', 'provider', 'status', 'created_at')
    search_fields = ('document__number', 'access_key', 'protocol', 'message')
    autocomplete_fields = ('document', 'actor', 'xml_file', 'danfe_file')
    readonly_fields = tuple((field.name for field in FiscalEmissionEvent._meta.fields))


@admin.register(FiscalEmailDelivery)
class FiscalEmailDeliveryAdmin(ImmutableAuditAdminMixin, admin.ModelAdmin):
    list_display = ('document', 'recipient_email', 'status', 'scheduled_at', 'sent_at', 'attempts')
    list_filter = ('status', 'scheduled_at', 'sent_at')
    search_fields = ('document__number', 'recipient_email', 'subject', 'last_error')
    autocomplete_fields = ('document', 'requested_by', 'xml_file', 'danfe_file')
    readonly_fields = tuple((field.name for field in FiscalEmailDelivery._meta.fields))
