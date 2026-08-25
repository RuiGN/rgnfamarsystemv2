from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from base.serializer_mixins import ModelSerializerContractMixin

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


class SingleInstanceRegulatorySerializerMixin(ModelSerializerContractMixin):
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


class RegulatoryProductSerializer(
    SingleInstanceRegulatorySerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = RegulatoryProduct
        fields = '__all__'
        read_only_fields = ('id', 'regulatory_code', 'status', 'created_at', 'updated_at')

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class RegulatoryDossierSerializer(
    SingleInstanceRegulatorySerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = RegulatoryDossier
        fields = '__all__'
        read_only_fields = (
            'id',
            'dossier_number',
            'status',
            'submitted_by',
            'submitted_at',
            'closed_by',
            'closed_at',
            'closure_summary',
            'cancel_reason',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('responsible', 'submitted_by', 'closed_by'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class RegulatoryRegistrationSerializer(
    SingleInstanceRegulatorySerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = RegulatoryRegistration
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        for field_name in ('regulatory_product', 'dossier'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class RegulatoryPetitionSerializer(
    SingleInstanceRegulatorySerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = RegulatoryPetition
        fields = '__all__'
        read_only_fields = (
            'id',
            'petition_number',
            'status',
            'protocol_number',
            'submitted_by',
            'submitted_at',
            'response_summary',
            'responded_by',
            'responded_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('responsible', 'submitted_by', 'responded_by'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class RegulatoryRequirementSerializer(
    SingleInstanceRegulatorySerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = RegulatoryRequirement
        fields = '__all__'
        read_only_fields = (
            'id',
            'requirement_number',
            'status',
            'response_summary',
            'evidence_reference',
            'content_hash',
            'answered_by',
            'answered_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('dossier', 'petition'):
            pass
        for field_name in ('responsible', 'answered_by'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class RegulatoryCommitmentSerializer(
    SingleInstanceRegulatorySerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = RegulatoryCommitment
        fields = '__all__'
        read_only_fields = (
            'id',
            'commitment_number',
            'status',
            'completion_summary',
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


class RegulatoryEvidenceSerializer(
    SingleInstanceRegulatorySerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = RegulatoryEvidence
        fields = '__all__'
        read_only_fields = ('id', 'uploaded_by', 'created_at', 'updated_at')

    def validate(self, attrs):
        for field_name in ('dossier', 'petition', 'requirement', 'commitment'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class RegulatoryLinkSerializer(
    SingleInstanceRegulatorySerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = RegulatoryLink
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        for field_name in (
            'dossier',
            'product',
            'stock_lot',
            'document',
            'change_control',
            'deviation_event',
            'capa',
            'partner',
        ):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class RegulatoryReportSerializer(
    SingleInstanceRegulatorySerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = RegulatoryReport
        fields = '__all__'
        read_only_fields = (
            'id',
            'status',
            'content_reference',
            'total_requirements',
            'open_commitments',
            'evidence_count',
            'generated_by',
            'generated_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class RegulatoryAlertSerializer(
    SingleInstanceRegulatorySerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = RegulatoryAlert
        fields = '__all__'
        read_only_fields = (
            'id',
            'status',
            'acknowledged_by',
            'acknowledged_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in (
            'regulatory_product',
            'dossier',
            'registration',
            'petition',
            'requirement',
            'commitment',
        ):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs
