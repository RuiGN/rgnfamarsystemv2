from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from base.serializer_mixins import ModelSerializerContractMixin

from maintenance.models import (
    EquipmentAsset,
    EquipmentDowntime,
    EquipmentUsageLog,
    MaintenanceMetricReport,
    MaintenanceOrder,
    MaintenancePlan,
)


class SingleInstanceMaintenanceSerializerMixin(ModelSerializerContractMixin):
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


class EquipmentAssetSerializer(
    SingleInstanceMaintenanceSerializerMixin, serializers.ModelSerializer
):
    is_available_for_use = serializers.BooleanField(read_only=True)

    class Meta:
        model = EquipmentAsset
        fields = '__all__'
        read_only_fields = (
            'id',
            'blocked_by',
            'blocked_at',
            'released_by',
            'released_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('responsible', 'blocked_by', 'released_by'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class MaintenancePlanSerializer(
    SingleInstanceMaintenanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = MaintenancePlan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        if self.instance is None and 'active' not in self.initial_data:
            attrs['active'] = True
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class MaintenanceOrderSerializer(
    SingleInstanceMaintenanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = MaintenanceOrder
        fields = '__all__'
        read_only_fields = (
            'id',
            'order_number',
            'status',
            'opened_by',
            'started_by',
            'started_at',
            'completed_by',
            'completed_at',
            'completion_summary',
            'evidence_reference',
            'content_hash',
            'cancelled_by',
            'cancelled_at',
            'cancel_reason',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        for field_name in ('asset', 'plan', 'source_lot'):
            pass
        for field_name in (
            'responsible',
            'opened_by',
            'started_by',
            'completed_by',
            'cancelled_by',
        ):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class EquipmentDowntimeSerializer(
    SingleInstanceMaintenanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = EquipmentDowntime
        fields = '__all__'
        read_only_fields = ('id', 'duration_hours', 'created_at', 'updated_at')

    def validate(self, attrs):
        for field_name in ('asset', 'order'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class EquipmentUsageLogSerializer(
    SingleInstanceMaintenanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = EquipmentUsageLog
        fields = '__all__'
        read_only_fields = ('id', 'logged_by', 'created_at', 'updated_at')

    def validate(self, attrs):
        for field_name in ('asset', 'source_lot'):
            pass
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class MaintenanceMetricReportSerializer(
    SingleInstanceMaintenanceSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = MaintenanceMetricReport
        fields = '__all__'
        read_only_fields = (
            'id',
            'status',
            'availability_rate',
            'downtime_hours',
            'mtbf_hours',
            'mttr_hours',
            'overdue_orders',
            'due_soon_orders',
            'content_reference',
            'generated_by',
            'generated_at',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs
