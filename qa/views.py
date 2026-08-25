from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from qa.models import (
    BatchRecordChecklistItem,
    CriticalActivityRule,
    LotRelease,
    QAReview,
    QualityBlock,
    TrainingRecord,
    TrainingRequirement,
)
from qa.serializers import (
    BatchRecordChecklistItemSerializer,
    CriticalActivityRuleSerializer,
    LotReleaseSerializer,
    QAReviewSerializer,
    QualityBlockSerializer,
    TrainingRecordSerializer,
    TrainingRequirementSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


User = get_user_model()


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstanceQAViewSet(viewsets.ModelViewSet):
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
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(obj)
        return Response(serializer.data)


class QAReviewViewSet(SingleInstanceQAViewSet):
    queryset = QAReview.objects.select_related(
        'stock_lot',
        'production_order',
        'quality_document',
        'submitted_by',
        'approved_by',
        'rejected_by',
    )
    serializer_class = QAReviewSerializer
    filterset_fields = (
        'review_type',
        'status',
        'stock_lot',
        'production_order',
        'quality_document',
    )
    search_fields = (
        'review_number',
        'title',
        'packaging_record_reference',
        'deviation_reference',
        'capa_reference',
        'change_reference',
        'controlled_document_reference',
    )
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        return self._domain_action_response(lambda review: review.submit(user=request.user))

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._domain_action_response(lambda review: review.approve(user=request.user))

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda review: review.reject(reason=reason, user=request.user)
        )


class BatchRecordChecklistItemViewSet(SingleInstanceQAViewSet):
    queryset = BatchRecordChecklistItem.objects.select_related(
        'review', 'responsible', 'completed_by'
    )
    serializer_class = BatchRecordChecklistItemSerializer
    filterset_fields = ('review', 'status', 'responsible', 'due_date')
    search_fields = ('review__review_number', 'title', 'comments', 'evidence_reference')
    ordering = ('review__review_number', 'created_at')

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        evidence_reference = request.data.get('evidence_reference', '')
        comments = request.data.get('comments', '')
        return self._domain_action_response(
            lambda item: item.complete(
                user=request.user, evidence_reference=evidence_reference, comments=comments
            )
        )


class LotReleaseViewSet(SingleInstanceQAViewSet):
    queryset = LotRelease.objects.select_related(
        'product', 'stock_lot', 'qa_review', 'quality_document', 'production_order', 'released_by'
    )
    serializer_class = LotReleaseSerializer
    action_permission_map = {
        'approve': ('qa.change_lotrelease',),
        'reject': ('qa.change_lotrelease',),
        'block': ('qa.change_lotrelease',),
        'unblock': ('qa.change_lotrelease',),
    }
    filterset_fields = (
        'release_status',
        'product',
        'stock_lot',
        'qa_review',
        'quality_document',
        'production_order',
    )
    search_fields = (
        'release_number',
        'product__code',
        'stock_lot__lot_number',
        'decision',
        'block_reason',
        'rejection_reason',
    )
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        decision = request.data.get('decision', '')
        return self._domain_action_response(
            lambda release: release.approve(user=request.user, decision=decision)
        )

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda release: release.reject(reason=reason, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda release: release.block(reason=reason, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda release: release.unblock(reason=reason, user=request.user)
        )


class QualityBlockViewSet(SingleInstanceQAViewSet):
    queryset = QualityBlock.objects.select_related(
        'product', 'stock_lot', 'supplier', 'quality_document', 'blocked_by', 'unblocked_by'
    )
    serializer_class = QualityBlockSerializer
    filterset_fields = (
        'target_type',
        'status',
        'product',
        'stock_lot',
        'supplier',
        'quality_document',
    )
    search_fields = (
        'block_number',
        'reason',
        'equipment_reference',
        'process_reference',
        'document_reference',
    )
    ordering = ('-blocked_at',)

    def perform_create(self, serializer):
        block = serializer.save(blocked_by=self.request.user)
        block.apply()

    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        return self._domain_action_response(lambda block: block.apply())

    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda block: block.unblock(reason=reason, user=request.user)
        )


class TrainingRequirementViewSet(SingleInstanceQAViewSet):
    queryset = TrainingRequirement.objects.select_related('target_user')
    serializer_class = TrainingRequirementSerializer
    filterset_fields = (
        'is_active',
        'is_mandatory',
        'required_role',
        'area',
        'process',
        'target_user',
    )
    search_fields = ('code', 'title', 'document_reference', 'required_role', 'area', 'process')
    ordering = ('code',)


class TrainingRecordViewSet(SingleInstanceQAViewSet):
    queryset = TrainingRecord.objects.select_related('requirement', 'user', 'trainer')
    serializer_class = TrainingRecordSerializer
    filterset_fields = ('requirement', 'user', 'trainer', 'status', 'valid_until')
    search_fields = (
        'requirement__code',
        'requirement__title',
        'user__email',
        'trainer__email',
        'evidence_reference',
    )
    ordering = ('-completed_at', '-created_at')

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        evidence_reference = request.data.get('evidence_reference', '')
        return self._domain_action_response(
            lambda record: record.complete(
                completed_at=timezone_now(),
                user=request.user,
                evidence_reference=evidence_reference,
            )
        )

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(lambda record: record.revoke(reason=reason))


def timezone_now():
    from django.utils import timezone

    return timezone.now()


class CriticalActivityRuleViewSet(SingleInstanceQAViewSet):
    queryset = CriticalActivityRule.objects.select_related('training_requirement')
    serializer_class = CriticalActivityRuleSerializer
    filterset_fields = (
        'is_active',
        'enforce_training',
        'training_requirement',
        'required_role',
        'area',
        'process',
    )
    search_fields = ('activity_code', 'name', 'required_role', 'area', 'process')
    ordering = ('activity_code',)

    @action(detail=True, methods=['post'])
    def authorize(self, request, pk=None):
        rule = self.get_object()
        user_id = request.data.get('user') or request.user.id
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return Response({'user': 'Usuário não encontrado.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rule.validate_user_training(user)
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        return Response({'authorized': True})
