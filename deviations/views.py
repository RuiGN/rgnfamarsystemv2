from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from deviations.models import (
    DeviationApproval,
    DeviationEvidence,
    DeviationImpactAssessment,
    DeviationInvestigation,
    DeviationLink,
    QualityEvent,
)
from deviations.serializers import (
    DeviationApprovalSerializer,
    DeviationEvidenceSerializer,
    DeviationImpactAssessmentSerializer,
    DeviationInvestigationSerializer,
    DeviationLinkSerializer,
    QualityEventSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstanceDeviationViewSet(viewsets.ModelViewSet):
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


class QualityEventViewSet(SingleInstanceDeviationViewSet):
    queryset = QualityEvent.objects.select_related(
        'product',
        'stock_lot',
        'controlled_document',
        'supplier',
        'customer',
        'responsible',
        'opened_by',
        'closed_by',
    )
    serializer_class = QualityEventSerializer
    filterset_fields = (
        'event_type',
        'origin',
        'status',
        'severity',
        'criticality',
        'product',
        'stock_lot',
        'responsible',
    )
    search_fields = (
        'event_number',
        'area',
        'description',
        'closure_summary',
    )
    ordering = ('-opened_at',)

    def perform_create(self, serializer):
        serializer.save(opened_by=self.request.user)

    @action(detail=True, methods=['post'])
    def start_investigation(self, request, pk=None):
        return self._domain_action_response(
            lambda event: event.start_investigation(user=request.user)
        )

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        summary = request.data.get('summary', '')
        return self._domain_action_response(
            lambda event: event.close(summary=summary, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(lambda event: event.cancel(reason=reason))


class DeviationEvidenceViewSet(SingleInstanceDeviationViewSet):
    queryset = DeviationEvidence.objects.select_related('event', 'uploaded_by')
    serializer_class = DeviationEvidenceSerializer
    filterset_fields = ('event', 'uploaded_by')
    search_fields = ('event__event_number', 'title', 'file_reference', 'content_hash', 'notes')
    ordering = ('event__event_number', 'title')

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class DeviationInvestigationViewSet(SingleInstanceDeviationViewSet):
    queryset = DeviationInvestigation.objects.select_related(
        'event', 'investigator', 'concluded_by'
    )
    serializer_class = DeviationInvestigationSerializer
    filterset_fields = ('event', 'status', 'investigator')
    search_fields = (
        'event__event_number',
        'immediate_actions',
        'containment_actions',
        'root_cause',
        'impact_conclusion',
        'conclusion',
    )
    ordering = ('event__event_number', '-created_at')

    @action(detail=True, methods=['post'])
    def conclude(self, request, pk=None):
        root_cause = request.data.get('root_cause', '')
        impact_conclusion = request.data.get('impact_conclusion', '')
        conclusion = request.data.get('conclusion', '')
        return self._domain_action_response(
            lambda investigation: investigation.conclude(
                root_cause=root_cause,
                impact_conclusion=impact_conclusion,
                conclusion=conclusion,
                user=request.user,
            )
        )


class DeviationImpactAssessmentViewSet(SingleInstanceDeviationViewSet):
    queryset = DeviationImpactAssessment.objects.select_related(
        'event', 'assessed_by', 'completed_by'
    )
    serializer_class = DeviationImpactAssessmentSerializer
    filterset_fields = (
        'event',
        'is_completed',
        'impacts_quality',
        'impacts_regulatory',
        'impacts_inventory',
    )
    search_fields = ('event__event_number', 'summary')
    ordering = ('event__event_number',)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        return self._domain_action_response(lambda impact: impact.complete(user=request.user))


class DeviationApprovalViewSet(SingleInstanceDeviationViewSet):
    queryset = DeviationApproval.objects.select_related('event', 'approver', 'decided_by')
    serializer_class = DeviationApprovalSerializer
    filterset_fields = ('event', 'role', 'approver', 'required', 'decision')
    search_fields = ('event__event_number', 'approver__email', 'comments')
    ordering = ('event__event_number', 'role')

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


class DeviationLinkViewSet(SingleInstanceDeviationViewSet):
    queryset = DeviationLink.objects.select_related(
        'event', 'customer_complaint', 'quality_result', 'stock_lot', 'controlled_document'
    )
    serializer_class = DeviationLinkSerializer
    filterset_fields = (
        'event',
        'link_type',
        'customer_complaint',
        'quality_result',
        'stock_lot',
        'controlled_document',
    )
    search_fields = ('event__event_number', 'reference_code', 'notes')
    ordering = ('event__event_number', 'link_type')
