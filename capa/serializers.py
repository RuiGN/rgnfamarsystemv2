from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from base.serializer_mixins import ModelSerializerContractMixin

from capa.models import (
    CapaAction,
    CapaApproval,
    CapaEvidence,
    CapaNotification,
    CapaRecord,
    EffectivenessCheck,
)


class SingleInstanceCapaSerializerMixin(ModelSerializerContractMixin):
    def _instance_for_clean(self, attrs):
        model = self.Meta.model
        if self.instance is None:
            return model(**attrs)
        values = {}
        for field in model._meta.concrete_fields:
            if field.primary_key:
                continue
            values[field.name] = attrs.get(field.name, getattr(self.instance, field.name))
        instance = model(**values)
        instance.pk = self.instance.pk
        return instance

    def _run_model_clean(self, instance):
        try:
            instance.full_clean(validate_unique=False)
        except DjangoValidationError as error:
            if hasattr(error, 'message_dict'):
                raise serializers.ValidationError(error.message_dict) from error
            raise serializers.ValidationError(error.messages) from error


class CapaRecordSerializer(SingleInstanceCapaSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = CapaRecord
        fields = '__all__'
        read_only_fields = (
            'id',
            'capa_number',
            'status',
            'opened_by',
            'opened_at',
            'closed_by',
            'closed_at',
            'closure_summary',
            'cancel_reason',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('deviation_event', 'customer_complaint', 'quality_result'):
            pass
        for field_name in ('owner', 'opened_by', 'closed_by'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class CapaActionSerializer(SingleInstanceCapaSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = CapaAction
        fields = '__all__'
        read_only_fields = (
            'id',
            'status',
            'completion_notes',
            'completed_by',
            'completed_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('responsible', 'completed_by'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class CapaEvidenceSerializer(SingleInstanceCapaSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = CapaEvidence
        fields = '__all__'
        read_only_fields = ('id', 'uploaded_by', 'created_at', 'updated_at')

    def validate(self, attrs):
        for field_name in ('capa', 'action'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class EffectivenessCheckSerializer(SingleInstanceCapaSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = EffectivenessCheck
        fields = '__all__'
        read_only_fields = (
            'id',
            'status',
            'result',
            'evidence_reference',
            'verified_by',
            'verified_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class CapaApprovalSerializer(SingleInstanceCapaSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = CapaApproval
        fields = '__all__'
        read_only_fields = (
            'id',
            'decision',
            'comments',
            'decided_by',
            'decided_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('approver', 'decided_by'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class CapaNotificationSerializer(SingleInstanceCapaSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = CapaNotification
        fields = '__all__'
        read_only_fields = ('id', 'status', 'sent_at', 'created_at', 'updated_at')

    def validate(self, attrs):
        for field_name in ('capa', 'action', 'approval', 'effectiveness_check'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs
