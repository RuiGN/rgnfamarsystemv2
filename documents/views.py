from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from documents.models import (
    ControlledDocument,
    DocumentApproval,
    DocumentAttachment,
    DocumentAuditTrail,
    DocumentDistribution,
    DocumentRelationship,
)
from documents.serializers import (
    ControlledDocumentSerializer,
    DocumentApprovalSerializer,
    DocumentAttachmentSerializer,
    DocumentAuditTrailSerializer,
    DocumentDistributionSerializer,
    DocumentRelationshipSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


class SingleInstanceDocumentViewSet(viewsets.ModelViewSet):
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


class ControlledDocumentViewSet(SingleInstanceDocumentViewSet):
    action_permission_map = {
        'create_revision': (
            'documents.change_controlleddocument',
            'documents.add_controlleddocument',
        ),
    }
    queryset = ControlledDocument.objects.select_related(
        'owner',
        'supersedes',
        'submitted_by',
        'reviewed_by',
        'approved_by',
        'published_by',
        'obsoleted_by',
        'cancelled_by',
        'archived_by',
    )
    serializer_class = ControlledDocumentSerializer
    filterset_fields = ('document_type', 'status', 'code', 'area', 'owner', 'supersedes')
    search_fields = ('code', 'title', 'area', 'version', 'content', 'change_summary')
    ordering = ('code', '-created_at')

    def perform_create(self, serializer):
        document = serializer.save()
        document.record_audit(
            DocumentAuditTrail.Action.CREATED,
            user=self.request.user,
            reason='Criação do documento controlado.',
        )

    @action(detail=True, methods=['post'])
    def submit_for_review(self, request, pk=None):
        return self._domain_action_response(
            lambda document: document.submit_for_review(user=request.user)
        )

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        comments = request.data.get('comments', '')
        return self._domain_action_response(
            lambda document: document.review(user=request.user, comments=comments)
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        comments = request.data.get('comments', '')
        return self._domain_action_response(
            lambda document: document.approve(user=request.user, comments=comments)
        )

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        return self._domain_action_response(lambda document: document.publish(user=request.user))

    @action(detail=True, methods=['post'])
    def obsolete(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda document: document.obsolete(reason=reason, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda document: document.cancel(reason=reason, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(
            lambda document: document.archive(reason=reason, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def create_revision(self, request, pk=None):
        document = self.get_object()
        try:
            revision = document.create_revision(
                user=request.user, change_summary=request.data.get('change_summary', '')
            )
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(revision)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DocumentAttachmentViewSet(SingleInstanceDocumentViewSet):
    queryset = DocumentAttachment.objects.select_related('document', 'uploaded_by')
    serializer_class = DocumentAttachmentSerializer
    filterset_fields = ('document', 'uploaded_by')
    search_fields = ('document__code', 'file_name', 'file_reference', 'content_hash', 'description')
    ordering = ('document__code', 'file_name')

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class DocumentRelationshipViewSet(SingleInstanceDocumentViewSet):
    queryset = DocumentRelationship.objects.select_related('source_document', 'related_document')
    serializer_class = DocumentRelationshipSerializer
    filterset_fields = ('source_document', 'related_document', 'relationship_type')
    search_fields = (
        'source_document__code',
        'related_document__code',
        'external_reference',
        'rationale',
    )
    ordering = ('source_document__code', 'relationship_type')


class DocumentApprovalViewSet(SingleInstanceDocumentViewSet):
    queryset = DocumentApproval.objects.select_related('document', 'user')
    serializer_class = DocumentApprovalSerializer
    filterset_fields = ('document', 'role', 'user', 'decision')
    search_fields = ('document__code', 'document__title', 'user__email', 'comments')
    ordering = ('document__code', 'role', 'created_at')


class DocumentDistributionViewSet(SingleInstanceDocumentViewSet):
    queryset = DocumentDistribution.objects.select_related(
        'document', 'recipient', 'distributed_by', 'confirmed_by'
    )
    serializer_class = DocumentDistributionSerializer
    filterset_fields = ('document', 'recipient', 'distributed_by', 'status', 'due_date')
    search_fields = ('document__code', 'document__title', 'recipient__email', 'confirmation_text')
    ordering = ('due_date', '-created_at')

    def perform_create(self, serializer):
        serializer.save(distributed_by=self.request.user)

    @action(detail=True, methods=['post'])
    def confirm_read(self, request, pk=None):
        confirmation_text = request.data.get('confirmation_text', '')
        return self._domain_action_response(
            lambda distribution: distribution.confirm_read(
                user=request.user, confirmation_text=confirmation_text
            )
        )


class DocumentAuditTrailViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    queryset = DocumentAuditTrail.objects.select_related('document', 'actor')
    serializer_class = DocumentAuditTrailSerializer
    filterset_fields = ('document', 'action', 'actor')
    search_fields = ('document__code', 'document__title', 'reason', 'snapshot')
    ordering = ('-created_at',)

    def get_queryset(self):
        return self.queryset.all()
