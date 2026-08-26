from django.contrib import admin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin, ImmutableAuditAdminMixin
from reports.models import (
    DashboardWidget,
    DashboardWorkspace,
    ReportDefinition,
    ReportExecution,
    ReportNotification,
    ReportSchedule,
)


class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 0
    fields = (
        'title',
        'widget_type',
        'module',
        'report_definition',
        'position_row',
        'position_column',
        'width',
        'height',
    )
    autocomplete_fields = ('report_definition',)


@admin.register(DashboardWorkspace)
class DashboardWorkspaceAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'title', 'module', 'profile_role', 'owner', 'is_active')
    list_filter = ('module', 'profile_role', 'is_active')
    search_fields = ('code', 'title', 'owner__email')
    autocomplete_fields = ('owner',)
    inlines = (DashboardWidgetInline,)


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = (
        'dashboard',
        'title',
        'widget_type',
        'module',
        'position_row',
        'position_column',
    )
    list_filter = ('widget_type', 'module')
    search_fields = ('dashboard__code', 'dashboard__title', 'title')
    autocomplete_fields = ('dashboard', 'report_definition')


@admin.register(ReportDefinition)
class ReportDefinitionAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'title', 'module', 'category', 'owner', 'is_active')
    list_filter = ('module', 'category', 'is_active')
    search_fields = ('code', 'title', 'description', 'owner__email')
    autocomplete_fields = ('owner',)


@admin.register(ReportExecution)
class ReportExecutionAdmin(
    AutomaticGeneratedFieldsAdminMixin, ImmutableAuditAdminMixin, admin.ModelAdmin
):
    list_display = (
        'execution_number',
        'definition',
        'export_format',
        'status',
        'requested_by',
        'requested_at',
        'completed_at',
    )
    list_filter = ('status', 'export_format', 'requested_at', 'completed_at')
    search_fields = (
        'execution_number',
        'definition__code',
        'definition__title',
        'result_reference',
        'content_hash',
        'requested_by__email',
    )
    autocomplete_fields = ('definition', 'schedule', 'requested_by')
    readonly_fields = (
        'execution_number',
        'requested_at',
        'started_at',
        'completed_at',
        'result_reference',
        'content_hash',
        'row_count',
        'error_message',
    )


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'definition',
        'frequency',
        'export_format',
        'next_run_at',
        'last_run_at',
        'owner',
        'is_active',
    )
    list_filter = ('frequency', 'export_format', 'next_run_at', 'is_active')
    search_fields = (
        'name',
        'definition__code',
        'definition__title',
        'owner__email',
        'cron_expression',
    )
    autocomplete_fields = ('definition', 'owner', 'recipients')
    filter_horizontal = ('recipients',)
    readonly_fields = ('last_run_at',)


@admin.register(ReportNotification)
class ReportNotificationAdmin(ImmutableAuditAdminMixin, admin.ModelAdmin):
    list_display = ('execution', 'recipient', 'channel', 'status', 'sent_at')
    list_filter = ('channel', 'status', 'sent_at')
    search_fields = (
        'execution__execution_number',
        'execution__definition__title',
        'recipient__email',
        'message',
        'error_message',
    )
    autocomplete_fields = ('execution', 'recipient')
    readonly_fields = (
        'execution',
        'recipient',
        'channel',
        'status',
        'message',
        'sent_at',
        'error_message',
        'created_at',
        'updated_at',
    )
