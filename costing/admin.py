from django.contrib import admin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from costing.models import (
    CostElement,
    CostReportSnapshot,
    CostSimulation,
    MonthlyCostClosing,
    ProductionCostCapture,
    StandardCost,
)


@admin.register(CostElement)
class CostElementAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('code', 'name')
    autocomplete_fields = ()
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StandardCost)
class StandardCostAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'version',
        'status',
        'effective_from',
        'total_standard_cost',
    )
    list_filter = ('status', 'effective_from')
    search_fields = (
        'product__code',
        'product__description',
        'version',
    )
    autocomplete_fields = ('product', 'unit')
    readonly_fields = (
        'status',
        'total_standard_cost',
        'approved_by',
        'approved_at',
        'created_at',
        'updated_at',
    )


@admin.register(CostSimulation)
class CostSimulationAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'product',
        'batch_size',
        'simulated_total_cost',
        'simulated_unit_cost',
    )
    list_filter = ()
    search_fields = ('name', 'product__code', 'product__description', 'formula__code')
    autocomplete_fields = ('product', 'formula')
    readonly_fields = ('simulated_total_cost', 'simulated_unit_cost', 'created_at', 'updated_at')


@admin.register(ProductionCostCapture)
class ProductionCostCaptureAdmin(admin.ModelAdmin):
    list_display = (
        'production_order',
        'period_start',
        'period_end',
        'planned_cost',
        'total_actual_cost',
        'variance_amount',
    )
    list_filter = ('period_start',)
    search_fields = (
        'production_order__order_number',
        'production_order__batch_number',
    )
    autocomplete_fields = ('production_order',)
    readonly_fields = ('total_actual_cost', 'variance_amount', 'created_at', 'updated_at')


@admin.register(MonthlyCostClosing)
class MonthlyCostClosingAdmin(admin.ModelAdmin):
    list_display = ('period_year', 'period_month', 'status', 'closed_by', 'closed_at')
    list_filter = ('status', 'period_year', 'period_month')
    search_fields = ('validation_notes',)
    autocomplete_fields = ('closed_by',)
    readonly_fields = ('closed_by', 'closed_at', 'created_at', 'updated_at')


@admin.register(CostReportSnapshot)
class CostReportSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'report_type',
        'product',
        'stock_lot',
        'production_order',
        'period_start',
        'margin_amount',
    )
    list_filter = ('report_type', 'period_start')
    search_fields = (
        'product__code',
        'product__description',
        'stock_lot__lot_number',
        'production_order__order_number',
        'notes',
    )
    autocomplete_fields = ('product', 'stock_lot', 'production_order')
    readonly_fields = (
        'margin_amount',
        'margin_percent',
        'generated_at',
        'created_at',
        'updated_at',
    )
