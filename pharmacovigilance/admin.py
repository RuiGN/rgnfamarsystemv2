from django.contrib import admin
from pharmacovigilance.models import (
    PharmacovigilanceAction,
    PharmacovigilanceCase,
    PharmacovigilanceCausalityAssessment,
    PharmacovigilanceClassification,
    PharmacovigilanceInvestigation,
    PharmacovigilanceLink,
    PharmacovigilanceSafetyReport,
)


@admin.register(PharmacovigilanceCase)
class PharmacovigilanceCaseAdmin(admin.ModelAdmin):
    list_display = (
        'case_number',
        'case_type',
        'status',
        'seriousness',
        'severity',
        'product',
        'responsible',
        'country_ref',
        'state_ref',
        'city_ref',
        'event_reported_at',
    )
    list_filter = (
        'case_type',
        'source',
        'status',
        'seriousness',
        'severity',
        'outcome',
        'country',
        'country_ref',
        'state_ref',
        'city_ref',
    )
    search_fields = (
        'case_number',
        'description',
        'patient_identifier_hash',
        'product__code',
        'stock_lot__lot_number',
        'customer__legal_name',
        'city_ref__name',
        'state_ref__name',
        'country_ref__name',
    )
    autocomplete_fields = (
        'product',
        'stock_lot',
        'customer',
        'responsible',
        'reported_by',
        'triaged_by',
        'investigation_started_by',
        'closed_by',
        'country_ref',
        'state_ref',
        'city_ref',
    )
    readonly_fields = ('case_number', 'triaged_at', 'investigation_started_at', 'closed_at')


@admin.register(PharmacovigilanceClassification)
class PharmacovigilanceClassificationAdmin(admin.ModelAdmin):
    list_display = (
        'case',
        'category',
        'seriousness',
        'expectedness',
        'classified_by',
        'classified_at',
    )
    list_filter = ('category', 'seriousness', 'expectedness', 'classified_at')
    search_fields = ('case__case_number', 'listedness_reference', 'notes')
    autocomplete_fields = ('case', 'classified_by')
    readonly_fields = ('classified_at',)


@admin.register(PharmacovigilanceCausalityAssessment)
class PharmacovigilanceCausalityAssessmentAdmin(admin.ModelAdmin):
    list_display = ('case', 'method', 'result', 'assessed_by', 'assessed_at')
    list_filter = ('method', 'result', 'assessed_at')
    search_fields = ('case__case_number', 'rationale')
    autocomplete_fields = ('case', 'assessed_by')
    readonly_fields = ('assessed_at',)


@admin.register(PharmacovigilanceInvestigation)
class PharmacovigilanceInvestigationAdmin(admin.ModelAdmin):
    list_display = ('case', 'status', 'responsible', 'completed_at')
    list_filter = ('status', 'completed_at')
    search_fields = ('case__case_number', 'summary', 'root_cause', 'conclusion')
    autocomplete_fields = ('case', 'responsible', 'completed_by')
    readonly_fields = ('completed_at',)


@admin.register(PharmacovigilanceAction)
class PharmacovigilanceActionAdmin(admin.ModelAdmin):
    list_display = (
        'action_number',
        'case',
        'action_type',
        'status',
        'mandatory',
        'due_date',
        'responsible',
    )
    list_filter = ('action_type', 'status', 'mandatory', 'evidence_required', 'due_date')
    search_fields = (
        'action_number',
        'case__case_number',
        'title',
        'description',
        'completion_notes',
        'evidence_reference',
        'content_hash',
    )
    autocomplete_fields = ('case', 'responsible', 'completed_by')
    readonly_fields = ('action_number', 'completed_at')


@admin.register(PharmacovigilanceLink)
class PharmacovigilanceLinkAdmin(admin.ModelAdmin):
    list_display = ('case', 'link_type', 'reference_code')
    list_filter = ('link_type',)
    search_fields = ('case__case_number', 'reference_code', 'description')
    autocomplete_fields = (
        'case',
        'customer_complaint',
        'deviation_event',
        'capa',
        'stock_lot',
        'customer',
        'product',
        'regulatory_dossier',
        'document',
    )


@admin.register(PharmacovigilanceSafetyReport)
class PharmacovigilanceSafetyReportAdmin(admin.ModelAdmin):
    list_display = (
        'case',
        'report_type',
        'title',
        'status',
        'case_count',
        'serious_cases',
        'recurrence_count',
    )
    list_filter = ('report_type', 'status', 'generated_at')
    search_fields = ('case__case_number', 'title', 'content_reference', 'indicator_summary')
    autocomplete_fields = ('case', 'generated_by')
    readonly_fields = (
        'status',
        'content_reference',
        'case_count',
        'serious_cases',
        'recurrence_count',
        'indicator_summary',
        'generated_at',
    )
