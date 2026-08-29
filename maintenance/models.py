from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from base.models import SingleInstanceModel
from base.sequences import IdentifierSpec, sequence_code


HOURS_SCALE = Decimal('0.01')
QUANTITY_SCALE = Decimal('0.0001')
PERCENT_SCALE = Decimal('0.01')
ZERO_HOURS = Decimal('0.00')
ZERO_QUANTITY = Decimal('0.0000')
ZERO_PERCENT = Decimal('0.00')


def _decimal(value, scale, message):
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(message) from exc
    return amount.quantize(scale, rounding=ROUND_HALF_UP)


def _hours(value):
    return _decimal(value, HOURS_SCALE, 'Informe uma quantidade de horas válida.')


def _quantity(value):
    return _decimal(value, QUANTITY_SCALE, 'Informe uma quantidade válida.')


def _percent(value):
    return _decimal(value, PERCENT_SCALE, 'Informe um percentual válido.')


def _sequence_code(model, *args):
    if len(args) == 3:
        _legacy_scope, field_name, prefix = args
    else:
        field_name, prefix = args
    return sequence_code(model, field_name, prefix)


class EquipmentAsset(SingleInstanceModel):
    AUTOMATIC_IDENTIFIERS = (IdentifierSpec('asset_code', 'EQP'),)

    class AssetType(models.TextChoices):
        EQUIPMENT = 'equipment', 'Equipamento'
        INSTRUMENT = 'instrument', 'Instrumento'
        PRODUCTION_LINE = 'production_line', 'Linha'
        ROOM = 'room', 'Sala'
        UTILITY = 'utility', 'Utilidade'
        CRITICAL_COMPONENT = 'critical_component', 'Componente crítico'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        AVAILABLE = 'available', 'Disponível'
        UNDER_MAINTENANCE = 'under_maintenance', 'Em manutenção'
        UNDER_CALIBRATION = 'under_calibration', 'Em calibração'
        CLEANING = 'cleaning', 'Em limpeza'
        SANITIZATION = 'sanitization', 'Em sanitização'
        BLOCKED = 'blocked', 'Interditado'
        DECOMMISSIONED = 'decommissioned', 'Desativado'

    class QualificationStatus(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        QUALIFIED = 'qualified', 'Qualificado'
        EXPIRED = 'expired', 'Vencido'
        NOT_REQUIRED = 'not_required', 'Não aplicável'

    class CalibrationStatus(models.TextChoices):
        NOT_REQUIRED = 'not_required', 'Não aplicável'
        VALID = 'valid', 'Válida'
        DUE = 'due', 'A vencer'
        EXPIRED = 'expired', 'Vencida'

    asset_code = models.CharField('código do ativo', max_length=80, blank=True)
    name = models.CharField('nome', max_length=180)
    asset_type = models.CharField('tipo', max_length=32, choices=AssetType.choices)
    area = models.CharField('área', max_length=120, blank=True)
    area_ref = models.ForeignKey(
        'auxiliary.BusinessArea',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='área normalizada',
    )
    location = models.CharField('localização', max_length=160, blank=True)
    site = models.ForeignKey(
        'masters.Site',
        on_delete=models.PROTECT,
        related_name='equipment_assets',
        null=True,
        blank=True,
        verbose_name='unidade/planta',
    )
    manufacturer = models.CharField('fabricante', max_length=120, blank=True)
    model = models.CharField('modelo', max_length=120, blank=True)
    serial_number = models.CharField('número de série', max_length=120, blank=True)
    is_critical = models.BooleanField('crítico', default=False)
    status = models.CharField('status', max_length=32, choices=Status.choices, default=Status.DRAFT)
    qualification_status = models.CharField(
        'status de qualificação',
        max_length=24,
        choices=QualificationStatus.choices,
        default=QualificationStatus.PENDING,
    )
    qualification_valid_until = models.DateField('qualificação válida até', null=True, blank=True)
    calibration_required = models.BooleanField('exige calibração', default=False)
    calibration_status = models.CharField(
        'status de calibração',
        max_length=24,
        choices=CalibrationStatus.choices,
        default=CalibrationStatus.NOT_REQUIRED,
    )
    calibration_valid_until = models.DateField('calibração válida até', null=True, blank=True)
    cleaning_required = models.BooleanField('exige limpeza', default=False)
    sanitization_required = models.BooleanField('exige sanitização', default=False)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_assets',
        verbose_name='responsável',
    )
    blocked_reason = models.TextField('motivo de interdição', blank=True)
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='blocked_assets',
        null=True,
        blank=True,
        verbose_name='interditado por',
    )
    blocked_at = models.DateTimeField('interditado em', null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='released_assets',
        null=True,
        blank=True,
        verbose_name='liberado por',
    )
    released_at = models.DateTimeField('liberado em', null=True, blank=True)

    class Meta:
        ordering = ['asset_code', 'name']
        constraints = [
            models.UniqueConstraint(fields=['asset_code'], name='unique_equipment_asset_code'),
        ]
        indexes = [
            models.Index(fields=['asset_type', 'status']),
            models.Index(fields=['qualification_status']),
            models.Index(fields=['calibration_status']),
            models.Index(fields=['calibration_valid_until']),
            models.Index(fields=['qualification_valid_until']),
            models.Index(fields=['responsible']),
            models.Index(fields=['asset_code']),
        ]
        verbose_name = 'equipamento ou ativo crítico'
        verbose_name_plural = 'equipamentos e ativos críticos'

    @property
    def qualification_is_valid(self):
        if self.qualification_status == self.QualificationStatus.NOT_REQUIRED:
            return True
        if self.qualification_status != self.QualificationStatus.QUALIFIED:
            return False
        if self.qualification_valid_until and self.qualification_valid_until < timezone.localdate():
            return False
        return True

    @property
    def calibration_is_valid(self):
        if not self.calibration_required:
            return True
        if self.calibration_status != self.CalibrationStatus.VALID:
            return False
        if self.calibration_valid_until and self.calibration_valid_until < timezone.localdate():
            return False
        return True

    @property
    def is_available_for_use(self):
        return (
            self.status == self.Status.AVAILABLE
            and self.qualification_is_valid
            and self.calibration_is_valid
        )

    def save(self, *args, **kwargs):
        if not self.asset_code:
            self.asset_code = _sequence_code(EquipmentAsset, 'asset_code', 'EQP')
        if not self.calibration_required:
            self.calibration_status = self.CalibrationStatus.NOT_REQUIRED
            self.calibration_valid_until = None
        super().save(*args, **kwargs)

    def block(self, reason, user=None):
        if not reason:
            raise ValidationError({'blocked_reason': 'Informe o motivo da interdição.'})
        if self.status == self.Status.DECOMMISSIONED:
            raise ValidationError({'status': 'Ativo desativado não pode ser interditado.'})
        self.status = self.Status.BLOCKED
        self.blocked_reason = reason
        self.blocked_by = user
        self.blocked_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=['status', 'blocked_reason', 'blocked_by', 'blocked_at', 'updated_at']
        )

    def release(self, user=None):
        errors = {}
        if self.status == self.Status.DECOMMISSIONED:
            errors['status'] = 'Ativo desativado não pode ser liberado.'
        if not self.qualification_is_valid:
            errors['qualification_status'] = (
                'Equipamento sem qualificação válida não pode ser liberado para uso.'
            )
        if not self.calibration_is_valid:
            errors['calibration_status'] = (
                'Equipamento com calibração vencida, pendente ou inválida não pode ser liberado para uso.'
            )
        if errors:
            raise ValidationError(errors)
        self.status = self.Status.AVAILABLE
        self.released_by = user
        self.released_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'released_by', 'released_at', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.calibration_required
            and self.calibration_status == self.CalibrationStatus.NOT_REQUIRED
        ):
            errors['calibration_status'] = (
                'Equipamento que exige calibração deve possuir status de calibração controlado.'
            )
        if (
            not self.calibration_required
            and self.calibration_status != self.CalibrationStatus.NOT_REQUIRED
        ):
            errors['calibration_status'] = (
                'Equipamento sem exigência de calibração deve usar status não aplicável.'
            )
        if (
            self.qualification_status == self.QualificationStatus.NOT_REQUIRED
            and self.qualification_valid_until
        ):
            errors['qualification_valid_until'] = (
                'Qualificação não aplicável não deve possuir validade.'
            )
        if self.status == self.Status.BLOCKED and not self.blocked_reason:
            errors['blocked_reason'] = 'Interdição exige motivo documentado.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.asset_code} - {self.name}'


class MaintenancePlan(SingleInstanceModel):
    class PlanType(models.TextChoices):
        PREVENTIVE_MAINTENANCE = 'preventive_maintenance', 'Manutenção preventiva'
        CORRECTIVE_MAINTENANCE = 'corrective_maintenance', 'Manutenção corretiva'
        CALIBRATION = 'calibration', 'Calibração'
        QUALIFICATION = 'qualification', 'Qualificação'
        CLEANING = 'cleaning', 'Limpeza'
        SANITIZATION = 'sanitization', 'Sanitização'

    class TriggerType(models.TextChoices):
        TIME = 'time', 'Tempo'
        USAGE = 'usage', 'Uso'
        EVENT = 'event', 'Evento'
        LOT = 'lot', 'Lote'
        RULE = 'rule', 'Regra configurável'

    asset = models.ForeignKey(
        EquipmentAsset,
        on_delete=models.PROTECT,
        related_name='maintenance_plans',
        verbose_name='ativo',
    )
    plan_type = models.CharField('tipo de plano', max_length=32, choices=PlanType.choices)
    trigger_type = models.CharField('gatilho', max_length=24, choices=TriggerType.choices)
    interval_days = models.PositiveIntegerField('intervalo em dias', null=True, blank=True)
    usage_limit = models.DecimalField(
        'limite de uso', max_digits=14, decimal_places=4, null=True, blank=True
    )
    usage_unit = models.CharField('unidade de uso', max_length=40, blank=True)
    event_name = models.CharField('evento', max_length=120, blank=True)
    lot_rule = models.CharField('regra por lote', max_length=160, blank=True)
    rule_expression = models.TextField('regra configurável', blank=True)
    next_due_date = models.DateField('próximo vencimento', null=True, blank=True)
    description = models.TextField('descrição')
    active = models.BooleanField('ativo', default=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_maintenance_plans',
        verbose_name='responsável',
    )

    class Meta:
        ordering = ['asset__asset_code', 'plan_type', 'next_due_date']
        indexes = [
            models.Index(fields=['asset', 'active']),
            models.Index(fields=['plan_type', 'trigger_type']),
            models.Index(fields=['next_due_date']),
            models.Index(fields=['responsible']),
        ]
        verbose_name = 'plano de manutenção e calibração'
        verbose_name_plural = 'planos de manutenção e calibração'

    def generate_order(self, triggered_by=None, due_date=None, source_lot=None):
        if not self.active:
            raise ValidationError({'active': 'Plano inativo não pode gerar ordem.'})
        if False:
            raise ValidationError(
                {'source_lot': 'O lote relacionado é incompatível com o registro.'}
            )
        with transaction.atomic():
            order = MaintenanceOrder(
                asset=self.asset,
                plan=self,
                order_type=self.plan_type,
                trigger_type=self.trigger_type,
                source_lot=source_lot,
                due_date=due_date or self.next_due_date or timezone.localdate(),
                description=self.description,
                responsible=self.responsible,
                opened_by=triggered_by,
            )
            order.full_clean()
            order.save()
            return order

    def clean(self):
        super().clean()
        errors = {}
        if self.trigger_type == self.TriggerType.TIME and not (
            self.interval_days or self.next_due_date
        ):
            errors['next_due_date'] = 'Plano por tempo exige intervalo ou próximo vencimento.'
        if self.trigger_type == self.TriggerType.USAGE and not self.usage_limit:
            errors['usage_limit'] = 'Plano por uso exige limite de uso.'
        if self.trigger_type == self.TriggerType.EVENT and not self.event_name:
            errors['event_name'] = 'Plano por evento exige nome do evento.'
        if self.trigger_type == self.TriggerType.RULE and not self.rule_expression:
            errors['rule_expression'] = 'Plano por regra configurável exige expressão documentada.'
        if self.usage_limit is not None and self.usage_limit <= 0:
            errors['usage_limit'] = 'O limite de uso deve ser maior que zero.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.asset} - {self.get_plan_type_display()}'


class MaintenanceOrder(SingleInstanceModel):
    AUTOMATIC_IDENTIFIERS = (IdentifierSpec('order_number', 'MAN'),)

    class OrderType(models.TextChoices):
        PREVENTIVE_MAINTENANCE = (
            'preventive_maintenance',
            'Manutenção preventiva',
        )
        CORRECTIVE_MAINTENANCE = (
            'corrective_maintenance',
            'Manutenção corretiva',
        )
        CALIBRATION = 'calibration', 'Calibração'
        QUALIFICATION = 'qualification', 'Qualificação'
        CLEANING = 'cleaning', 'Limpeza'
        SANITIZATION = 'sanitization', 'Sanitização'

    class Status(models.TextChoices):
        OPEN = 'open', 'Aberta'
        IN_PROGRESS = 'in_progress', 'Em execução'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'

    class Priority(models.TextChoices):
        LOW = 'low', 'Baixa'
        MEDIUM = 'medium', 'Média'
        HIGH = 'high', 'Alta'
        CRITICAL = 'critical', 'Crítica'

    order_number = models.CharField('ordem', max_length=80, blank=True)
    asset = models.ForeignKey(
        EquipmentAsset,
        on_delete=models.PROTECT,
        related_name='maintenance_orders',
        verbose_name='ativo',
    )
    plan = models.ForeignKey(
        MaintenancePlan,
        on_delete=models.PROTECT,
        related_name='orders',
        null=True,
        blank=True,
        verbose_name='plano',
    )
    order_type = models.CharField('tipo', max_length=32, choices=OrderType.choices)
    trigger_type = models.CharField(
        'gatilho', max_length=24, choices=MaintenancePlan.TriggerType.choices
    )
    source_lot = models.ForeignKey(
        'inventory.StockLot',
        on_delete=models.PROTECT,
        related_name='maintenance_orders',
        null=True,
        blank=True,
        verbose_name='lote',
    )
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(
        'prioridade', max_length=24, choices=Priority.choices, default=Priority.MEDIUM
    )
    due_date = models.DateField('vencimento')
    description = models.TextField('descrição')
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_maintenance_orders',
        verbose_name='responsável',
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='opened_maintenance_orders',
        null=True,
        blank=True,
        verbose_name='aberta por',
    )
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='started_maintenance_orders',
        null=True,
        blank=True,
        verbose_name='iniciada por',
    )
    started_at = models.DateTimeField('iniciada em', null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='completed_maintenance_orders',
        null=True,
        blank=True,
        verbose_name='concluída por',
    )
    completed_at = models.DateTimeField('concluída em', null=True, blank=True)
    completion_summary = models.TextField('resumo de conclusão', blank=True)
    evidence_reference = models.CharField('referência da evidência', max_length=255, blank=True)
    content_hash = models.CharField('hash da evidência', max_length=128, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cancelled_maintenance_orders',
        null=True,
        blank=True,
        verbose_name='cancelada por',
    )
    cancelled_at = models.DateTimeField('cancelada em', null=True, blank=True)
    cancel_reason = models.TextField('motivo do cancelamento', blank=True)

    class Meta:
        ordering = ['-due_date', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['order_number'], name='unique_maintenance_order_number'
            ),
        ]
        indexes = [
            models.Index(fields=['asset', 'status']),
            models.Index(fields=['plan']),
            models.Index(fields=['order_type', 'trigger_type']),
            models.Index(fields=['due_date']),
            models.Index(fields=['responsible']),
            models.Index(fields=['order_number']),
        ]
        verbose_name = 'ordem de manutenção e calibração'
        verbose_name_plural = 'ordens de manutenção e calibração'

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = _sequence_code(MaintenanceOrder, 'order_number', 'MAN')
        super().save(*args, **kwargs)

    def start(self, user=None):
        if self.status != self.Status.OPEN:
            raise ValidationError({'status': 'Somente ordens abertas podem ser iniciadas.'})
        if self.asset.status == EquipmentAsset.Status.DECOMMISSIONED:
            raise ValidationError({'asset': 'Ativo desativado não pode iniciar ordem.'})
        self.status = self.Status.IN_PROGRESS
        self.started_by = user
        self.started_at = timezone.now()
        if self.order_type == self.OrderType.CALIBRATION:
            self.asset.status = EquipmentAsset.Status.UNDER_CALIBRATION
        elif self.order_type == self.OrderType.CLEANING:
            self.asset.status = EquipmentAsset.Status.CLEANING
        elif self.order_type == self.OrderType.SANITIZATION:
            self.asset.status = EquipmentAsset.Status.SANITIZATION
        else:
            self.asset.status = EquipmentAsset.Status.UNDER_MAINTENANCE
        self.full_clean()
        self.asset.full_clean()
        self.save(update_fields=['status', 'started_by', 'started_at', 'updated_at'])
        self.asset.save(update_fields=['status', 'updated_at'])

    def complete(self, summary, evidence_reference, content_hash, user=None):
        errors = {}
        if self.status != self.Status.IN_PROGRESS:
            errors['status'] = 'Conclusão exige ordem em execução.'
        if not summary:
            errors['completion_summary'] = 'Informe o resumo da conclusão.'
        if not evidence_reference:
            errors['evidence_reference'] = 'Informe a referência da evidência.'
        if not content_hash:
            errors['content_hash'] = 'Informe o hash da evidência.'
        if errors:
            raise ValidationError(errors)
        self.status = self.Status.COMPLETED
        self.completion_summary = summary
        self.evidence_reference = evidence_reference
        self.content_hash = content_hash
        self.completed_by = user
        self.completed_at = timezone.now()
        valid_until = timezone.localdate() + timedelta_days(
            self.plan.interval_days if self.plan and self.plan.interval_days else 365
        )
        if self.order_type == self.OrderType.CALIBRATION:
            self.asset.calibration_required = True
            self.asset.calibration_status = EquipmentAsset.CalibrationStatus.VALID
            self.asset.calibration_valid_until = valid_until
        if self.order_type == self.OrderType.QUALIFICATION:
            self.asset.qualification_status = EquipmentAsset.QualificationStatus.QUALIFIED
            self.asset.qualification_valid_until = valid_until
        self.asset.status = EquipmentAsset.Status.AVAILABLE
        self.full_clean()
        self.asset.full_clean()
        with transaction.atomic():
            self.save(
                update_fields=[
                    'status',
                    'completion_summary',
                    'evidence_reference',
                    'content_hash',
                    'completed_by',
                    'completed_at',
                    'updated_at',
                ]
            )
            self.asset.save(
                update_fields=[
                    'status',
                    'calibration_required',
                    'calibration_status',
                    'calibration_valid_until',
                    'qualification_status',
                    'qualification_valid_until',
                    'updated_at',
                ]
            )
            if self.plan and self.plan.interval_days:
                self.plan.next_due_date = timezone.localdate() + timedelta_days(
                    self.plan.interval_days
                )
                self.plan.save(update_fields=['next_due_date', 'updated_at'])

    def cancel(self, reason, user=None):
        if not reason:
            raise ValidationError({'cancel_reason': 'Informe o motivo do cancelamento.'})
        if self.status == self.Status.COMPLETED:
            raise ValidationError({'status': 'Ordem concluída não pode ser cancelada.'})
        self.status = self.Status.CANCELLED
        self.cancel_reason = reason
        self.cancelled_by = user
        self.cancelled_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=['status', 'cancel_reason', 'cancelled_by', 'cancelled_at', 'updated_at']
        )

    def clean(self):
        super().clean()
        errors = {}
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
        if self.plan and self.asset and self.plan.asset_id != self.asset_id:
            errors['plan'] = 'O plano deve pertencer ao ativo informado.'
        if self.status == self.Status.IN_PROGRESS and (
            not self.started_by_id or not self.started_at
        ):
            errors['started_by'] = 'Ordem em execução exige responsável e data de início.'
        if self.status == self.Status.COMPLETED:
            if not self.completion_summary:
                errors['completion_summary'] = 'Ordem concluída exige resumo.'
            if not self.evidence_reference:
                errors['evidence_reference'] = 'Ordem concluída exige evidência.'
            if not self.content_hash:
                errors['content_hash'] = 'Ordem concluída exige hash da evidência.'
            if not self.completed_by_id or not self.completed_at:
                errors['completed_by'] = 'Ordem concluída exige responsável e data de conclusão.'
        if self.status == self.Status.CANCELLED and not self.cancel_reason:
            errors['cancel_reason'] = 'Cancelamento exige motivo.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.order_number


def timedelta_days(days):
    return timedelta(days=int(days))


class EquipmentDowntime(SingleInstanceModel):
    class DowntimeType(models.TextChoices):
        PLANNED = 'planned', 'Planejada'
        UNPLANNED = 'unplanned', 'Não planejada'
        MAINTENANCE = 'maintenance', 'Manutenção'
        CALIBRATION = 'calibration', 'Calibração'
        CLEANING = 'cleaning', 'Limpeza'

    asset = models.ForeignKey(
        EquipmentAsset, on_delete=models.PROTECT, related_name='downtimes', verbose_name='ativo'
    )
    order = models.ForeignKey(
        MaintenanceOrder,
        on_delete=models.PROTECT,
        related_name='downtimes',
        null=True,
        blank=True,
        verbose_name='ordem',
    )
    downtime_type = models.CharField('tipo de parada', max_length=24, choices=DowntimeType.choices)
    started_at = models.DateTimeField('iniciada em')
    ended_at = models.DateTimeField('encerrada em', null=True, blank=True)
    duration_hours = models.DecimalField(
        'duração em horas', max_digits=12, decimal_places=2, default=ZERO_HOURS
    )
    reason = models.TextField('motivo')

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['asset', 'started_at']),
            models.Index(fields=['downtime_type']),
            models.Index(fields=['order']),
        ]
        verbose_name = 'parada de equipamento'
        verbose_name_plural = 'paradas de equipamentos'

    def save(self, *args, **kwargs):
        if self.started_at and self.ended_at:
            duration = Decimal(str((self.ended_at - self.started_at).total_seconds())) / Decimal(
                '3600'
            )
            self.duration_hours = _hours(duration)
        super().save(*args, **kwargs)

    def close(self, ended_at=None):
        if self.ended_at:
            raise ValidationError({'ended_at': 'Parada já encerrada.'})
        self.ended_at = ended_at or timezone.now()
        self.full_clean()
        self.save(update_fields=['ended_at', 'duration_hours', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        if self.order and self.asset and self.order.asset_id != self.asset_id:
            errors['order'] = 'A ordem deve pertencer ao ativo informado.'
        if self.ended_at and self.ended_at <= self.started_at:
            errors['ended_at'] = 'O término deve ser posterior ao início.'
        if self.duration_hours < 0:
            errors['duration_hours'] = 'A duração não pode ser negativa.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.asset} - {self.started_at:%Y-%m-%d %H:%M}'


class EquipmentUsageLog(SingleInstanceModel):
    asset = models.ForeignKey(
        EquipmentAsset, on_delete=models.PROTECT, related_name='usage_logs', verbose_name='ativo'
    )
    source_lot = models.ForeignKey(
        'inventory.StockLot',
        on_delete=models.PROTECT,
        related_name='equipment_usage_logs',
        null=True,
        blank=True,
        verbose_name='lote',
    )
    used_at = models.DateTimeField('usado em')
    usage_quantity = models.DecimalField(
        'quantidade de uso', max_digits=14, decimal_places=4, default=ZERO_QUANTITY
    )
    usage_unit = models.CharField('unidade de uso', max_length=40)
    event_reference = models.CharField('referência do evento', max_length=120, blank=True)
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='equipment_usage_logs',
        null=True,
        blank=True,
        verbose_name='registrado por',
    )

    class Meta:
        ordering = ['-used_at']
        indexes = [
            models.Index(fields=['asset', 'used_at']),
            models.Index(fields=['source_lot']),
            models.Index(fields=['event_reference']),
        ]
        verbose_name = 'uso de equipamento'
        verbose_name_plural = 'usos de equipamentos'

    def clean(self):
        super().clean()
        errors = {}
        if _quantity(self.usage_quantity) <= ZERO_QUANTITY:
            errors['usage_quantity'] = 'A quantidade de uso deve ser maior que zero.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.asset} - {self.used_at:%Y-%m-%d %H:%M}'


class MaintenanceMetricReport(SingleInstanceModel):
    class ReportType(models.TextChoices):
        AVAILABILITY = 'availability', 'Disponibilidade'
        DOWNTIME = 'downtime', 'Paradas'
        MTBF = 'mtbf', 'MTBF'
        MTTR = 'mttr', 'MTTR'
        DUE_DATES = 'due_dates', 'Vencimentos'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        GENERATED = 'generated', 'Gerado'

    asset = models.ForeignKey(
        EquipmentAsset,
        on_delete=models.PROTECT,
        related_name='metric_reports',
        null=True,
        blank=True,
        verbose_name='ativo',
    )
    report_type = models.CharField('tipo de relatório', max_length=24, choices=ReportType.choices)
    title = models.CharField('título', max_length=180)
    period_start = models.DateTimeField('início do período')
    period_end = models.DateTimeField('fim do período')
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.DRAFT)
    availability_rate = models.DecimalField(
        'disponibilidade %', max_digits=7, decimal_places=2, default=ZERO_PERCENT
    )
    downtime_hours = models.DecimalField(
        'horas paradas', max_digits=12, decimal_places=2, default=ZERO_HOURS
    )
    mtbf_hours = models.DecimalField(
        'MTBF horas', max_digits=12, decimal_places=2, default=ZERO_HOURS
    )
    mttr_hours = models.DecimalField(
        'MTTR horas', max_digits=12, decimal_places=2, default=ZERO_HOURS
    )
    overdue_orders = models.PositiveIntegerField('ordens atrasadas', default=0)
    due_soon_orders = models.PositiveIntegerField('ordens a vencer', default=0)
    content_reference = models.CharField('referência do relatório', max_length=255, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='generated_maintenance_metric_reports',
        null=True,
        blank=True,
        verbose_name='gerado por',
    )
    generated_at = models.DateTimeField('gerado em', null=True, blank=True)

    class Meta:
        ordering = ['-period_end', '-created_at']
        indexes = [
            models.Index(fields=['asset', 'report_type']),
            models.Index(fields=['status']),
            models.Index(fields=['period_start', 'period_end']),
            models.Index(fields=['generated_by']),
        ]
        verbose_name = 'indicador de manutenção'
        verbose_name_plural = 'indicadores de manutenção'

    def generate(self, user=None, content_reference=''):
        if not content_reference:
            raise ValidationError(
                {'content_reference': 'Informe a referência do relatório gerado.'}
            )
        total_hours = Decimal(str((self.period_end - self.period_start).total_seconds())) / Decimal(
            '3600'
        )
        total_hours = _hours(total_hours)
        downtime_qs = EquipmentDowntime.objects.filter(
            started_at__gte=self.period_start,
            started_at__lte=self.period_end,
        )
        orders_qs = MaintenanceOrder.objects.all()
        if self.asset_id:
            downtime_qs = downtime_qs.filter(asset=self.asset)
            orders_qs = orders_qs.filter(asset=self.asset)
        downtime_hours = downtime_qs.aggregate(total=Sum('duration_hours'))['total'] or ZERO_HOURS
        downtime_hours = _hours(downtime_hours)
        downtime_count = downtime_qs.filter(duration_hours__gt=0).count()
        uptime_hours = max(total_hours - downtime_hours, ZERO_HOURS)
        self.downtime_hours = downtime_hours
        self.availability_rate = _percent(
            (uptime_hours / total_hours * Decimal('100')) if total_hours else ZERO_PERCENT
        )
        self.mttr_hours = _hours(downtime_hours / downtime_count) if downtime_count else ZERO_HOURS
        self.mtbf_hours = _hours(uptime_hours / downtime_count) if downtime_count else uptime_hours
        today = timezone.localdate()
        pending_statuses = [MaintenanceOrder.Status.OPEN, MaintenanceOrder.Status.IN_PROGRESS]
        self.overdue_orders = orders_qs.filter(
            status__in=pending_statuses, due_date__lt=today
        ).count()
        self.due_soon_orders = orders_qs.filter(
            status__in=pending_statuses,
            due_date__gte=today,
            due_date__lte=today + timedelta_days(30),
        ).count()
        self.status = self.Status.GENERATED
        self.content_reference = content_reference
        self.generated_by = user
        self.generated_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=[
                'availability_rate',
                'downtime_hours',
                'mtbf_hours',
                'mttr_hours',
                'overdue_orders',
                'due_soon_orders',
                'status',
                'content_reference',
                'generated_by',
                'generated_at',
                'updated_at',
            ]
        )

    def clean(self):
        super().clean()
        errors = {}
        if self.period_end and self.period_start and self.period_end <= self.period_start:
            errors['period_end'] = 'O fim do período deve ser posterior ao início.'
        if self.status == self.Status.GENERATED and not self.content_reference:
            errors['content_reference'] = 'Relatório gerado exige referência do conteúdo.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title
