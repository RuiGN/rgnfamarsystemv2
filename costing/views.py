from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from costing.models import (
    CostElement,
    CostReportSnapshot,
    CostSimulation,
    MonthlyCostClosing,
    ProductionCostCapture,
    StandardCost,
)
from costing.serializers import (
    CostElementSerializer,
    CostReportSnapshotSerializer,
    CostSimulationSerializer,
    MonthlyCostClosingSerializer,
    ProductionCostCaptureSerializer,
    StandardCostSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


class SingleInstanceCostingViewSet(viewsets.ModelViewSet):
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


class CostElementViewSet(SingleInstanceCostingViewSet):
    queryset = CostElement.objects.all()
    serializer_class = CostElementSerializer
    filterset_fields = ('category', 'is_active')
    search_fields = ('code', 'name')
    ordering = ('category', 'code')


class StandardCostViewSet(SingleInstanceCostingViewSet):
    queryset = StandardCost.objects.select_related('product', 'unit', 'approved_by')
    serializer_class = StandardCostSerializer
    filterset_fields = ('product', 'status', 'effective_from')
    search_fields = (
        'product__code',
        'product__description',
        'version',
    )
    ordering = ('product__code', '-effective_from')

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        return self._domain_action_response(lambda standard: standard.recalculate())

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._domain_action_response(lambda standard: standard.approve(user=request.user))

    @action(detail=True, methods=['post'])
    def obsolete(self, request, pk=None):
        return self._domain_action_response(lambda standard: standard.obsolete())


class CostSimulationViewSet(SingleInstanceCostingViewSet):
    queryset = CostSimulation.objects.select_related('product', 'formula')
    serializer_class = CostSimulationSerializer
    filterset_fields = ('product', 'formula')
    search_fields = ('name', 'product__code', 'product__description', 'formula__code')
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        return self._domain_action_response(lambda simulation: simulation.calculate())


class ProductionCostCaptureViewSet(SingleInstanceCostingViewSet):
    queryset = ProductionCostCapture.objects.select_related('production_order')
    serializer_class = ProductionCostCaptureSerializer
    filterset_fields = ('production_order', 'period_start', 'period_end')
    search_fields = (
        'production_order__order_number',
        'production_order__batch_number',
    )
    ordering = ('-period_start', 'production_order__order_number')

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        return self._domain_action_response(lambda capture: capture.calculate_actuals())


class MonthlyCostClosingViewSet(SingleInstanceCostingViewSet):
    queryset = MonthlyCostClosing.objects.select_related('closed_by')
    serializer_class = MonthlyCostClosingSerializer
    filterset_fields = ('period_year', 'period_month', 'status')
    search_fields = ('validation_notes',)
    ordering = ('-period_year', '-period_month')

    @action(detail=True, methods=['post'])
    def validate_period(self, request, pk=None):
        notes = request.data.get('validation_notes', '')
        return self._domain_action_response(lambda closing: closing.validate_period(notes=notes))

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        return self._domain_action_response(lambda closing: closing.close(user=request.user))

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        reason = request.data.get('validation_notes', '')
        return self._domain_action_response(
            lambda closing: closing.reopen(reason=reason, user=request.user)
        )


class CostReportSnapshotViewSet(SingleInstanceCostingViewSet):
    queryset = CostReportSnapshot.objects.select_related('product', 'stock_lot', 'production_order')
    serializer_class = CostReportSnapshotSerializer
    filterset_fields = (
        'report_type',
        'product',
        'stock_lot',
        'production_order',
        'period_start',
        'period_end',
    )
    search_fields = (
        'product__code',
        'product__description',
        'stock_lot__lot_number',
        'production_order__order_number',
        'notes',
    )
    ordering = ('-generated_at',)

    @action(detail=True, methods=['post'])
    def calculate_margin(self, request, pk=None):
        return self._domain_action_response(lambda snapshot: snapshot.calculate_margin())
