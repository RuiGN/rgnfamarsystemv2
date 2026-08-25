from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from base.models import SingleInstanceModel
from base.normalized_locations import validate_normalized_location
from base.sequences import sequence_code
from masters.models import BusinessPartner


def _sequence_code(model, *args):
    if len(args) == 3:
        _legacy_scope, field_name, prefix = args
    else:
        field_name, prefix = args
    return sequence_code(model, field_name, prefix)


class PharmacovigilanceCase(SingleInstanceModel):
    class CaseType(models.TextChoices):
        ADVERSE_EVENT = 'adverse_event', 'Evento adverso'
        TECHNICAL_COMPLAINT = 'technical_complaint', 'Queixa técnica'
        SUSPECTED_DEVIATION = 'suspected_deviation', 'Suspeita de desvio'
        PATIENT_COMPLAINT = 'patient_complaint', 'Reclamação de paciente'
        SAFETY_NOTIFICATION = 'safety_notification', 'Notificação de segurança'

    class Source(models.TextChoices):
        PATIENT = 'patient', 'Paciente'
        HEALTHCARE_PROFESSIONAL = 'healthcare_professional', 'Profissional de saúde'
        CUSTOMER = 'customer', 'Cliente'
        DISTRIBUTOR = 'distributor', 'Distribuidor'
        AUTHORITY = 'authority', 'Autoridade sanitária'
        INTERNAL = 'internal', 'Interna'
        LITERATURE = 'literature', 'Literatura'
        OTHER = 'other', 'Outra'

    class Seriousness(models.TextChoices):
        NON_SERIOUS = 'non_serious', 'Não sério'
        SERIOUS = 'serious', 'Sério'

    class Severity(models.TextChoices):
        LOW = 'low', 'Baixa'
        MEDIUM = 'medium', 'Média'
        HIGH = 'high', 'Alta'
        CRITICAL = 'critical', 'Crítica'

    class Outcome(models.TextChoices):
        RECOVERED = 'recovered', 'Recuperado'
        RECOVERING = 'recovering', 'Em recuperação'
        NOT_RECOVERED = 'not_recovered', 'Não recuperado'
        FATAL = 'fatal', 'Fatal'
        UNKNOWN = 'unknown', 'Desconhecido'
        NOT_APPLICABLE = 'not_applicable', 'Não aplicável'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        TRIAGE = 'triage', 'Triagem'
        INVESTIGATION = 'investigation', 'Investigação'
        PENDING_ACTIONS = 'pending_actions', 'Ações pendentes'
        CLOSED = 'closed', 'Encerrado'
        CANCELLED = 'cancelled', 'Cancelado'

    case_number = models.CharField('caso', max_length=80, blank=True)
    case_type = models.CharField('tipo', max_length=32, choices=CaseType.choices)
    source = models.CharField('fonte', max_length=40, choices=Source.choices)
    product = models.ForeignKey(
        'masters.Product',
        on_delete=models.PROTECT,
        related_name='pharmacovigilance_cases',
        null=True,
        blank=True,
        verbose_name='produto',
    )
    stock_lot = models.ForeignKey(
        'inventory.StockLot',
        on_delete=models.PROTECT,
        related_name='pharmacovigilance_cases',
        null=True,
        blank=True,
        verbose_name='lote',
    )
    customer = models.ForeignKey(
        'masters.BusinessPartner',
        on_delete=models.PROTECT,
        related_name='pharmacovigilance_cases',
        null=True,
        blank=True,
        verbose_name='cliente',
    )
    patient_identifier_hash = models.CharField(
        'hash do paciente anonimizado', max_length=128, blank=True
    )
    patient_age = models.PositiveSmallIntegerField('idade do paciente', null=True, blank=True)
    patient_gender = models.CharField('gênero do paciente', max_length=32, blank=True)
    country = models.CharField('país', max_length=80)
    country_ref = models.ForeignKey(
        'auxiliary.Country',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='país normalizado',
    )
    state_ref = models.ForeignKey(
        'auxiliary.StateProvince',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='UF',
    )
    city_ref = models.ForeignKey(
        'auxiliary.City',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='Cidade',
    )
    seriousness = models.CharField('seriedade', max_length=24, choices=Seriousness.choices)
    severity = models.CharField('gravidade', max_length=24, choices=Severity.choices)
    severity_ref = models.ForeignKey(
        'auxiliary.ImpactLevel',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='gravidade normalizada',
    )
    outcome = models.CharField('desfecho', max_length=24, choices=Outcome.choices)
    description = models.TextField('descrição')
    event_started_at = models.DateTimeField('início do evento', null=True, blank=True)
    event_reported_at = models.DateTimeField('data do relato')
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_pharmacovigilance_cases',
        verbose_name='responsável',
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reported_pharmacovigilance_cases',
        null=True,
        blank=True,
        verbose_name='relatado por',
    )
    status = models.CharField('status', max_length=32, choices=Status.choices, default=Status.DRAFT)
    triaged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='triaged_pharmacovigilance_cases',
        null=True,
        blank=True,
        verbose_name='triado por',
    )
    triaged_at = models.DateTimeField('triado em', null=True, blank=True)
    investigation_started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='started_pharmacovigilance_investigations',
        null=True,
        blank=True,
        verbose_name='investigação iniciada por',
    )
    investigation_started_at = models.DateTimeField(
        'investigação iniciada em', null=True, blank=True
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='closed_pharmacovigilance_cases',
        null=True,
        blank=True,
        verbose_name='encerrado por',
    )
    closed_at = models.DateTimeField('encerrado em', null=True, blank=True)
    closure_summary = models.TextField('resumo de encerramento', blank=True)
    cancel_reason = models.TextField('motivo do cancelamento', blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['case_number'], name='unique_pharmacovigilance_case_number'
            ),
        ]
        indexes = [
            models.Index(fields=['case_type', 'status']),
            models.Index(fields=['product']),
            models.Index(fields=['stock_lot']),
            models.Index(fields=['customer']),
            models.Index(fields=['seriousness', 'severity']),
            models.Index(fields=['event_reported_at']),
            models.Index(fields=['responsible']),
            models.Index(fields=['case_number']),
        ]
        verbose_name = 'caso de farmacovigilância'
        verbose_name_plural = 'casos de farmacovigilância'

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = _sequence_code(PharmacovigilanceCase, 'case_number', 'PVCASE')
        super().save(*args, **kwargs)

    def start_triage(self, user=None):
        if self.status != self.Status.DRAFT:
            raise ValidationError({'status': 'Somente casos em rascunho podem iniciar triagem.'})
        self.status = self.Status.TRIAGE
        self.triaged_by = user or self.triaged_by
        self.triaged_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'triaged_by', 'triaged_at', 'updated_at'])

    def start_investigation(self, user=None):
        if self.status != self.Status.TRIAGE:
            raise ValidationError({'status': 'Investigação exige caso em triagem.'})
        if not self.classifications.exists():
            raise ValidationError({'classifications': 'Investigação exige classificação do caso.'})
        self.status = self.Status.INVESTIGATION
        self.investigation_started_by = user or self.investigation_started_by
        self.investigation_started_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'investigation_started_by',
                'investigation_started_at',
                'updated_at',
            ]
        )

    def close(self, summary, user=None):
        if not summary:
            raise ValidationError({'closure_summary': 'Informe o resumo de encerramento.'})
        if not self.classifications.exists():
            raise ValidationError({'classifications': 'Encerramento exige classificação do caso.'})
        if not self.causality_assessments.exists():
            raise ValidationError(
                {'causality_assessments': 'Encerramento exige avaliação de causalidade.'}
            )
        if not self.investigations.filter(
            status=PharmacovigilanceInvestigation.Status.COMPLETED
        ).exists():
            raise ValidationError({'investigations': 'Encerramento exige investigação concluída.'})
        if (
            not self.actions.exists()
            or self.actions.filter(mandatory=True)
            .exclude(status=PharmacovigilanceAction.Status.COMPLETED)
            .exists()
        ):
            raise ValidationError({'actions': 'Encerramento exige ações obrigatórias concluídas.'})
        if not self.reports.filter(status=PharmacovigilanceSafetyReport.Status.GENERATED).exists():
            raise ValidationError({'reports': 'Encerramento exige relatório de segurança gerado.'})
        if self.status not in {self.Status.INVESTIGATION, self.Status.PENDING_ACTIONS}:
            raise ValidationError(
                {'status': 'Encerramento exige caso em investigação ou ações pendentes.'}
            )
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
            raise ValidationError({'status': 'Caso encerrado não pode ser cancelado.'})
        self.status = self.Status.CANCELLED
        self.cancel_reason = reason
        self.save(update_fields=['status', 'cancel_reason', 'updated_at'])

    def clean(self):
        super().clean()
        validate_normalized_location(self)
        errors = {}
        for field in ('product', 'stock_lot', 'customer'):
            pass
        for field in (
            'responsible',
            'reported_by',
            'triaged_by',
            'investigation_started_by',
            'closed_by',
        ):
            pass
        if self.stock_lot and self.product and self.stock_lot.product_id != self.product_id:
            errors['stock_lot'] = 'O lote deve pertencer ao produto informado.'
        if self.customer and self.customer.partner_type != BusinessPartner.PartnerType.CUSTOMER:
            errors['customer'] = 'O cliente deve usar parceiro de negócio do tipo cliente.'
        if self.patient_age and self.patient_age > 130:
            errors['patient_age'] = 'Idade do paciente fora do intervalo esperado.'
        if (
            self.event_started_at
            and self.event_reported_at
            and self.event_started_at > self.event_reported_at
        ):
            errors['event_started_at'] = 'O início do evento não pode ser posterior ao relato.'
        if self.status == self.Status.CLOSED and (
            not self.closure_summary or not self.closed_by_id or not self.closed_at
        ):
            errors['closure_summary'] = 'Caso encerrado exige resumo, responsável e data.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.case_number


class PharmacovigilanceClassification(SingleInstanceModel):
    class Category(models.TextChoices):
        ADVERSE_REACTION = 'adverse_reaction', 'Reação adversa'
        QUALITY_DEFECT = 'quality_defect', 'Defeito de qualidade'
        MEDICATION_ERROR = 'medication_error', 'Erro de medicação'
        LACK_OF_EFFICACY = 'lack_of_efficacy', 'Falta de eficácia'
        OFF_LABEL_USE = 'off_label_use', 'Uso off-label'
        OVERDOSE = 'overdose', 'Sobredose'
        OTHER = 'other', 'Outra'

    class Seriousness(models.TextChoices):
        NON_SERIOUS = 'non_serious', 'Não sério'
        SERIOUS = 'serious', 'Sério'

    class Expectedness(models.TextChoices):
        EXPECTED = 'expected', 'Esperado'
        UNEXPECTED = 'unexpected', 'Inesperado'
        UNKNOWN = 'unknown', 'Desconhecido'

    case = models.ForeignKey(
        PharmacovigilanceCase,
        on_delete=models.CASCADE,
        related_name='classifications',
        verbose_name='caso',
    )
    category = models.CharField('categoria', max_length=32, choices=Category.choices)
    seriousness = models.CharField('seriedade', max_length=24, choices=Seriousness.choices)
    expectedness = models.CharField('previsibilidade', max_length=24, choices=Expectedness.choices)
    listedness_reference = models.CharField(
        'referência de bula/listagem', max_length=180, blank=True
    )
    classified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='classified_pharmacovigilance_cases',
        null=True,
        blank=True,
        verbose_name='classificado por',
    )
    classified_at = models.DateTimeField('classificado em', default=timezone.now)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['case__case_number', '-classified_at']
        indexes = [
            models.Index(fields=['case']),
            models.Index(fields=['category']),
            models.Index(fields=['seriousness']),
            models.Index(fields=['expectedness']),
        ]
        verbose_name = 'classificação de farmacovigilância'
        verbose_name_plural = 'classificações de farmacovigilância'

    def clean(self):
        super().clean()
        errors = {}
        if self.expectedness == self.Expectedness.UNEXPECTED and not self.listedness_reference:
            errors['listedness_reference'] = 'Evento inesperado exige referência de listagem/bula.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.case} - {self.get_category_display()}'


class PharmacovigilanceCausalityAssessment(SingleInstanceModel):
    class Method(models.TextChoices):
        WHO_UMC = 'who_umc', 'WHO-UMC'
        NARANJO = 'naranjo', 'Naranjo'
        EXPERT_JUDGMENT = 'expert_judgment', 'Julgamento especialista'

    class Result(models.TextChoices):
        CERTAIN = 'certain', 'Certa'
        PROBABLE = 'probable', 'Provável'
        POSSIBLE = 'possible', 'Possível'
        UNLIKELY = 'unlikely', 'Improvável'
        UNCLASSIFIED = 'unclassified', 'Não classificada'

    case = models.ForeignKey(
        PharmacovigilanceCase,
        on_delete=models.CASCADE,
        related_name='causality_assessments',
        verbose_name='caso',
    )
    method = models.CharField('método', max_length=32, choices=Method.choices)
    result = models.CharField('resultado', max_length=24, choices=Result.choices)
    rationale = models.TextField('justificativa')
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assessed_pharmacovigilance_causality',
        null=True,
        blank=True,
        verbose_name='avaliado por',
    )
    assessed_at = models.DateTimeField('avaliado em', default=timezone.now)

    class Meta:
        ordering = ['case__case_number', '-assessed_at']
        indexes = [
            models.Index(fields=['case']),
            models.Index(fields=['method']),
            models.Index(fields=['result']),
        ]
        verbose_name = 'avaliação de causalidade'
        verbose_name_plural = 'avaliações de causalidade'

    def clean(self):
        super().clean()
        errors = {}
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.case} - {self.get_result_display()}'


class PharmacovigilanceInvestigation(SingleInstanceModel):
    class Status(models.TextChoices):
        OPEN = 'open', 'Aberta'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'

    case = models.ForeignKey(
        PharmacovigilanceCase,
        on_delete=models.CASCADE,
        related_name='investigations',
        verbose_name='caso',
    )
    summary = models.TextField('resumo da investigação')
    root_cause = models.TextField('causa raiz')
    conclusion = models.TextField('conclusão')
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_pharmacovigilance_investigations',
        verbose_name='responsável',
    )
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.OPEN)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='completed_pharmacovigilance_investigations',
        null=True,
        blank=True,
        verbose_name='concluída por',
    )
    completed_at = models.DateTimeField('concluída em', null=True, blank=True)

    class Meta:
        ordering = ['case__case_number', '-created_at']
        indexes = [
            models.Index(fields=['case', 'status']),
            models.Index(fields=['responsible']),
        ]
        verbose_name = 'investigação de farmacovigilância'
        verbose_name_plural = 'investigações de farmacovigilância'

    def complete(self, user=None):
        if not self.summary or not self.root_cause or not self.conclusion:
            raise ValidationError({'conclusion': 'Conclusão exige resumo, causa raiz e conclusão.'})
        self.status = self.Status.COMPLETED
        self.completed_by = user or self.completed_by
        self.completed_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'completed_by', 'completed_at', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        for field in ('responsible', 'completed_by'):
            pass
        if self.status == self.Status.COMPLETED and (
            not self.completed_by_id or not self.completed_at
        ):
            errors['completed_by'] = 'Investigação concluída exige responsável e data.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.case} - {self.get_status_display()}'


class PharmacovigilanceAction(SingleInstanceModel):
    class ActionType(models.TextChoices):
        CAPA = 'capa', 'CAPA'
        DEVIATION = 'deviation', 'Desvio'
        REGULATORY_NOTIFICATION = 'regulatory_notification', 'Notificação regulatória'
        LABELING_CHANGE = 'labeling_change', 'Alteração de bula/rotulagem'
        RECALL = 'recall', 'Recolhimento'
        COMMUNICATION = 'communication', 'Comunicação'
        MONITORING = 'monitoring', 'Monitoramento'
        OTHER = 'other', 'Outra'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        IN_PROGRESS = 'in_progress', 'Em andamento'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'

    action_number = models.CharField('ação', max_length=80, blank=True)
    case = models.ForeignKey(
        PharmacovigilanceCase, on_delete=models.CASCADE, related_name='actions', verbose_name='caso'
    )
    action_type = models.CharField('tipo', max_length=32, choices=ActionType.choices)
    title = models.CharField('título', max_length=180)
    description = models.TextField('descrição')
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_pharmacovigilance_actions',
        verbose_name='responsável',
    )
    due_date = models.DateField('prazo')
    mandatory = models.BooleanField('obrigatória', default=True)
    evidence_required = models.BooleanField('exige evidência', default=True)
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.PENDING
    )
    completion_notes = models.TextField('notas de conclusão', blank=True)
    evidence_reference = models.CharField('evidência', max_length=255, blank=True)
    content_hash = models.CharField('hash do conteúdo', max_length=128, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='completed_pharmacovigilance_actions',
        null=True,
        blank=True,
        verbose_name='concluída por',
    )
    completed_at = models.DateTimeField('concluída em', null=True, blank=True)

    class Meta:
        ordering = ['case__case_number', 'due_date']
        constraints = [
            models.UniqueConstraint(
                fields=['action_number'],
                name='unique_pharmacovigilance_action_number',
            ),
        ]
        indexes = [
            models.Index(fields=['case', 'status']),
            models.Index(fields=['action_type', 'status']),
            models.Index(fields=['responsible', 'due_date']),
            models.Index(fields=['action_number']),
        ]
        verbose_name = 'ação de farmacovigilância'
        verbose_name_plural = 'ações de farmacovigilância'

    def save(self, *args, **kwargs):
        if not self.action_number:
            self.action_number = _sequence_code(
                PharmacovigilanceAction, 'action_number', 'PVACTION'
            )
        super().save(*args, **kwargs)

    def start(self):
        if self.status != self.Status.PENDING:
            raise ValidationError({'status': 'Somente ações pendentes podem ser iniciadas.'})
        self.status = self.Status.IN_PROGRESS
        self.save(update_fields=['status', 'updated_at'])

    def complete(self, completion_notes, evidence_reference='', content_hash='', user=None):
        if not completion_notes:
            raise ValidationError({'completion_notes': 'Informe as notas de conclusão.'})
        if self.evidence_required and (not evidence_reference or not content_hash):
            raise ValidationError({'evidence_reference': 'Conclusão exige evidência e hash.'})
        self.status = self.Status.COMPLETED
        self.completion_notes = completion_notes
        self.evidence_reference = evidence_reference
        self.content_hash = content_hash
        self.completed_by = user
        self.completed_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'completion_notes',
                'evidence_reference',
                'content_hash',
                'completed_by',
                'completed_at',
                'updated_at',
            ]
        )

    def clean(self):
        super().clean()
        errors = {}
        for field in ('responsible', 'completed_by'):
            pass
        if self.status == self.Status.COMPLETED:
            if not self.completion_notes or not self.completed_by_id or not self.completed_at:
                errors['completion_notes'] = 'Ação concluída exige notas, responsável e data.'
            if self.evidence_required and (not self.evidence_reference or not self.content_hash):
                errors['evidence_reference'] = (
                    'Ação com evidência obrigatória exige evidência e hash.'
                )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.action_number


class PharmacovigilanceLink(SingleInstanceModel):
    class LinkType(models.TextChoices):
        COMPLAINT = 'complaint', 'Reclamação'
        DEVIATION = 'deviation', 'Desvio'
        CAPA = 'capa', 'CAPA'
        RECALL = 'recall', 'Recolhimento'
        LOT = 'lot', 'Lote'
        CUSTOMER = 'customer', 'Cliente'
        PRODUCT = 'product', 'Produto'
        REGULATORY_DOSSIER = 'regulatory_dossier', 'Dossiê regulatório'
        DOCUMENT = 'document', 'Documento'

    case = models.ForeignKey(
        PharmacovigilanceCase, on_delete=models.CASCADE, related_name='links', verbose_name='caso'
    )
    link_type = models.CharField('tipo de vínculo', max_length=32, choices=LinkType.choices)
    customer_complaint = models.ForeignKey(
        'crm.CustomerComplaint',
        on_delete=models.PROTECT,
        related_name='pharmacovigilance_links',
        null=True,
        blank=True,
        verbose_name='reclamação',
    )
    deviation_event = models.ForeignKey(
        'deviations.QualityEvent',
        on_delete=models.PROTECT,
        related_name='pharmacovigilance_links',
        null=True,
        blank=True,
        verbose_name='desvio',
    )
    capa = models.ForeignKey(
        'capa.CapaRecord',
        on_delete=models.PROTECT,
        related_name='pharmacovigilance_links',
        null=True,
        blank=True,
        verbose_name='CAPA',
    )
    stock_lot = models.ForeignKey(
        'inventory.StockLot',
        on_delete=models.PROTECT,
        related_name='pharmacovigilance_links',
        null=True,
        blank=True,
        verbose_name='lote',
    )
    customer = models.ForeignKey(
        'masters.BusinessPartner',
        on_delete=models.PROTECT,
        related_name='pharmacovigilance_links',
        null=True,
        blank=True,
        verbose_name='cliente',
    )
    product = models.ForeignKey(
        'masters.Product',
        on_delete=models.PROTECT,
        related_name='pharmacovigilance_links',
        null=True,
        blank=True,
        verbose_name='produto',
    )
    regulatory_dossier = models.ForeignKey(
        'regulatory.RegulatoryDossier',
        on_delete=models.PROTECT,
        related_name='pharmacovigilance_links',
        null=True,
        blank=True,
        verbose_name='dossiê regulatório',
    )
    document = models.ForeignKey(
        'documents.ControlledDocument',
        on_delete=models.PROTECT,
        related_name='pharmacovigilance_links',
        null=True,
        blank=True,
        verbose_name='documento',
    )
    reference_code = models.CharField('referência', max_length=120, blank=True)
    description = models.TextField('descrição')

    class Meta:
        ordering = ['case__case_number', 'link_type']
        indexes = [
            models.Index(fields=['case', 'link_type']),
            models.Index(fields=['customer_complaint']),
            models.Index(fields=['deviation_event']),
            models.Index(fields=['capa']),
            models.Index(fields=['stock_lot']),
            models.Index(fields=['customer']),
            models.Index(fields=['product']),
            models.Index(fields=['regulatory_dossier']),
            models.Index(fields=['document']),
            models.Index(fields=['reference_code']),
        ]
        verbose_name = 'vínculo de farmacovigilância'
        verbose_name_plural = 'vínculos de farmacovigilância'

    def clean(self):
        super().clean()
        errors = {}
        for field in (
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
        required_by_type = {
            self.LinkType.COMPLAINT: ('customer_complaint', self.customer_complaint_id),
            self.LinkType.DEVIATION: ('deviation_event', self.deviation_event_id),
            self.LinkType.CAPA: ('capa', self.capa_id),
            self.LinkType.LOT: ('stock_lot', self.stock_lot_id),
            self.LinkType.CUSTOMER: ('customer', self.customer_id),
            self.LinkType.PRODUCT: ('product', self.product_id),
            self.LinkType.REGULATORY_DOSSIER: ('regulatory_dossier', self.regulatory_dossier_id),
            self.LinkType.DOCUMENT: ('document', self.document_id),
        }
        if self.link_type in required_by_type:
            field, value = required_by_type[self.link_type]
            if not value:
                errors[field] = 'Informe o cadastro relacionado ao tipo de vínculo.'
        if self.link_type == self.LinkType.RECALL and not self.reference_code:
            errors['reference_code'] = 'Informe a referência do recolhimento.'
        if self.stock_lot and self.product and self.stock_lot.product_id != self.product_id:
            errors['stock_lot'] = 'O lote deve pertencer ao produto informado.'
        if self.customer and self.customer.partner_type != BusinessPartner.PartnerType.CUSTOMER:
            errors['customer'] = 'O cliente deve usar parceiro de negócio do tipo cliente.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.case} - {self.get_link_type_display()}'


class PharmacovigilanceSafetyReport(SingleInstanceModel):
    class ReportType(models.TextChoices):
        SAFETY_CASE = 'safety_case', 'Relatório individual de segurança'
        TREND = 'trend', 'Tendência'
        RECURRENCE = 'recurrence', 'Recorrência'
        INDICATORS = 'indicators', 'Indicadores'
        REGULATORY_NOTIFICATION = 'regulatory_notification', 'Notificação regulatória'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        GENERATED = 'generated', 'Gerado'

    case = models.ForeignKey(
        PharmacovigilanceCase, on_delete=models.CASCADE, related_name='reports', verbose_name='caso'
    )
    report_type = models.CharField('tipo', max_length=32, choices=ReportType.choices)
    title = models.CharField('título', max_length=180)
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.DRAFT)
    content_reference = models.CharField('conteúdo gerado', max_length=255, blank=True)
    case_count = models.PositiveIntegerField('casos', default=0)
    serious_cases = models.PositiveIntegerField('casos sérios', default=0)
    recurrence_count = models.PositiveIntegerField('recorrências', default=0)
    indicator_summary = models.TextField('resumo de indicadores', blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='generated_pharmacovigilance_reports',
        null=True,
        blank=True,
        verbose_name='gerado por',
    )
    generated_at = models.DateTimeField('gerado em', null=True, blank=True)

    class Meta:
        ordering = ['case__case_number', '-created_at']
        indexes = [
            models.Index(fields=['case', 'status']),
            models.Index(fields=['report_type']),
            models.Index(fields=['generated_at']),
        ]
        verbose_name = 'relatório de segurança'
        verbose_name_plural = 'relatórios de segurança'

    def _recurrence_queryset(self):
        queryset = PharmacovigilanceCase.objects.filter(case_type=self.case.case_type)
        if self.case.product_id:
            return queryset.filter(product=self.case.product)
        return queryset.filter(pk=self.case_id)

    def generate(self, user=None, content_reference=''):
        if not content_reference:
            raise ValidationError(
                {'content_reference': 'Informe a referência do relatório gerado.'}
            )
        recurrence_queryset = self._recurrence_queryset()
        if self.report_type in {
            self.ReportType.TREND,
            self.ReportType.RECURRENCE,
            self.ReportType.INDICATORS,
        }:
            report_queryset = recurrence_queryset
        else:
            report_queryset = PharmacovigilanceCase.objects.filter(pk=self.case_id)
        self.case_count = report_queryset.count()
        self.serious_cases = report_queryset.filter(
            seriousness=PharmacovigilanceCase.Seriousness.SERIOUS
        ).count()
        self.recurrence_count = recurrence_queryset.count()
        self.indicator_summary = (
            f'{self.case_count} caso(s), {self.serious_cases} sério(s), '
            f'{self.recurrence_count} recorrência(s) para produto/tipo do caso.'
        )
        self.content_reference = content_reference
        self.generated_by = user
        self.generated_at = timezone.now()
        self.status = self.Status.GENERATED
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'content_reference',
                'case_count',
                'serious_cases',
                'recurrence_count',
                'indicator_summary',
                'generated_by',
                'generated_at',
                'updated_at',
            ]
        )

    def clean(self):
        super().clean()
        errors = {}
        if self.status == self.Status.GENERATED and (
            not self.content_reference or not self.generated_by_id or not self.generated_at
        ):
            errors['content_reference'] = 'Relatório gerado exige referência, usuário e data.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


# Create your models here.
