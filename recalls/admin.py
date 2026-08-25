from django.contrib import admin
from recalls.models import (
    MarketComplaint,
    ProductReturn,
    RecallCampaign,
    RecallCommunication,
    RecallEffectivenessReport,
    RecallImpactedCustomer,
)


@admin.register(MarketComplaint)
class MarketComplaintAdmin(admin.ModelAdmin):
    list_display = (
        'complaint_number',
        'complaint_type',
        'status',
        'criticality',
        'customer',
        'product',
        'responsible',
        'received_at',
    )
    list_filter = (
        'complaint_type',
        'source',
        'status',
        'criticality',
        'regulatory_communication_required',
        'state_ref',
        'city_ref',
        'received_at',
    )
    search_fields = (
        'complaint_number',
        'description',
        'regulatory_communication_reference',
        'customer__legal_name',
        'product__code',
        'stock_lot__lot_number',
        'city_ref__name',
        'state_ref__name',
    )
    autocomplete_fields = (
        'customer',
        'product',
        'stock_lot',
        'sales_order',
        'fiscal_document',
        'customer_complaint',
        'quality_sample',
        'deviation_event',
        'capa',
        'document',
        'responsible',
        'reported_by',
        'triaged_by',
        'investigation_started_by',
        'regulatory_communicated_by',
        'closed_by',
        'state_ref',
        'city_ref',
    )
    readonly_fields = (
        'complaint_number',
        'triaged_at',
        'investigation_started_at',
        'regulatory_communicated_at',
        'closed_at',
    )


@admin.register(ProductReturn)
class ProductReturnAdmin(admin.ModelAdmin):
    list_display = (
        'return_number',
        'return_type',
        'status',
        'customer',
        'product',
        'stock_lot',
        'quantity',
        'received_quantity',
    )
    list_filter = (
        'return_type',
        'status',
        'disposition',
        'authorized_at',
        'received_at',
        'inspected_at',
    )
    search_fields = (
        'return_number',
        'reason',
        'inspection_notes',
        'closure_summary',
        'customer__legal_name',
        'product__code',
        'stock_lot__lot_number',
    )
    autocomplete_fields = (
        'complaint',
        'customer',
        'product',
        'stock_lot',
        'sales_order',
        'fiscal_document',
        'unit',
        'requested_by',
        'authorized_by',
        'received_by',
        'inspected_by',
        'closed_by',
    )
    readonly_fields = ('return_number', 'authorized_at', 'received_at', 'inspected_at', 'closed_at')


@admin.register(RecallCampaign)
class RecallCampaignAdmin(admin.ModelAdmin):
    list_display = (
        'campaign_number',
        'campaign_type',
        'status',
        'criticality',
        'product',
        'stock_lot',
        'target_completion_date',
        'responsible',
    )
    list_filter = (
        'campaign_type',
        'trigger',
        'status',
        'criticality',
        'decision_date',
        'target_completion_date',
    )
    search_fields = (
        'campaign_number',
        'reason',
        'closure_summary',
        'product__code',
        'stock_lot__lot_number',
    )
    autocomplete_fields = (
        'product',
        'stock_lot',
        'complaint',
        'deviation_event',
        'capa',
        'responsible',
        'approved_by',
        'started_by',
        'closed_by',
    )
    readonly_fields = ('campaign_number', 'approved_at', 'started_at', 'closed_at')


@admin.register(RecallImpactedCustomer)
class RecallImpactedCustomerAdmin(admin.ModelAdmin):
    list_display = (
        'campaign',
        'customer',
        'response_status',
        'quantity_distributed',
        'quantity_recalled',
        'quantity_returned',
    )
    list_filter = ('response_status',)
    search_fields = (
        'campaign__campaign_number',
        'customer__legal_name',
        'contact_name',
        'contact_email',
        'response_notes',
    )
    autocomplete_fields = ('campaign', 'customer', 'sales_order', 'fiscal_document')
    readonly_fields = ('response_received_at', 'returned_at')


@admin.register(RecallCommunication)
class RecallCommunicationAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'channel', 'subject', 'status', 'response_due_date', 'sent_at')
    list_filter = ('channel', 'status', 'response_due_date', 'sent_at')
    search_fields = ('campaign__campaign_number', 'subject', 'message', 'content_hash')
    autocomplete_fields = ('campaign', 'impacted_customer', 'sent_by')
    readonly_fields = ('sent_at', 'acknowledged_at')


@admin.register(RecallEffectivenessReport)
class RecallEffectivenessReportAdmin(admin.ModelAdmin):
    list_display = (
        'campaign',
        'report_type',
        'title',
        'status',
        'impacted_customers',
        'customers_contacted',
        'responses_received',
        'effectiveness_rate',
    )
    list_filter = ('report_type', 'status', 'generated_at')
    search_fields = ('campaign__campaign_number', 'title', 'content_reference')
    autocomplete_fields = ('campaign', 'generated_by')
    readonly_fields = (
        'status',
        'content_reference',
        'impacted_customers',
        'customers_contacted',
        'responses_received',
        'total_distributed',
        'total_recalled',
        'total_returned',
        'effectiveness_rate',
        'generated_at',
    )
