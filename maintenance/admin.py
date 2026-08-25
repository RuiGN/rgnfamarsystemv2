from django.contrib import admin
from base.admin_mixins import ImmutableAuditAdminMixin
from maintenance.models import (
    EquipmentAsset,
    EquipmentDowntime,
    EquipmentUsageLog,
    MaintenanceMetricReport,
    MaintenanceOrder,
    MaintenancePlan,
)


@admin.register(EquipmentAsset)
class EquipmentAssetAdmin(admin.ModelAdmin):
    list_display = (
        'asset_code',
        'name',
        'asset_type',
        'status',
        'qualification_status',
        'calibration_status',
        'responsible',
    )
    list_filter = (
        'asset_type',
        'status',
        'qualification_status',
        'calibration_required',
        'calibration_status',
        'is_critical',
    )
    search_fields = (
        'asset_code',
        'name',
        'area',
        'location',
        'manufacturer',
        'model',
        'serial_number',
    )
    autocomplete_fields = ('responsible', 'blocked_by', 'released_by')
    readonly_fields = ('blocked_at', 'released_at')


@admin.register(MaintenancePlan)
class MaintenancePlanAdmin(admin.ModelAdmin):
    list_display = ('asset', 'plan_type', 'trigger_type', 'active', 'next_due_date', 'responsible')
    list_filter = ('plan_type', 'trigger_type', 'active', 'next_due_date')
    search_fields = (
        'asset__asset_code',
        'asset__name',
        'description',
        'event_name',
        'lot_rule',
        'rule_expression',
    )
    autocomplete_fields = ('asset', 'responsible')


@admin.register(MaintenanceOrder)
class MaintenanceOrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number',
        'asset',
        'order_type',
        'trigger_type',
        'status',
        'priority',
        'due_date',
        'responsible',
    )
    list_filter = ('order_type', 'trigger_type', 'status', 'priority', 'due_date')
    search_fields = (
        'order_number',
        'description',
        'completion_summary',
        'evidence_reference',
        'content_hash',
        'asset__asset_code',
        'asset__name',
    )
    autocomplete_fields = (
        'asset',
        'plan',
        'source_lot',
        'responsible',
        'opened_by',
        'started_by',
        'completed_by',
        'cancelled_by',
    )
    readonly_fields = ('order_number', 'started_at', 'completed_at', 'cancelled_at')


@admin.register(EquipmentDowntime)
class EquipmentDowntimeAdmin(admin.ModelAdmin):
    list_display = ('asset', 'downtime_type', 'started_at', 'ended_at', 'duration_hours')
    list_filter = ('downtime_type', 'started_at', 'ended_at')
    search_fields = ('asset__asset_code', 'asset__name', 'order__order_number', 'reason')
    autocomplete_fields = ('asset', 'order')
    readonly_fields = ('duration_hours',)


@admin.register(EquipmentUsageLog)
class EquipmentUsageLogAdmin(ImmutableAuditAdminMixin, admin.ModelAdmin):
    list_display = (
        'asset',
        'source_lot',
        'used_at',
        'usage_quantity',
        'usage_unit',
        'event_reference',
    )
    list_filter = ('used_at', 'usage_unit')
    search_fields = (
        'asset__asset_code',
        'asset__name',
        'source_lot__lot_number',
        'usage_unit',
        'event_reference',
    )
    autocomplete_fields = ('asset', 'source_lot', 'logged_by')


@admin.register(MaintenanceMetricReport)
class MaintenanceMetricReportAdmin(ImmutableAuditAdminMixin, admin.ModelAdmin):
    list_display = (
        'title',
        'asset',
        'report_type',
        'status',
        'availability_rate',
        'downtime_hours',
        'mtbf_hours',
        'mttr_hours',
        'overdue_orders',
    )
    list_filter = ('report_type', 'status', 'generated_at')
    search_fields = ('title', 'content_reference', 'asset__asset_code', 'asset__name')
    autocomplete_fields = ('asset', 'generated_by')
    readonly_fields = (
        'status',
        'availability_rate',
        'downtime_hours',
        'mtbf_hours',
        'mttr_hours',
        'overdue_orders',
        'due_soon_orders',
        'content_reference',
        'generated_at',
    )
