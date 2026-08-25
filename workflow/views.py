from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from base.permissions import SingleInstanceDjangoModelPermissions
from workflow.models import (
    ApprovalQueue,
    ApprovalTask,
    AsyncJobStatus,
    WorkflowAttachment,
    WorkflowComment,
    WorkflowDelegation,
    WorkflowHistory,
    WorkflowNotification,
)
from workflow.serializers import (
    ApprovalQueueSerializer,
    ApprovalTaskSerializer,
    AsyncJobStatusSerializer,
    WorkflowAttachmentSerializer,
    WorkflowCommentSerializer,
    WorkflowDelegationSerializer,
    WorkflowHistorySerializer,
    WorkflowNotificationSerializer,
)


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstanceWorkflowViewSet(viewsets.ModelViewSet):
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
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        serializer = (serializer_class or self.get_serializer_class())(
            result, context=self.get_serializer_context()
        )
        return Response(serializer.data, status=response_status)


class WorkflowNotificationViewSet(SingleInstanceWorkflowViewSet):
    queryset = WorkflowNotification.objects.select_related('recipient')
    serializer_class = WorkflowNotificationSerializer
    filterset_fields = (
        'recipient',
        'category',
        'channel',
        'source_module',
        'criticality',
        'status',
        'due_at',
    )
    search_fields = ('title', 'message', 'source_model', 'source_record_id', 'recipient__email')
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        return self._domain_action_response(lambda notification: notification.send())

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        return self._domain_action_response(
            lambda notification: notification.mark_read(user=request.user)
        )

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        return self._domain_action_response(
            lambda notification: notification.archive(user=request.user)
        )


class ApprovalQueueViewSet(SingleInstanceWorkflowViewSet):
    queryset = ApprovalQueue.objects.select_related('created_by')
    serializer_class = ApprovalQueueSerializer
    filterset_fields = ('module', 'area', 'profile_role', 'criticality', 'created_by', 'is_active')
    search_fields = ('code', 'name', 'area', 'description')
    ordering = ('module', 'area', 'code')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ApprovalTaskViewSet(SingleInstanceWorkflowViewSet):
    queryset = ApprovalTask.objects.select_related(
        'queue', 'requested_by', 'assigned_to', 'decided_by'
    )
    serializer_class = ApprovalTaskSerializer
    filterset_fields = (
        'queue',
        'source_module',
        'source_model',
        'source_record_id',
        'area',
        'criticality',
        'status',
        'requested_by',
        'assigned_to',
        'due_at',
    )
    search_fields = (
        'task_number',
        'title',
        'description',
        'source_model',
        'source_record_id',
        'requested_by__email',
        'assigned_to__email',
    )
    ordering = ('-created_at',)

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._domain_action_response(
            lambda task: task.approve(user=request.user, comments=request.data.get('comments', ''))
        )

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return self._domain_action_response(
            lambda task: task.reject(user=request.user, comments=request.data.get('comments', ''))
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return self._domain_action_response(
            lambda task: task.cancel(user=request.user, comments=request.data.get('comments', ''))
        )


class WorkflowDelegationViewSet(SingleInstanceWorkflowViewSet):
    queryset = WorkflowDelegation.objects.select_related('from_user', 'to_user')
    serializer_class = WorkflowDelegationSerializer
    filterset_fields = ('from_user', 'to_user', 'module', 'starts_at', 'ends_at', 'is_active')
    search_fields = ('from_user__email', 'to_user__email', 'reason')
    ordering = ('-starts_at',)


class WorkflowCommentViewSet(SingleInstanceWorkflowViewSet):
    queryset = WorkflowComment.objects.select_related('task', 'author')
    serializer_class = WorkflowCommentSerializer
    filterset_fields = ('task', 'author', 'is_internal')
    search_fields = ('task__task_number', 'task__title', 'author__email', 'comment')
    ordering = ('created_at',)

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user)
        comment.task.record_history(
            WorkflowHistory.Action.COMMENTED,
            actor=self.request.user,
            details={'comment': comment.comment},
        )


class WorkflowAttachmentViewSet(SingleInstanceWorkflowViewSet):
    queryset = WorkflowAttachment.objects.select_related('task', 'uploaded_by')
    serializer_class = WorkflowAttachmentSerializer
    filterset_fields = ('task', 'uploaded_by')
    search_fields = (
        'task__task_number',
        'task__title',
        'file_name',
        'file_reference',
        'content_hash',
    )
    ordering = ('task__task_number', 'file_name')

    def perform_create(self, serializer):
        attachment = serializer.save(uploaded_by=self.request.user)
        attachment.task.record_history(
            WorkflowHistory.Action.ATTACHED,
            actor=self.request.user,
            details={'file_name': attachment.file_name},
        )


class AsyncJobStatusViewSet(SingleInstanceWorkflowViewSet):
    queryset = AsyncJobStatus.objects.select_related('requested_by')
    serializer_class = AsyncJobStatusSerializer
    filterset_fields = (
        'task_name',
        'task_id',
        'source_module',
        'source_model',
        'source_record_id',
        'status',
        'requested_by',
    )
    search_fields = (
        'job_number',
        'task_name',
        'task_id',
        'title',
        'loading_message',
        'message',
        'result_reference',
        'error_message',
    )
    ordering = ('-created_at',)

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        return self._domain_action_response(
            lambda job: job.start(task_id=request.data.get('task_id', ''))
        )

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        return self._domain_action_response(
            lambda job: job.update_progress(
                progress_percent=request.data.get('progress_percent', 0),
                message=request.data.get('message', ''),
            )
        )

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        return self._domain_action_response(
            lambda job: job.complete(
                result_reference=request.data.get('result_reference', ''),
                message=request.data.get('message', ''),
            )
        )

    @action(detail=True, methods=['post'])
    def fail(self, request, pk=None):
        return self._domain_action_response(
            lambda job: job.fail(
                error_message=request.data.get('error_message', ''),
                message=request.data.get('message', ''),
            )
        )


class WorkflowHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    queryset = WorkflowHistory.objects.select_related('task', 'notification', 'async_job', 'actor')
    serializer_class = WorkflowHistorySerializer
    filterset_fields = ('task', 'notification', 'async_job', 'action', 'actor', 'occurred_at')
    search_fields = (
        'task__task_number',
        'notification__title',
        'async_job__job_number',
        'actor__email',
        'snapshot',
    )
    ordering = ('-occurred_at',)

    def get_queryset(self):
        return self.queryset.all()
