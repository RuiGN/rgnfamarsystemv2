from django.contrib import admin
from base.admin_mixins import GxpRetentionModelAdmin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from deviations.models import (
    DeviationApproval,
    DeviationEvidence,
    DeviationImpactAssessment,
    DeviationInvestigation,
    DeviationLink,
    QualityEvent,
)


@admin.register(QualityEvent)
class QualityEventAdmin(AutomaticGeneratedFieldsAdminMixin, GxpRetentionModelAdmin):
    list_display = (
        'event_number',
        'event_type',
        'origin',
        'area',
        'severity',
        'criticality',
        'status',
        'responsible',
    )
    list_filter = ('event_type', 'origin', 'status', 'severity', 'criticality', 'area')
    search_fields = (
        'event_number',
        'area',
        'description',
        'product__code',
        'stock_lot__lot_number',
    )
    autocomplete_fields = (
        'product',
        'stock_lot',
        'controlled_document',
        'supplier',
        'customer',
        'responsible',
        'opened_by',
        'closed_by',
    )
    readonly_fields = ('event_number', 'opened_at', 'closed_at')


@admin.register(DeviationEvidence)
class DeviationEvidenceAdmin(GxpRetentionModelAdmin):
    list_display = ('event', 'title', 'content_hash', 'uploaded_by')
    list_filter = ('uploaded_by',)
    search_fields = ('event__event_number', 'title', 'file_reference', 'content_hash', 'notes')
    autocomplete_fields = ('event', 'uploaded_by')


@admin.register(DeviationInvestigation)
class DeviationInvestigationAdmin(GxpRetentionModelAdmin):
    list_display = ('event', 'status', 'investigator', 'concluded_by', 'concluded_at')
    list_filter = ('status', 'concluded_at')
    search_fields = (
        'event__event_number',
        'immediate_actions',
        'containment_actions',
        'root_cause',
        'impact_conclusion',
        'conclusion',
    )
    autocomplete_fields = ('event', 'investigator', 'concluded_by')
    readonly_fields = ('concluded_at',)


@admin.register(DeviationImpactAssessment)
class DeviationImpactAssessmentAdmin(GxpRetentionModelAdmin):
    list_display = (
        'event',
        'is_completed',
        'impacts_quality',
        'impacts_regulatory',
        'impacts_inventory',
        'assessed_by',
    )
    list_filter = (
        'is_completed',
        'impacts_quality',
        'impacts_safety',
        'impacts_efficacy',
        'impacts_regulatory',
        'impacts_patient',
        'impacts_inventory',
        'impacts_cost',
        'impacts_deadline',
    )
    search_fields = ('event__event_number', 'summary')
    autocomplete_fields = ('event', 'assessed_by', 'completed_by')
    readonly_fields = ('completed_at',)


@admin.register(DeviationApproval)
class DeviationApprovalAdmin(GxpRetentionModelAdmin):
    list_display = ('event', 'role', 'approver', 'required', 'decision', 'decided_at')
    list_filter = ('role', 'required', 'decision', 'decided_at')
    search_fields = ('event__event_number', 'approver__email', 'comments')
    autocomplete_fields = ('event', 'approver', 'decided_by')
    readonly_fields = ('decided_at',)


@admin.register(DeviationLink)
class DeviationLinkAdmin(GxpRetentionModelAdmin):
    list_display = ('event', 'link_type', 'reference_code')
    list_filter = ('link_type',)
    search_fields = ('event__event_number', 'reference_code', 'notes')
    autocomplete_fields = (
        'event',
        'customer_complaint',
        'quality_result',
        'stock_lot',
        'controlled_document',
    )
