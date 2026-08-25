from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from base.serializer_mixins import ModelSerializerContractMixin

from pharmacovigilance.models import (
    PharmacovigilanceAction,
    PharmacovigilanceCase,
    PharmacovigilanceCausalityAssessment,
    PharmacovigilanceClassification,
    PharmacovigilanceInvestigation,
    PharmacovigilanceLink,
    PharmacovigilanceSafetyReport,
)


class SingleInstancePharmacovigilanceSerializerMixin(ModelSerializerContractMixin):
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


class PharmacovigilanceCaseSerializer(
    SingleInstancePharmacovigilanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PharmacovigilanceCase
        fields = '__all__'
        read_only_fields = (
            'id',
            'case_number',
            'status',
            'reported_by',
            'triaged_by',
            'triaged_at',
            'investigation_started_by',
            'investigation_started_at',
            'closed_by',
            'closed_at',
            'closure_summary',
            'cancel_reason',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('product', 'stock_lot', 'customer'):
            pass
        for field_name in (
            'responsible',
            'reported_by',
            'triaged_by',
            'investigation_started_by',
            'closed_by',
        ):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class PharmacovigilanceClassificationSerializer(
    SingleInstancePharmacovigilanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PharmacovigilanceClassification
        fields = '__all__'
        read_only_fields = (
            'id',
            'classified_by',
            'classified_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class PharmacovigilanceCausalityAssessmentSerializer(
    SingleInstancePharmacovigilanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PharmacovigilanceCausalityAssessment
        fields = '__all__'
        read_only_fields = (
            'id',
            'assessed_by',
            'assessed_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class PharmacovigilanceInvestigationSerializer(
    SingleInstancePharmacovigilanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PharmacovigilanceInvestigation
        fields = '__all__'
        read_only_fields = (
            'id',
            'status',
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


class PharmacovigilanceActionSerializer(
    SingleInstancePharmacovigilanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PharmacovigilanceAction
        fields = '__all__'
        read_only_fields = (
            'id',
            'action_number',
            'status',
            'completion_notes',
            'evidence_reference',
            'content_hash',
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


class PharmacovigilanceLinkSerializer(
    SingleInstancePharmacovigilanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PharmacovigilanceLink
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        for field_name in (
            'case',
            'customer_complaint',
            'deviation_event',
            'capa',
            'stock_lot',
            'customer',
            'product',
            'regulatory_dossier',
            'document',
        ):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class PharmacovigilanceSafetyReportSerializer(
    SingleInstancePharmacovigilanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PharmacovigilanceSafetyReport
        fields = '__all__'
        read_only_fields = (
            'id',
            'status',
            'content_reference',
            'case_count',
            'serious_cases',
            'recurrence_count',
            'indicator_summary',
            'generated_by',
            'generated_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs
