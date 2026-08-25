from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

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
from crm.serializers import (
    CampaignSerializer,
    CustomerComplaintSerializer,
    CustomerContactSerializer,
    CustomerGroupSerializer,
    CustomerInteractionSerializer,
    CustomerProfileSerializer,
    OpportunitySerializer,
    SalesChannelSerializer,
    SalesContractSerializer,
    SalesOrderItemSerializer,
    SalesOrderSerializer,
    SalesProposalItemSerializer,
    SalesProposalSerializer,
    SalesRepresentativeSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


class SingleInstanceCrmViewSet(viewsets.ModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    ordering: tuple[str, ...] = ('-created_at',)

    def get_queryset(self):
        return self.queryset.all()

    def perform_create(self, serializer):
        serializer.save()

    def _domain_action_response(self, callback):
        obj = self.get_object()
        try:
            callback(obj)
        except DjangoValidationError as error:
            return Response(error.message_dict, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(obj)
        return Response(serializer.data)


class CustomerGroupViewSet(SingleInstanceCrmViewSet):
    queryset = CustomerGroup.objects.all()
    serializer_class = CustomerGroupSerializer
    filterset_fields = ('is_active',)
    search_fields = ('code', 'name', 'description')
    ordering = ('name',)


class SalesChannelViewSet(SingleInstanceCrmViewSet):
    queryset = SalesChannel.objects.all()
    serializer_class = SalesChannelSerializer
    filterset_fields = ('channel_type', 'is_active')
    search_fields = ('code', 'name')
    ordering = ('name',)


class SalesRepresentativeViewSet(SingleInstanceCrmViewSet):
    queryset = SalesRepresentative.objects.select_related('user', 'partner')
    serializer_class = SalesRepresentativeSerializer
    filterset_fields = ('is_active', 'partner')
    search_fields = ('code', 'name', 'email', 'territory', 'partner__legal_name')
    ordering = ('name',)


class CustomerProfileViewSet(SingleInstanceCrmViewSet):
    queryset = CustomerProfile.objects.select_related(
        'customer', 'group', 'default_channel', 'representative'
    )
    serializer_class = CustomerProfileSerializer
    filterset_fields = (
        'is_active',
        'credit_hold',
        'regulatory_hold',
        'group',
        'default_channel',
        'representative',
    )
    search_fields = (
        'customer__code',
        'customer__legal_name',
        'customer__document',
        'price_list_code',
    )
    ordering = ('customer__legal_name',)


class CustomerContactViewSet(SingleInstanceCrmViewSet):
    queryset = CustomerContact.objects.select_related('customer')
    serializer_class = CustomerContactSerializer
    filterset_fields = ('customer', 'is_primary', 'is_active')
    search_fields = ('customer__legal_name', 'name', 'email', 'role')
    ordering = ('customer__legal_name', 'name')


class CampaignViewSet(SingleInstanceCrmViewSet):
    queryset = Campaign.objects.select_related('channel')
    serializer_class = CampaignSerializer
    filterset_fields = ('status', 'channel', 'start_date', 'end_date')
    search_fields = ('code', 'name')
    ordering = ('-start_date', 'name')


class OpportunityViewSet(SingleInstanceCrmViewSet):
    queryset = Opportunity.objects.select_related(
        'customer', 'contact', 'channel', 'representative', 'campaign'
    )
    serializer_class = OpportunitySerializer
    filterset_fields = (
        'stage',
        'customer',
        'channel',
        'representative',
        'campaign',
        'expected_close_date',
    )
    search_fields = ('title', 'customer__legal_name', 'contact__name', 'loss_reason')
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def advance(self, request, pk=None):
        stage = request.data.get('stage')
        if not stage:
            return Response(
                {'stage': 'Informe a etapa de destino.'}, status=status.HTTP_400_BAD_REQUEST
            )
        return self._domain_action_response(lambda opportunity: opportunity.advance_to(stage))

    @action(detail=True, methods=['post'])
    def mark_won(self, request, pk=None):
        return self._domain_action_response(lambda opportunity: opportunity.mark_won())

    @action(detail=True, methods=['post'])
    def mark_lost(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda opportunity: opportunity.mark_lost(reason=reason)
        )


class SalesProposalViewSet(SingleInstanceCrmViewSet):
    queryset = SalesProposal.objects.select_related('opportunity', 'customer')
    serializer_class = SalesProposalSerializer
    filterset_fields = ('status', 'customer', 'opportunity', 'valid_until')
    search_fields = ('proposal_number', 'customer__legal_name', 'opportunity__title')
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        return self._domain_action_response(lambda proposal: proposal.recalculate_total())

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        return self._domain_action_response(lambda proposal: proposal.send())

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        return self._domain_action_response(lambda proposal: proposal.accept())

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(lambda proposal: proposal.reject(reason=reason))


class SalesProposalItemViewSet(SingleInstanceCrmViewSet):
    queryset = SalesProposalItem.objects.select_related('proposal', 'product')
    serializer_class = SalesProposalItemSerializer
    filterset_fields = ('proposal', 'product')
    search_fields = ('proposal__proposal_number', 'product__code', 'product__description')
    ordering = ('proposal__proposal_number', 'product__code')


class SalesContractViewSet(SingleInstanceCrmViewSet):
    queryset = SalesContract.objects.select_related(
        'customer', 'opportunity', 'proposal', 'approved_by'
    )
    serializer_class = SalesContractSerializer
    filterset_fields = ('status', 'customer', 'opportunity', 'proposal', 'start_date', 'end_date')
    search_fields = ('contract_number', 'customer__legal_name', 'regulatory_requirements')
    ordering = ('-start_date', 'contract_number')

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        return self._domain_action_response(lambda contract: contract.activate(user=request.user))

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        return self._domain_action_response(lambda contract: contract.suspend())

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return self._domain_action_response(lambda contract: contract.cancel())


class SalesOrderViewSet(SingleInstanceCrmViewSet):
    queryset = SalesOrder.objects.select_related(
        'customer',
        'proposal',
        'contract',
        'channel',
        'representative',
        'approved_by',
        'shipping_state_ref',
        'shipping_city_ref',
    )
    serializer_class = SalesOrderSerializer
    filterset_fields = (
        'status',
        'customer',
        'proposal',
        'contract',
        'channel',
        'representative',
        'requested_delivery_date',
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
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        return self._domain_action_response(lambda order: order.recalculate_total())

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._domain_action_response(lambda order: order.approve(user=request.user))

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(lambda order: order.cancel(reason=reason))


class SalesOrderItemViewSet(SingleInstanceCrmViewSet):
    queryset = SalesOrderItem.objects.select_related('order', 'product')
    serializer_class = SalesOrderItemSerializer
    filterset_fields = ('order', 'product', 'promised_date')
    search_fields = ('order__order_number', 'product__code', 'product__description')
    ordering = ('order__order_number', 'product__code')


class CustomerInteractionViewSet(SingleInstanceCrmViewSet):
    queryset = CustomerInteraction.objects.select_related(
        'customer', 'contact', 'opportunity', 'created_by'
    )
    serializer_class = CustomerInteractionSerializer
    filterset_fields = (
        'customer',
        'contact',
        'opportunity',
        'interaction_type',
        'occurred_at',
        'created_by',
    )
    search_fields = ('customer__legal_name', 'contact__name', 'subject', 'description')
    ordering = ('-occurred_at',)


class CustomerComplaintViewSet(SingleInstanceCrmViewSet):
    queryset = CustomerComplaint.objects.select_related(
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
    serializer_class = CustomerComplaintSerializer
    filterset_fields = (
        'status',
        'severity',
        'customer',
        'product',
        'stock_lot',
        'sales_order',
        'fiscal_document',
        'state_ref',
        'city_ref',
    )
    search_fields = (
        'complaint_number',
        'customer__legal_name',
        'product__code',
        'stock_lot__lot_number',
        'quality_reference',
        'capa_reference',
        'description',
        'city_ref__name',
        'state_ref__name',
    )
    ordering = ('-received_at',)

    @action(detail=True, methods=['post'])
    def start_investigation(self, request, pk=None):
        return self._domain_action_response(lambda complaint: complaint.start_investigation())

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        resolution = request.data.get('resolution', '')
        return self._domain_action_response(
            lambda complaint: complaint.close(resolution=resolution, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(lambda complaint: complaint.cancel(reason=reason))
