from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.dateparse import parse_date
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from base.permissions import SingleInstanceDjangoModelPermissions
from training.models import (
    Competency,
    CriticalActivityRule,
    JobPosition,
    TrainingEnrollment,
    TrainingIndicatorReport,
    TrainingMatrixRequirement,
    TrainingRequirement,
    TrainingSession,
    WorkFunction,
)
from training.serializers import (
    CompetencySerializer,
    CriticalActivityRuleSerializer,
    JobPositionSerializer,
    TrainingEnrollmentSerializer,
    TrainingIndicatorReportSerializer,
    TrainingMatrixRequirementSerializer,
    TrainingRequirementSerializer,
    TrainingSessionSerializer,
    WorkFunctionSerializer,
)


User = get_user_model()


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstanceTrainingViewSet(viewsets.ModelViewSet):
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


class JobPositionViewSet(SingleInstanceTrainingViewSet):
    queryset = JobPosition.objects.all()
    serializer_class = JobPositionSerializer
    filterset_fields = ('area', 'department', 'is_active')
    search_fields = ('code', 'title', 'area', 'department', 'description')
    ordering = ('area', 'title')


class WorkFunctionViewSet(SingleInstanceTrainingViewSet):
    queryset = WorkFunction.objects.select_related('job_position')
    serializer_class = WorkFunctionSerializer
    filterset_fields = ('job_position', 'area', 'process', 'is_critical', 'is_active')
    search_fields = ('code', 'name', 'area', 'process', 'description')
    ordering = ('area', 'process', 'name')


class CompetencyViewSet(SingleInstanceTrainingViewSet):
    queryset = Competency.objects.all()
    serializer_class = CompetencySerializer
    filterset_fields = ('competency_type', 'is_active')
    search_fields = ('code', 'name', 'description')
    ordering = ('competency_type', 'name')


class TrainingRequirementViewSet(SingleInstanceTrainingViewSet):
    queryset = TrainingRequirement.objects.select_related(
        'job_position', 'function', 'competency', 'document'
    )
    serializer_class = TrainingRequirementSerializer
    filterset_fields = (
        'training_type',
        'area',
        'process',
        'job_position',
        'function',
        'competency',
        'document',
        'module_code',
        'is_mandatory',
        'block_without_valid_training',
        'is_active',
    )
    search_fields = (
        'code',
        'title',
        'area',
        'process',
        'module_code',
        'regulatory_requirement_reference',
        'notes',
    )
    ordering = ('code',)


class TrainingMatrixRequirementViewSet(SingleInstanceTrainingViewSet):
    queryset = TrainingMatrixRequirement.objects.select_related(
        'job_position', 'function', 'competency', 'requirement'
    )
    serializer_class = TrainingMatrixRequirementSerializer
    filterset_fields = (
        'job_position',
        'function',
        'competency',
        'requirement',
        'is_mandatory',
        'priority',
    )
    search_fields = (
        'job_position__title',
        'function__name',
        'competency__name',
        'requirement__code',
        'requirement__title',
        'notes',
    )
    ordering = ('job_position__title', 'requirement__code')


class TrainingSessionViewSet(SingleInstanceTrainingViewSet):
    queryset = TrainingSession.objects.select_related(
        'requirement', 'instructor', 'location_state_ref', 'location_city_ref'
    )
    serializer_class = TrainingSessionSerializer
    filterset_fields = (
        'requirement',
        'delivery_method',
        'status',
        'scheduled_start',
        'instructor',
        'location_state_ref',
        'location_city_ref',
    )
    search_fields = (
        'session_number',
        'title',
        'requirement__code',
        'requirement__title',
        'location',
        'location_city_ref__name',
        'location_state_ref__name',
        'notes',
    )
    ordering = ('-scheduled_start',)

    @action(detail=True, methods=['post'])
    def convocate(self, request, pk=None):
        user_id = request.data.get('user')
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return Response({'user': 'Usuário não encontrado.'}, status=status.HTTP_400_BAD_REQUEST)
        due_date = (
            parse_date(request.data.get('due_date')) if request.data.get('due_date') else None
        )
        if request.data.get('due_date') and due_date is None:
            return Response(
                {'due_date': 'Informe uma data válida.'}, status=status.HTTP_400_BAD_REQUEST
            )
        return self._domain_action_response(
            lambda session: session.convocate(
                user=user, convoked_by=request.user, due_date=due_date
            ),
            serializer_class=TrainingEnrollmentSerializer,
        )


class TrainingEnrollmentViewSet(SingleInstanceTrainingViewSet):
    queryset = TrainingEnrollment.objects.select_related(
        'requirement',
        'session',
        'user',
        'convoked_by',
        'started_by',
        'completed_by',
        'approved_by',
        'revoked_by',
    )
    serializer_class = TrainingEnrollmentSerializer
    filterset_fields = (
        'requirement',
        'session',
        'user',
        'status',
        'due_date',
        'valid_until',
        'recertification_due_date',
    )
    search_fields = (
        'enrollment_number',
        'requirement__code',
        'requirement__title',
        'user__email',
        'evidence_reference',
        'content_hash',
        'certificate_number',
        'certificate_reference',
    )
    ordering = ('-convoked_at', '-created_at')

    def perform_create(self, serializer):
        serializer.save(convoked_by=self.request.user)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        return self._domain_action_response(lambda enrollment: enrollment.start(user=request.user))

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        return self._domain_action_response(
            lambda enrollment: enrollment.complete(
                score=request.data.get('score'),
                evidence_reference=request.data.get('evidence_reference', ''),
                content_hash=request.data.get('content_hash', ''),
                user=request.user,
            )
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._domain_action_response(
            lambda enrollment: enrollment.approve(
                user=request.user,
                certificate_reference=request.data.get('certificate_reference', ''),
            )
        )

    @action(detail=True, methods=['post'])
    def fail(self, request, pk=None):
        return self._domain_action_response(
            lambda enrollment: enrollment.fail(
                reason=request.data.get('reason', ''), user=request.user
            )
        )

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        return self._domain_action_response(
            lambda enrollment: enrollment.revoke(
                reason=request.data.get('reason', ''), user=request.user
            )
        )


class CriticalActivityRuleViewSet(SingleInstanceTrainingViewSet):
    queryset = CriticalActivityRule.objects.select_related('requirement')
    serializer_class = CriticalActivityRuleSerializer
    filterset_fields = (
        'requirement',
        'enforcement_mode',
        'area',
        'process',
        'module_code',
        'is_active',
    )
    search_fields = (
        'activity_code',
        'name',
        'requirement__code',
        'requirement__title',
        'area',
        'process',
        'module_code',
        'notes',
    )
    ordering = ('activity_code',)

    @action(detail=True, methods=['post'])
    def authorize(self, request, pk=None):
        rule = self.get_object()
        user_id = request.data.get('user') or request.user.id
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return Response({'user': 'Usuário não encontrado.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            authorized = rule.authorize_user(user)
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        return Response({'authorized': bool(authorized), 'enforcement_mode': rule.enforcement_mode})


class TrainingIndicatorReportViewSet(SingleInstanceTrainingViewSet):
    queryset = TrainingIndicatorReport.objects.select_related(
        'job_position', 'function', 'generated_by'
    )
    serializer_class = TrainingIndicatorReportSerializer
    filterset_fields = (
        'report_type',
        'status',
        'area',
        'process',
        'job_position',
        'function',
        'generated_by',
    )
    search_fields = ('title', 'area', 'process', 'content_reference')
    ordering = ('-period_end', '-created_at')

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        content_reference = request.data.get('content_reference', '')
        return self._domain_action_response(
            lambda report: report.generate(user=request.user, content_reference=content_reference)
        )
