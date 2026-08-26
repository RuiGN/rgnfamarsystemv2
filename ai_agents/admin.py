from django.contrib import admin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin, ImmutableAuditAdminMixin
from ai_agents.models import AIAgentProfile, AIAgentRun, AIInsightSuggestion, AIPromptAuditLog


@admin.register(AIAgentProfile)
class AIAgentProfileAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'agent_type',
        'source_module',
        'provider',
        'model_name',
        'is_active',
    )
    list_filter = ('agent_type', 'source_module', 'provider', 'is_active')
    search_fields = ('code', 'name', 'system_prompt', 'created_by__email')
    autocomplete_fields = ('created_by',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AIAgentRun)
class AIAgentRunAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        'run_number',
        'agent',
        'source_module',
        'source_model',
        'status',
        'requested_by',
        'completed_at',
    )
    list_filter = (
        'status',
        'execution_mode',
        'source_module',
        'graph_engine',
        'created_at',
        'completed_at',
    )
    search_fields = (
        'run_number',
        'agent__code',
        'source_model',
        'source_record_id',
        'prompt_text',
        'output_text',
        'error_message',
        'requested_by__email',
    )
    autocomplete_fields = ('agent', 'requested_by')
    readonly_fields = (
        'run_number',
        'celery_task_name',
        'task_id',
        'status',
        'graph_engine',
        'prompt_text',
        'model_name',
        'output_payload',
        'output_text',
        'error_message',
        'started_at',
        'completed_at',
        'created_at',
        'updated_at',
    )


@admin.register(AIInsightSuggestion)
class AIInsightSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'suggestion_type',
        'status',
        'confidence',
        'source_module',
        'reviewed_by',
    )
    list_filter = ('suggestion_type', 'status', 'source_module', 'reviewed_at')
    search_fields = (
        'title',
        'description',
        'run__run_number',
        'source_model',
        'source_record_id',
        'reviewed_by__email',
    )
    autocomplete_fields = ('run', 'reviewed_by')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AIPromptAuditLog)
class AIPromptAuditLogAdmin(ImmutableAuditAdminMixin, admin.ModelAdmin):
    list_display = ('run', 'agent', 'model_name', 'status', 'user', 'occurred_at')
    list_filter = ('status', 'model_name', 'occurred_at')
    search_fields = (
        'run__run_number',
        'agent__code',
        'user__email',
        'prompt_text',
        'output_text',
        'error_message',
    )
    autocomplete_fields = ('run', 'agent', 'user')
    readonly_fields = (
        'run',
        'agent',
        'user',
        'prompt_text',
        'model_name',
        'input_payload',
        'output_payload',
        'output_text',
        'status',
        'error_message',
        'occurred_at',
        'created_at',
        'updated_at',
    )
