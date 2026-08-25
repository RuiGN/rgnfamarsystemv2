from django.contrib import admin
from planning.models import (
    CapacityLoad,
    CapacityResource,
    InventoryPosition,
    MPSLine,
    MRPRun,
    MRPSuggestion,
    MasterProductionSchedule,
    PlanningPolicy,
)


class MPSLineInline(admin.TabularInline):
    model = MPSLine
    extra = 0
    autocomplete_fields = ('product', 'unit')
    fields = ('product', 'due_date', 'demand_quantity', 'unit', 'source', 'customer_reference')


class MRPSuggestionInline(admin.TabularInline):
    model = MRPSuggestion
    extra = 0
    can_delete = False
    readonly_fields = (
        'product',
        'suggestion_type',
        'due_date',
        'required_quantity',
        'available_quantity',
        'net_requirement',
        'suggested_quantity',
        'release_date',
        'alert_level',
    )
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PlanningPolicy)
class PlanningPolicyAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'preferred_source',
        'safety_stock_quantity',
        'minimum_order_quantity',
        'order_multiple',
        'lead_time_days',
        'is_active',
    )
    list_filter = ('preferred_source', 'is_active')
    search_fields = ('product__code', 'product__description')
    autocomplete_fields = ('product',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MasterProductionSchedule)
class MasterProductionScheduleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'period_start', 'period_end', 'status')
    list_filter = ('status', 'period_start')
    search_fields = ('code', 'name')
    autocomplete_fields = ()
    readonly_fields = ('created_at', 'updated_at')
    inlines = (MPSLineInline,)


@admin.register(MPSLine)
class MPSLineAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'product', 'due_date', 'demand_quantity', 'unit', 'source')
    list_filter = ('source', 'due_date', 'product__item_type')
    search_fields = (
        'schedule__code',
        'product__code',
        'product__description',
        'customer_reference',
    )
    autocomplete_fields = ('schedule', 'product', 'unit')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(InventoryPosition)
class InventoryPositionAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'on_hand_quantity',
        'quarantine_quantity',
        'reserved_quantity',
        'incoming_purchase_quantity',
        'incoming_production_quantity',
        'expiry_date',
    )
    list_filter = ('expiry_date',)
    search_fields = ('product__code', 'product__description')
    autocomplete_fields = ('product', 'unit')
    readonly_fields = (
        'available_quantity',
        'projected_available_quantity',
        'created_at',
        'updated_at',
    )


@admin.register(MRPRun)
class MRPRunAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'status', 'run_at', 'scenario_name')
    list_filter = ('status', 'created_at')
    search_fields = ('schedule__code', 'scenario_name', 'notes')
    autocomplete_fields = ('schedule',)
    readonly_fields = ('status', 'run_at', 'created_at', 'updated_at')
    inlines = (MRPSuggestionInline,)


@admin.register(MRPSuggestion)
class MRPSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        'run',
        'product',
        'suggestion_type',
        'required_quantity',
        'net_requirement',
        'suggested_quantity',
        'release_date',
        'alert_level',
    )
    list_filter = ('suggestion_type', 'alert_level', 'due_date')
    search_fields = ('product__code', 'product__description', 'run__schedule__code', 'notes')
    autocomplete_fields = ('run', 'product')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CapacityResource)
class CapacityResourceAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'resource_type',
        'work_center',
        'daily_capacity_minutes',
        'is_active',
    )
    list_filter = ('resource_type', 'work_center', 'is_active')
    search_fields = ('code', 'name', 'work_center')
    autocomplete_fields = ()
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CapacityLoad)
class CapacityLoadAdmin(admin.ModelAdmin):
    list_display = (
        'resource',
        'period_date',
        'shift',
        'required_minutes',
        'available_minutes',
        'is_overloaded',
        'overload_minutes',
    )
    list_filter = ('period_date', 'shift', 'resource__resource_type')
    search_fields = ('resource__code', 'resource__name', 'shift', 'notes')
    autocomplete_fields = ('run', 'resource')
    readonly_fields = ('is_overloaded', 'overload_minutes', 'created_at', 'updated_at')
