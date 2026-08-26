from django.contrib import admin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from quality.models import (
    AnalyticalSpecification,
    LaboratoryInvestigation,
    QualityAnalysis,
    QualityDocument,
    QualityResult,
    QualitySample,
)


@admin.register(AnalyticalSpecification)
class AnalyticalSpecificationAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'parameter_name',
        'version',
        'method_code',
        'status',
        'effective_from',
        'effective_to',
    )
    list_filter = ('status', 'method_code', 'effective_from')
    search_fields = (
        'product__code',
        'product__description',
        'method_code',
        'method_name',
        'parameter_name',
        'acceptance_criteria',
    )
    autocomplete_fields = ('product', 'stock_lot', 'unit', 'approved_by')
    readonly_fields = ('approved_at',)


@admin.register(QualitySample)
class QualitySampleAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        'sample_number',
        'sample_type',
        'product',
        'stock_lot',
        'status',
        'collected_at',
        'approved_at',
    )
    list_filter = ('sample_type', 'status', 'collected_at', 'approved_at')
    search_fields = (
        'sample_number',
        'product__code',
        'product__description',
        'stock_lot__lot_number',
    )
    autocomplete_fields = (
        'product',
        'stock_lot',
        'specification',
        'source_purchase_receipt',
        'source_production_order',
        'customer_complaint',
        'unit',
        'collected_by',
        'received_by',
        'started_by',
        'reviewed_by',
        'approved_by',
        'rejected_by',
    )
    readonly_fields = (
        'sample_number',
        'collected_at',
        'received_at',
        'started_at',
        'reviewed_at',
        'approved_at',
        'rejected_at',
    )


@admin.register(QualityAnalysis)
class QualityAnalysisAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        'analysis_number',
        'sample',
        'specification',
        'status',
        'equipment_code',
        'analyst',
        'reviewer',
        'approver',
    )
    list_filter = ('status', 'equipment_code')
    search_fields = (
        'analysis_number',
        'sample__sample_number',
        'method_reference',
        'equipment_code',
        'reagent_lot',
        'standard_lot',
    )
    autocomplete_fields = ('sample', 'specification', 'analyst', 'reviewer', 'approver')
    readonly_fields = (
        'analysis_number',
        'started_at',
        'completed_at',
        'reviewed_at',
        'approved_at',
    )


@admin.register(QualityResult)
class QualityResultAdmin(admin.ModelAdmin):
    list_display = (
        'analysis',
        'parameter_name',
        'result_type',
        'numeric_result',
        'text_result',
        'result_status',
    )
    list_filter = ('result_type', 'result_status')
    search_fields = (
        'analysis__analysis_number',
        'parameter_name',
        'text_result',
        'attachment_reference',
    )
    autocomplete_fields = ('analysis', 'specification', 'unit', 'recorded_by')
    readonly_fields = ('is_blocking',)


@admin.register(LaboratoryInvestigation)
class LaboratoryInvestigationAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        'investigation_number',
        'sample',
        'result',
        'investigation_type',
        'status',
        'opened_at',
        'concluded_at',
    )
    list_filter = ('investigation_type', 'status', 'opened_at')
    search_fields = ('investigation_number', 'justification', 'root_cause', 'conclusion')
    autocomplete_fields = ('sample', 'analysis', 'result', 'opened_by', 'concluded_by')
    readonly_fields = ('investigation_number', 'opened_at', 'started_at', 'concluded_at')


@admin.register(QualityDocument)
class QualityDocumentAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        'document_number',
        'document_type',
        'sample',
        'product',
        'stock_lot',
        'status',
        'issued_by',
        'issued_at',
    )
    list_filter = ('document_type', 'status', 'issued_at')
    search_fields = (
        'document_number',
        'sample__sample_number',
        'product__code',
        'stock_lot__lot_number',
        'summary',
        'conclusion',
    )
    autocomplete_fields = ('sample', 'product', 'stock_lot', 'issued_by')
    readonly_fields = ('document_number', 'issued_at')
