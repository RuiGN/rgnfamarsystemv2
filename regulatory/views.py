from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from regulatory.models import (
    RegulatoryAlert,
    RegulatoryCommitment,
    RegulatoryDossier,
    RegulatoryEvidence,
    RegulatoryLink,
    RegulatoryPetition,
    RegulatoryProduct,
    RegulatoryRegistration,
    RegulatoryReport,
    RegulatoryRequirement,
)
from regulatory.serializers import (
    RegulatoryAlertSerializer,
    RegulatoryCommitmentSerializer,
    RegulatoryDossierSerializer,
    RegulatoryEvidenceSerializer,
    RegulatoryLinkSerializer,
    RegulatoryPetitionSerializer,
    RegulatoryProductSerializer,
    RegulatoryRegistrationSerializer,
    RegulatoryReportSerializer,
    RegulatoryRequirementSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstanceRegulatoryViewSet(viewsets.ModelViewSet):
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


class RegulatoryProductViewSet(SingleInstanceRegulatoryViewSet):
    queryset = RegulatoryProduct.objects.select_related('product', 'responsible')
    serializer_class = RegulatoryProductSerializer
    filterset_fields = ('product', 'status', 'responsible', 'dosage_form', 'route')
    search_fields = (
        'regulatory_code',
        'presentation',
        'registration_holder',
        'therapeutic_class',
        'strength',
    )
    ordering = ('regulatory_code',)


class RegulatoryDossierViewSet(SingleInstanceRegulatoryViewSet):
    queryset = RegulatoryDossier.objects.select_related(
        'regulatory_product', 'responsible', 'submitted_by', 'closed_by'
    )
    serializer_class = RegulatoryDossierSerializer
    filterset_fields = (
        'regulatory_product',
        'dossier_type',
        'status',
        'responsible',
        'authority',
        'due_date',
    )
    search_fields = ('dossier_number', 'title', 'authority', 'subject')
    ordering = ('-created_at',)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        return self._domain_action_response(lambda dossier: dossier.submit(user=request.user))

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        summary = request.data.get('summary', '')
        return self._domain_action_response(
            lambda dossier: dossier.close(summary=summary, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(lambda dossier: dossier.cancel(reason=reason))


class RegulatoryRegistrationViewSet(SingleInstanceRegulatoryViewSet):
    queryset = RegulatoryRegistration.objects.select_related(
        'regulatory_product', 'dossier', 'responsible'
    )
    serializer_class = RegulatoryRegistrationSerializer
    filterset_fields = (
        'regulatory_product',
        'dossier',
        'status',
        'responsible',
        'valid_until',
        'next_renewal_due_date',
    )
    search_fields = ('registration_number', 'regulatory_product__presentation')
    ordering = ('registration_number',)


class RegulatoryPetitionViewSet(SingleInstanceRegulatoryViewSet):
    queryset = RegulatoryPetition.objects.select_related(
        'dossier', 'responsible', 'submitted_by', 'responded_by'
    )
    serializer_class = RegulatoryPetitionSerializer
    filterset_fields = ('dossier', 'petition_type', 'status', 'responsible', 'response_due_date')
    search_fields = ('petition_number', 'protocol_number', 'subject', 'response_summary')
    ordering = ('dossier__dossier_number', '-created_at')

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        protocol_number = request.data.get('protocol_number', '')
        return self._domain_action_response(
            lambda petition: petition.submit(protocol_number=protocol_number, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def record_response(self, request, pk=None):
        response_summary = request.data.get('response_summary', '')
        return self._domain_action_response(
            lambda petition: petition.record_response(
                response_summary=response_summary, user=request.user
            )
        )


class RegulatoryRequirementViewSet(SingleInstanceRegulatoryViewSet):
    queryset = RegulatoryRequirement.objects.select_related(
        'dossier', 'petition', 'responsible', 'answered_by'
    )
    serializer_class = RegulatoryRequirementSerializer
    filterset_fields = ('dossier', 'petition', 'status', 'responsible', 'response_due_date')
    search_fields = (
        'requirement_number',
        'description',
        'response_summary',
        'evidence_reference',
        'content_hash',
    )
    ordering = ('dossier__dossier_number', 'response_due_date')

    @action(detail=True, methods=['post'])
    def answer(self, request, pk=None):
        response_summary = request.data.get('response_summary', '')
        evidence_reference = request.data.get('evidence_reference', '')
        content_hash = request.data.get('content_hash', '')
        return self._domain_action_response(
            lambda requirement: requirement.answer(
                response_summary=response_summary,
                evidence_reference=evidence_reference,
                content_hash=content_hash,
                user=request.user,
            )
        )


class RegulatoryCommitmentViewSet(SingleInstanceRegulatoryViewSet):
    queryset = RegulatoryCommitment.objects.select_related('dossier', 'responsible', 'completed_by')
    serializer_class = RegulatoryCommitmentSerializer
    filterset_fields = ('dossier', 'status', 'responsible', 'due_date')
    search_fields = (
        'commitment_number',
        'description',
        'completion_summary',
        'evidence_reference',
        'content_hash',
    )
    ordering = ('dossier__dossier_number', 'due_date')

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        completion_summary = request.data.get('completion_summary', '')
        evidence_reference = request.data.get('evidence_reference', '')
        content_hash = request.data.get('content_hash', '')
        return self._domain_action_response(
            lambda commitment: commitment.complete(
                completion_summary=completion_summary,
                evidence_reference=evidence_reference,
                content_hash=content_hash,
                user=request.user,
            )
        )


class RegulatoryEvidenceViewSet(SingleInstanceRegulatoryViewSet):
    queryset = RegulatoryEvidence.objects.select_related(
        'dossier', 'petition', 'requirement', 'commitment', 'uploaded_by'
    )
    serializer_class = RegulatoryEvidenceSerializer
    filterset_fields = ('dossier', 'petition', 'requirement', 'commitment', 'uploaded_by')
    search_fields = ('dossier__dossier_number', 'title', 'file_reference', 'content_hash', 'notes')
    ordering = ('dossier__dossier_number', 'title')

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class RegulatoryLinkViewSet(SingleInstanceRegulatoryViewSet):
    queryset = RegulatoryLink.objects.select_related(
        'dossier',
        'product',
        'stock_lot',
        'document',
        'change_control',
        'deviation_event',
        'capa',
        'partner',
    )
    serializer_class = RegulatoryLinkSerializer
    filterset_fields = (
        'dossier',
        'link_type',
        'product',
        'stock_lot',
        'document',
        'change_control',
        'deviation_event',
        'capa',
        'partner',
    )
    search_fields = ('dossier__dossier_number', 'reference_code', 'description')
    ordering = ('dossier__dossier_number', 'link_type')


class RegulatoryReportViewSet(SingleInstanceRegulatoryViewSet):
    queryset = RegulatoryReport.objects.select_related('dossier', 'generated_by')
    serializer_class = RegulatoryReportSerializer
    filterset_fields = ('dossier', 'report_type', 'status', 'generated_by', 'generated_at')
    search_fields = ('dossier__dossier_number', 'title', 'content_reference')
    ordering = ('dossier__dossier_number', '-created_at')

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        content_reference = request.data.get('content_reference', '')
        return self._domain_action_response(
            lambda report: report.generate(user=request.user, content_reference=content_reference)
        )


class RegulatoryAlertViewSet(SingleInstanceRegulatoryViewSet):
    queryset = RegulatoryAlert.objects.select_related(
        'regulatory_product',
        'dossier',
        'registration',
        'petition',
        'requirement',
        'commitment',
        'acknowledged_by',
    )
    serializer_class = RegulatoryAlertSerializer
    filterset_fields = (
        'regulatory_product',
        'dossier',
        'registration',
        'petition',
        'requirement',
        'commitment',
        'alert_type',
        'severity',
        'status',
        'due_date',
    )
    search_fields = ('message', 'dossier__dossier_number')
    ordering = ('-created_at',)

    @action(detail=False, methods=['post'])
    def generate(self, request):
        generated = RegulatoryAlert.generate_all()
        return Response({'generated': generated})

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        return self._domain_action_response(lambda alert: alert.acknowledge(user=request.user))
