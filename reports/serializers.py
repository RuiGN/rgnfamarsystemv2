from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from base.serializer_mixins import ModelSerializerContractMixin

from reports.models import (
    DashboardWidget,
    DashboardWorkspace,
    ReportDefinition,
    ReportExecution,
    ReportNotification,
    ReportSchedule,
    clone_safe_json_object,
)


class SingleInstanceReportSerializerMixin(ModelSerializerContractMixin):
    def _validate_users_scope(self, attrs, field_name):
        return None

    def _instance_for_clean(self, attrs):
        model = self.Meta.model
        if self.instance is None:
            return model(
                **{key: value for key, value in attrs.items() if key not in {'recipients'}}
            )
        values = {}
        for field in model._meta.concrete_fields:
            if field.primary_key:
                continue
            if field.name in attrs:
                values[field.name] = attrs[field.name]
            else:
                values[field.attname] = getattr(self.instance, field.attname)
        instance = model(**values)
        instance.pk = self.instance.pk
        instance._state.adding = False
        return instance

    def _run_model_clean(self, instance):
        try:
            instance.full_clean(validate_unique=False)
        except DjangoValidationError as error:
            if hasattr(error, 'message_dict'):
                raise serializers.ValidationError(error.message_dict) from error
            raise serializers.ValidationError(error.messages) from error


class DashboardWorkspaceSerializer(
    SingleInstanceReportSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = DashboardWorkspace
        fields = '__all__'
        read_only_fields = ('id', 'owner', 'created_at', 'updated_at')

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class DashboardWidgetSerializer(SingleInstanceReportSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class ReportDefinitionSerializer(SingleInstanceReportSerializerMixin, serializers.ModelSerializer):
    SYSTEM_TECHNICAL_FIELDS = (
        'code',
        'executor_key',
        'query_config',
        'filter_schema',
        'required_permission',
        'is_system_managed',
    )

    class Meta:
        model = ReportDefinition
        fields = '__all__'
        read_only_fields = (
            'id',
            'owner',
            'executor_key',
            'filter_schema',
            'required_permission',
            'is_system_managed',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        if self.instance is not None and self.instance.is_system_managed:
            initial_data = getattr(self, 'initial_data', None)
            if not isinstance(initial_data, dict):
                raise serializers.ValidationError(
                    {'non_field_errors': 'Informe os dados como um objeto válido.'}
                )
            errors = {
                field_name: (
                    'Este campo técnico não pode ser alterado em relatório gerenciado pelo sistema.'
                )
                for field_name in self.SYSTEM_TECHNICAL_FIELDS
                if dict.__contains__(initial_data, field_name)
            }
            if errors:
                raise serializers.ValidationError(errors)
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class ReportExecutionSerializer(SingleInstanceReportSerializerMixin, serializers.ModelSerializer):
    IMMUTABLE_INPUT_FIELDS = (
        'definition',
        'filters',
        'export_format',
        'requested_by',
        'schedule',
        'execution_number',
        'requested_at',
    )

    class Meta:
        model = ReportExecution
        fields = '__all__'
        read_only_fields = (
            'id',
            'execution_number',
            'status',
            'requested_by',
            'requested_at',
            'started_at',
            'completed_at',
            'result_file',
            'result_reference',
            'content_hash',
            'row_count',
            'error_message',
            'celery_task_name',
            'celery_task_id',
            'created_at',
            'updated_at',
        )

    def to_internal_value(self, data):
        if self.instance is not None:
            if not isinstance(data, dict):
                raise serializers.ValidationError(
                    {'non_field_errors': 'Informe os dados como um objeto válido.'}
                )
            errors = {
                field_name: ('Este dado de entrada não pode ser alterado após criar a execução.')
                for field_name in self.IMMUTABLE_INPUT_FIELDS
                if dict.__contains__(data, field_name)
            }
            if errors:
                raise serializers.ValidationError(errors)
        return super().to_internal_value(data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('result_reference', None)
        if instance.status != instance.Status.COMPLETED:
            representation['result_file'] = None
            representation['content_hash'] = ''
        return representation

    def validate(self, attrs):
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class RunReportSerializer(serializers.Serializer):
    export_format = serializers.ChoiceField(choices=ReportExecution.ExportFormat.choices)
    filters = serializers.JSONField(default=dict)

    def validate(self, attrs):
        definition = self.context['definition']
        if attrs['export_format'] not in (definition.allowed_export_formats or []):
            raise serializers.ValidationError(
                {'export_format': 'Formato de exportação não permitido para este relatório.'}
            )
        try:
            filters = clone_safe_json_object(attrs.get('filters'))
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                {'filters': 'Filtros devem ser um objeto JSON seguro.'}
            ) from None
        try:
            attrs['filters'] = definition.normalize_filters(filters)
        except DjangoValidationError as error:
            details = error.message_dict if hasattr(error, 'message_dict') else error.messages
            raise serializers.ValidationError({'filters': details}) from error
        return attrs


class ReportScheduleSerializer(SingleInstanceReportSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ReportSchedule
        fields = '__all__'
        read_only_fields = ('id', 'owner', 'last_run_at', 'created_at', 'updated_at')

    def validate(self, attrs):
        self._validate_users_scope(attrs, 'recipients')
        self._run_model_clean(self._instance_for_clean(attrs))
        return attrs


class ReportNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportNotification
        fields = '__all__'
        read_only_fields = (
            'id',
            'execution',
            'recipient',
            'channel',
            'status',
            'message',
            'sent_at',
            'error_message',
            'created_at',
            'updated_at',
        )
