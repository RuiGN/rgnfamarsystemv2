from django.contrib import admin
from base.admin_mixins import ImmutableAuditAdminMixin
from governance.models import (
    DemoScenarioLoad,
    GovernanceAuditLog,
    GovernanceCatalogItem,
    GovernanceParameter,
    InstitutionSettings,
    TechnicalResponsible,
)


@admin.register(InstitutionSettings)
class InstitutionSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            'Identificação',
            {
                'fields': (
                    'trade_name',
                    'legal_name',
                    'document',
                    'tax_regime',
                    'is_active',
                )
            },
        ),
        (
            'Inscrições',
            {'fields': ('state_registration', 'municipal_registration')},
        ),
        (
            'Contato',
            {'fields': ('phone', 'email', 'website')},
        ),
        (
            'Endereço',
            {
                'fields': (
                    'zipcode',
                    'street',
                    'street_number',
                    'complement',
                    'neighborhood',
                    'city_ref',
                    'state_ref',
                )
            },
        ),
        ('Marca', {'fields': ('logo',)}),
        ('Auditoria', {'fields': ('created_at', 'updated_at')}),
    )
    list_display = ('trade_name', 'legal_name', 'document', 'city_ref', 'state_ref', 'is_active')
    search_fields = (
        'trade_name',
        'legal_name',
        'document',
        'email',
        'city_ref__name',
        'state_ref__name',
        'state_ref__name',
    )
    autocomplete_fields = ('city_ref', 'state_ref')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(GovernanceParameter)
class GovernanceParameterAdmin(admin.ModelAdmin):
    list_display = ('key', 'scope', 'module', 'value_type', 'is_active', 'updated_by')
    list_filter = ('scope', 'module', 'value_type', 'is_active')
    search_fields = ('key', 'description', 'value', 'default_value', 'rules', 'updated_by__email')
    autocomplete_fields = ('updated_by',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TechnicalResponsible)
class TechnicalResponsibleAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            'Identificação',
            {
                'fields': (
                    'full_name',
                    'cpf',
                    'email',
                    'phone',
                    'user',
                    'is_active',
                )
            },
        ),
        (
            'Vínculo',
            {'fields': ('institution', 'fiscal_company', 'responsibility_type')},
        ),
        (
            'Registro profissional',
            {
                'fields': (
                    'profession',
                    'council',
                    'council_state',
                    'council_registration_number',
                    'registration_type',
                    'registration_status',
                )
            },
        ),
        (
            'Vigência e assistência',
            {
                'fields': (
                    'start_date',
                    'end_date',
                    'weekly_workload_hours',
                    'work_schedule',
                )
            },
        ),
        (
            'Certidão de regularidade',
            {
                'fields': (
                    'regularity_certificate_number',
                    'regularity_certificate_issued_at',
                    'regularity_certificate_valid_until',
                    'certificate_file_reference',
                    'verification_url',
                    'verified_at',
                )
            },
        ),
        ('Observações', {'fields': ('notes',)}),
        ('Auditoria', {'fields': ('created_at', 'updated_at')}),
    )
    list_display = (
        'full_name',
        'responsibility_type',
        'council',
        'council_state',
        'council_registration_number',
        'institution',
        'fiscal_company',
        'registration_status',
        'regularity_certificate_valid_until',
        'is_active',
    )
    list_filter = (
        'responsibility_type',
        'registration_status',
        'council',
        'council_state',
        'is_active',
    )
    search_fields = (
        'full_name',
        'cpf',
        'email',
        'council_registration_number',
        'regularity_certificate_number',
        'institution__legal_name',
        'institution__trade_name',
        'fiscal_company__legal_name',
        'fiscal_company__document',
    )
    autocomplete_fields = ('institution', 'fiscal_company', 'user', 'council_state')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(GovernanceCatalogItem)
class GovernanceCatalogItemAdmin(admin.ModelAdmin):
    list_display = ('code', 'label', 'catalog_type', 'module', 'order', 'is_active')
    list_filter = ('catalog_type', 'module', 'is_active')
    search_fields = ('code', 'label', 'value', 'metadata')
    autocomplete_fields = ('parent',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(GovernanceAuditLog)
class GovernanceAuditLogAdmin(ImmutableAuditAdminMixin, admin.ModelAdmin):
    list_display = ('action', 'log_type', 'severity', 'module', 'user', 'occurred_at')
    list_filter = ('log_type', 'severity', 'module', 'occurred_at')
    search_fields = (
        'action',
        'target_model',
        'target_record_id',
        'user__email',
        'message',
        'request_id',
    )
    autocomplete_fields = ('user',)
    readonly_fields = (
        'log_type',
        'severity',
        'module',
        'action',
        'target_model',
        'target_record_id',
        'user',
        'message',
        'safe_context',
        'request_id',
        'occurred_at',
        'created_at',
        'updated_at',
    )


@admin.register(DemoScenarioLoad)
class DemoScenarioLoadAdmin(admin.ModelAdmin):
    list_display = ('scenario', 'status', 'requested_by', 'started_at', 'completed_at')
    list_filter = ('scenario', 'status', 'started_at', 'completed_at')
    search_fields = ('scenario', 'records_created', 'error_message', 'requested_by__email')
    autocomplete_fields = ('requested_by',)
    readonly_fields = (
        'status',
        'started_at',
        'completed_at',
        'records_created',
        'error_message',
        'created_at',
        'updated_at',
    )
