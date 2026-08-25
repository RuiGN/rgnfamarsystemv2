from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from changes.models import (
    ChangeAction,
    ChangeAffectedItem,
    ChangeApproval,
    ChangeAssessment,
    ChangeControl,
    ChangeStockAssessment,
)
from changes.serializers import (
    ChangeActionSerializer,
    ChangeAffectedItemSerializer,
    ChangeApprovalSerializer,
    ChangeAssessmentSerializer,
    ChangeControlSerializer,
    ChangeStockAssessmentSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstanceChangeViewSet(viewsets.ModelViewSet):
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


class ChangeControlViewSet(SingleInstanceChangeViewSet):
    queryset = ChangeControl.objects.select_related(
        'owner',
        'requested_by',
        'submitted_by',
        'approved_by',
        'implementation_started_by',
        'closed_by',
    )
    serializer_class = ChangeControlSerializer
    filterset_fields = ('change_type', 'status', 'owner', 'due_date', 'requires_stock_assessment')
    search_fields = (
        'change_number',
        'title',
        'scope',
        'justification',
        'affected_areas',
        'equipment_reference',
        'system_reference',
        'impact_summary',
    )
    ordering = ('-created_at',)

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        return self._domain_action_response(lambda change: change.submit(user=request.user))

    @action(detail=True, methods=['post'])
    def approve_for_implementation(self, request, pk=None):
        return self._domain_action_response(
            lambda change: change.approve_for_implementation(user=request.user)
        )

    @action(detail=True, methods=['post'])
    def start_implementation(self, request, pk=None):
        return self._domain_action_response(
            lambda change: change.start_implementation(user=request.user)
        )

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        summary = request.data.get('summary', '')
        return self._domain_action_response(
            lambda change: change.close(summary=summary, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(lambda change: change.cancel(reason=reason))


class ChangeAffectedItemViewSet(SingleInstanceChangeViewSet):
    queryset = ChangeAffectedItem.objects.select_related(
        'change', 'product', 'document', 'supplier'
    )
    serializer_class = ChangeAffectedItemSerializer
    filterset_fields = ('change', 'item_type', 'product', 'document', 'supplier')
    search_fields = ('change__change_number', 'reference_code', 'impact_description')
    ordering = ('change__change_number', 'item_type')


class ChangeAssessmentViewSet(SingleInstanceChangeViewSet):
    queryset = ChangeAssessment.objects.select_related('change', 'assessor', 'completed_by')
    serializer_class = ChangeAssessmentSerializer
    filterset_fields = ('change', 'department', 'status', 'assessor', 'impact_level')
    search_fields = ('change__change_number', 'impact_description', 'required_actions')
    ordering = ('change__change_number', 'department')

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        impact_level = request.data.get('impact_level', '')
        impact_description = request.data.get('impact_description', '')
        required_actions = request.data.get('required_actions', '')
        return self._domain_action_response(
            lambda assessment: assessment.complete(
                impact_level=impact_level,
                impact_description=impact_description,
                required_actions=required_actions,
                user=request.user,
            )
        )


class ChangeActionViewSet(SingleInstanceChangeViewSet):
    queryset = ChangeAction.objects.select_related('change', 'responsible', 'completed_by')
    serializer_class = ChangeActionSerializer
    filterset_fields = (
        'change',
        'action_type',
        'status',
        'responsible',
        'mandatory',
        'required_before_implementation',
        'due_date',
    )
    search_fields = (
        'change__change_number',
        'title',
        'description',
        'completion_notes',
        'evidence_reference',
        'content_hash',
    )
    ordering = ('change__change_number', 'due_date')

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        return self._domain_action_response(lambda action_obj: action_obj.start())

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        completion_notes = request.data.get('completion_notes', '')
        evidence_reference = request.data.get('evidence_reference', '')
        content_hash = request.data.get('content_hash', '')
        return self._domain_action_response(
            lambda action_obj: action_obj.complete(
                user=request.user,
                completion_notes=completion_notes,
                evidence_reference=evidence_reference,
                content_hash=content_hash,
            )
        )


class ChangeApprovalViewSet(SingleInstanceChangeViewSet):
    queryset = ChangeApproval.objects.select_related('change', 'approver', 'decided_by')
    serializer_class = ChangeApprovalSerializer
    filterset_fields = ('change', 'role', 'approver', 'required', 'decision')
    search_fields = ('change__change_number', 'approver__email', 'comments')
    ordering = ('change__change_number', 'role')

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        comments = request.data.get('comments', '')
        return self._domain_action_response(
            lambda approval: approval.approve(user=request.user, comments=comments)
        )

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        comments = request.data.get('comments', '')
        return self._domain_action_response(
            lambda approval: approval.reject(user=request.user, comments=comments)
        )


class ChangeStockAssessmentViewSet(SingleInstanceChangeViewSet):
    queryset = ChangeStockAssessment.objects.select_related(
        'change', 'product', 'stock_lot', 'assessed_by'
    )
    serializer_class = ChangeStockAssessmentSerializer
    filterset_fields = ('change', 'product', 'stock_lot', 'required', 'status', 'decision')
    search_fields = (
        'change__change_number',
        'product__code',
        'stock_lot__lot_number',
        'assessment_summary',
    )
    ordering = ('change__change_number', 'product__code')

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        decision = request.data.get('decision', '')
        assessment_summary = request.data.get('assessment_summary', '')
        return self._domain_action_response(
            lambda stock: stock.complete(
                decision=decision,
                assessment_summary=assessment_summary,
                user=request.user,
            )
        )
