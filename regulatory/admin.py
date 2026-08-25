from django.contrib import admin
from regulatory.models import (
    RegulatoryAlert,
    RegulatoryCommitment,
    RegulatoryDossier,
    RegulatoryEvidence,
    RegulatoryLink,
    RegulatoryPetition,
    RegulatoryProduct,
    RegulatoryRegistration,
    RegulatoryReport,
    RegulatoryRequirement,
)


@admin.register(RegulatoryProduct)
class RegulatoryProductAdmin(admin.ModelAdmin):
    list_display = ('regulatory_code', 'presentation', 'product', 'status', 'responsible')
    list_filter = ('status', 'dosage_form', 'route')
    search_fields = (
        'regulatory_code',
        'presentation',
        'registration_holder',
        'therapeutic_class',
        'strength',
        'product__code',
    )
    autocomplete_fields = ('product', 'responsible')
    readonly_fields = ('regulatory_code',)


@admin.register(RegulatoryDossier)
class RegulatoryDossierAdmin(admin.ModelAdmin):
    list_display = (
        'dossier_number',
        'dossier_type',
        'title',
        'status',
        'authority',
        'responsible',
        'due_date',
    )
    list_filter = ('dossier_type', 'status', 'authority', 'due_date')
    search_fields = (
        'dossier_number',
        'title',
        'authority',
        'subject',
        'regulatory_product__presentation',
    )
    autocomplete_fields = ('regulatory_product', 'responsible', 'submitted_by', 'closed_by')
    readonly_fields = ('dossier_number', 'submitted_at', 'closed_at')


@admin.register(RegulatoryRegistration)
class RegulatoryRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        'registration_number',
        'regulatory_product',
        'status',
        'valid_until',
        'next_renewal_due_date',
    )
    list_filter = ('status', 'valid_until', 'next_renewal_due_date')
    search_fields = ('registration_number', 'regulatory_product__presentation')
    autocomplete_fields = ('regulatory_product', 'dossier', 'responsible')


@admin.register(RegulatoryPetition)
class RegulatoryPetitionAdmin(admin.ModelAdmin):
    list_display = (
        'petition_number',
        'petition_type',
        'subject',
        'status',
        'protocol_number',
        'response_due_date',
    )
    list_filter = ('petition_type', 'status', 'response_due_date')
    search_fields = (
        'petition_number',
        'protocol_number',
        'subject',
        'response_summary',
        'dossier__dossier_number',
    )
    autocomplete_fields = ('dossier', 'responsible', 'submitted_by', 'responded_by')
    readonly_fields = ('petition_number', 'submitted_at', 'responded_at')


@admin.register(RegulatoryRequirement)
class RegulatoryRequirementAdmin(admin.ModelAdmin):
    list_display = ('requirement_number', 'dossier', 'status', 'responsible', 'response_due_date')
    list_filter = ('status', 'response_due_date')
    search_fields = (
        'requirement_number',
        'description',
        'response_summary',
        'evidence_reference',
        'content_hash',
    )
    autocomplete_fields = ('dossier', 'petition', 'responsible', 'answered_by')
    readonly_fields = ('requirement_number', 'answered_at')


@admin.register(RegulatoryCommitment)
class RegulatoryCommitmentAdmin(admin.ModelAdmin):
    list_display = ('commitment_number', 'dossier', 'status', 'responsible', 'due_date')
    list_filter = ('status', 'due_date')
    search_fields = (
        'commitment_number',
        'description',
        'completion_summary',
        'evidence_reference',
        'content_hash',
    )
    autocomplete_fields = ('dossier', 'responsible', 'completed_by')
    readonly_fields = ('commitment_number', 'completed_at')


@admin.register(RegulatoryEvidence)
class RegulatoryEvidenceAdmin(admin.ModelAdmin):
    list_display = ('dossier', 'title', 'file_reference', 'content_hash', 'uploaded_by')
    list_filter = ('uploaded_by',)
    search_fields = ('dossier__dossier_number', 'title', 'file_reference', 'content_hash', 'notes')
    autocomplete_fields = ('dossier', 'petition', 'requirement', 'commitment', 'uploaded_by')


@admin.register(RegulatoryLink)
class RegulatoryLinkAdmin(admin.ModelAdmin):
    list_display = ('dossier', 'link_type', 'reference_code')
    list_filter = ('link_type',)
    search_fields = ('dossier__dossier_number', 'reference_code', 'description')
    autocomplete_fields = (
        'dossier',
        'product',
        'stock_lot',
        'document',
        'change_control',
        'deviation_event',
        'capa',
        'partner',
    )


@admin.register(RegulatoryReport)
class RegulatoryReportAdmin(admin.ModelAdmin):
    list_display = (
        'dossier',
        'report_type',
        'title',
        'status',
        'total_requirements',
        'open_commitments',
        'evidence_count',
    )
    list_filter = ('report_type', 'status', 'generated_at')
    search_fields = ('dossier__dossier_number', 'title', 'content_reference')
    autocomplete_fields = ('dossier', 'generated_by')
    readonly_fields = (
        'status',
        'content_reference',
        'total_requirements',
        'open_commitments',
        'evidence_count',
        'generated_at',
    )


@admin.register(RegulatoryAlert)
class RegulatoryAlertAdmin(admin.ModelAdmin):
    list_display = ('alert_type', 'severity', 'status', 'dossier', 'due_date', 'acknowledged_at')
    list_filter = ('alert_type', 'severity', 'status', 'due_date')
    search_fields = ('message', 'dossier__dossier_number')
    autocomplete_fields = (
        'regulatory_product',
        'dossier',
        'registration',
        'petition',
        'requirement',
        'commitment',
        'acknowledged_by',
    )
    readonly_fields = ('acknowledged_at',)
