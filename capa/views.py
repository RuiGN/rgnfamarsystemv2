from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from capa.models import (
    CapaAction,
    CapaApproval,
    CapaEvidence,
    CapaNotification,
    CapaRecord,
    EffectivenessCheck,
)
from capa.serializers import (
    CapaActionSerializer,
    CapaApprovalSerializer,
    CapaEvidenceSerializer,
    CapaNotificationSerializer,
    CapaRecordSerializer,
    EffectivenessCheckSerializer,
)
from base.permissions import SingleInstanceDjangoModelPermissions


def _validation_payload(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


def _parse_boolean(value):
    if isinstance(value, bool):
        return value
    if value in (None, ''):
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', '1', 'yes', 'sim', 'on'}:
            return True
        if normalized in {'false', '0', 'no', 'nao', 'não', 'off'}:
            return False
    raise DjangoValidationError({'effective': 'Informe um valor booleano válido.'})


class SingleInstanceCapaViewSet(viewsets.ModelViewSet):
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


class CapaRecordViewSet(SingleInstanceCapaViewSet):
    action_permission_map = {
        'generate_notifications': (
            'capa.change_caparecord',
            'capa.add_capanotification',
        ),
    }
    queryset = CapaRecord.objects.select_related(
        'deviation_event',
        'customer_complaint',
        'quality_result',
        'owner',
        'opened_by',
        'closed_by',
    )
    serializer_class = CapaRecordSerializer
    filterset_fields = (
        'source_type',
        'status',
        'owner',
        'deviation_event',
        'customer_complaint',
        'quality_result',
        'due_date',
    )
    search_fields = (
        'capa_number',
        'title',
        'root_cause',
        'action_plan',
        'source_reference',
        'closure_summary',
    )
    ordering = ('-created_at',)

    def perform_create(self, serializer):
        serializer.save(opened_by=self.request.user)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        return self._domain_action_response(lambda capa: capa.submit(user=request.user))

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        return self._domain_action_response(lambda capa: capa.start(user=request.user))

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        summary = request.data.get('summary', '')
        return self._domain_action_response(
            lambda capa: capa.close(summary=summary, user=request.user)
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', '')
        return self._domain_action_response(lambda capa: capa.cancel(reason=reason))

    @action(detail=True, methods=['post'])
    def generate_notifications(self, request, pk=None):
        capa = self.get_object()
        notifications = capa.generate_notifications()
        serializer = CapaNotificationSerializer(
            notifications, many=True, context=self.get_serializer_context()
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CapaActionViewSet(SingleInstanceCapaViewSet):
    queryset = CapaAction.objects.select_related('capa', 'responsible', 'completed_by')
    serializer_class = CapaActionSerializer
    filterset_fields = ('capa', 'action_type', 'status', 'responsible', 'due_date')
    search_fields = ('capa__capa_number', 'title', 'description', 'completion_notes')
    ordering = ('capa__capa_number', 'due_date')

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        return self._domain_action_response(lambda action: action.start())

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        completion_notes = request.data.get('completion_notes', '')
        return self._domain_action_response(
            lambda action: action.complete(user=request.user, completion_notes=completion_notes)
        )


class CapaEvidenceViewSet(SingleInstanceCapaViewSet):
    queryset = CapaEvidence.objects.select_related('capa', 'action', 'uploaded_by')
    serializer_class = CapaEvidenceSerializer
    filterset_fields = ('capa', 'action', 'uploaded_by')
    search_fields = ('capa__capa_number', 'title', 'file_reference', 'content_hash', 'notes')
    ordering = ('capa__capa_number', 'title')

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class EffectivenessCheckViewSet(SingleInstanceCapaViewSet):
    queryset = EffectivenessCheck.objects.select_related('capa', 'verified_by')
    serializer_class = EffectivenessCheckSerializer
    filterset_fields = ('capa', 'status', 'planned_date', 'verified_by')
    search_fields = ('capa__capa_number', 'criteria', 'result', 'evidence_reference')
    ordering = ('planned_date',)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        result = request.data.get('result', '')
        evidence_reference = request.data.get('evidence_reference', '')
        try:
            effective = _parse_boolean(request.data.get('effective', False))
        except DjangoValidationError as error:
            return Response(_validation_payload(error), status=status.HTTP_400_BAD_REQUEST)
        return self._domain_action_response(
            lambda check: check.verify(
                result=result,
                effective=effective,
                user=request.user,
                evidence_reference=evidence_reference,
            )
        )


class CapaApprovalViewSet(SingleInstanceCapaViewSet):
    queryset = CapaApproval.objects.select_related('capa', 'approver', 'decided_by')
    serializer_class = CapaApprovalSerializer
    filterset_fields = ('capa', 'role', 'approver', 'required', 'decision')
    search_fields = ('capa__capa_number', 'approver__email', 'comments')
    ordering = ('capa__capa_number', 'role')

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


class CapaNotificationViewSet(SingleInstanceCapaViewSet):
    queryset = CapaNotification.objects.select_related(
        'capa', 'action', 'approval', 'effectiveness_check', 'recipient'
    )
    serializer_class = CapaNotificationSerializer
    filterset_fields = ('capa', 'notification_type', 'recipient', 'status', 'due_date')
    search_fields = ('capa__capa_number', 'message')
    ordering = ('due_date', 'notification_type')

    @action(detail=True, methods=['post'])
    def mark_sent(self, request, pk=None):
        return self._domain_action_response(lambda notification: notification.mark_sent())
