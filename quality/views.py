from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from quality.models import (
    AnalyticalSpecification,
    LaboratoryInvestigation,
    QualityAnalysis,
    QualityDocument,
    QualityResult,
    QualitySample,
)
from quality.serializers import (
    AnalyticalSpecificationSerializer,
    LaboratoryInvestigationSerializer,
    QualityAnalysisSerializer,
    QualityDocumentSerializer,
    QualityResultSerializer,
    QualitySampleSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstanceQualityViewSet(viewsets.ModelViewSet):
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


class AnalyticalSpecificationViewSet(SingleInstanceQualityViewSet):
    queryset = AnalyticalSpecification.objects.select_related(
        'product', 'stock_lot', 'unit', 'approved_by'
    )
    serializer_class = AnalyticalSpecificationSerializer
    filterset_fields = (
        'product',
        'stock_lot',
        'status',
        'method_code',
        'version',
        'effective_from',
    )
    search_fields = (
        'product__code',
        'product__description',
        'method_code',
        'method_name',
        'parameter_name',
        'acceptance_criteria',
    )
    ordering = ('product__code', 'parameter_name', 'version')

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._domain_action_response(
            lambda specification: specification.approve(user=request.user)
        )

    @action(detail=True, methods=['post'])
    def obsolete(self, request, pk=None):
        return self._domain_action_response(lambda specification: specification.obsolete())


class QualitySampleViewSet(SingleInstanceQualityViewSet):
    action_permission_map = {
        'create_analysis': ('quality.change_qualitysample', 'quality.add_qualityanalysis'),
    }
    queryset = QualitySample.objects.select_related(
        'product',
        'stock_lot',
        'specification',
        'source_purchase_receipt',
        'source_production_order',
        'customer_complaint',
        'unit',
        'collected_by',
        'received_by',
        'started_by',
        'reviewed_by',
        'approved_by',
        'rejected_by',
    )
    serializer_class = QualitySampleSerializer
    filterset_fields = ('sample_type', 'status', 'product', 'stock_lot', 'specification')
    search_fields = (
        'sample_number',
        'product__code',
        'product__description',
        'stock_lot__lot_number',
        'notes',
    )
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def collect(self, request, pk=None):
        return self._domain_action_response(lambda sample: sample.collect(user=request.user))

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        return self._domain_action_response(lambda sample: sample.receive(user=request.user))

    @action(detail=True, methods=['post'])
    def start_analysis(self, request, pk=None):
        return self._domain_action_response(lambda sample: sample.start_analysis(user=request.user))

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        return self._domain_action_response(lambda sample: sample.review(user=request.user))

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._domain_action_response(lambda sample: sample.approve(user=request.user))

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda sample: sample.reject(reason=reason, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(lambda sample: sample.cancel(reason=reason))

    @action(detail=True, methods=['post'])
    def create_analysis(self, request, pk=None):
        sample = self.get_object()
        try:
            analysis = sample.create_analysis(
                method_reference=request.data.get('method_reference', '')
            )
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        serializer = QualityAnalysisSerializer(analysis, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class QualityAnalysisViewSet(SingleInstanceQualityViewSet):
    queryset = QualityAnalysis.objects.select_related(
        'sample', 'specification', 'analyst', 'reviewer', 'approver'
    )
    serializer_class = QualityAnalysisSerializer
    filterset_fields = ('sample', 'specification', 'status', 'analyst', 'reviewer', 'approver')
    search_fields = (
        'analysis_number',
        'sample__sample_number',
        'method_reference',
        'reagent_lot',
        'standard_lot',
    )
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        return self._domain_action_response(lambda analysis: analysis.start(user=request.user))

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        return self._domain_action_response(lambda analysis: analysis.complete())

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        return self._domain_action_response(lambda analysis: analysis.review(user=request.user))

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._domain_action_response(lambda analysis: analysis.approve(user=request.user))

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda analysis: analysis.reject(reason=reason, user=request.user)
        )


class QualityResultViewSet(SingleInstanceQualityViewSet):
    queryset = QualityResult.objects.select_related(
        'analysis', 'specification', 'unit', 'recorded_by'
    )
    serializer_class = QualityResultSerializer
    filterset_fields = ('analysis', 'specification', 'result_type', 'result_status', 'unit')
    search_fields = (
        'analysis__analysis_number',
        'parameter_name',
        'text_result',
        'attachment_reference',
    )
    ordering = ('analysis__analysis_number', 'parameter_name')

    @action(detail=True, methods=['post'])
    def evaluate(self, request, pk=None):
        return self._domain_action_response(lambda result: result.evaluate())


class LaboratoryInvestigationViewSet(SingleInstanceQualityViewSet):
    queryset = LaboratoryInvestigation.objects.select_related(
        'sample',
        'analysis',
        'result',
        'opened_by',
        'concluded_by',
    )
    serializer_class = LaboratoryInvestigationSerializer
    filterset_fields = ('sample', 'analysis', 'result', 'investigation_type', 'status')
    search_fields = ('investigation_number', 'justification', 'root_cause', 'conclusion')
    ordering = ('-opened_at',)

    def perform_create(self, serializer):
        serializer.save(opened_by=self.request.user)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        return self._domain_action_response(lambda investigation: investigation.start())

    @action(detail=True, methods=['post'])
    def approve_repeat(self, request, pk=None):
        justification = request.data.get('justification', '')
        return self._domain_action_response(
            lambda investigation: investigation.approve_repeat(
                justification=justification, user=request.user
            )
        )

    @action(detail=True, methods=['post'])
    def approve_retest(self, request, pk=None):
        justification = request.data.get('justification', '')
        return self._domain_action_response(
            lambda investigation: investigation.approve_retest(
                justification=justification, user=request.user
            )
        )

    @action(detail=True, methods=['post'])
    def approve_resampling(self, request, pk=None):
        justification = request.data.get('justification', '')
        return self._domain_action_response(
            lambda investigation: investigation.approve_resampling(
                justification=justification, user=request.user
            )
        )

    @action(detail=True, methods=['post'])
    def conclude(self, request, pk=None):
        root_cause = request.data.get('root_cause', '')
        conclusion = request.data.get('conclusion', '')
        return self._domain_action_response(
            lambda investigation: investigation.conclude(
                root_cause=root_cause, conclusion=conclusion, user=request.user
            )
        )


class QualityDocumentViewSet(SingleInstanceQualityViewSet):
    queryset = QualityDocument.objects.select_related('sample', 'product', 'stock_lot', 'issued_by')
    serializer_class = QualityDocumentSerializer
    filterset_fields = ('document_type', 'status', 'sample', 'product', 'stock_lot')
    search_fields = (
        'document_number',
        'sample__sample_number',
        'product__code',
        'stock_lot__lot_number',
        'summary',
        'conclusion',
    )
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def issue(self, request, pk=None):
        return self._domain_action_response(lambda document: document.issue(user=request.user))

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(lambda document: document.cancel(reason=reason))
