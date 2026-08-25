from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from base.serializer_mixins import ModelSerializerContractMixin

from qa.models import (
    BatchRecordChecklistItem,
    CriticalActivityRule,
    LotRelease,
    QAReview,
    QualityBlock,
    TrainingRecord,
    TrainingRequirement,
)


class SingleInstanceQASerializerMixin(ModelSerializerContractMixin):
    immutable_update_fields: tuple[str, ...] = ()

    def to_internal_value(self, data):
        immutable_fields = [
            field_name
            for field_name in self.immutable_update_fields
            if self.instance is not None and field_name in data
        ]
        if immutable_fields:
            raise serializers.ValidationError(
                {
                    field_name: 'Campo de identidade imutável após a criação.'
                    for field_name in immutable_fields
                }
            )
        return serializers.ModelSerializer.to_internal_value(self, data)

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
        instance._state.adding = False
        instance._state.db = self.instance._state.db
        return instance

    def _run_model_clean(self, instance):
        try:
            instance.full_clean(validate_unique=False)
        except DjangoValidationError as error:
            if hasattr(error, 'message_dict'):
                raise serializers.ValidationError(error.message_dict) from error
            raise serializers.ValidationError(error.messages) from error


class QAReviewSerializer(SingleInstanceQASerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = QAReview
        fields = '__all__'
        read_only_fields = (
            'id',
            'review_number',
            'status',
            'submitted_by',
            'submitted_at',
            'approved_by',
            'approved_at',
            'rejected_by',
            'rejected_at',
            'rejection_reason',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('stock_lot', 'production_order', 'quality_document'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class BatchRecordChecklistItemSerializer(
    SingleInstanceQASerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = BatchRecordChecklistItem
        fields = '__all__'
        read_only_fields = (
            'id',
            'completed_by',
            'completed_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('review', 'responsible'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class LotReleaseSerializer(SingleInstanceQASerializerMixin, serializers.ModelSerializer):
    immutable_update_fields = LotRelease.TARGET_FIELDS

    class Meta:
        model = LotRelease
        fields = '__all__'
        read_only_fields = (
            'id',
            'release_number',
            'release_status',
            'released_by',
            'released_at',
            'rejected_by',
            'rejected_at',
            'rejection_reason',
            'blocked_by',
            'blocked_at',
            'block_reason',
            'unblocked_by',
            'unblocked_at',
            'unblock_reason',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        if (
            self.instance is not None
            and self.instance.release_status
            in {LotRelease.ReleaseStatus.RELEASED, LotRelease.ReleaseStatus.REJECTED}
            and attrs
        ):
            raise serializers.ValidationError(
                {'release_status': 'Uma disposição terminal não pode ser reescrita.'}
            )
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class QualityBlockSerializer(SingleInstanceQASerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = QualityBlock
        fields = '__all__'
        read_only_fields = (
            'id',
            'block_number',
            'status',
            'blocked_by',
            'blocked_at',
            'unblocked_by',
            'unblocked_at',
            'unblock_reason',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('product', 'stock_lot', 'supplier', 'quality_document'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class TrainingRequirementSerializer(SingleInstanceQASerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = TrainingRequirement
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class TrainingRecordSerializer(SingleInstanceQASerializerMixin, serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = TrainingRecord
        fields = '__all__'
        read_only_fields = (
            'id',
            'status',
            'completed_at',
            'valid_until',
            'is_valid',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('requirement', 'user', 'trainer'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class CriticalActivityRuleSerializer(SingleInstanceQASerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = CriticalActivityRule
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs
