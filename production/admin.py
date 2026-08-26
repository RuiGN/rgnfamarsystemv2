from django.contrib import admin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from production.models import MaterialConsumption, ProductionOrder


class MaterialConsumptionInline(admin.TabularInline):
    model = MaterialConsumption
    extra = 0
    autocomplete_fields = ('component', 'material', 'unit')
    fields = (
        'component',
        'material',
        'planned_quantity',
        'actual_quantity',
        'loss_quantity',
        'returned_quantity',
        'unit',
        'quality_status',
        'expiry_date',
    )


@admin.register(ProductionOrder)
class ProductionOrderAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = ('order_number', 'batch_number', 'product', 'status', 'planned_quantity', 'unit')
    list_filter = ('status', 'product__item_type')
    search_fields = ('order_number', 'batch_number', 'product__code', 'product__description')
    autocomplete_fields = (
        'product',
        'formula',
        'route',
        'unit',
        'approved_by',
        'released_by',
        'started_by',
        'completed_by',
        'cancelled_by',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'approved_at',
        'released_at',
        'actual_start',
        'actual_end',
        'cancelled_at',
    )
    inlines = (MaterialConsumptionInline,)


@admin.register(MaterialConsumption)
class MaterialConsumptionAdmin(admin.ModelAdmin):
    list_display = (
        'order',
        'material',
        'planned_quantity',
        'actual_quantity',
        'unit',
        'quality_status',
        'expiry_date',
    )
    list_filter = ('quality_status', 'material__item_type')
    search_fields = (
        'order__order_number',
        'order__batch_number',
        'material__code',
        'material__description',
        'lot_number',
    )
    autocomplete_fields = ('order', 'component', 'material', 'unit')
    readonly_fields = ('created_at', 'updated_at')
