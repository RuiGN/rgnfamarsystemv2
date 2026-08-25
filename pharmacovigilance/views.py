from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from pharmacovigilance.models import (
    PharmacovigilanceAction,
    PharmacovigilanceCase,
    PharmacovigilanceCausalityAssessment,
    PharmacovigilanceClassification,
    PharmacovigilanceInvestigation,
    PharmacovigilanceLink,
    PharmacovigilanceSafetyReport,
)
from pharmacovigilance.serializers import (
    PharmacovigilanceActionSerializer,
    PharmacovigilanceCaseSerializer,
    PharmacovigilanceCausalityAssessmentSerializer,
    PharmacovigilanceClassificationSerializer,
    PharmacovigilanceInvestigationSerializer,
    PharmacovigilanceLinkSerializer,
    PharmacovigilanceSafetyReportSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstancePharmacovigilanceViewSet(viewsets.ModelViewSet):
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


class PharmacovigilanceCaseViewSet(SingleInstancePharmacovigilanceViewSet):
    queryset = PharmacovigilanceCase.objects.select_related(
        'product',
        'stock_lot',
        'customer',
        'responsible',
        'reported_by',
        'triaged_by',
        'investigation_started_by',
        'closed_by',
        'country_ref',
        'state_ref',
        'city_ref',
    )
    serializer_class = PharmacovigilanceCaseSerializer
    filterset_fields = (
        'case_type',
        'source',
        'status',
        'product',
        'stock_lot',
        'customer',
        'seriousness',
        'severity',
        'outcome',
        'responsible',
        'country',
        'country_ref',
        'state_ref',
        'city_ref',
    )
    search_fields = (
        'case_number',
        'description',
        'patient_identifier_hash',
        'product__code',
        'stock_lot__lot_number',
        'customer__legal_name',
        'city_ref__name',
        'state_ref__name',
        'country_ref__name',
    )
    ordering = ('-created_at',)

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)

    @action(detail=True, methods=['post'])
    def start_triage(self, request, pk=None):
        return self._domain_action_response(lambda case: case.start_triage(user=request.user))

    @action(detail=True, methods=['post'])
    def start_investigation(self, request, pk=None):
        return self._domain_action_response(
            lambda case: case.start_investigation(user=request.user)
        )

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        summary = request.data.get('summary', '')
        return self._domain_action_response(
            lambda case: case.close(summary=summary, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(lambda case: case.cancel(reason=reason))


class PharmacovigilanceClassificationViewSet(SingleInstancePharmacovigilanceViewSet):
    queryset = PharmacovigilanceClassification.objects.select_related('case', 'classified_by')
    serializer_class = PharmacovigilanceClassificationSerializer
    filterset_fields = ('case', 'category', 'seriousness', 'expectedness', 'classified_by')
    search_fields = ('case__case_number', 'listedness_reference', 'notes')
    ordering = ('case__case_number', '-classified_at')

    def perform_create(self, serializer):
        serializer.save(classified_by=self.request.user)


class PharmacovigilanceCausalityAssessmentViewSet(SingleInstancePharmacovigilanceViewSet):
    queryset = PharmacovigilanceCausalityAssessment.objects.select_related('case', 'assessed_by')
    serializer_class = PharmacovigilanceCausalityAssessmentSerializer
    filterset_fields = ('case', 'method', 'result', 'assessed_by')
    search_fields = ('case__case_number', 'rationale')
    ordering = ('case__case_number', '-assessed_at')

    def perform_create(self, serializer):
        serializer.save(assessed_by=self.request.user)


class PharmacovigilanceInvestigationViewSet(SingleInstancePharmacovigilanceViewSet):
    queryset = PharmacovigilanceInvestigation.objects.select_related(
        'case', 'responsible', 'completed_by'
    )
    serializer_class = PharmacovigilanceInvestigationSerializer
    filterset_fields = ('case', 'status', 'responsible', 'completed_by')
    search_fields = ('case__case_number', 'summary', 'root_cause', 'conclusion')
    ordering = ('case__case_number', '-created_at')

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        return self._domain_action_response(
            lambda investigation: investigation.complete(user=request.user)
        )


class PharmacovigilanceActionViewSet(SingleInstancePharmacovigilanceViewSet):
    queryset = PharmacovigilanceAction.objects.select_related('case', 'responsible', 'completed_by')
    serializer_class = PharmacovigilanceActionSerializer
    filterset_fields = (
        'case',
        'action_type',
        'status',
        'responsible',
        'due_date',
        'mandatory',
        'evidence_required',
    )
    search_fields = (
        'action_number',
        'case__case_number',
        'title',
        'description',
        'completion_notes',
        'evidence_reference',
        'content_hash',
    )
    ordering = ('case__case_number', 'due_date')

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
                completion_notes=completion_notes,
                evidence_reference=evidence_reference,
                content_hash=content_hash,
                user=request.user,
            )
        )


class PharmacovigilanceLinkViewSet(SingleInstancePharmacovigilanceViewSet):
    queryset = PharmacovigilanceLink.objects.select_related(
        'case',
        'customer_complaint',
        'deviation_event',
        'capa',
        'stock_lot',
        'customer',
        'product',
        'regulatory_dossier',
        'document',
    )
    serializer_class = PharmacovigilanceLinkSerializer
    filterset_fields = (
        'case',
        'link_type',
        'customer_complaint',
        'deviation_event',
        'capa',
        'stock_lot',
        'customer',
        'product',
        'regulatory_dossier',
        'document',
    )
    search_fields = ('case__case_number', 'reference_code', 'description')
    ordering = ('case__case_number', 'link_type')


class PharmacovigilanceSafetyReportViewSet(SingleInstancePharmacovigilanceViewSet):
    queryset = PharmacovigilanceSafetyReport.objects.select_related('case', 'generated_by')
    serializer_class = PharmacovigilanceSafetyReportSerializer
    filterset_fields = ('case', 'report_type', 'status', 'generated_by', 'generated_at')
    search_fields = ('case__case_number', 'title', 'content_reference', 'indicator_summary')
    ordering = ('case__case_number', '-created_at')

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        content_reference = request.data.get('content_reference', '')
        return self._domain_action_response(
            lambda report: report.generate(user=request.user, content_reference=content_reference)
        )


# Create your views here.
