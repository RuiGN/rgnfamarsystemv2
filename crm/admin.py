from django.contrib import admin
from base.admin_mixins import AutomaticGeneratedFieldsAdminMixin
from crm.models import (
    Campaign,
    CustomerComplaint,
    CustomerContact,
    CustomerGroup,
    CustomerInteraction,
    CustomerProfile,
    Opportunity,
    SalesChannel,
    SalesContract,
    SalesOrder,
    SalesOrderItem,
    SalesProposal,
    SalesProposalItem,
    SalesRepresentative,
)


@admin.register(CustomerGroup)
class CustomerGroupAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(SalesChannel)
class SalesChannelAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'channel_type', 'is_active')
    list_filter = ('channel_type', 'is_active')
    search_fields = ('code', 'name')


@admin.register(SalesRepresentative)
class SalesRepresentativeAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'email', 'commission_percent', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name', 'email', 'partner__legal_name')
    autocomplete_fields = ('user', 'partner')


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = (
        'customer',
        'group',
        'default_channel',
        'representative',
        'credit_limit',
        'credit_hold',
        'regulatory_hold',
        'is_active',
    )
    list_filter = ('is_active', 'credit_hold', 'regulatory_hold', 'group', 'default_channel')
    search_fields = (
        'customer__code',
        'customer__legal_name',
        'customer__document',
        'price_list_code',
    )
    autocomplete_fields = ('customer', 'group', 'default_channel', 'representative')


@admin.register(CustomerContact)
class CustomerContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'customer', 'role', 'email', 'is_primary', 'is_active')
    list_filter = ('is_primary', 'is_active')
    search_fields = ('name', 'email', 'role', 'customer__legal_name')
    autocomplete_fields = ('customer',)


@admin.register(Campaign)
class CampaignAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'channel', 'start_date', 'end_date', 'status', 'budget_amount')
    list_filter = ('status', 'channel', 'start_date')
    search_fields = ('code', 'name')
    autocomplete_fields = ('channel',)


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'customer',
        'stage',
        'estimated_amount',
        'probability_percent',
        'expected_close_date',
    )
    list_filter = ('stage', 'channel', 'representative', 'campaign')
    search_fields = ('title', 'customer__legal_name', 'contact__name')
    autocomplete_fields = ('customer', 'contact', 'channel', 'representative', 'campaign')


class SalesProposalItemInline(admin.TabularInline):
    model = SalesProposalItem
    extra = 0
    autocomplete_fields = ('product',)
    readonly_fields = ('line_subtotal', 'discount_amount', 'line_total')


@admin.register(SalesProposal)
class SalesProposalAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = ('proposal_number', 'customer', 'status', 'valid_until', 'total_amount')
    list_filter = ('status', 'valid_until')
    search_fields = ('proposal_number', 'customer__legal_name', 'opportunity__title')
    autocomplete_fields = ('opportunity', 'customer')
    readonly_fields = ('proposal_number', 'total_amount', 'sent_at', 'accepted_at', 'rejected_at')
    inlines = (SalesProposalItemInline,)


@admin.register(SalesProposalItem)
class SalesProposalItemAdmin(admin.ModelAdmin):
    list_display = (
        'proposal',
        'product',
        'quantity',
        'unit_price',
        'discount_percent',
        'line_total',
    )
    search_fields = ('proposal__proposal_number', 'product__code', 'product__description')
    autocomplete_fields = ('proposal', 'product')
    readonly_fields = ('line_subtotal', 'discount_amount', 'line_total')


@admin.register(SalesContract)
class SalesContractAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        'contract_number',
        'customer',
        'status',
        'start_date',
        'end_date',
        'contract_value',
        'approved_by',
    )
    list_filter = ('status', 'start_date', 'end_date')
    search_fields = ('contract_number', 'customer__legal_name', 'regulatory_requirements')
    autocomplete_fields = ('customer', 'opportunity', 'proposal', 'approved_by')
    readonly_fields = ('approved_at',)


class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 0
    autocomplete_fields = ('product',)
    readonly_fields = ('line_subtotal', 'discount_amount', 'line_total')


@admin.register(SalesOrder)
class SalesOrderAdmin(AutomaticGeneratedFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        'order_number',
        'customer',
        'status',
        'requested_delivery_date',
        'shipping_state_ref',
        'shipping_city_ref',
        'total_amount',
        'approved_by',
    )
    list_filter = (
        'status',
        'requested_delivery_date',
        'channel',
        'representative',
        'shipping_state_ref',
        'shipping_city_ref',
    )
    search_fields = (
        'order_number',
        'customer__legal_name',
        'block_reason',
        'shipping_city_ref__name',
        'shipping_state_ref__name',
    )
    autocomplete_fields = (
        'customer',
        'proposal',
        'contract',
        'channel',
        'representative',
        'shipping_state_ref',
        'shipping_city_ref',
        'approved_by',
    )
    readonly_fields = ('order_number', 'total_amount', 'approved_at', 'block_reason')
    inlines = (SalesOrderItemInline,)


@admin.register(SalesOrderItem)
class SalesOrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'order',
        'product',
        'quantity',
        'unit_price',
        'discount_percent',
        'promised_date',
        'line_total',
    )
    list_filter = ('promised_date',)
    search_fields = ('order__order_number', 'product__code', 'product__description')
    autocomplete_fields = ('order', 'product')
    readonly_fields = ('line_subtotal', 'discount_amount', 'line_total')


@admin.register(CustomerInteraction)
class CustomerInteractionAdmin(admin.ModelAdmin):
    list_display = ('subject', 'customer', 'interaction_type', 'occurred_at', 'created_by')
    list_filter = ('interaction_type', 'occurred_at')
    search_fields = ('subject', 'description', 'customer__legal_name', 'contact__name')
    autocomplete_fields = ('customer', 'contact', 'opportunity', 'created_by')


@admin.register(CustomerComplaint)
class CustomerComplaintAdmin(admin.ModelAdmin):
    list_display = (
        'complaint_number',
        'customer',
        'status',
        'severity',
        'product',
        'state_ref',
        'city_ref',
        'received_at',
        'closed_by',
    )
    list_filter = ('status', 'severity', 'received_at', 'state_ref', 'city_ref')
    search_fields = (
        'complaint_number',
        'customer__legal_name',
        'product__code',
        'stock_lot__lot_number',
        'quality_reference',
        'capa_reference',
        'city_ref__name',
        'state_ref__name',
    )
    autocomplete_fields = (
        'customer',
        'contact',
        'product',
        'stock_lot',
        'sales_order',
        'fiscal_document',
        'state_ref',
        'city_ref',
        'closed_by',
    )
    readonly_fields = ('complaint_number', 'closed_at')
