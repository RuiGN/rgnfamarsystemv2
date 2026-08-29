import math
from datetime import timedelta
from re import compile as compile_pattern

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_date

from base.models import SingleInstanceModel
from base.sequences import AutoCodeMixin, IdentifierSpec, sequence_code
from base.roles import OperationalRole, user_has_operational_role


ALLOWED_FILTER_FIELDS = {
    'unit',
    'area',
    'period_start',
    'period_end',
    'product',
    'lot',
    'customer',
    'supplier',
    'status',
    'criticality',
    'responsible',
}

SYSTEM_MANAGED_TECHNICAL_FIELDS = (
    'code',
    'executor_key',
    'query_config',
    'filter_schema',
    'required_permission',
    'is_system_managed',
    'module',
    'allowed_export_formats',
)
REPORT_EXECUTION_IMMUTABLE_FIELDS = (
    ('definition_id', 'definition'),
    ('filters', 'filters'),
    ('export_format', 'export_format'),
    ('requested_by_id', 'requested_by'),
    ('schedule_id', 'schedule'),
    ('execution_number', 'execution_number'),
    ('requested_at', 'requested_at'),
)
PERMISSION_LABEL_PATTERN = compile_pattern(r'[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*')


def _is_safe_json_value(value, *, depth=0):
    if depth > 20:
        return False
    value_type = type(value)
    if value_type in {type(None), bool, int, str}:
        return True
    if value_type is float:
        return math.isfinite(value)
    if value_type is list:
        return all(_is_safe_json_value(item, depth=depth + 1) for item in value)
    if value_type is dict:
        return all(
            type(key) is str and _is_safe_json_value(item, depth=depth + 1)
            for key, item in value.items()
        )
    return False


class _UnsafeJsonValue(ValueError):
    pass


def _clone_safe_json_value(value, *, depth=0, remaining=None):
    if remaining is None:
        remaining = [10_000]
    remaining[0] -= 1
    if remaining[0] < 0 or depth > 20:
        raise _UnsafeJsonValue
    value_type = type(value)
    if value_type in {type(None), bool, int, str}:
        return value
    if value_type is float:
        if not math.isfinite(value):
            raise _UnsafeJsonValue
        return value
    if value_type is list:
        return [
            _clone_safe_json_value(item, depth=depth + 1, remaining=remaining) for item in value
        ]
    if value_type is dict:
        cloned = {}
        for key, item in value.items():
            if type(key) is not str:
                raise _UnsafeJsonValue
            cloned[key] = _clone_safe_json_value(
                item,
                depth=depth + 1,
                remaining=remaining,
            )
        return cloned
    raise _UnsafeJsonValue


def clone_safe_json_object(value):
    if type(value) is not dict:
        raise _UnsafeJsonValue
    return _clone_safe_json_value(value)


def _sequence_code(model, *args):
    if len(args) == 3:
        _legacy_scope, field_name, prefix = args
    else:
        field_name, prefix = args
    return sequence_code(model, field_name, prefix)


def _validate_filter_map(filters, required_filters=None):
    errors = {}
    if not isinstance(filters or {}, dict):
        raise ValidationError({'filters': 'Filtros devem ser um objeto chave/valor.'})
    filters = filters or {}
    unsupported = sorted(set(filters) - ALLOWED_FILTER_FIELDS)
    if unsupported:
        errors['unsupported'] = f'Filtros não suportados: {", ".join(unsupported)}.'
    missing = sorted(set(required_filters or []) - set(filters))
    if missing:
        errors['required_filters'] = f'Filtros obrigatórios ausentes: {", ".join(missing)}.'
    period_start = (
        parse_date(str(filters.get('period_start'))) if filters.get('period_start') else None
    )
    period_end = parse_date(str(filters.get('period_end'))) if filters.get('period_end') else None
    if filters.get('period_start') and period_start is None:
        errors['period_start'] = 'Informe data inicial válida.'
    if filters.get('period_end') and period_end is None:
        errors['period_end'] = 'Informe data final válida.'
    if period_start and period_end and period_end < period_start:
        errors['period_end'] = 'Data final não pode ser anterior à data inicial.'
    if errors:
        raise ValidationError(errors)


class ReportDefinition(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'RPT'

    class Module(models.TextChoices):
        PRODUCTION = 'production', 'Produção'
        MRP = 'mrp', 'MRP'
        PROCUREMENT = 'procurement', 'Compras'
        INVENTORY = 'inventory', 'Estoque'
        TRACEABILITY = 'traceability', 'Rastreabilidade'
        COSTING = 'costing', 'Custos'
        FINANCE = 'finance', 'Financeiro'
        FISCAL = 'fiscal', 'Fiscal'
        QUALITY = 'quality', 'Qualidade'
        AUDIT = 'audit', 'Auditoria'
        CAPA = 'capa', 'CAPA'
        DEVIATIONS = 'deviations', 'Desvios'
        RISKS = 'risks', 'Riscos'

    class Category(models.TextChoices):
        OPERATIONAL = 'operational', 'Operacional'
        MANAGEMENT = 'management', 'Gerencial'
        INDICATOR = 'indicator', 'Indicador'
        AUDIT = 'audit', 'Auditoria'

    code = models.CharField('código', max_length=80, blank=True)
    title = models.CharField('título', max_length=180)
    module = models.CharField('módulo', max_length=32, choices=Module.choices)
    module_ref = models.ForeignKey(
        'auxiliary.SystemModule',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='módulo normalizado',
    )
    category = models.CharField('categoria', max_length=32, choices=Category.choices)
    allowed_export_formats = models.JSONField('formatos permitidos', default=list)
    default_filters = models.JSONField('filtros padrão', default=dict, blank=True)
    required_filters = models.JSONField('filtros obrigatórios', default=list, blank=True)
    query_config = models.JSONField('configuração de consulta', default=dict, blank=True)
    executor_key = models.CharField('executor registrado', max_length=120, blank=True)
    is_system_managed = models.BooleanField('gerenciado pelo sistema', default=False)
    filter_schema = models.JSONField('esquema de filtros', default=dict, blank=True)
    required_permission = models.CharField(
        'permissão de domínio exigida', max_length=120, blank=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_report_definitions',
        null=True,
        blank=True,
        verbose_name='responsável',
    )
    is_active = models.BooleanField('ativo', default=True)
    description = models.TextField('descrição', blank=True)

    class Meta:
        ordering = ['module', 'code']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_report_definition_code'),
        ]
        indexes = [
            models.Index(fields=['module', 'category', 'is_active']),
            models.Index(fields=['owner']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'definição de relatório'
        verbose_name_plural = 'definições de relatórios'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def _persisted_system_values(self):
        if not self.pk:
            return None
        return (
            type(self)
            .objects.filter(pk=self.pk, is_system_managed=True)
            .values(*SYSTEM_MANAGED_TECHNICAL_FIELDS)
            .first()
        )

    def _validate_system_technical_types(self):
        self._invalid_system_technical_fields = frozenset()
        original = self._persisted_system_values()
        is_managed = original is not None or self.is_system_managed is True
        if not is_managed:
            return
        if type(self.module) is self.Module:
            self.module = self.module.value
        if type(self.allowed_export_formats) is list:
            self.allowed_export_formats = [
                item.value if type(item) is ReportExecution.ExportFormat else item
                for item in self.allowed_export_formats
            ]
        errors = {}
        for field_name in ('query_config', 'filter_schema'):
            value = getattr(self, field_name)
            if type(value) is not dict or not _is_safe_json_value(value):
                errors[field_name] = 'A configuração técnica deve ser um objeto JSON seguro.'
        if type(self.executor_key) is not str:
            errors['executor_key'] = 'Executor de relatório não registrado.'
        if type(self.required_permission) is not str:
            errors['required_permission'] = 'Informe uma permissão de domínio válida.'
        elif (
            self.required_permission
            and PERMISSION_LABEL_PATTERN.fullmatch(self.required_permission) is None
        ):
            errors['required_permission'] = 'Informe uma permissão de domínio válida.'
        if type(self.module) is not str:
            errors['module'] = 'Informe um módulo válido.'
        formats = self.allowed_export_formats
        if type(formats) is not list or any(type(item) is not str for item in formats):
            errors['allowed_export_formats'] = 'Informe formatos de exportação válidos.'
        if type(self.is_system_managed) is not bool:
            errors['is_system_managed'] = 'Informe um estado de gerenciamento válido.'
        if errors:
            self._invalid_system_technical_fields = frozenset(errors)
            raise ValidationError(errors)

    def clean_fields(self, exclude=None):
        self._validate_system_technical_types()
        super().clean_fields(exclude=exclude)

    def normalize_filters(self, filters=None):
        if self.is_system_managed is True:
            from reports.filtering import normalize_system_filters

            return normalize_system_filters(
                schema=self.filter_schema,
                required_filters=self.required_filters,
                default_filters=self.default_filters,
                incoming_filters=filters,
                allowed_fields=ALLOWED_FILTER_FIELDS,
                clone_json_object=clone_safe_json_object,
            )
        try:
            merged = clone_safe_json_object(self.default_filters or {})
            incoming = clone_safe_json_object({} if filters is None else filters)
        except _UnsafeJsonValue:
            raise ValidationError({'filters': 'Filtros devem ser um objeto JSON seguro.'}) from None
        merged.update(incoming)
        _validate_filter_map(merged, required_filters=self.required_filters)
        return merged

    def create_execution(self, filters=None, export_format='pdf', requested_by=None, schedule=None):
        if export_format not in (self.allowed_export_formats or []):
            raise ValidationError(
                {'export_format': 'Formato de exportação não permitido para este relatório.'}
            )
        merged_filters = self.normalize_filters(filters)
        execution = ReportExecution.objects.create(
            definition=self,
            schedule=schedule,
            filters=merged_filters,
            export_format=export_format,
            requested_by=requested_by,
            celery_task_name='reports.tasks.generate_report_execution' if schedule else '',
        )
        return execution

    def clean(self):
        super().clean()
        errors = {}
        formats = self.allowed_export_formats or []
        if not isinstance(formats, list) or not formats:
            errors['allowed_export_formats'] = 'Informe ao menos um formato de exportação.'
        elif unsupported := sorted(set(formats) - set(ReportExecution.ExportFormat.values)):
            errors['allowed_export_formats'] = f'Formatos inválidos: {", ".join(unsupported)}.'
        if not isinstance(self.required_filters or [], list):
            errors['required_filters'] = 'Filtros obrigatórios devem ser uma lista.'
        else:
            unsupported_required = sorted(set(self.required_filters) - ALLOWED_FILTER_FIELDS)
            if unsupported_required:
                errors['required_filters'] = (
                    f'Filtros obrigatórios inválidos: {", ".join(unsupported_required)}.'
                )
        try:
            _validate_filter_map(self.default_filters or {})
        except ValidationError as error:
            errors['default_filters'] = error.message_dict
        original = self._persisted_system_values()
        invalid_technical_fields = getattr(self, '_invalid_system_technical_fields', frozenset())
        if self.is_system_managed is True and 'executor_key' not in invalid_technical_fields:
            from reports.registry import get_executor

            try:
                get_executor(self.executor_key)
            except ValidationError:
                errors['executor_key'] = 'Executor de relatório não registrado.'
        if original is not None:
            for field_name in SYSTEM_MANAGED_TECHNICAL_FIELDS:
                if field_name in invalid_technical_fields:
                    continue
                if getattr(self, field_name) != original[field_name]:
                    errors[field_name] = (
                        'Campo técnico não pode ser alterado em relatório gerenciado pelo sistema.'
                    )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.code} - {self.title}'


class DashboardWorkspace(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'DASH'
    code = models.CharField('código', max_length=80, blank=True)
    title = models.CharField('título', max_length=180)
    module = models.CharField('módulo', max_length=32, choices=ReportDefinition.Module.choices)
    module_ref = models.ForeignKey(
        'auxiliary.SystemModule',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='módulo normalizado',
    )
    profile_role = models.CharField(
        'perfil', max_length=32, choices=OperationalRole.choices, blank=True
    )
    role_ref = models.ForeignKey(
        'auxiliary.OrganizationalRole',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='perfil normalizado',
    )
    layout = models.JSONField('layout', default=dict, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_dashboards',
        null=True,
        blank=True,
        verbose_name='responsável',
    )
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['module', 'code']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_dashboard_workspace_code'),
        ]
        indexes = [
            models.Index(fields=['module', 'profile_role', 'is_active']),
            models.Index(fields=['owner']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'dashboard'
        verbose_name_plural = 'dashboards'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def available_to(self, user):
        if not user or not getattr(user, 'is_authenticated', False) or not user.is_active:
            return False
        if user.is_superuser or user.pk == self.owner_id:
            return True
        return user_has_operational_role(user, self.profile_role)

    def clean(self):
        super().clean()
        errors = {}
        if not isinstance(self.layout or {}, dict):
            errors['layout'] = 'Layout deve ser um objeto JSON.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.code} - {self.title}'


class DashboardWidget(SingleInstanceModel):
    class WidgetType(models.TextChoices):
        KPI = 'kpi', 'KPI'
        CHART = 'chart', 'Gráfico'
        TABLE = 'table', 'Tabela'
        LIST = 'list', 'Lista'

    dashboard = models.ForeignKey(
        DashboardWorkspace,
        on_delete=models.CASCADE,
        related_name='widgets',
        verbose_name='dashboard',
    )
    title = models.CharField('título', max_length=160)
    widget_type = models.CharField('tipo', max_length=24, choices=WidgetType.choices)
    module = models.CharField('módulo', max_length=32, choices=ReportDefinition.Module.choices)
    module_ref = models.ForeignKey(
        'auxiliary.SystemModule',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='módulo normalizado',
    )
    report_definition = models.ForeignKey(
        ReportDefinition,
        on_delete=models.PROTECT,
        related_name='dashboard_widgets',
        null=True,
        blank=True,
        verbose_name='relatório',
    )
    position_row = models.PositiveIntegerField('linha', default=1)
    position_column = models.PositiveIntegerField('coluna', default=1)
    width = models.PositiveIntegerField('largura', default=4)
    height = models.PositiveIntegerField('altura', default=2)
    configuration = models.JSONField('configuração', default=dict, blank=True)

    class Meta:
        ordering = ['dashboard', 'position_row', 'position_column']
        indexes = [
            models.Index(fields=['dashboard', 'module']),
            models.Index(fields=['widget_type']),
            models.Index(fields=['report_definition']),
        ]
        verbose_name = 'widget de dashboard'
        verbose_name_plural = 'widgets de dashboard'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        if self.report_definition and self.report_definition.module != self.module:
            errors['report_definition'] = 'O relatório do widget deve pertencer ao mesmo módulo.'
        if self.width <= 0 or self.height <= 0:
            errors['width'] = 'Largura e altura devem ser maiores que zero.'
        if not isinstance(self.configuration or {}, dict):
            errors['configuration'] = 'Configuração deve ser um objeto JSON.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.dashboard.code} - {self.title}'


class ReportExecution(SingleInstanceModel):
    AUTOMATIC_IDENTIFIERS = (IdentifierSpec('execution_number', 'REP'),)

    class ExportFormat(models.TextChoices):
        PDF = 'pdf', 'PDF'
        XLSX = 'xlsx', 'XLSX'
        CSV = 'csv', 'CSV'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        RUNNING = 'running', 'Executando'
        COMPLETED = 'completed', 'Concluído'
        FAILED = 'failed', 'Falhou'
        CANCELLED = 'cancelled', 'Cancelado'

    execution_number = models.CharField('execução', max_length=80, blank=True)
    definition = models.ForeignKey(
        ReportDefinition,
        on_delete=models.PROTECT,
        related_name='executions',
        verbose_name='relatório',
    )
    schedule = models.ForeignKey(
        'ReportSchedule',
        on_delete=models.SET_NULL,
        related_name='executions',
        null=True,
        blank=True,
        verbose_name='agendamento',
    )
    filters = models.JSONField('filtros', default=dict, blank=True)
    export_format = models.CharField('formato', max_length=12, choices=ExportFormat.choices)
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.PENDING
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='requested_report_executions',
        null=True,
        blank=True,
        verbose_name='solicitado por',
    )
    result_file = models.ForeignKey(
        'files.ProtectedFile',
        on_delete=models.PROTECT,
        related_name='report_executions',
        null=True,
        blank=True,
        verbose_name='arquivo gerado',
    )
    requested_at = models.DateTimeField('solicitado em', default=timezone.now)
    started_at = models.DateTimeField('iniciado em', null=True, blank=True)
    completed_at = models.DateTimeField('concluído em', null=True, blank=True)
    result_reference = models.CharField('referência do arquivo', max_length=255, blank=True)
    content_hash = models.CharField('hash do conteúdo', max_length=128, blank=True)
    row_count = models.PositiveIntegerField('linhas', default=0)
    error_message = models.TextField('erro', blank=True)
    celery_task_name = models.CharField('tarefa Celery', max_length=160, blank=True)
    celery_task_id = models.CharField('id da tarefa Celery', max_length=160, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['execution_number'], name='unique_report_execution_number'
            ),
        ]
        indexes = [
            models.Index(fields=['definition', 'status']),
            models.Index(fields=['schedule']),
            models.Index(fields=['requested_by']),
            models.Index(fields=['requested_at']),
            models.Index(fields=['export_format']),
        ]
        verbose_name = 'execução de relatório'
        verbose_name_plural = 'execuções de relatórios'

    def save(self, *args, **kwargs):
        if not self.execution_number:
            self.execution_number = _sequence_code(ReportExecution, 'execution_number', 'REP')
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def _persisted_input_values(self):
        if not self.pk:
            return None
        return (
            type(self)
            .objects.filter(pk=self.pk)
            .values(*(attname for attname, _field_name in REPORT_EXECUTION_IMMUTABLE_FIELDS))
            .first()
        )

    def clean_fields(self, exclude=None):
        self._invalid_execution_input_fields = frozenset()
        try:
            clone_safe_json_object(self.filters)
        except _UnsafeJsonValue:
            self._invalid_execution_input_fields = frozenset({'filters'})
            raise ValidationError(
                {'filters': 'Filtros da execução devem ser um objeto JSON seguro.'}
            ) from None
        super().clean_fields(exclude=exclude)

    def run(self, user=None):
        from reports.services import execute_report

        return execute_report(self, user if user is not None else self.requested_by)

    def mark_failed(self, error_message):
        self.status = self.Status.FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=['status', 'completed_at', 'error_message', 'updated_at'])

    def cancel(self, user=None):
        if self.status == self.Status.COMPLETED:
            raise ValidationError({'status': 'Relatório concluído não pode ser cancelado.'})
        self.status = self.Status.CANCELLED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def notify_completion(self):
        recipients = []
        if self.schedule_id:
            recipients = list(self.schedule.recipients.all())
        if not recipients and self.requested_by:
            recipients = [self.requested_by]
        for recipient in recipients:
            notification, _created = ReportNotification.objects.get_or_create(
                execution=self,
                recipient=recipient,
                channel=ReportNotification.Channel.INTERNAL,
                defaults={
                    'message': f'Relatório {self.definition.title} concluído.',
                },
            )
            notification.send()

    def clean(self):
        super().clean()
        errors = {}
        invalid_input_fields = getattr(self, '_invalid_execution_input_fields', frozenset())
        if self.definition_id and self.export_format not in (
            self.definition.allowed_export_formats or []
        ):
            errors['export_format'] = 'Formato de exportação não permitido para este relatório.'
        try:
            if self.definition_id and 'filters' not in invalid_input_fields:
                _validate_filter_map(
                    self.filters or {}, required_filters=self.definition.required_filters
                )
        except ValidationError as error:
            errors.update(error.message_dict)
        original = self._persisted_input_values()
        if original is not None:
            for attname, field_name in REPORT_EXECUTION_IMMUTABLE_FIELDS:
                if field_name in invalid_input_fields:
                    continue
                if getattr(self, attname) != original[attname]:
                    errors[field_name] = (
                        'Dado de entrada não pode ser alterado após criar a execução.'
                    )
        if self.completed_at and self.started_at and self.completed_at < self.started_at:
            errors['completed_at'] = 'Conclusão não pode ser anterior ao início.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.execution_number


class ReportSchedule(SingleInstanceModel):
    class Frequency(models.TextChoices):
        DAILY = 'daily', 'Diário'
        WEEKLY = 'weekly', 'Semanal'
        MONTHLY = 'monthly', 'Mensal'
        CRON = 'cron', 'Cron'

    definition = models.ForeignKey(
        ReportDefinition,
        on_delete=models.PROTECT,
        related_name='schedules',
        verbose_name='relatório',
    )
    name = models.CharField('nome', max_length=160)
    frequency = models.CharField('frequência', max_length=24, choices=Frequency.choices)
    cron_expression = models.CharField('expressão cron', max_length=120, blank=True)
    filters = models.JSONField('filtros', default=dict, blank=True)
    export_format = models.CharField(
        'formato', max_length=12, choices=ReportExecution.ExportFormat.choices
    )
    next_run_at = models.DateTimeField('próxima execução')
    last_run_at = models.DateTimeField('última execução', null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_report_schedules',
        null=True,
        blank=True,
        verbose_name='responsável',
    )
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='report_schedules',
        blank=True,
        verbose_name='destinatários',
    )
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['next_run_at', 'name']
        indexes = [
            models.Index(fields=['definition', 'is_active']),
            models.Index(fields=['frequency', 'next_run_at']),
            models.Index(fields=['owner']),
        ]
        verbose_name = 'agendamento de relatório'
        verbose_name_plural = 'agendamentos de relatórios'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def trigger_now(self, user=None, run_immediately=False):
        execution = self.definition.create_execution(
            filters=self.filters,
            export_format=self.export_format,
            requested_by=user or self.owner,
            schedule=self,
        )
        if run_immediately:
            from reports.tasks import generate_report_execution

            generate_report_execution(execution.pk)
            execution.refresh_from_db()
        else:
            from reports.tasks import generate_report_execution

            result = generate_report_execution.delay(execution.pk)
            execution.celery_task_id = result.id
            execution.save(update_fields=['celery_task_id', 'updated_at'])
        return execution

    def record_run(self):
        now = timezone.now()
        self.last_run_at = now
        self.next_run_at = self._next_run_after(now)
        self.save(update_fields=['last_run_at', 'next_run_at', 'updated_at'])

    def _next_run_after(self, current):
        if self.frequency == self.Frequency.DAILY:
            return current + timedelta(days=1)
        if self.frequency == self.Frequency.WEEKLY:
            return current + timedelta(days=7)
        if self.frequency == self.Frequency.MONTHLY:
            return current + timedelta(days=30)
        return current + timedelta(days=1)

    def clean(self):
        super().clean()
        errors = {}
        if self.definition_id and self.export_format not in (
            self.definition.allowed_export_formats or []
        ):
            errors['export_format'] = 'Formato de exportação não permitido para este relatório.'
        if self.frequency == self.Frequency.CRON and not self.cron_expression:
            errors['cron_expression'] = 'Agendamento cron exige expressão cron.'
        try:
            if self.definition_id:
                self.definition.normalize_filters(self.filters)
        except ValidationError as error:
            errors.update(error.message_dict)
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name


class ReportNotification(SingleInstanceModel):
    class Channel(models.TextChoices):
        INTERNAL = 'internal', 'Interna'
        EMAIL = 'email', 'Email'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        SENT = 'sent', 'Enviada'
        FAILED = 'failed', 'Falhou'

    execution = models.ForeignKey(
        ReportExecution,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='execução',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='report_notifications',
        verbose_name='destinatário',
    )
    channel = models.CharField(
        'canal', max_length=24, choices=Channel.choices, default=Channel.INTERNAL
    )
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.PENDING
    )
    message = models.TextField('mensagem')
    sent_at = models.DateTimeField('enviada em', null=True, blank=True)
    error_message = models.TextField('erro', blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['execution', 'recipient', 'channel'],
                name='unique_report_notification_recipient',
            ),
        ]
        indexes = [
            models.Index(fields=['execution', 'status']),
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['channel']),
        ]
        verbose_name = 'notificação de relatório'
        verbose_name_plural = 'notificações de relatórios'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def send(self):
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.error_message = ''
        self.save(update_fields=['status', 'sent_at', 'error_message', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        if self.status == self.Status.SENT and not self.sent_at:
            errors['sent_at'] = 'Notificação enviada exige data de envio.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.execution.execution_number} - {self.recipient}'
