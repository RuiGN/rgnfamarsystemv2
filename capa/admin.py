from django.contrib import admin
from base.admin_mixins import GxpRetentionModelAdmin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from capa.models import (
    CapaAction,
    CapaApproval,
    CapaEvidence,
    CapaNotification,
    CapaRecord,
    EffectivenessCheck,
)


@admin.register(CapaRecord)
class CapaRecordAdmin(AutomaticGeneratedFieldsAdminMixin, GxpRetentionModelAdmin):
    list_display = (
        'capa_number',
        'source_type',
        'title',
        'status',
        'owner',
        'due_date',
        'closed_at',
    )
    list_filter = ('source_type', 'status', 'requires_effectiveness_check', 'due_date', 'closed_at')
    search_fields = (
        'capa_number',
        'title',
        'root_cause',
        'action_plan',
        'source_reference',
        'closure_summary',
    )
    autocomplete_fields = (
        'deviation_event',
        'customer_complaint',
        'quality_result',
        'owner',
        'opened_by',
        'closed_by',
    )
    readonly_fields = ('capa_number', 'opened_at', 'closed_at')


@admin.register(CapaAction)
class CapaActionAdmin(GxpRetentionModelAdmin):
    list_display = (
        'capa',
        'action_type',
        'title',
        'responsible',
        'due_date',
        'status',
        'completed_at',
    )
    list_filter = ('action_type', 'status', 'evidence_required', 'due_date', 'completed_at')
    search_fields = (
        'capa__capa_number',
        'title',
        'description',
        'completion_notes',
        'responsible__email',
    )
    autocomplete_fields = ('capa', 'responsible', 'completed_by')
    readonly_fields = ('completed_at',)


@admin.register(CapaEvidence)
class CapaEvidenceAdmin(GxpRetentionModelAdmin):
    list_display = ('capa', 'action', 'title', 'content_hash', 'uploaded_by')
    list_filter = ('uploaded_by',)
    search_fields = ('capa__capa_number', 'title', 'file_reference', 'content_hash', 'notes')
    autocomplete_fields = ('capa', 'action', 'uploaded_by')


@admin.register(EffectivenessCheck)
class EffectivenessCheckAdmin(GxpRetentionModelAdmin):
    list_display = ('capa', 'planned_date', 'status', 'verified_by', 'verified_at')
    list_filter = ('status', 'planned_date', 'verified_at')
    search_fields = ('capa__capa_number', 'criteria', 'result', 'evidence_reference')
    autocomplete_fields = ('capa', 'verified_by')
    readonly_fields = ('verified_at',)


@admin.register(CapaApproval)
class CapaApprovalAdmin(GxpRetentionModelAdmin):
    list_display = ('capa', 'role', 'approver', 'required', 'decision', 'decided_at')
    list_filter = ('role', 'required', 'decision', 'decided_at')
    search_fields = ('capa__capa_number', 'approver__email', 'comments')
    autocomplete_fields = ('capa', 'approver', 'decided_by')
    readonly_fields = ('decided_at',)


@admin.register(CapaNotification)
class CapaNotificationAdmin(GxpRetentionModelAdmin):
    list_display = ('capa', 'notification_type', 'recipient', 'due_date', 'status', 'sent_at')
    list_filter = ('notification_type', 'status', 'due_date', 'sent_at')
    search_fields = ('capa__capa_number', 'recipient__email', 'message')
    autocomplete_fields = ('capa', 'action', 'approval', 'effectiveness_check', 'recipient')
    readonly_fields = ('sent_at',)
