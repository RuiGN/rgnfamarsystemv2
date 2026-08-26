from django.contrib import admin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from changes.models import (
    ChangeAction,
    ChangeAffectedItem,
    ChangeApproval,
    ChangeAssessment,
    ChangeControl,
    ChangeStockAssessment,
)


@admin.register(ChangeControl)
class ChangeControlAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        'change_number',
        'change_type',
        'title',
        'status',
        'owner',
        'due_date',
        'closed_at',
    )
    list_filter = ('change_type', 'status', 'requires_stock_assessment', 'due_date', 'closed_at')
    search_fields = (
        'change_number',
        'title',
        'scope',
        'justification',
        'affected_areas',
        'equipment_reference',
        'system_reference',
        'impact_summary',
    )
    autocomplete_fields = (
        'owner',
        'requested_by',
        'submitted_by',
        'approved_by',
        'implementation_started_by',
        'closed_by',
    )
    readonly_fields = (
        'change_number',
        'submitted_at',
        'approved_at',
        'implementation_started_at',
        'closed_at',
    )


@admin.register(ChangeAffectedItem)
class ChangeAffectedItemAdmin(admin.ModelAdmin):
    list_display = ('change', 'item_type', 'product', 'document', 'supplier')
    list_filter = ('item_type',)
    search_fields = (
        'change__change_number',
        'reference_code',
        'impact_description',
        'product__code',
        'document__code',
        'supplier__code',
    )
    autocomplete_fields = ('change', 'product', 'document', 'supplier')


@admin.register(ChangeAssessment)
class ChangeAssessmentAdmin(admin.ModelAdmin):
    list_display = ('change', 'department', 'assessor', 'impact_level', 'status', 'completed_at')
    list_filter = ('department', 'impact_level', 'status', 'completed_at')
    search_fields = (
        'change__change_number',
        'impact_description',
        'required_actions',
        'assessor__email',
    )
    autocomplete_fields = ('change', 'assessor', 'completed_by')
    readonly_fields = ('completed_at',)


@admin.register(ChangeAction)
class ChangeActionAdmin(admin.ModelAdmin):
    list_display = (
        'change',
        'action_type',
        'title',
        'responsible',
        'due_date',
        'mandatory',
        'required_before_implementation',
        'status',
    )
    list_filter = (
        'action_type',
        'status',
        'mandatory',
        'required_before_implementation',
        'evidence_required',
        'due_date',
    )
    search_fields = (
        'change__change_number',
        'title',
        'description',
        'completion_notes',
        'evidence_reference',
        'content_hash',
        'responsible__email',
    )
    autocomplete_fields = ('change', 'responsible', 'completed_by')
    readonly_fields = ('completed_at',)


@admin.register(ChangeApproval)
class ChangeApprovalAdmin(admin.ModelAdmin):
    list_display = ('change', 'role', 'approver', 'required', 'decision', 'decided_at')
    list_filter = ('role', 'required', 'decision', 'decided_at')
    search_fields = ('change__change_number', 'approver__email', 'comments')
    autocomplete_fields = ('change', 'approver', 'decided_by')
    readonly_fields = ('decided_at',)


@admin.register(ChangeStockAssessment)
class ChangeStockAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        'change',
        'product',
        'stock_lot',
        'quantity_affected',
        'required',
        'status',
        'decision',
    )
    list_filter = ('required', 'status', 'decision')
    search_fields = (
        'change__change_number',
        'product__code',
        'stock_lot__lot_number',
        'assessment_summary',
    )
    autocomplete_fields = ('change', 'product', 'stock_lot', 'assessed_by')
    readonly_fields = ('assessed_at',)
