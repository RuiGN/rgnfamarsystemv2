from django.contrib import admin
from risks.models import (
    RiskAlert,
    RiskAssessment,
    RiskControl,
    RiskLink,
    RiskMitigationAction,
    RiskRecord,
    RiskReview,
)


@admin.register(RiskRecord)
class RiskRecordAdmin(admin.ModelAdmin):
    list_display = (
        'risk_number',
        'risk_category',
        'title',
        'status',
        'initial_level',
        'residual_level',
        'owner',
        'due_date',
        'next_review_date',
    )
    list_filter = (
        'risk_category',
        'status',
        'initial_level',
        'residual_level',
        'due_date',
        'next_review_date',
    )
    search_fields = ('risk_number', 'title', 'description', 'process_area', 'owner__email')
    autocomplete_fields = (
        'owner',
        'identified_by',
        'treatment_started_by',
        'monitoring_started_by',
        'closed_by',
    )
    readonly_fields = (
        'risk_number',
        'identified_at',
        'treatment_started_at',
        'monitoring_started_at',
        'closed_at',
        'initial_score',
        'initial_level',
        'residual_score',
        'residual_level',
    )


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        'risk',
        'assessment_type',
        'method',
        'score',
        'risk_level',
        'assessed_by',
        'assessed_at',
    )
    list_filter = ('assessment_type', 'method', 'risk_level', 'assessed_at')
    search_fields = ('risk__risk_number', 'risk__title', 'rationale', 'assessed_by__email')
    autocomplete_fields = ('risk', 'assessed_by')
    readonly_fields = ('score', 'risk_level', 'assessed_at')


@admin.register(RiskControl)
class RiskControlAdmin(admin.ModelAdmin):
    list_display = ('risk', 'control_type', 'title', 'status', 'owner')
    list_filter = ('control_type', 'status')
    search_fields = (
        'risk__risk_number',
        'risk__title',
        'title',
        'description',
        'evidence_reference',
        'content_hash',
    )
    autocomplete_fields = ('risk', 'owner')


@admin.register(RiskMitigationAction)
class RiskMitigationActionAdmin(admin.ModelAdmin):
    list_display = (
        'risk',
        'action_type',
        'title',
        'responsible',
        'due_date',
        'mandatory',
        'status',
    )
    list_filter = ('action_type', 'status', 'mandatory', 'evidence_required', 'due_date')
    search_fields = (
        'risk__risk_number',
        'risk__title',
        'title',
        'description',
        'completion_notes',
        'evidence_reference',
        'content_hash',
    )
    autocomplete_fields = ('risk', 'responsible', 'completed_by')
    readonly_fields = ('completed_at',)


@admin.register(RiskLink)
class RiskLinkAdmin(admin.ModelAdmin):
    list_display = ('risk', 'link_type', 'reference_code')
    list_filter = ('link_type',)
    search_fields = ('risk__risk_number', 'risk__title', 'reference_code', 'impact_description')
    autocomplete_fields = (
        'risk',
        'product',
        'document',
        'deviation_event',
        'capa',
        'change_control',
        'audit',
        'supplier',
    )


@admin.register(RiskReview)
class RiskReviewAdmin(admin.ModelAdmin):
    list_display = ('risk', 'planned_date', 'status', 'reviewer', 'next_review_date')
    list_filter = ('status', 'planned_date', 'next_review_date')
    search_fields = ('risk__risk_number', 'risk__title', 'review_scope', 'result')
    autocomplete_fields = ('risk', 'reviewer', 'completed_by')
    readonly_fields = ('completed_at',)


@admin.register(RiskAlert)
class RiskAlertAdmin(admin.ModelAdmin):
    list_display = ('risk', 'alert_type', 'severity', 'status', 'due_date', 'acknowledged_at')
    list_filter = ('alert_type', 'severity', 'status', 'due_date')
    search_fields = ('risk__risk_number', 'risk__title', 'message')
    autocomplete_fields = ('risk', 'action', 'acknowledged_by')
    readonly_fields = ('acknowledged_at',)
