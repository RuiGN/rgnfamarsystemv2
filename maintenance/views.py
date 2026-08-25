from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from inventory.models import StockLot
from maintenance.models import (
    EquipmentAsset,
    EquipmentDowntime,
    EquipmentUsageLog,
    MaintenanceMetricReport,
    MaintenanceOrder,
    MaintenancePlan,
)
from maintenance.serializers import (
    EquipmentAssetSerializer,
    EquipmentDowntimeSerializer,
    EquipmentUsageLogSerializer,
    MaintenanceMetricReportSerializer,
    MaintenanceOrderSerializer,
    MaintenancePlanSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


def _parse_datetime_or_now(value):
    if not value:
        return timezone.now()
    parsed = parse_datetime(value)
    if parsed is None:
        raise DjangoValidationError({'ended_at': 'Informe uma data/hora válida.'})
    return parsed


class SingleInstanceMaintenanceViewSet(viewsets.ModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    ordering: tuple[str, ...] = ('-created_at',)

    def get_queryset(self):
        return self.queryset.all()

    def perform_create(self, serializer):
        serializer.save()

    def _domain_action_response(self, callback, serializer_class=None):
        obj = self.get_object()
        try:
            result = callback(obj) or obj
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        serializer = (serializer_class or self.get_serializer_class())(
            result, context=self.get_serializer_context()
        )
        return Response(serializer.data)


class EquipmentAssetViewSet(SingleInstanceMaintenanceViewSet):
    queryset = EquipmentAsset.objects.select_related('responsible', 'blocked_by', 'released_by')
    serializer_class = EquipmentAssetSerializer
    filterset_fields = (
        'asset_type',
        'status',
        'qualification_status',
        'calibration_required',
        'calibration_status',
        'is_critical',
        'responsible',
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
    ordering = ('asset_code', 'name')

    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda asset: asset.block(reason=reason, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        return self._domain_action_response(lambda asset: asset.release(user=request.user))


class MaintenancePlanViewSet(SingleInstanceMaintenanceViewSet):
    queryset = MaintenancePlan.objects.select_related('asset', 'responsible')
    serializer_class = MaintenancePlanSerializer
    filterset_fields = (
        'asset',
        'plan_type',
        'trigger_type',
        'active',
        'next_due_date',
        'responsible',
    )
    search_fields = (
        'asset__asset_code',
        'asset__name',
        'description',
        'event_name',
        'lot_rule',
        'rule_expression',
    )
    ordering = ('asset__asset_code', 'next_due_date')

    @action(detail=True, methods=['post'])
    def generate_order(self, request, pk=None):
        source_lot = None
        source_lot_id = request.data.get('source_lot')
        if source_lot_id:
            try:
                source_lot = StockLot.objects.get(id=source_lot_id)
            except StockLot.DoesNotExist:
                return Response(
                    {'source_lot': 'O lote informado não foi encontrado.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        due_date = (
            parse_date(request.data.get('due_date')) if request.data.get('due_date') else None
        )
        if request.data.get('due_date') and due_date is None:
            return Response(
                {'due_date': 'Informe uma data válida.'}, status=status.HTTP_400_BAD_REQUEST
            )
        return self._domain_action_response(
            lambda plan: plan.generate_order(
                triggered_by=request.user, due_date=due_date, source_lot=source_lot
            ),
            serializer_class=MaintenanceOrderSerializer,
        )


class MaintenanceOrderViewSet(SingleInstanceMaintenanceViewSet):
    queryset = MaintenanceOrder.objects.select_related(
        'asset',
        'plan',
        'source_lot',
        'responsible',
        'opened_by',
        'started_by',
        'completed_by',
        'cancelled_by',
    )
    serializer_class = MaintenanceOrderSerializer
    filterset_fields = (
        'asset',
        'plan',
        'order_type',
        'trigger_type',
        'source_lot',
        'status',
        'priority',
        'due_date',
        'responsible',
    )
    search_fields = (
        'order_number',
        'description',
        'completion_summary',
        'evidence_reference',
        'content_hash',
        'asset__asset_code',
        'asset__name',
    )
    ordering = ('-due_date', '-created_at')

    def perform_create(self, serializer):
        serializer.save(opened_by=self.request.user)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        return self._domain_action_response(lambda order: order.start(user=request.user))

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        summary = request.data.get('summary', '')
        evidence_reference = request.data.get('evidence_reference', '')
        content_hash = request.data.get('content_hash', '')
        return self._domain_action_response(
            lambda order: order.complete(
                summary=summary,
                evidence_reference=evidence_reference,
                content_hash=content_hash,
                user=request.user,
            )
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda order: order.cancel(reason=reason, user=request.user)
        )


class EquipmentDowntimeViewSet(SingleInstanceMaintenanceViewSet):
    queryset = EquipmentDowntime.objects.select_related('asset', 'order')
    serializer_class = EquipmentDowntimeSerializer
    filterset_fields = ('asset', 'order', 'downtime_type', 'started_at', 'ended_at')
    search_fields = ('asset__asset_code', 'asset__name', 'order__order_number', 'reason')
    ordering = ('-started_at',)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        try:
            ended_at = _parse_datetime_or_now(request.data.get('ended_at'))
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        return self._domain_action_response(lambda downtime: downtime.close(ended_at=ended_at))


class EquipmentUsageLogViewSet(SingleInstanceMaintenanceViewSet):
    queryset = EquipmentUsageLog.objects.select_related('asset', 'source_lot', 'logged_by')
    serializer_class = EquipmentUsageLogSerializer
    filterset_fields = (
        'asset',
        'source_lot',
        'used_at',
        'usage_unit',
        'event_reference',
        'logged_by',
    )
    search_fields = (
        'asset__asset_code',
        'asset__name',
        'source_lot__lot_number',
        'usage_unit',
        'event_reference',
    )
    ordering = ('-used_at',)

    def perform_create(self, serializer):
        serializer.save(logged_by=self.request.user)


class MaintenanceMetricReportViewSet(SingleInstanceMaintenanceViewSet):
    queryset = MaintenanceMetricReport.objects.select_related('asset', 'generated_by')
    serializer_class = MaintenanceMetricReportSerializer
    filterset_fields = ('asset', 'report_type', 'status', 'generated_by', 'generated_at')
    search_fields = ('title', 'content_reference', 'asset__asset_code', 'asset__name')
    ordering = ('-period_end', '-created_at')

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        content_reference = request.data.get('content_reference', '')
        return self._domain_action_response(
            lambda report: report.generate(user=request.user, content_reference=content_reference)
        )
