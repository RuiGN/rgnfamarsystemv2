from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from files.downloads import protected_file_client_metadata, protected_file_download_response
from files.models import ProtectedFileAuditTrail
from reports.models import (
    DashboardWidget,
    DashboardWorkspace,
    ReportDefinition,
    ReportExecution,
    ReportNotification,
    ReportSchedule,
)
from reports.serializers import (
    DashboardWidgetSerializer,
    DashboardWorkspaceSerializer,
    ReportDefinitionSerializer,
    ReportExecutionSerializer,
    ReportNotificationSerializer,
    ReportScheduleSerializer,
    RunReportSerializer,
)
from reports.services import ReportExecutionInProgress, run_report_definition
from base.permissions import SingleInstanceDjangoModelPermissions


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstanceReportViewSet(viewsets.ModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
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
        except ReportExecutionInProgress as error:
            return Response(
                _validation_payload(error),
                status=status.HTTP_409_CONFLICT,
            )
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        serializer = (serializer_class or self.get_serializer_class())(
            result, context=self.get_serializer_context()
        )
        return Response(serializer.data, status=response_status)


class DashboardWorkspaceViewSet(SingleInstanceReportViewSet):
    queryset = DashboardWorkspace.objects.select_related('owner')
    serializer_class = DashboardWorkspaceSerializer
    filterset_fields = ('module', 'profile_role', 'owner', 'is_active')
    search_fields = ('code', 'title')
    ordering = ('module', 'code')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class DashboardWidgetViewSet(SingleInstanceReportViewSet):
    queryset = DashboardWidget.objects.select_related('dashboard', 'report_definition')
    serializer_class = DashboardWidgetSerializer
    filterset_fields = ('dashboard', 'widget_type', 'module', 'report_definition')
    search_fields = ('dashboard__code', 'dashboard__title', 'title')
    ordering = ('dashboard__code', 'position_row', 'position_column')


class ReportDefinitionViewSet(SingleInstanceReportViewSet):
    action_permission_map = {
        'list': ('reports.change_reportdefinition',),
        'retrieve': ('reports.change_reportdefinition',),
        'create': (
            'reports.change_reportdefinition',
            'reports.add_reportdefinition',
        ),
        'update': ('reports.change_reportdefinition',),
        'partial_update': ('reports.change_reportdefinition',),
        'destroy': (
            'reports.change_reportdefinition',
            'reports.delete_reportdefinition',
        ),
        'run': ('reports.view_reportdefinition', 'reports.add_reportexecution'),
    }
    queryset = ReportDefinition.objects.select_related('owner')
    serializer_class = ReportDefinitionSerializer
    filterset_fields = ('module', 'category', 'owner', 'is_active')
    search_fields = ('code', 'title', 'description')
    ordering = ('module', 'code')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        definition = self.get_object()
        input_serializer = RunReportSerializer(
            data=request.data,
            context={'definition': definition},
        )
        input_serializer.is_valid(raise_exception=True)
        try:
            execution = run_report_definition(
                definition=definition,
                user=request.user,
                **input_serializer.validated_data,
            )
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        serializer = ReportExecutionSerializer(execution, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ReportExecutionViewSet(SingleInstanceReportViewSet):
    action_permission_map = {
        'download': ('reports.view_reportexecution', 'files.view_protectedfile'),
    }
    queryset = ReportExecution.objects.select_related(
        'definition',
        'schedule',
        'requested_by',
        'result_file',
    )
    serializer_class = ReportExecutionSerializer
    filterset_fields = (
        'definition',
        'schedule',
        'export_format',
        'status',
        'requested_by',
        'requested_at',
    )
    search_fields = (
        'execution_number',
        'definition__code',
        'definition__title',
        'result_reference',
        'content_hash',
        'error_message',
    )
    ordering = ('-requested_at', '-created_at')

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        execution = self.get_object()
        if execution.status != ReportExecution.Status.COMPLETED or execution.result_file_id is None:
            if execution.result_file_id is not None:
                execution.result_file.record_audit(
                    ProtectedFileAuditTrail.Action.ACCESS_DENIED,
                    user=request.user,
                    details={'reason': 'execution_not_completed'},
                    **protected_file_client_metadata(request),
                )
            return Response(
                {'detail': 'Arquivo de relatório indisponível.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            return protected_file_download_response(
                execution.result_file,
                user=request.user,
                **protected_file_client_metadata(request),
            )
        except DjangoValidationError:
            return Response(
                {'detail': 'Arquivo de relatório indisponível.'},
                status=status.HTTP_403_FORBIDDEN,
            )

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        return self._domain_action_response(lambda execution: execution.run(user=request.user))

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return self._domain_action_response(lambda execution: execution.cancel(user=request.user))


class ReportScheduleViewSet(SingleInstanceReportViewSet):
    action_permission_map = {
        'trigger_now': ('reports.change_reportschedule', 'reports.add_reportexecution'),
    }
    queryset = ReportSchedule.objects.select_related('definition', 'owner').prefetch_related(
        'recipients'
    )
    serializer_class = ReportScheduleSerializer
    filterset_fields = ('definition', 'frequency', 'owner', 'is_active', 'next_run_at')
    search_fields = ('name', 'definition__code', 'definition__title', 'cron_expression')
    ordering = ('next_run_at', 'name')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def trigger_now(self, request, pk=None):
        return self._domain_action_response(
            lambda schedule: schedule.trigger_now(user=request.user, run_immediately=True),
            serializer_class=ReportExecutionSerializer,
            response_status=status.HTTP_201_CREATED,
        )


class ReportNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    queryset = ReportNotification.objects.select_related(
        'execution', 'execution__definition', 'recipient'
    )
    serializer_class = ReportNotificationSerializer
    filterset_fields = ('execution', 'recipient', 'channel', 'status', 'sent_at')
    search_fields = (
        'execution__execution_number',
        'execution__definition__title',
        'recipient__email',
        'message',
        'error_message',
    )
    ordering = ('-created_at',)

    def get_queryset(self):
        return self.queryset.all()
