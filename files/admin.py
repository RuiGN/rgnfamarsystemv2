from django.contrib import admin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin, ImmutableAuditAdminMixin
from files.models import (
    ProtectedFile,
    ProtectedFileAccessRule,
    ProtectedFileAuditTrail,
    SecureFileLink,
)


@admin.register(ProtectedFile)
class ProtectedFileAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        'file_number',
        'title',
        'source_module',
        'file_type',
        'status',
        'encryption_algorithm',
        'responsible',
        'uploaded_by',
        'valid_until',
    )
    list_filter = (
        'source_module',
        'file_type',
        'origin',
        'criticality',
        'confidentiality',
        'status',
        'encryption_algorithm',
        'valid_until',
    )
    search_fields = (
        'file_number',
        'title',
        'file_name',
        'file_reference',
        'content_hash',
        'source_model',
        'source_record_id',
    )
    autocomplete_fields = (
        'controlled_document',
        'fiscal_document',
        'quality_document',
        'financial_title',
        'responsible',
        'uploaded_by',
        'supersedes',
        'replaced_by',
        'deleted_by',
    )
    readonly_fields = (
        'file_number',
        'encryption_algorithm',
        'encryption_key_id',
        'encrypted_at',
        'encrypted_size',
        'uploaded_at',
        'deleted_at',
        'created_at',
        'updated_at',
    )


@admin.register(ProtectedFileAccessRule)
class ProtectedFileAccessRuleAdmin(admin.ModelAdmin):
    list_display = (
        'protected_file',
        'rule_type',
        'permission',
        'user',
        'role',
        'source_module',
        'is_active',
    )
    list_filter = ('rule_type', 'permission', 'role', 'source_module', 'is_active')
    search_fields = (
        'protected_file__file_number',
        'protected_file__title',
        'user__email',
        'source_model',
        'source_record_id',
        'notes',
    )
    autocomplete_fields = ('protected_file', 'user')


@admin.register(SecureFileLink)
class SecureFileLinkAdmin(admin.ModelAdmin):
    list_display = (
        'protected_file',
        'purpose',
        'requested_by',
        'expires_at',
        'use_count',
        'max_uses',
        'is_revoked',
    )
    list_filter = ('purpose', 'expires_at', 'is_revoked')
    search_fields = (
        'protected_file__file_number',
        'protected_file__title',
        'token',
        'requested_by__email',
    )
    autocomplete_fields = ('protected_file', 'requested_by', 'revoked_by')
    readonly_fields = ('token', 'use_count', 'used_at', 'revoked_at', 'created_at', 'updated_at')


@admin.register(ProtectedFileAuditTrail)
class ProtectedFileAuditTrailAdmin(ImmutableAuditAdminMixin, admin.ModelAdmin):
    list_display = ('protected_file', 'action', 'actor', 'occurred_at')
    list_filter = ('action', 'occurred_at')
    search_fields = (
        'protected_file__file_number',
        'protected_file__title',
        'actor__email',
        'user_agent',
        'details',
    )
    autocomplete_fields = ('protected_file', 'secure_link', 'actor')
    readonly_fields = (
        'protected_file',
        'secure_link',
        'action',
        'actor',
        'occurred_at',
        'ip_address',
        'user_agent',
        'details',
        'created_at',
        'updated_at',
    )
