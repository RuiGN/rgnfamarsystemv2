from django.contrib import admin
from base.admin_mixins import GxpRetentionModelAdmin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from audits.models import (
    AuditChecklistItem,
    AuditEvidence,
    AuditFinding,
    AuditFindingLink,
    AuditFollowUpAction,
    AuditPlan,
    AuditProgram,
    AuditReport,
)


@admin.register(AuditProgram)
class AuditProgramAdmin(AutomaticGeneratedFieldsAdminMixin, GxpRetentionModelAdmin):
    list_display = ('program_number', 'audit_type', 'title', 'year', 'status', 'owner')
    list_filter = ('audit_type', 'status', 'year')
    search_fields = ('program_number', 'title', 'scope', 'criteria', 'owner__email')
    autocomplete_fields = ('owner',)
    readonly_fields = ('program_number',)


@admin.register(AuditPlan)
class AuditPlanAdmin(AutomaticGeneratedFieldsAdminMixin, GxpRetentionModelAdmin):
    list_display = (
        'audit_number',
        'audit_type',
        'title',
        'status',
        'lead_auditor',
        'scheduled_start',
        'venue_state_ref',
        'venue_city_ref',
        'closed_at',
    )
    list_filter = (
        'audit_type',
        'status',
        'area',
        'scheduled_start',
        'venue_state_ref',
        'venue_city_ref',
        'closed_at',
    )
    search_fields = (
        'audit_number',
        'title',
        'scope',
        'criteria',
        'agenda',
        'auditee_name',
        'area',
        'venue_city_ref__name',
        'venue_state_ref__name',
        'lead_auditor__email',
    )
    autocomplete_fields = (
        'program',
        'supplier',
        'lead_auditor',
        'submitted_by',
        'started_by',
        'completed_by',
        'closed_by',
        'venue_state_ref',
        'venue_city_ref',
    )
    readonly_fields = ('audit_number', 'submitted_at', 'actual_start', 'actual_end', 'closed_at')


@admin.register(AuditChecklistItem)
class AuditChecklistItemAdmin(GxpRetentionModelAdmin):
    list_display = ('audit', 'section', 'required', 'status', 'answered_by')
    list_filter = ('section', 'required', 'status')
    search_fields = (
        'audit__audit_number',
        'section',
        'question',
        'requirement_reference',
        'answer_text',
    )
    autocomplete_fields = ('audit', 'answered_by')
    readonly_fields = ('answered_at',)


@admin.register(AuditFinding)
class AuditFindingAdmin(GxpRetentionModelAdmin):
    list_display = (
        'audit',
        'classification',
        'criticality',
        'title',
        'status',
        'responsible',
        'due_date',
    )
    list_filter = ('classification', 'criticality', 'status', 'due_date')
    search_fields = ('audit__audit_number', 'title', 'description', 'responsible__email')
    autocomplete_fields = ('audit', 'checklist_item', 'responsible')


@admin.register(AuditEvidence)
class AuditEvidenceAdmin(GxpRetentionModelAdmin):
    list_display = ('audit', 'finding', 'title', 'content_hash', 'uploaded_by')
    list_filter = ('uploaded_by',)
    search_fields = (
        'audit__audit_number',
        'finding__title',
        'title',
        'file_reference',
        'content_hash',
        'notes',
    )
    autocomplete_fields = ('audit', 'finding', 'uploaded_by')


@admin.register(AuditFollowUpAction)
class AuditFollowUpActionAdmin(GxpRetentionModelAdmin):
    list_display = ('finding', 'title', 'responsible', 'due_date', 'mandatory', 'status')
    list_filter = ('mandatory', 'evidence_required', 'status', 'due_date')
    search_fields = (
        'finding__audit__audit_number',
        'finding__title',
        'title',
        'description',
        'completion_notes',
        'evidence_reference',
        'content_hash',
    )
    autocomplete_fields = ('finding', 'responsible', 'completed_by')
    readonly_fields = ('completed_at',)


@admin.register(AuditFindingLink)
class AuditFindingLinkAdmin(GxpRetentionModelAdmin):
    list_display = ('finding', 'link_type', 'reference_code')
    list_filter = ('link_type',)
    search_fields = ('finding__audit__audit_number', 'finding__title', 'reference_code')
    autocomplete_fields = (
        'finding',
        'capa',
        'deviation_event',
        'change_control',
        'supplier',
        'document',
    )


@admin.register(AuditReport)
class AuditReportAdmin(GxpRetentionModelAdmin):
    list_display = (
        'audit',
        'status',
        'total_findings',
        'critical_findings',
        'major_findings',
        'compliance_rate',
        'issued_at',
    )
    list_filter = ('status', 'issued_at')
    search_fields = ('audit__audit_number', 'executive_summary', 'conclusion', 'issued_by__email')
    autocomplete_fields = ('audit', 'issued_by')
    readonly_fields = (
        'status',
        'total_findings',
        'critical_findings',
        'major_findings',
        'minor_findings',
        'opportunities',
        'total_checklist_items',
        'conform_items',
        'nonconform_items',
        'compliance_rate',
        'issued_at',
    )
