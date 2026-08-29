from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from base.models import SingleInstanceModel
from base.normalized_locations import validate_normalized_location
from base.sequences import AutoCodeMixin, IdentifierSpec, sequence_code


PERCENT_SCALE = Decimal('0.01')
ZERO_PERCENT = Decimal('0.00')


def _percent(value):
    try:
        amount = Decimal(str(value or ZERO_PERCENT))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError('Informe um percentual válido.') from exc
    return amount.quantize(PERCENT_SCALE, rounding=ROUND_HALF_UP)


def _sequence_code(model, *args):
    if len(args) == 3:
        _legacy_scope, field_name, prefix = args
    else:
        field_name, prefix = args
    return sequence_code(model, field_name, prefix)


class JobPosition(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'JP'
    code = models.CharField('código', max_length=40, blank=True)
    title = models.CharField('cargo', max_length=160)
    area = models.CharField('área', max_length=120)
    area_ref = models.ForeignKey(
        'auxiliary.BusinessArea',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='área normalizada',
    )
    department = models.CharField('departamento', max_length=120, blank=True)
    department_ref = models.ForeignKey(
        'auxiliary.Department',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='departamento normalizado',
    )
    description = models.TextField('descrição', blank=True)
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['area', 'title']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_job_position_code'),
        ]
        indexes = [
            models.Index(fields=['area', 'is_active']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'cargo'
        verbose_name_plural = 'cargos'

    def __str__(self):
        return f'{self.code} - {self.title}'


class WorkFunction(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'WF'
    code = models.CharField('código', max_length=40, blank=True)
    name = models.CharField('função', max_length=160)
    job_position = models.ForeignKey(
        JobPosition,
        on_delete=models.PROTECT,
        related_name='functions',
        null=True,
        blank=True,
        verbose_name='cargo',
    )
    area = models.CharField('área', max_length=120)
    area_ref = models.ForeignKey(
        'auxiliary.BusinessArea',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='área normalizada',
    )
    process = models.CharField('processo', max_length=120, blank=True)
    process_ref = models.ForeignKey(
        'auxiliary.BusinessProcess',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='processo normalizado',
    )
    is_critical = models.BooleanField('crítica', default=False)
    is_active = models.BooleanField('ativo', default=True)
    description = models.TextField('descrição', blank=True)

    class Meta:
        ordering = ['area', 'process', 'name']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_work_function_code'),
        ]
        indexes = [
            models.Index(fields=['area', 'process']),
            models.Index(fields=['is_critical', 'is_active']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'função'
        verbose_name_plural = 'funções'

    def clean(self):
        super().clean()
        errors = {}
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.code} - {self.name}'


class Competency(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'CPT'

    class CompetencyType(models.TextChoices):
        TECHNICAL = 'technical', 'Técnica'
        GMP = 'gmp', 'BPF/GMP'
        SAFETY = 'safety', 'Segurança'
        REGULATORY = 'regulatory', 'Regulatória'
        SYSTEM = 'system', 'Sistema'
        BEHAVIORAL = 'behavioral', 'Comportamental'

    code = models.CharField('código', max_length=40, blank=True)
    name = models.CharField('competência', max_length=160)
    competency_type = models.CharField('tipo', max_length=24, choices=CompetencyType.choices)
    description = models.TextField('descrição', blank=True)
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['competency_type', 'name']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_competency_code'),
        ]
        indexes = [
            models.Index(fields=['competency_type', 'is_active']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'competência'
        verbose_name_plural = 'competências'

    def __str__(self):
        return f'{self.code} - {self.name}'


class TrainingRequirement(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'TR'

    class TrainingType(models.TextChoices):
        DOCUMENT = 'document', 'Documento'
        CRITICAL_ACTIVITY = 'critical_activity', 'Atividade crítica'
        EQUIPMENT = 'equipment', 'Equipamento'
        MODULE = 'module', 'Módulo do sistema'
        REGULATORY = 'regulatory', 'Requisito regulatório'
        RECYCLE = 'recycle', 'Reciclagem'

    code = models.CharField('código', max_length=40, blank=True)
    title = models.CharField('treinamento', max_length=180)
    training_type = models.CharField('tipo', max_length=32, choices=TrainingType.choices)
    area = models.CharField('área', max_length=120)
    area_ref = models.ForeignKey(
        'auxiliary.BusinessArea',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='área normalizada',
    )
    process = models.CharField('processo', max_length=120, blank=True)
    process_ref = models.ForeignKey(
        'auxiliary.BusinessProcess',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='processo normalizado',
    )
    job_position = models.ForeignKey(
        JobPosition,
        on_delete=models.PROTECT,
        related_name='training_requirements',
        null=True,
        blank=True,
        verbose_name='cargo',
    )
    function = models.ForeignKey(
        WorkFunction,
        on_delete=models.PROTECT,
        related_name='training_requirements',
        null=True,
        blank=True,
        verbose_name='função',
    )
    competency = models.ForeignKey(
        Competency,
        on_delete=models.PROTECT,
        related_name='training_requirements',
        null=True,
        blank=True,
        verbose_name='competência',
    )
    document = models.ForeignKey(
        'documents.ControlledDocument',
        on_delete=models.PROTECT,
        related_name='training_requirements',
        null=True,
        blank=True,
        verbose_name='documento',
    )
    equipment = models.ForeignKey(
        'maintenance.EquipmentAsset',
        on_delete=models.PROTECT,
        related_name='training_requirements',
        null=True,
        blank=True,
        verbose_name='equipamento',
    )
    module_code = models.CharField('módulo', max_length=80, blank=True)
    regulatory_requirement_reference = models.CharField(
        'requisito regulatório', max_length=160, blank=True
    )
    validity_days = models.PositiveIntegerField('validade em dias', default=365)
    alert_before_days = models.PositiveIntegerField('alertar antes de dias', default=30)
    passing_score = models.DecimalField(
        'nota mínima', max_digits=5, decimal_places=2, default=Decimal('80.00')
    )
    requires_evaluation = models.BooleanField('exige avaliação', default=True)
    requires_certificate = models.BooleanField('exige certificado', default=True)
    is_mandatory = models.BooleanField('obrigatório', default=True)
    block_without_valid_training = models.BooleanField(
        'bloquear sem treinamento válido', default=False
    )
    is_active = models.BooleanField('ativo', default=True)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(
                fields=['code'], name='unique_people_training_requirement_code'
            ),
        ]
        indexes = [
            models.Index(fields=['training_type', 'is_active']),
            models.Index(fields=['area', 'process']),
            models.Index(fields=['job_position']),
            models.Index(fields=['function']),
            models.Index(fields=['competency']),
            models.Index(fields=['document']),
            models.Index(fields=['equipment']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'requisito de treinamento'
        verbose_name_plural = 'requisitos de treinamento'

    def user_has_valid_training(self, user):
        return (
            self.enrollments.filter(user=user, status=TrainingEnrollment.Status.APPROVED)
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.localdate()))
            .exists()
        )

    def clean(self):
        super().clean()
        errors = {}
        for field in ('job_position', 'function', 'competency', 'document', 'equipment'):
            pass
        if (
            self.function
            and self.job_position
            and self.function.job_position_id
            and self.function.job_position_id != self.job_position_id
        ):
            errors['function'] = 'A função deve pertencer ao cargo informado.'
        if self.validity_days <= 0:
            errors['validity_days'] = 'A validade deve ser maior que zero.'
        if self.alert_before_days >= self.validity_days:
            errors['alert_before_days'] = 'O alerta deve ocorrer antes do fim da validade.'
        if _percent(self.passing_score) < ZERO_PERCENT or _percent(self.passing_score) > Decimal(
            '100.00'
        ):
            errors['passing_score'] = 'A nota mínima deve estar entre 0 e 100.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.code} - {self.title}'


class TrainingMatrixRequirement(SingleInstanceModel):
    class Priority(models.TextChoices):
        LOW = 'low', 'Baixa'
        MEDIUM = 'medium', 'Média'
        HIGH = 'high', 'Alta'
        CRITICAL = 'critical', 'Crítica'

    job_position = models.ForeignKey(
        JobPosition,
        on_delete=models.PROTECT,
        related_name='matrix_requirements',
        verbose_name='cargo',
    )
    function = models.ForeignKey(
        WorkFunction,
        on_delete=models.PROTECT,
        related_name='matrix_requirements',
        null=True,
        blank=True,
        verbose_name='função',
    )
    competency = models.ForeignKey(
        Competency,
        on_delete=models.PROTECT,
        related_name='matrix_requirements',
        null=True,
        blank=True,
        verbose_name='competência',
    )
    requirement = models.ForeignKey(
        TrainingRequirement,
        on_delete=models.PROTECT,
        related_name='matrix_entries',
        verbose_name='requisito',
    )
    is_mandatory = models.BooleanField('obrigatório', default=True)
    priority = models.CharField(
        'prioridade', max_length=24, choices=Priority.choices, default=Priority.MEDIUM
    )
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['job_position__title', 'requirement__code']
        constraints = [
            models.UniqueConstraint(
                fields=['job_position', 'function', 'competency', 'requirement'],
                name='unique_training_matrix_requirement',
            ),
        ]
        indexes = [
            models.Index(fields=['job_position', 'priority']),
            models.Index(fields=['function']),
            models.Index(fields=['competency']),
            models.Index(fields=['requirement']),
        ]
        verbose_name = 'matriz de treinamento'
        verbose_name_plural = 'matriz de treinamento'

    def clean(self):
        super().clean()
        errors = {}
        for field in ('job_position', 'function', 'competency', 'requirement'):
            pass
        if (
            self.function
            and self.function.job_position_id
            and self.function.job_position_id != self.job_position_id
        ):
            errors['function'] = 'A função deve pertencer ao cargo informado.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.job_position} - {self.requirement}'


class TrainingSession(SingleInstanceModel):
    AUTOMATIC_IDENTIFIERS = (IdentifierSpec('session_number', 'TRNS'),)

    class DeliveryMethod(models.TextChoices):
        CLASSROOM = 'classroom', 'Presencial'
        ONLINE = 'online', 'Online'
        ON_THE_JOB = 'on_the_job', 'No posto de trabalho'
        SELF_STUDY = 'self_study', 'Autotreinamento'

    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planejada'
        OPEN = 'open', 'Aberta'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'

    session_number = models.CharField('turma', max_length=80, blank=True)
    requirement = models.ForeignKey(
        TrainingRequirement,
        on_delete=models.PROTECT,
        related_name='sessions',
        verbose_name='requisito',
    )
    title = models.CharField('título', max_length=180)
    delivery_method = models.CharField(
        'método', max_length=24, choices=DeliveryMethod.choices, default=DeliveryMethod.CLASSROOM
    )
    scheduled_start = models.DateTimeField('início programado')
    scheduled_end = models.DateTimeField('fim programado')
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='instructed_training_sessions',
        verbose_name='instrutor',
    )
    capacity = models.PositiveIntegerField('capacidade', default=30)
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.PLANNED
    )
    location = models.CharField('local', max_length=160, blank=True)
    location_zipcode = models.CharField('CEP do local', max_length=20, blank=True)
    location_street = models.CharField('logradouro do local', max_length=200, blank=True)
    location_street_number = models.CharField('número', max_length=20, blank=True)
    location_complement = models.CharField('complemento', max_length=100, blank=True)
    location_neighborhood = models.CharField('bairro do local', max_length=120, blank=True)
    location_country_ref = models.ForeignKey(
        'auxiliary.Country',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name='país',
    )
    location_state_ref = models.ForeignKey(
        'auxiliary.StateProvince',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='UF',
    )
    location_city_ref = models.ForeignKey(
        'auxiliary.City',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='Cidade',
    )
    location_site = models.ForeignKey(
        'masters.Site',
        on_delete=models.PROTECT,
        related_name='training_sessions',
        null=True,
        blank=True,
        verbose_name='unidade/planta',
    )
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['-scheduled_start']
        constraints = [
            models.UniqueConstraint(
                fields=['session_number'], name='unique_training_session_number'
            ),
        ]
        indexes = [
            models.Index(fields=['requirement', 'status']),
            models.Index(fields=['scheduled_start']),
            models.Index(fields=['instructor']),
            models.Index(fields=['session_number']),
        ]
        verbose_name = 'turma de treinamento'
        verbose_name_plural = 'turmas de treinamento'

    def save(self, *args, **kwargs):
        if not self.session_number:
            self.session_number = _sequence_code(TrainingSession, 'session_number', 'TRNS')
        super().save(*args, **kwargs)

    def convocate(self, user, convoked_by=None, due_date=None):
        errors = {}
        if self.status == self.Status.CANCELLED:
            errors['status'] = 'Turma cancelada não pode convocar usuários.'
        if self.enrollments.count() >= self.capacity:
            errors['capacity'] = 'Turma sem capacidade disponível.'
        if errors:
            raise ValidationError(errors)
        enrollment = TrainingEnrollment(
            requirement=self.requirement,
            session=self,
            user=user,
            status=TrainingEnrollment.Status.CONVOKED,
            convoked_by=convoked_by,
            convoked_at=timezone.now(),
            due_date=due_date or timezone.localdate(value=self.scheduled_start),
        )
        enrollment.full_clean()
        enrollment.save()
        if self.status == self.Status.PLANNED:
            self.status = self.Status.OPEN
            self.save(update_fields=['status', 'updated_at'])
        return enrollment

    def clean(self):
        super().clean()
        validate_normalized_location(
            self,
            city_ref_field='location_city_ref',
            state_ref_field='location_state_ref',
        )
        errors = {}
        if (
            self.scheduled_end
            and self.scheduled_start
            and self.scheduled_end <= self.scheduled_start
        ):
            errors['scheduled_end'] = 'O término deve ser posterior ao início.'
        if self.capacity <= 0:
            errors['capacity'] = 'A capacidade deve ser maior que zero.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.session_number


class TrainingEnrollment(SingleInstanceModel):
    AUTOMATIC_IDENTIFIERS = (
        IdentifierSpec('enrollment_number', 'TRN'),
        IdentifierSpec('certificate_number', 'CERT', trigger='approval'),
    )

    class Status(models.TextChoices):
        CONVOKED = 'convoked', 'Convocado'
        IN_PROGRESS = 'in_progress', 'Em realização'
        COMPLETED = 'completed', 'Realizado'
        APPROVED = 'approved', 'Aprovado'
        FAILED = 'failed', 'Reprovado'
        EXPIRED = 'expired', 'Vencido'
        REVOKED = 'revoked', 'Revogado'

    enrollment_number = models.CharField('registro', max_length=80, blank=True)
    requirement = models.ForeignKey(
        TrainingRequirement,
        on_delete=models.PROTECT,
        related_name='enrollments',
        verbose_name='requisito',
    )
    session = models.ForeignKey(
        TrainingSession,
        on_delete=models.PROTECT,
        related_name='enrollments',
        null=True,
        blank=True,
        verbose_name='turma',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='people_training_enrollments',
        verbose_name='usuário',
    )
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.CONVOKED
    )
    convoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='convoked_training_enrollments',
        null=True,
        blank=True,
        verbose_name='convocado por',
    )
    convoked_at = models.DateTimeField('convocado em', null=True, blank=True)
    due_date = models.DateField('prazo', null=True, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='started_training_enrollments',
        null=True,
        blank=True,
        verbose_name='iniciado por',
    )
    started_at = models.DateTimeField('iniciado em', null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='completed_people_training_enrollments',
        null=True,
        blank=True,
        verbose_name='realizado por',
    )
    completed_at = models.DateTimeField('realizado em', null=True, blank=True)
    score = models.DecimalField('nota', max_digits=5, decimal_places=2, null=True, blank=True)
    evidence_reference = models.CharField('evidência', max_length=255, blank=True)
    content_hash = models.CharField('hash da evidência', max_length=128, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='approved_training_enrollments',
        null=True,
        blank=True,
        verbose_name='aprovado por',
    )
    approved_at = models.DateTimeField('aprovado em', null=True, blank=True)
    valid_until = models.DateField('válido até', null=True, blank=True)
    recertification_due_date = models.DateField('reciclagem até', null=True, blank=True)
    certificate_number = models.CharField('certificado', max_length=80, blank=True)
    certificate_reference = models.CharField(
        'referência do certificado', max_length=255, blank=True
    )
    failure_reason = models.TextField('motivo da reprovação', blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='revoked_training_enrollments',
        null=True,
        blank=True,
        verbose_name='revogado por',
    )
    revoked_at = models.DateTimeField('revogado em', null=True, blank=True)
    revocation_reason = models.TextField('motivo da revogação', blank=True)

    class Meta:
        ordering = ['-convoked_at', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['enrollment_number'],
                name='unique_training_enrollment_number',
            ),
            models.UniqueConstraint(
                fields=['certificate_number'],
                condition=~models.Q(certificate_number=''),
                name='unique_nonempty_training_certificate_number',
            ),
        ]
        indexes = [
            models.Index(fields=['requirement', 'status']),
            models.Index(fields=['session']),
            models.Index(fields=['user', 'valid_until']),
            models.Index(fields=['due_date']),
            models.Index(fields=['certificate_number']),
            models.Index(fields=['enrollment_number']),
        ]
        verbose_name = 'registro de treinamento'
        verbose_name_plural = 'registros de treinamento'

    @property
    def is_valid(self):
        if self.status != self.Status.APPROVED:
            return False
        if self.valid_until and self.valid_until < timezone.localdate():
            return False
        return True

    def save(self, *args, **kwargs):
        if not self.enrollment_number:
            self.enrollment_number = _sequence_code(TrainingEnrollment, 'enrollment_number', 'TRN')
        super().save(*args, **kwargs)

    def start(self, user=None):
        if self.status != self.Status.CONVOKED:
            raise ValidationError(
                {'status': 'Somente treinamentos convocados podem ser iniciados.'}
            )
        self.status = self.Status.IN_PROGRESS
        self.started_by = user
        self.started_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'started_by', 'started_at', 'updated_at'])

    def complete(self, score=None, evidence_reference='', content_hash='', user=None):
        errors = {}
        if self.status != self.Status.IN_PROGRESS:
            errors['status'] = 'Conclusão exige treinamento em realização.'
        if self.requirement.requires_evaluation and score is None:
            errors['score'] = 'Treinamento com avaliação exige nota.'
        score_value = _percent(score) if score is not None else None
        if score_value is not None and (
            score_value < ZERO_PERCENT or score_value > Decimal('100.00')
        ):
            errors['score'] = 'A nota deve estar entre 0 e 100.'
        if (
            score_value is not None
            and self.requirement.requires_evaluation
            and score_value < self.requirement.passing_score
        ):
            errors['score'] = 'Nota inferior ao mínimo de aprovação.'
        if not evidence_reference:
            errors['evidence_reference'] = 'Informe a evidência de realização.'
        if not content_hash:
            errors['content_hash'] = 'Informe o hash da evidência.'
        if errors:
            raise ValidationError(errors)
        self.status = self.Status.COMPLETED
        self.score = score_value
        self.evidence_reference = evidence_reference
        self.content_hash = content_hash
        self.completed_by = user
        self.completed_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'score',
                'evidence_reference',
                'content_hash',
                'completed_by',
                'completed_at',
                'updated_at',
            ]
        )

    def approve(self, user=None, certificate_reference=''):
        errors = {}
        if self.status != self.Status.COMPLETED:
            errors['status'] = 'Aprovação exige treinamento realizado.'
        if self.requirement.requires_certificate and not certificate_reference:
            errors['certificate_reference'] = (
                'Treinamento com certificado exige referência do certificado.'
            )
        if errors:
            raise ValidationError(errors)
        today = timezone.localdate()
        self.status = self.Status.APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.valid_until = today + timedelta(days=self.requirement.validity_days)
        self.recertification_due_date = self.valid_until - timedelta(
            days=self.requirement.alert_before_days
        )
        self.certificate_reference = certificate_reference or self.certificate_reference
        if self.requirement.requires_certificate and not self.certificate_number:
            self.certificate_number = _sequence_code(
                TrainingEnrollment, 'certificate_number', 'CERT'
            )
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'approved_by',
                'approved_at',
                'valid_until',
                'recertification_due_date',
                'certificate_reference',
                'certificate_number',
                'updated_at',
            ]
        )

    def fail(self, reason, user=None):
        if not reason:
            raise ValidationError({'failure_reason': 'Informe o motivo da reprovação.'})
        if self.status not in {self.Status.IN_PROGRESS, self.Status.COMPLETED}:
            raise ValidationError(
                {'status': 'Reprovação exige treinamento em realização ou realizado.'}
            )
        self.status = self.Status.FAILED
        self.failure_reason = reason
        self.completed_by = user or self.completed_by
        self.completed_at = self.completed_at or timezone.now()
        self.save(
            update_fields=['status', 'failure_reason', 'completed_by', 'completed_at', 'updated_at']
        )

    def revoke(self, reason, user=None):
        if not reason:
            raise ValidationError({'revocation_reason': 'Informe o motivo da revogação.'})
        if self.status not in {self.Status.APPROVED, self.Status.COMPLETED}:
            raise ValidationError(
                {'status': 'Somente treinamento concluído ou aprovado pode ser revogado.'}
            )
        self.status = self.Status.REVOKED
        self.revocation_reason = reason
        self.revoked_by = user
        self.revoked_at = timezone.now()
        self.save(
            update_fields=['status', 'revocation_reason', 'revoked_by', 'revoked_at', 'updated_at']
        )

    def clean(self):
        super().clean()
        errors = {}
        for field in ('requirement', 'session'):
            pass
        for field in (
            'user',
            'convoked_by',
            'started_by',
            'completed_by',
            'approved_by',
            'revoked_by',
        ):
            pass
        if self.session and self.requirement and self.session.requirement_id != self.requirement_id:
            errors['session'] = 'A turma deve pertencer ao requisito informado.'
        if self.status == self.Status.IN_PROGRESS and (
            not self.started_by_id or not self.started_at
        ):
            errors['started_by'] = 'Treinamento em realização exige usuário e data de início.'
        if self.status in {self.Status.COMPLETED, self.Status.APPROVED} and (
            not self.completed_by_id or not self.completed_at
        ):
            errors['completed_by'] = 'Treinamento realizado exige responsável e data.'
        if self.status == self.Status.APPROVED:
            if not self.approved_by_id or not self.approved_at:
                errors['approved_by'] = 'Treinamento aprovado exige aprovador e data.'
            if self.requirement.requires_certificate and (
                not self.certificate_number or not self.certificate_reference
            ):
                errors['certificate_reference'] = (
                    'Certificado obrigatório exige número e referência.'
                )
        if (
            self.valid_until
            and self.completed_at
            and self.valid_until < timezone.localdate(value=self.completed_at)
        ):
            errors['valid_until'] = 'A validade não pode ser anterior à conclusão.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.enrollment_number


class CriticalActivityRule(SingleInstanceModel):
    class EnforcementMode(models.TextChoices):
        BLOCK = 'block', 'Bloquear'
        ALERT = 'alert', 'Alertar'
        NONE = 'none', 'Não aplicar'

    activity_code = models.CharField('atividade', max_length=80)
    name = models.CharField('nome', max_length=180)
    requirement = models.ForeignKey(
        TrainingRequirement,
        on_delete=models.PROTECT,
        related_name='critical_activity_rules',
        verbose_name='requisito',
    )
    enforcement_mode = models.CharField(
        'modo de aplicação',
        max_length=24,
        choices=EnforcementMode.choices,
        default=EnforcementMode.BLOCK,
    )
    area = models.CharField('área', max_length=120, blank=True)
    area_ref = models.ForeignKey(
        'auxiliary.BusinessArea',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='área normalizada',
    )
    process = models.CharField('processo', max_length=120, blank=True)
    process_ref = models.ForeignKey(
        'auxiliary.BusinessProcess',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='processo normalizado',
    )
    equipment = models.ForeignKey(
        'maintenance.EquipmentAsset',
        on_delete=models.PROTECT,
        related_name='training_critical_activity_rules',
        null=True,
        blank=True,
        verbose_name='equipamento',
    )
    module_code = models.CharField('módulo', max_length=80, blank=True)
    is_active = models.BooleanField('ativo', default=True)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['activity_code']
        constraints = [
            models.UniqueConstraint(
                fields=['activity_code'],
                name='unique_people_critical_activity_code',
            ),
        ]
        indexes = [
            models.Index(fields=['is_active', 'enforcement_mode']),
            models.Index(fields=['requirement']),
            models.Index(fields=['equipment']),
            models.Index(fields=['activity_code']),
        ]
        verbose_name = 'atividade crítica de treinamento'
        verbose_name_plural = 'atividades críticas de treinamento'

    def authorize_user(self, user):
        errors = {}
        if errors:
            raise ValidationError(errors)
        if not self.is_active or self.enforcement_mode == self.EnforcementMode.NONE:
            return True
        if self.requirement.user_has_valid_training(user):
            return True
        if self.enforcement_mode == self.EnforcementMode.ALERT:
            return False
        raise ValidationError(
            {'training': 'Usuário sem treinamento válido para atividade crítica.'}
        )

    def clean(self):
        super().clean()
        errors = {}
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.activity_code} - {self.name}'


class TrainingIndicatorReport(SingleInstanceModel):
    class ReportType(models.TextChoices):
        COMPLIANCE = 'compliance', 'Aderência'
        EXPIRATION = 'expiration', 'Vencimentos'
        CRITICAL_GAPS = 'critical_gaps', 'Lacunas críticas'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        GENERATED = 'generated', 'Gerado'

    report_type = models.CharField('tipo de relatório', max_length=24, choices=ReportType.choices)
    title = models.CharField('título', max_length=180)
    area = models.CharField('área', max_length=120, blank=True)
    area_ref = models.ForeignKey(
        'auxiliary.BusinessArea',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='área normalizada',
    )
    process = models.CharField('processo', max_length=120, blank=True)
    process_ref = models.ForeignKey(
        'auxiliary.BusinessProcess',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='processo normalizado',
    )
    job_position = models.ForeignKey(
        JobPosition,
        on_delete=models.PROTECT,
        related_name='training_reports',
        null=True,
        blank=True,
        verbose_name='cargo',
    )
    function = models.ForeignKey(
        WorkFunction,
        on_delete=models.PROTECT,
        related_name='training_reports',
        null=True,
        blank=True,
        verbose_name='função',
    )
    period_start = models.DateTimeField('início do período')
    period_end = models.DateTimeField('fim do período')
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.DRAFT)
    total_required = models.PositiveIntegerField('treinamentos requeridos', default=0)
    total_completed = models.PositiveIntegerField('treinamentos realizados', default=0)
    total_valid = models.PositiveIntegerField('treinamentos válidos', default=0)
    overdue_trainings = models.PositiveIntegerField('treinamentos atrasados', default=0)
    due_soon_trainings = models.PositiveIntegerField('treinamentos a vencer', default=0)
    compliance_rate = models.DecimalField(
        'aderência %', max_digits=7, decimal_places=2, default=ZERO_PERCENT
    )
    content_reference = models.CharField('referência do relatório', max_length=255, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='generated_training_indicator_reports',
        null=True,
        blank=True,
        verbose_name='gerado por',
    )
    generated_at = models.DateTimeField('gerado em', null=True, blank=True)

    class Meta:
        ordering = ['-period_end', '-created_at']
        indexes = [
            models.Index(fields=['report_type', 'status']),
            models.Index(fields=['area', 'process']),
            models.Index(fields=['job_position']),
            models.Index(fields=['function']),
            models.Index(fields=['period_start', 'period_end']),
        ]
        verbose_name = 'indicador de treinamento'
        verbose_name_plural = 'indicadores de treinamento'

    def generate(self, user=None, content_reference=''):
        if not content_reference:
            raise ValidationError(
                {'content_reference': 'Informe a referência do relatório gerado.'}
            )
        enrollments = TrainingEnrollment.objects.filter(
            convoked_at__gte=self.period_start,
            convoked_at__lte=self.period_end,
        ).select_related('requirement')
        if self.area:
            enrollments = enrollments.filter(requirement__area=self.area)
        if self.process:
            enrollments = enrollments.filter(requirement__process=self.process)
        if self.job_position_id:
            enrollments = enrollments.filter(requirement__job_position=self.job_position)
        if self.function_id:
            enrollments = enrollments.filter(requirement__function=self.function)
        today = timezone.localdate()
        due_horizon = today + timedelta(days=30)
        valid_filter = Q(status=TrainingEnrollment.Status.APPROVED) & (
            Q(valid_until__isnull=True) | Q(valid_until__gte=today)
        )
        self.total_required = enrollments.count()
        self.total_completed = enrollments.filter(
            status__in=[TrainingEnrollment.Status.COMPLETED, TrainingEnrollment.Status.APPROVED]
        ).count()
        self.total_valid = enrollments.filter(valid_filter).count()
        self.overdue_trainings = enrollments.filter(
            Q(
                status__in=[
                    TrainingEnrollment.Status.CONVOKED,
                    TrainingEnrollment.Status.IN_PROGRESS,
                    TrainingEnrollment.Status.FAILED,
                ],
                due_date__lt=today,
            )
            | Q(status=TrainingEnrollment.Status.APPROVED, valid_until__lt=today)
        ).count()
        self.due_soon_trainings = enrollments.filter(
            Q(
                status=TrainingEnrollment.Status.APPROVED,
                valid_until__gte=today,
                valid_until__lte=due_horizon,
            )
            | Q(
                status__in=[
                    TrainingEnrollment.Status.CONVOKED,
                    TrainingEnrollment.Status.IN_PROGRESS,
                ],
                due_date__gte=today,
                due_date__lte=due_horizon,
            )
        ).count()
        self.compliance_rate = _percent(
            (Decimal(self.total_valid) / Decimal(self.total_required) * Decimal('100'))
            if self.total_required
            else ZERO_PERCENT
        )
        self.status = self.Status.GENERATED
        self.content_reference = content_reference
        self.generated_by = user
        self.generated_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=[
                'total_required',
                'total_completed',
                'total_valid',
                'overdue_trainings',
                'due_soon_trainings',
                'compliance_rate',
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
