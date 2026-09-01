from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from governance.models import (
    DemoScenarioLoad,
    GovernanceAuditLog,
    GovernanceCatalogItem,
    GovernanceParameter,
    InstitutionSettings,
)
from governance.serializers import (
    DemoScenarioLoadSerializer,
    GovernanceAuditLogSerializer,
    GovernanceCatalogItemSerializer,
    GovernanceParameterSerializer,
    InstitutionSettingsSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstanceGovernanceViewSet(viewsets.ModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    search_fields: tuple[str, ...] = ()
    ordering: tuple[str, ...] = ('-created_at',)

    def get_queryset(self):
        return self.queryset.all()

    def perform_create(self, serializer):
        serializer.save()

    def _domain_action_response(
        self, callback, serializer_class=None, response_status=status.HTTP_200_OK
    ):
        obj = self.get_object()
        try:
            result = callback(obj) or obj
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        serializer = (serializer_class or self.get_serializer_class())(
            result, context=self.get_serializer_context()
        )
        return Response(serializer.data, status=response_status)


class GovernanceParameterViewSet(SingleInstanceGovernanceViewSet):
    queryset = GovernanceParameter.objects.select_related('updated_by')
    serializer_class = GovernanceParameterSerializer
    filterset_fields = ('scope', 'module', 'key', 'value_type', 'is_active', 'updated_by')
    search_fields = ('key', 'description', 'value', 'default_value', 'rules', 'updated_by__email')
    ordering = ('scope', 'module', 'key')

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)


class InstitutionSettingsViewSet(SingleInstanceGovernanceViewSet):
    queryset = InstitutionSettings.objects.select_related('city_ref', 'state_ref')
    serializer_class = InstitutionSettingsSerializer
    filterset_fields = ('tax_regime', 'is_active', 'state_ref', 'city_ref')
    search_fields = (
        'trade_name',
        'legal_name',
        'document',
        'email',
        'city_ref__name',
        'state_ref__name',
        'state_ref__name',
    )
    ordering = ('legal_name',)


class GovernanceCatalogItemViewSet(SingleInstanceGovernanceViewSet):
    queryset = GovernanceCatalogItem.objects.select_related('parent')
    serializer_class = GovernanceCatalogItemSerializer
    filterset_fields = ('catalog_type', 'module', 'code', 'value', 'is_active', 'parent')
    search_fields = ('code', 'label', 'value', 'metadata')
    ordering = ('catalog_type', 'module', 'order', 'code')


class GovernanceAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    queryset = GovernanceAuditLog.objects.select_related('user')
    serializer_class = GovernanceAuditLogSerializer
    filterset_fields = ('log_type', 'severity', 'module', 'action', 'user', 'occurred_at')
    search_fields = (
        'action',
        'target_model',
        'target_record_id',
        'user__email',
        'message',
        'request_id',
    )
    ordering = ('-occurred_at',)

    def get_queryset(self):
        return self.queryset.all()


class DemoScenarioLoadViewSet(SingleInstanceGovernanceViewSet):
    queryset = DemoScenarioLoad.objects.select_related('requested_by')
    serializer_class = DemoScenarioLoadSerializer
    filterset_fields = ('scenario', 'status', 'requested_by', 'started_at', 'completed_at')
    search_fields = ('scenario', 'records_created', 'error_message', 'requested_by__email')
    ordering = ('-created_at',)

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        return self._domain_action_response(lambda demo_load: demo_load.run(user=request.user))
