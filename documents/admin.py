from django.contrib import admin
from base.admin_mixins import ImmutableAuditAdminMixin
from documents.models import (
    ControlledDocument,
    DocumentApproval,
    DocumentAttachment,
    DocumentAuditTrail,
    DocumentDistribution,
    DocumentRelationship,
)


@admin.register(ControlledDocument)
class ControlledDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'version',
        'title',
        'document_type',
        'status',
        'area',
        'owner',
        'published_at',
    )
    list_filter = ('document_type', 'status', 'area', 'published_at')
    search_fields = (
        'code',
        'title',
        'area',
        'version',
        'content',
        'change_summary',
        'owner__email',
    )
    autocomplete_fields = (
        'owner',
        'supersedes',
        'submitted_by',
        'reviewed_by',
        'approved_by',
        'published_by',
        'obsoleted_by',
        'cancelled_by',
        'archived_by',
    )
    readonly_fields = (
        'submitted_at',
        'reviewed_at',
        'approved_at',
        'published_at',
        'obsoleted_at',
        'cancelled_at',
        'archived_at',
    )


@admin.register(DocumentAttachment)
class DocumentAttachmentAdmin(admin.ModelAdmin):
    list_display = ('document', 'file_name', 'content_hash', 'uploaded_by')
    list_filter = ('uploaded_by',)
    search_fields = (
        'document__code',
        'document__title',
        'file_name',
        'file_reference',
        'content_hash',
        'description',
    )
    autocomplete_fields = ('document', 'uploaded_by')


@admin.register(DocumentRelationship)
class DocumentRelationshipAdmin(admin.ModelAdmin):
    list_display = (
        'source_document',
        'relationship_type',
        'related_document',
        'external_reference',
    )
    list_filter = ('relationship_type',)
    search_fields = (
        'source_document__code',
        'source_document__title',
        'related_document__code',
        'external_reference',
        'rationale',
    )
    autocomplete_fields = ('source_document', 'related_document')


@admin.register(DocumentApproval)
class DocumentApprovalAdmin(admin.ModelAdmin):
    list_display = ('document', 'role', 'user', 'decision', 'decided_at')
    list_filter = ('role', 'decision', 'decided_at')
    search_fields = ('document__code', 'document__title', 'user__email', 'comments')
    autocomplete_fields = ('document', 'user')


@admin.register(DocumentDistribution)
class DocumentDistributionAdmin(admin.ModelAdmin):
    list_display = ('document', 'recipient', 'status', 'due_date', 'confirmed_at')
    list_filter = ('status', 'due_date', 'confirmed_at')
    search_fields = ('document__code', 'document__title', 'recipient__email', 'confirmation_text')
    autocomplete_fields = ('document', 'recipient', 'distributed_by', 'confirmed_by')
    readonly_fields = ('confirmed_at',)


@admin.register(DocumentAuditTrail)
class DocumentAuditTrailAdmin(ImmutableAuditAdminMixin, admin.ModelAdmin):
    list_display = ('document', 'action', 'actor', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('document__code', 'document__title', 'actor__email', 'reason', 'snapshot')
    autocomplete_fields = ('document', 'actor')
    readonly_fields = (
        'document',
        'action',
        'actor',
        'reason',
        'snapshot',
        'created_at',
        'updated_at',
    )
