from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ai_agents.models import AIAgentProfile, AIAgentRun, AIInsightSuggestion, AIPromptAuditLog
from ai_agents.serializers import (
    AIAgentProfileSerializer,
    AIAgentRunRequestSerializer,
    AIAgentRunSerializer,
    AIInsightSuggestionSerializer,
    AIPromptAuditLogSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstanceAIViewSet(viewsets.ModelViewSet):
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


class AIAgentProfileViewSet(SingleInstanceAIViewSet):
    action_permission_map = {
        'run': ('ai_agents.change_aiagentprofile', 'ai_agents.add_aiagentrun'),
    }
    queryset = AIAgentProfile.objects.select_related('created_by')
    serializer_class = AIAgentProfileSerializer
    filterset_fields = (
        'agent_type',
        'source_module',
        'provider',
        'model_name',
        'is_active',
        'created_by',
    )
    search_fields = ('code', 'name', 'system_prompt', 'created_by__email')
    ordering = ('source_module', 'code')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        agent = self.get_object()
        request_serializer = AIAgentRunRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        data = request_serializer.validated_data
        try:
            agent_run = agent.create_run(
                source_module=data['source_module'],
                source_model=data['source_model'],
                source_record_id=data['source_record_id'],
                input_payload=data['input_payload'],
                requested_by=request.user,
            )
            if data['run_immediately']:
                agent_run.execute(user=request.user)
            else:
                agent_run.enqueue(dispatch=data['dispatch'])
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        serializer = AIAgentRunSerializer(agent_run, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AIAgentRunViewSet(SingleInstanceAIViewSet):
    queryset = AIAgentRun.objects.select_related('agent', 'requested_by')
    serializer_class = AIAgentRunSerializer
    filterset_fields = (
        'agent',
        'source_module',
        'source_model',
        'source_record_id',
        'execution_mode',
        'status',
        'requested_by',
    )
    search_fields = (
        'run_number',
        'source_model',
        'source_record_id',
        'prompt_text',
        'output_text',
        'error_message',
        'requested_by__email',
    )
    ordering = ('-created_at',)

    def perform_create(self, serializer):
        agent = serializer.validated_data['agent']
        instance = serializer.save(
            requested_by=self.request.user,
            prompt_text=agent.build_prompt(
                serializer.validated_data['source_module'],
                serializer.validated_data['source_model'],
                serializer.validated_data['source_record_id'],
                serializer.validated_data.get('input_payload') or {},
            ),
            model_name=agent.model_name,
        )
        instance.full_clean()

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        return self._domain_action_response(lambda agent_run: agent_run.execute(user=request.user))

    @action(detail=True, methods=['post'])
    def enqueue(self, request, pk=None):
        return self._domain_action_response(
            lambda agent_run: agent_run.enqueue(dispatch=bool(request.data.get('dispatch', False)))
        )


class AIInsightSuggestionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    queryset = AIInsightSuggestion.objects.select_related('run', 'reviewed_by')
    serializer_class = AIInsightSuggestionSerializer
    filterset_fields = (
        'run',
        'suggestion_type',
        'status',
        'source_module',
        'source_model',
        'source_record_id',
        'reviewed_by',
    )
    search_fields = (
        'title',
        'description',
        'source_model',
        'source_record_id',
        'reviewed_by__email',
        'review_comments',
    )
    ordering = ('-created_at',)

    def get_queryset(self):
        return self.queryset.all()

    def _review_response(self, callback):
        obj = self.get_object()
        try:
            callback(obj)
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._review_response(
            lambda suggestion: suggestion.approve(
                user=request.user, comments=request.data.get('comments', '')
            )
        )

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return self._review_response(
            lambda suggestion: suggestion.reject(
                user=request.user, comments=request.data.get('comments', '')
            )
        )

    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        return self._review_response(
            lambda suggestion: suggestion.apply(
                user=request.user, comments=request.data.get('comments', '')
            )
        )


class AIPromptAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    queryset = AIPromptAuditLog.objects.select_related('run', 'agent', 'user')
    serializer_class = AIPromptAuditLogSerializer
    filterset_fields = ('run', 'agent', 'user', 'model_name', 'status', 'occurred_at')
    search_fields = (
        'run__run_number',
        'agent__code',
        'user__email',
        'prompt_text',
        'output_text',
        'error_message',
    )
    ordering = ('-occurred_at',)

    def get_queryset(self):
        return self.queryset.all()
