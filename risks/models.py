from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from base.models import SingleInstanceModel
from base.sequences import sequence_code
from masters.models import BusinessPartner


def _sequence_code(model, *args):
    if len(args) == 3:
        _legacy_scope, field_name, prefix = args
    else:
        field_name, prefix = args
    return sequence_code(model, field_name, prefix)


class RiskLevelChoices(models.TextChoices):
    LOW = 'low', 'Baixo'
    MEDIUM = 'medium', 'Médio'
    HIGH = 'high', 'Alto'
    CRITICAL = 'critical', 'Crítico'


class RiskRecord(SingleInstanceModel):
    RiskLevel = RiskLevelChoices

    class RiskCategory(models.TextChoices):
        QUALITY = 'quality', 'Qualidade'
        PRODUCTION = 'production', 'Produção'
        SUPPLIER = 'supplier', 'Fornecedor'
        PROCESS = 'process', 'Processo'
        PRODUCT = 'product', 'Produto'
        REGULATORY = 'regulatory', 'Regulatório'
        FINANCIAL = 'financial', 'Financeiro'
        FISCAL = 'fiscal', 'Fiscal'
        OPERATIONS = 'operations', 'Operações'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        IN_TREATMENT = 'in_treatment', 'Em tratamento'
        MONITORING = 'monitoring', 'Em monitoramento'
        CLOSED = 'closed', 'Encerrado'
        CANCELLED = 'cancelled', 'Cancelado'

    risk_number = models.CharField('risco', max_length=80, blank=True)
    risk_category = models.CharField('categoria', max_length=32, choices=RiskCategory.choices)
    title = models.CharField('título', max_length=180)
    description = models.TextField('descrição')
    process_area = models.CharField('processo/área', max_length=140)
    process_ref = models.ForeignKey(
        'auxiliary.BusinessProcess',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='processo normalizado',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_risks',
        verbose_name='responsável',
    )
    due_date = models.DateField('prazo de tratamento')
    next_review_date = models.DateField('próxima revisão')
    status = models.CharField('status', max_length=32, choices=Status.choices, default=Status.DRAFT)
    identified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='identified_risks',
        null=True,
        blank=True,
        verbose_name='identificado por',
    )
    identified_at = models.DateTimeField('identificado em', default=timezone.now)
    treatment_started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='started_risk_treatments',
        null=True,
        blank=True,
        verbose_name='tratamento iniciado por',
    )
    treatment_started_at = models.DateTimeField('tratamento iniciado em', null=True, blank=True)
    monitoring_started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='started_risk_monitoring',
        null=True,
        blank=True,
        verbose_name='monitoramento iniciado por',
    )
    monitoring_started_at = models.DateTimeField('monitoramento iniciado em', null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='closed_risks',
        null=True,
        blank=True,
        verbose_name='encerrado por',
    )
    closed_at = models.DateTimeField('encerrado em', null=True, blank=True)
    closure_summary = models.TextField('resumo de encerramento', blank=True)
    cancel_reason = models.TextField('motivo do cancelamento', blank=True)
    initial_score = models.PositiveIntegerField('score inicial', default=0)
    initial_level = models.CharField(
        'nível inicial', max_length=24, choices=RiskLevel.choices, blank=True
    )
    residual_score = models.PositiveIntegerField('score residual', default=0)
    residual_level = models.CharField(
        'nível residual', max_length=24, choices=RiskLevel.choices, blank=True
    )

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['risk_number'], name='unique_risk_number'),
        ]
        indexes = [
            models.Index(fields=['risk_category', 'status']),
            models.Index(fields=['owner']),
            models.Index(fields=['due_date']),
            models.Index(fields=['next_review_date']),
            models.Index(fields=['initial_level']),
            models.Index(fields=['residual_level']),
            models.Index(fields=['risk_number']),
        ]
        verbose_name = 'risco'
        verbose_name_plural = 'riscos'

    def save(self, *args, **kwargs):
        if not self.risk_number:
            self.risk_number = _sequence_code(RiskRecord, 'risk_number', 'RSK')
        super().save(*args, **kwargs)

    @property
    def current_score(self):
        return self.residual_score or self.initial_score

    @property
    def current_level(self):
        return self.residual_level or self.initial_level

    def update_risk_scores(self):
        initial = (
            self.assessments.filter(assessment_type=RiskAssessment.AssessmentType.INITIAL)
            .order_by('-assessed_at', '-id')
            .first()
        )
        residual = (
            self.assessments.filter(assessment_type=RiskAssessment.AssessmentType.RESIDUAL)
            .order_by('-assessed_at', '-id')
            .first()
        )
        updates = []
        if initial:
            self.initial_score = initial.score
            self.initial_level = initial.risk_level
            updates.extend(['initial_score', 'initial_level'])
        if residual:
            self.residual_score = residual.score
            self.residual_level = residual.risk_level
            updates.extend(['residual_score', 'residual_level'])
        if updates:
            self.save(update_fields=[*updates, 'updated_at'])

    def start_treatment(self, user=None):
        if self.status != self.Status.DRAFT:
            raise ValidationError(
                {'status': 'Somente riscos em rascunho podem iniciar tratamento.'}
            )
        if not self.assessments.filter(
            assessment_type=RiskAssessment.AssessmentType.INITIAL
        ).exists():
            raise ValidationError({'assessments': 'Tratamento exige avaliação inicial do risco.'})
        self.status = self.Status.IN_TREATMENT
        self.treatment_started_by = user
        self.treatment_started_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=['status', 'treatment_started_by', 'treatment_started_at', 'updated_at']
        )

    def start_monitoring(self, user=None):
        if self.status != self.Status.IN_TREATMENT:
            raise ValidationError({'status': 'Monitoramento exige risco em tratamento.'})
        mandatory_actions = self.actions.filter(mandatory=True)
        if (
            not mandatory_actions.exists()
            or mandatory_actions.exclude(status=RiskMitigationAction.Status.COMPLETED).exists()
        ):
            raise ValidationError({'actions': 'Monitoramento exige ações obrigatórias concluídas.'})
        if not self.assessments.filter(
            assessment_type=RiskAssessment.AssessmentType.RESIDUAL
        ).exists():
            raise ValidationError(
                {'residual_risk': 'Monitoramento exige avaliação de risco residual.'}
            )
        self.status = self.Status.MONITORING
        self.monitoring_started_by = user
        self.monitoring_started_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=['status', 'monitoring_started_by', 'monitoring_started_at', 'updated_at']
        )

    def close(self, summary, user=None):
        if not summary:
            raise ValidationError({'closure_summary': 'Informe o resumo de encerramento.'})
        if self.status != self.Status.MONITORING:
            raise ValidationError({'status': 'Encerramento exige risco em monitoramento.'})
        if not self.reviews.filter(status=RiskReview.Status.COMPLETED).exists():
            raise ValidationError({'reviews': 'Encerramento exige ao menos uma revisão concluída.'})
        self.status = self.Status.CLOSED
        self.closure_summary = summary
        self.closed_by = user
        self.closed_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=['status', 'closure_summary', 'closed_by', 'closed_at', 'updated_at']
        )

    def cancel(self, reason):
        if not reason:
            raise ValidationError({'cancel_reason': 'Informe o motivo do cancelamento.'})
        if self.status == self.Status.CLOSED:
            raise ValidationError({'status': 'Risco encerrado não pode ser cancelado.'})
        self.status = self.Status.CANCELLED
        self.cancel_reason = reason
        self.save(update_fields=['status', 'cancel_reason', 'updated_at'])

    def generate_alerts(self):
        return RiskAlert.generate_for_risk(self)

    def clean(self):
        super().clean()
        errors = {}
        for field in (
            'owner',
            'identified_by',
            'treatment_started_by',
            'monitoring_started_by',
            'closed_by',
        ):
            pass
        if self.due_date and self.next_review_date and self.next_review_date < self.due_date:
            errors['next_review_date'] = (
                'A próxima revisão não pode ser anterior ao prazo de tratamento.'
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.risk_number


class RiskAssessment(SingleInstanceModel):
    RiskLevel = RiskLevelChoices

    class AssessmentType(models.TextChoices):
        INITIAL = 'initial', 'Inicial'
        RESIDUAL = 'residual', 'Residual'
        PERIODIC = 'periodic', 'Periódica'

    class Method(models.TextChoices):
        MATRIX = 'matrix', 'Matriz de risco'
        FMEA = 'fmea', 'FMEA'

    risk = models.ForeignKey(
        RiskRecord, on_delete=models.CASCADE, related_name='assessments', verbose_name='risco'
    )
    assessment_type = models.CharField('tipo', max_length=24, choices=AssessmentType.choices)
    method = models.CharField('método', max_length=24, choices=Method.choices)
    probability = models.PositiveSmallIntegerField('probabilidade')
    severity = models.PositiveSmallIntegerField('severidade')
    detectability = models.PositiveSmallIntegerField('detectabilidade', default=1)
    score = models.PositiveIntegerField('score', default=0)
    risk_level = models.CharField(
        'nível de risco', max_length=24, choices=RiskLevel.choices, blank=True
    )
    rationale = models.TextField('racional')
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='risk_assessments',
        verbose_name='avaliado por',
    )
    assessed_at = models.DateTimeField('avaliado em', default=timezone.now)

    class Meta:
        ordering = ['risk__risk_number', '-assessed_at']
        indexes = [
            models.Index(fields=['risk', 'assessment_type']),
            models.Index(fields=['method', 'risk_level']),
            models.Index(fields=['assessed_by']),
            models.Index(fields=['assessed_at']),
        ]
        verbose_name = 'avaliação de risco'
        verbose_name_plural = 'avaliações de risco'

    def save(self, *args, **kwargs):
        self.calculate_score()
        super().save(*args, **kwargs)
        if self.risk_id:
            self.risk.update_risk_scores()

    def calculate_score(self):
        multiplier = self.detectability if self.method == self.Method.FMEA else 1
        self.score = self.probability * self.severity * multiplier
        if self.method == self.Method.FMEA:
            if self.score >= 64:
                self.risk_level = self.RiskLevel.CRITICAL
            elif self.score >= 27:
                self.risk_level = self.RiskLevel.HIGH
            elif self.score >= 8:
                self.risk_level = self.RiskLevel.MEDIUM
            else:
                self.risk_level = self.RiskLevel.LOW
            return
        if self.score >= 20:
            self.risk_level = self.RiskLevel.CRITICAL
        elif self.score >= 12:
            self.risk_level = self.RiskLevel.HIGH
        elif self.score >= 6:
            self.risk_level = self.RiskLevel.MEDIUM
        else:
            self.risk_level = self.RiskLevel.LOW

    def clean(self):
        super().clean()
        errors = {}
        for field in ('probability', 'severity', 'detectability'):
            value = getattr(self, field)
            if value < 1 or value > 5:
                errors[field] = 'Informe valor entre 1 e 5.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.risk} - {self.get_assessment_type_display()}'


class RiskControl(SingleInstanceModel):
    class ControlType(models.TextChoices):
        PREVENTIVE = 'preventive', 'Preventivo'
        DETECTIVE = 'detective', 'Detectivo'
        CORRECTIVE = 'corrective', 'Corretivo'
        CONTINGENCY = 'contingency', 'Contingência'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Ativo'
        INEFFECTIVE = 'ineffective', 'Ineficaz'
        RETIRED = 'retired', 'Retirado'

    risk = models.ForeignKey(
        RiskRecord, on_delete=models.CASCADE, related_name='controls', verbose_name='risco'
    )
    control_type = models.CharField('tipo de controle', max_length=24, choices=ControlType.choices)
    title = models.CharField('título', max_length=180)
    description = models.TextField('descrição')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_risk_controls',
        verbose_name='responsável',
    )
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.ACTIVE
    )
    evidence_reference = models.CharField('evidência', max_length=255, blank=True)
    content_hash = models.CharField('hash do conteúdo', max_length=128, blank=True)

    class Meta:
        ordering = ['risk__risk_number', 'control_type', 'title']
        indexes = [
            models.Index(fields=['risk', 'status']),
            models.Index(fields=['control_type']),
            models.Index(fields=['owner']),
        ]
        verbose_name = 'controle de risco'
        verbose_name_plural = 'controles de risco'

    def clean(self):
        super().clean()
        errors = {}
        if bool(self.evidence_reference) != bool(self.content_hash):
            errors['content_hash'] = 'Evidência de controle exige referência e hash.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class RiskMitigationAction(SingleInstanceModel):
    class ActionType(models.TextChoices):
        MITIGATION = 'mitigation', 'Mitigação'
        CONTINGENCY = 'contingency', 'Contingência'
        MONITORING = 'monitoring', 'Monitoramento'
        REVIEW = 'review', 'Revisão'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        IN_PROGRESS = 'in_progress', 'Em andamento'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'

    risk = models.ForeignKey(
        RiskRecord, on_delete=models.CASCADE, related_name='actions', verbose_name='risco'
    )
    action_type = models.CharField('tipo de ação', max_length=24, choices=ActionType.choices)
    title = models.CharField('título', max_length=180)
    description = models.TextField('descrição')
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='risk_actions',
        verbose_name='responsável',
    )
    due_date = models.DateField('prazo')
    mandatory = models.BooleanField('obrigatória', default=True)
    evidence_required = models.BooleanField('exige evidência', default=True)
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.PENDING
    )
    completion_notes = models.TextField('observações de conclusão', blank=True)
    evidence_reference = models.CharField('evidência', max_length=255, blank=True)
    content_hash = models.CharField('hash do conteúdo', max_length=128, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='completed_risk_actions',
        null=True,
        blank=True,
        verbose_name='concluída por',
    )
    completed_at = models.DateTimeField('concluída em', null=True, blank=True)

    class Meta:
        ordering = ['risk__risk_number', 'due_date']
        indexes = [
            models.Index(fields=['risk', 'status']),
            models.Index(fields=['responsible', 'due_date']),
            models.Index(fields=['mandatory']),
        ]
        verbose_name = 'ação de risco'
        verbose_name_plural = 'ações de risco'

    def start(self):
        if self.status != self.Status.PENDING:
            raise ValidationError({'status': 'Somente ações pendentes podem iniciar.'})
        self.status = self.Status.IN_PROGRESS
        self.save(update_fields=['status', 'updated_at'])

    def complete(self, user=None, completion_notes='', evidence_reference='', content_hash=''):
        if not completion_notes:
            raise ValidationError({'completion_notes': 'Informe as observações de conclusão.'})
        if self.evidence_required and (not evidence_reference or not content_hash):
            raise ValidationError(
                {'evidence_reference': 'Ação com evidência obrigatória exige referência e hash.'}
            )
        self.status = self.Status.COMPLETED
        self.completed_by = user
        self.completed_at = timezone.now()
        self.completion_notes = completion_notes
        self.evidence_reference = evidence_reference
        self.content_hash = content_hash
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'completed_by',
                'completed_at',
                'completion_notes',
                'evidence_reference',
                'content_hash',
                'updated_at',
            ]
        )

    def clean(self):
        super().clean()
        errors = {}
        if self.status == self.Status.COMPLETED and (
            not self.completion_notes or not self.completed_by_id or not self.completed_at
        ):
            errors['completion_notes'] = 'Ação concluída exige responsável, data e observações.'
        if (
            self.status == self.Status.COMPLETED
            and self.evidence_required
            and (not self.evidence_reference or not self.content_hash)
        ):
            errors['evidence_reference'] = 'Ação com evidência obrigatória exige referência e hash.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class RiskLink(SingleInstanceModel):
    class LinkType(models.TextChoices):
        PROCESS = 'process', 'Processo'
        PRODUCT = 'product', 'Produto'
        DOCUMENT = 'document', 'Documento'
        DEVIATION = 'deviation', 'Desvio'
        CAPA = 'capa', 'CAPA'
        CHANGE = 'change', 'Mudança'
        AUDIT = 'audit', 'Auditoria'
        SUPPLIER = 'supplier', 'Fornecedor'
        EQUIPMENT = 'equipment', 'Equipamento'

    risk = models.ForeignKey(
        RiskRecord, on_delete=models.CASCADE, related_name='links', verbose_name='risco'
    )
    link_type = models.CharField('tipo de vínculo', max_length=24, choices=LinkType.choices)
    product = models.ForeignKey(
        'masters.Product',
        on_delete=models.PROTECT,
        related_name='risk_links',
        null=True,
        blank=True,
        verbose_name='produto',
    )
    document = models.ForeignKey(
        'documents.ControlledDocument',
        on_delete=models.PROTECT,
        related_name='risk_links',
        null=True,
        blank=True,
        verbose_name='documento',
    )
    deviation_event = models.ForeignKey(
        'deviations.QualityEvent',
        on_delete=models.PROTECT,
        related_name='risk_links',
        null=True,
        blank=True,
        verbose_name='desvio',
    )
    capa = models.ForeignKey(
        'capa.CapaRecord',
        on_delete=models.PROTECT,
        related_name='risk_links',
        null=True,
        blank=True,
        verbose_name='CAPA',
    )
    change_control = models.ForeignKey(
        'changes.ChangeControl',
        on_delete=models.PROTECT,
        related_name='risk_links',
        null=True,
        blank=True,
        verbose_name='mudança',
    )
    audit = models.ForeignKey(
        'audits.AuditPlan',
        on_delete=models.PROTECT,
        related_name='risk_links',
        null=True,
        blank=True,
        verbose_name='auditoria',
    )
    supplier = models.ForeignKey(
        'masters.BusinessPartner',
        on_delete=models.PROTECT,
        related_name='risk_links',
        null=True,
        blank=True,
        verbose_name='fornecedor',
    )
    reference_code = models.CharField('referência', max_length=120, blank=True)
    impact_description = models.TextField('descrição do impacto')

    class Meta:
        ordering = ['risk__risk_number', 'link_type']
        indexes = [
            models.Index(fields=['risk', 'link_type']),
            models.Index(fields=['product']),
            models.Index(fields=['document']),
            models.Index(fields=['deviation_event']),
            models.Index(fields=['capa']),
            models.Index(fields=['change_control']),
            models.Index(fields=['audit']),
            models.Index(fields=['supplier']),
        ]
        verbose_name = 'vínculo de risco'
        verbose_name_plural = 'vínculos de risco'

    def clean(self):
        super().clean()
        errors = {}
        for field in (
            'risk',
            'product',
            'document',
            'deviation_event',
            'capa',
            'change_control',
            'audit',
            'supplier',
        ):
            pass
        required_by_type = {
            self.LinkType.PRODUCT: ('product', self.product_id),
            self.LinkType.DOCUMENT: ('document', self.document_id),
            self.LinkType.DEVIATION: ('deviation_event', self.deviation_event_id),
            self.LinkType.CAPA: ('capa', self.capa_id),
            self.LinkType.CHANGE: ('change_control', self.change_control_id),
            self.LinkType.AUDIT: ('audit', self.audit_id),
            self.LinkType.SUPPLIER: ('supplier', self.supplier_id),
        }
        if self.link_type in required_by_type:
            field, value = required_by_type[self.link_type]
            if not value:
                errors[field] = 'Informe o cadastro relacionado ao tipo de vínculo.'
        if (
            self.link_type in {self.LinkType.PROCESS, self.LinkType.EQUIPMENT}
            and not self.reference_code
        ):
            errors['reference_code'] = 'Informe a referência do vínculo.'
        if self.supplier and self.supplier.partner_type not in {
            BusinessPartner.PartnerType.SUPPLIER,
            BusinessPartner.PartnerType.MANUFACTURER,
            BusinessPartner.PartnerType.OUTSOURCED_LAB,
        }:
            errors['supplier'] = (
                'Fornecedor vinculado deve ser fornecedor, fabricante ou laboratório terceirizado.'
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.risk} - {self.get_link_type_display()}'


class RiskReview(SingleInstanceModel):
    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planejada'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'

    risk = models.ForeignKey(
        RiskRecord, on_delete=models.CASCADE, related_name='reviews', verbose_name='risco'
    )
    planned_date = models.DateField('data planejada')
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='risk_reviews',
        verbose_name='revisor',
    )
    review_scope = models.TextField('escopo da revisão')
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.PLANNED
    )
    result = models.TextField('resultado', blank=True)
    next_review_date = models.DateField('próxima revisão', null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='completed_risk_reviews',
        null=True,
        blank=True,
        verbose_name='concluída por',
    )
    completed_at = models.DateTimeField('concluída em', null=True, blank=True)

    class Meta:
        ordering = ['risk__risk_number', 'planned_date']
        indexes = [
            models.Index(fields=['risk', 'status']),
            models.Index(fields=['reviewer', 'planned_date']),
            models.Index(fields=['next_review_date']),
        ]
        verbose_name = 'revisão de risco'
        verbose_name_plural = 'revisões de risco'

    def complete(self, result, next_review_date, user=None):
        if not result:
            raise ValidationError({'result': 'Informe o resultado da revisão.'})
        if not next_review_date:
            raise ValidationError({'next_review_date': 'Informe a próxima revisão.'})
        self.status = self.Status.COMPLETED
        self.result = result
        self.next_review_date = next_review_date
        self.completed_by = user or self.completed_by
        self.completed_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'result',
                'next_review_date',
                'completed_by',
                'completed_at',
                'updated_at',
            ]
        )
        self.risk.next_review_date = next_review_date
        self.risk.save(update_fields=['next_review_date', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        for field in ('reviewer', 'completed_by'):
            pass
        if self.status == self.Status.COMPLETED and (
            not self.result
            or not self.next_review_date
            or not self.completed_by_id
            or not self.completed_at
        ):
            errors['result'] = (
                'Revisão concluída exige resultado, próxima revisão, responsável e data.'
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.risk} - {self.planned_date}'


class RiskAlert(SingleInstanceModel):
    class AlertType(models.TextChoices):
        CRITICAL_RISK = 'critical_risk', 'Risco crítico'
        OVERDUE_ACTION = 'overdue_action', 'Ação atrasada'
        REVIEW_DUE = 'review_due', 'Revisão vencida'

    class Status(models.TextChoices):
        OPEN = 'open', 'Aberto'
        SENT = 'sent', 'Enviado'
        ACKNOWLEDGED = 'acknowledged', 'Reconhecido'

    risk = models.ForeignKey(
        RiskRecord, on_delete=models.CASCADE, related_name='alerts', verbose_name='risco'
    )
    action = models.ForeignKey(
        RiskMitigationAction,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True,
        verbose_name='ação',
    )
    alert_type = models.CharField('tipo', max_length=32, choices=AlertType.choices)
    severity = models.CharField('severidade', max_length=24, choices=RiskLevelChoices.choices)
    severity_ref = models.ForeignKey(
        'auxiliary.ImpactLevel',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='severidade normalizada',
    )
    message = models.TextField('mensagem')
    due_date = models.DateField('prazo', null=True, blank=True)
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.OPEN)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='acknowledged_risk_alerts',
        null=True,
        blank=True,
        verbose_name='reconhecido por',
    )
    acknowledged_at = models.DateTimeField('reconhecido em', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['risk', 'alert_type', 'status']),
            models.Index(fields=['action']),
            models.Index(fields=['due_date']),
        ]
        verbose_name = 'alerta de risco'
        verbose_name_plural = 'alertas de risco'

    @classmethod
    def generate_all(cls):
        total = 0
        for risk in RiskRecord.objects.exclude(
            status__in=[RiskRecord.Status.CLOSED, RiskRecord.Status.CANCELLED]
        ):
            total += cls.generate_for_risk(risk)
        return total

    @classmethod
    def generate_for_risk(cls, risk):
        generated = 0
        if (
            risk.current_level == RiskLevelChoices.CRITICAL
            and not cls.objects.filter(
                risk=risk,
                alert_type=cls.AlertType.CRITICAL_RISK,
                status=cls.Status.OPEN,
            ).exists()
        ):
            cls.objects.create(
                risk=risk,
                alert_type=cls.AlertType.CRITICAL_RISK,
                severity=RiskLevelChoices.CRITICAL,
                message=f'Risco crítico: {risk.title}',
                due_date=risk.next_review_date,
            )
            generated += 1
        overdue_actions = risk.actions.filter(due_date__lt=timezone.localdate()).exclude(
            status__in=[
                RiskMitigationAction.Status.COMPLETED,
                RiskMitigationAction.Status.CANCELLED,
            ]
        )
        for action in overdue_actions:
            if cls.objects.filter(
                risk=risk,
                action=action,
                alert_type=cls.AlertType.OVERDUE_ACTION,
                status=cls.Status.OPEN,
            ).exists():
                continue
            cls.objects.create(
                risk=risk,
                action=action,
                alert_type=cls.AlertType.OVERDUE_ACTION,
                severity=RiskLevelChoices.HIGH,
                message=f'Ação de risco atrasada: {action.title}',
                due_date=action.due_date,
            )
            generated += 1
        if (
            risk.next_review_date < timezone.localdate()
            and not cls.objects.filter(
                risk=risk,
                alert_type=cls.AlertType.REVIEW_DUE,
                status=cls.Status.OPEN,
            ).exists()
        ):
            cls.objects.create(
                risk=risk,
                alert_type=cls.AlertType.REVIEW_DUE,
                severity=RiskLevelChoices.MEDIUM,
                message=f'Revisão de risco vencida: {risk.title}',
                due_date=risk.next_review_date,
            )
            generated += 1
        return generated

    def acknowledge(self, user=None):
        self.status = self.Status.ACKNOWLEDGED
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        if self.action and self.risk and self.action.risk_id != self.risk_id:
            errors['action'] = 'A ação deve pertencer ao risco informado.'
        if self.status == self.Status.ACKNOWLEDGED and (
            not self.acknowledged_by_id or not self.acknowledged_at
        ):
            errors['acknowledged_by'] = 'Reconhecimento exige usuário e data.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.get_alert_type_display()} - {self.risk}'
