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


class RegulatoryProduct(SingleInstanceModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        ACTIVE = 'active', 'Ativo'
        SUSPENDED = 'suspended', 'Suspenso'
        CANCELLED = 'cancelled', 'Cancelado'

    regulatory_code = models.CharField('código regulatório', max_length=80, blank=True)
    product = models.ForeignKey(
        'masters.Product',
        on_delete=models.PROTECT,
        related_name='regulatory_products',
        verbose_name='produto',
    )
    presentation = models.CharField('apresentação', max_length=180)
    registration_holder = models.CharField('detentor do registro', max_length=180)
    registration_holder_partner = models.ForeignKey(
        'masters.BusinessPartner',
        on_delete=models.PROTECT,
        related_name='regulatory_products_as_holder',
        null=True,
        blank=True,
        verbose_name='detentor do registro (parceiro)',
    )
    manufacturer_partner = models.ForeignKey(
        'masters.BusinessPartner',
        on_delete=models.PROTECT,
        related_name='regulatory_products_as_manufacturer',
        null=True,
        blank=True,
        verbose_name='fabricante (parceiro)',
    )
    therapeutic_class = models.CharField('classe terapêutica', max_length=140)
    dosage_form = models.CharField('forma farmacêutica', max_length=120)
    strength = models.CharField('concentração', max_length=80)
    route = models.CharField('via de administração', max_length=80)
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.DRAFT)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_regulatory_products',
        verbose_name='responsável',
    )

    class Meta:
        ordering = ['regulatory_code']
        constraints = [
            models.UniqueConstraint(
                fields=['regulatory_code'], name='unique_regulatory_product_code'
            ),
            models.UniqueConstraint(
                fields=['product', 'presentation'],
                name='unique_product_presentation',
            ),
        ]
        indexes = [
            models.Index(fields=['product', 'status']),
            models.Index(fields=['responsible']),
            models.Index(fields=['regulatory_code']),
        ]
        verbose_name = 'produto regulatório'
        verbose_name_plural = 'produtos regulatórios'

    def save(self, *args, **kwargs):
        if not self.regulatory_code:
            self.regulatory_code = _sequence_code(RegulatoryProduct, 'regulatory_code', 'REGPROD')
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.regulatory_code} - {self.presentation}'


class RegulatoryDossier(SingleInstanceModel):
    class DossierType(models.TextChoices):
        REGISTRATION = 'registration', 'Registro'
        POST_REGISTRATION = 'post_registration', 'Pós-registro'
        RENEWAL = 'renewal', 'Renovação'
        VARIATION = 'variation', 'Variação'
        INSPECTION = 'inspection', 'Inspeção'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        SUBMITTED = 'submitted', 'Submetido'
        UNDER_REVIEW = 'under_review', 'Em análise'
        APPROVED = 'approved', 'Aprovado'
        REJECTED = 'rejected', 'Rejeitado'
        CLOSED = 'closed', 'Encerrado'
        CANCELLED = 'cancelled', 'Cancelado'

    dossier_number = models.CharField('dossiê', max_length=80, blank=True)
    regulatory_product = models.ForeignKey(
        RegulatoryProduct,
        on_delete=models.PROTECT,
        related_name='dossiers',
        verbose_name='produto regulatório',
    )
    dossier_type = models.CharField('tipo', max_length=32, choices=DossierType.choices)
    title = models.CharField('título', max_length=180)
    authority = models.CharField('autoridade sanitária', max_length=120, default='ANVISA')
    subject = models.TextField('assunto')
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_regulatory_dossiers',
        verbose_name='responsável',
    )
    due_date = models.DateField('prazo')
    status = models.CharField('status', max_length=32, choices=Status.choices, default=Status.DRAFT)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='submitted_regulatory_dossiers',
        null=True,
        blank=True,
        verbose_name='submetido por',
    )
    submitted_at = models.DateTimeField('submetido em', null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='closed_regulatory_dossiers',
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
                fields=['dossier_number'], name='unique_regulatory_dossier_number'
            ),
        ]
        indexes = [
            models.Index(fields=['regulatory_product', 'status']),
            models.Index(fields=['dossier_type', 'status']),
            models.Index(fields=['responsible']),
            models.Index(fields=['due_date']),
            models.Index(fields=['dossier_number']),
        ]
        verbose_name = 'dossiê regulatório'
        verbose_name_plural = 'dossiês regulatórios'

    def save(self, *args, **kwargs):
        if not self.dossier_number:
            self.dossier_number = _sequence_code(RegulatoryDossier, 'dossier_number', 'REGDOS')
        super().save(*args, **kwargs)

    def submit(self, user=None):
        if self.status != self.Status.DRAFT:
            raise ValidationError({'status': 'Somente dossiês em rascunho podem ser submetidos.'})
        if not self.evidences.exists():
            raise ValidationError(
                {'evidences': 'Submissão exige ao menos uma evidência ou documento técnico.'}
            )
        self.status = self.Status.SUBMITTED
        self.submitted_by = user or self.submitted_by
        self.submitted_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'submitted_by', 'submitted_at', 'updated_at'])

    def close(self, summary, user=None):
        if not summary:
            raise ValidationError({'closure_summary': 'Informe o resumo de encerramento.'})
        if self.status not in {
            self.Status.SUBMITTED,
            self.Status.UNDER_REVIEW,
            self.Status.APPROVED,
        }:
            raise ValidationError(
                {'status': 'Encerramento exige dossiê submetido, em análise ou aprovado.'}
            )
        if self.requirements.exclude(
            status__in=[
                RegulatoryRequirement.Status.ANSWERED,
                RegulatoryRequirement.Status.CLOSED,
                RegulatoryRequirement.Status.CANCELLED,
            ]
        ).exists():
            raise ValidationError(
                {'requirements': 'Encerramento exige exigências respondidas ou encerradas.'}
            )
        if self.commitments.exclude(
            status__in=[
                RegulatoryCommitment.Status.COMPLETED,
                RegulatoryCommitment.Status.CANCELLED,
            ]
        ).exists():
            raise ValidationError(
                {'commitments': 'Encerramento exige compromissos concluídos ou cancelados.'}
            )
        if not self.reports.filter(status=RegulatoryReport.Status.GENERATED).exists():
            raise ValidationError(
                {'reports': 'Encerramento exige relatório ou dossiê consolidado gerado.'}
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
            raise ValidationError({'status': 'Dossiê encerrado não pode ser cancelado.'})
        self.status = self.Status.CANCELLED
        self.cancel_reason = reason
        self.save(update_fields=['status', 'cancel_reason', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        for field in ('responsible', 'submitted_by', 'closed_by'):
            pass
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.dossier_number


class RegulatoryRegistration(SingleInstanceModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        ACTIVE = 'active', 'Ativo'
        PENDING_RENEWAL = 'pending_renewal', 'Renovação pendente'
        EXPIRED = 'expired', 'Vencido'
        SUSPENDED = 'suspended', 'Suspenso'
        CANCELLED = 'cancelled', 'Cancelado'

    regulatory_product = models.ForeignKey(
        RegulatoryProduct,
        on_delete=models.PROTECT,
        related_name='registrations',
        verbose_name='produto regulatório',
    )
    dossier = models.ForeignKey(
        RegulatoryDossier,
        on_delete=models.PROTECT,
        related_name='registrations',
        null=True,
        blank=True,
        verbose_name='dossiê',
    )
    registration_number = models.CharField('número de registro', max_length=80)
    status = models.CharField(
        'status', max_length=32, choices=Status.choices, default=Status.PENDING
    )
    valid_from = models.DateField('vigência inicial')
    valid_until = models.DateField('vigência final')
    next_renewal_due_date = models.DateField('prazo de renovação')
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_regulatory_registrations',
        verbose_name='responsável',
    )

    class Meta:
        ordering = ['registration_number']
        constraints = [
            models.UniqueConstraint(
                fields=['registration_number'], name='unique_registration_number'
            ),
        ]
        indexes = [
            models.Index(fields=['regulatory_product', 'status']),
            models.Index(fields=['valid_until']),
            models.Index(fields=['next_renewal_due_date']),
            models.Index(fields=['registration_number']),
        ]
        verbose_name = 'registro regulatório'
        verbose_name_plural = 'registros regulatórios'

    def clean(self):
        super().clean()
        errors = {}
        if self.valid_until and self.valid_from and self.valid_until <= self.valid_from:
            errors['valid_until'] = 'A vigência final deve ser posterior ao início.'
        if (
            self.next_renewal_due_date
            and self.valid_until
            and self.next_renewal_due_date > self.valid_until
        ):
            errors['next_renewal_due_date'] = (
                'A renovação deve ocorrer antes do vencimento do registro.'
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.registration_number


class RegulatoryPetition(SingleInstanceModel):
    class PetitionType(models.TextChoices):
        INITIAL_REGISTRATION = 'initial_registration', 'Registro inicial'
        POST_REGISTRATION = 'post_registration', 'Pós-registro'
        RENEWAL = 'renewal', 'Renovação'
        REQUIREMENT_RESPONSE = 'requirement_response', 'Resposta de exigência'
        COMMITMENT = 'commitment', 'Compromisso'
        OTHER = 'other', 'Outro'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        SUBMITTED = 'submitted', 'Submetida'
        UNDER_REVIEW = 'under_review', 'Em análise'
        APPROVED = 'approved', 'Aprovada'
        REJECTED = 'rejected', 'Rejeitada'
        CLOSED = 'closed', 'Encerrada'
        CANCELLED = 'cancelled', 'Cancelada'

    petition_number = models.CharField('petição', max_length=80, blank=True)
    dossier = models.ForeignKey(
        RegulatoryDossier, on_delete=models.CASCADE, related_name='petitions', verbose_name='dossiê'
    )
    petition_type = models.CharField('tipo', max_length=32, choices=PetitionType.choices)
    subject = models.CharField('assunto', max_length=180)
    protocol_number = models.CharField('protocolo', max_length=120, blank=True)
    response_due_date = models.DateField('prazo de resposta', null=True, blank=True)
    status = models.CharField('status', max_length=32, choices=Status.choices, default=Status.DRAFT)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_regulatory_petitions',
        verbose_name='responsável',
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='submitted_regulatory_petitions',
        null=True,
        blank=True,
        verbose_name='submetida por',
    )
    submitted_at = models.DateTimeField('submetida em', null=True, blank=True)
    response_summary = models.TextField('resumo da resposta', blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responded_regulatory_petitions',
        null=True,
        blank=True,
        verbose_name='respondida por',
    )
    responded_at = models.DateTimeField('respondida em', null=True, blank=True)

    class Meta:
        ordering = ['dossier__dossier_number', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['petition_number'],
                name='unique_regulatory_petition_number',
            ),
        ]
        indexes = [
            models.Index(fields=['dossier', 'status']),
            models.Index(fields=['petition_type', 'status']),
            models.Index(fields=['response_due_date']),
            models.Index(fields=['petition_number']),
            models.Index(fields=['protocol_number']),
        ]
        verbose_name = 'petição regulatória'
        verbose_name_plural = 'petições regulatórias'

    def save(self, *args, **kwargs):
        if not self.petition_number:
            self.petition_number = _sequence_code(RegulatoryPetition, 'petition_number', 'REGPET')
        super().save(*args, **kwargs)

    def submit(self, protocol_number, user=None):
        if not protocol_number:
            raise ValidationError({'protocol_number': 'Informe o protocolo da submissão.'})
        if self.status != self.Status.DRAFT:
            raise ValidationError({'status': 'Somente petições em rascunho podem ser submetidas.'})
        self.status = self.Status.SUBMITTED
        self.protocol_number = protocol_number
        self.submitted_by = user or self.submitted_by
        self.submitted_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'protocol_number',
                'submitted_by',
                'submitted_at',
                'updated_at',
            ]
        )

    def record_response(self, response_summary, user=None):
        if not response_summary:
            raise ValidationError({'response_summary': 'Informe o resumo da resposta.'})
        self.response_summary = response_summary
        self.responded_by = user
        self.responded_at = timezone.now()
        self.status = self.Status.CLOSED
        self.full_clean()
        self.save(
            update_fields=[
                'response_summary',
                'responded_by',
                'responded_at',
                'status',
                'updated_at',
            ]
        )

    def clean(self):
        super().clean()
        errors = {}
        for field in ('responsible', 'submitted_by', 'responded_by'):
            pass
        if self.status == self.Status.SUBMITTED and (
            not self.protocol_number or not self.submitted_by_id or not self.submitted_at
        ):
            errors['protocol_number'] = 'Petição submetida exige protocolo, responsável e data.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.petition_number


class RegulatoryRequirement(SingleInstanceModel):
    class Status(models.TextChoices):
        OPEN = 'open', 'Aberta'
        ANSWERED = 'answered', 'Respondida'
        CLOSED = 'closed', 'Encerrada'
        CANCELLED = 'cancelled', 'Cancelada'

    requirement_number = models.CharField('exigência', max_length=80, blank=True)
    dossier = models.ForeignKey(
        RegulatoryDossier,
        on_delete=models.CASCADE,
        related_name='requirements',
        verbose_name='dossiê',
    )
    petition = models.ForeignKey(
        RegulatoryPetition,
        on_delete=models.PROTECT,
        related_name='requirements',
        null=True,
        blank=True,
        verbose_name='petição',
    )
    description = models.TextField('descrição')
    received_at = models.DateField('recebida em')
    response_due_date = models.DateField('prazo de resposta')
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_regulatory_requirements',
        verbose_name='responsável',
    )
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.OPEN)
    response_summary = models.TextField('resumo da resposta', blank=True)
    evidence_reference = models.CharField('evidência', max_length=255, blank=True)
    content_hash = models.CharField('hash do conteúdo', max_length=128, blank=True)
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='answered_regulatory_requirements',
        null=True,
        blank=True,
        verbose_name='respondida por',
    )
    answered_at = models.DateTimeField('respondida em', null=True, blank=True)

    class Meta:
        ordering = ['dossier__dossier_number', 'response_due_date']
        constraints = [
            models.UniqueConstraint(
                fields=['requirement_number'],
                name='unique_regulatory_requirement_number',
            ),
        ]
        indexes = [
            models.Index(fields=['dossier', 'status']),
            models.Index(fields=['petition']),
            models.Index(fields=['responsible', 'response_due_date']),
            models.Index(fields=['requirement_number']),
        ]
        verbose_name = 'exigência regulatória'
        verbose_name_plural = 'exigências regulatórias'

    def save(self, *args, **kwargs):
        if not self.requirement_number:
            self.requirement_number = _sequence_code(
                RegulatoryRequirement, 'requirement_number', 'REGREQ'
            )
        super().save(*args, **kwargs)

    def answer(self, response_summary, evidence_reference, content_hash, user=None):
        if not response_summary:
            raise ValidationError({'response_summary': 'Informe o resumo da resposta.'})
        if not evidence_reference or not content_hash:
            raise ValidationError(
                {'evidence_reference': 'Resposta de exigência exige evidência e hash.'}
            )
        self.status = self.Status.ANSWERED
        self.response_summary = response_summary
        self.evidence_reference = evidence_reference
        self.content_hash = content_hash
        self.answered_by = user
        self.answered_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'response_summary',
                'evidence_reference',
                'content_hash',
                'answered_by',
                'answered_at',
                'updated_at',
            ]
        )

    def clean(self):
        super().clean()
        errors = {}
        for field in ('responsible', 'answered_by'):
            pass
        if self.petition and self.dossier and self.petition.dossier_id != self.dossier_id:
            errors['petition'] = 'A petição deve pertencer ao dossiê informado.'
        if self.status == self.Status.ANSWERED and (
            not self.response_summary
            or not self.evidence_reference
            or not self.content_hash
            or not self.answered_by_id
            or not self.answered_at
        ):
            errors['response_summary'] = (
                'Exigência respondida exige resposta, evidência, hash, responsável e data.'
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.requirement_number


class RegulatoryCommitment(SingleInstanceModel):
    class Status(models.TextChoices):
        OPEN = 'open', 'Aberto'
        COMPLETED = 'completed', 'Concluído'
        CANCELLED = 'cancelled', 'Cancelado'

    commitment_number = models.CharField('compromisso', max_length=80, blank=True)
    dossier = models.ForeignKey(
        RegulatoryDossier,
        on_delete=models.CASCADE,
        related_name='commitments',
        verbose_name='dossiê',
    )
    description = models.TextField('descrição')
    due_date = models.DateField('prazo')
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='responsible_regulatory_commitments',
        verbose_name='responsável',
    )
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.OPEN)
    completion_summary = models.TextField('resumo de conclusão', blank=True)
    evidence_reference = models.CharField('evidência', max_length=255, blank=True)
    content_hash = models.CharField('hash do conteúdo', max_length=128, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='completed_regulatory_commitments',
        null=True,
        blank=True,
        verbose_name='concluído por',
    )
    completed_at = models.DateTimeField('concluído em', null=True, blank=True)

    class Meta:
        ordering = ['dossier__dossier_number', 'due_date']
        constraints = [
            models.UniqueConstraint(
                fields=['commitment_number'],
                name='unique_regulatory_commitment_number',
            ),
        ]
        indexes = [
            models.Index(fields=['dossier', 'status']),
            models.Index(fields=['responsible', 'due_date']),
            models.Index(fields=['commitment_number']),
        ]
        verbose_name = 'compromisso regulatório'
        verbose_name_plural = 'compromissos regulatórios'

    def save(self, *args, **kwargs):
        if not self.commitment_number:
            self.commitment_number = _sequence_code(
                RegulatoryCommitment, 'commitment_number', 'REGCOM'
            )
        super().save(*args, **kwargs)

    def complete(self, completion_summary, evidence_reference, content_hash, user=None):
        if not completion_summary:
            raise ValidationError({'completion_summary': 'Informe o resumo de conclusão.'})
        if not evidence_reference or not content_hash:
            raise ValidationError(
                {'evidence_reference': 'Conclusão de compromisso exige evidência e hash.'}
            )
        self.status = self.Status.COMPLETED
        self.completion_summary = completion_summary
        self.evidence_reference = evidence_reference
        self.content_hash = content_hash
        self.completed_by = user
        self.completed_at = timezone.now()
        self.full_clean()
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

    def clean(self):
        super().clean()
        errors = {}
        for field in ('responsible', 'completed_by'):
            pass
        if self.status == self.Status.COMPLETED and (
            not self.completion_summary
            or not self.evidence_reference
            or not self.content_hash
            or not self.completed_by_id
            or not self.completed_at
        ):
            errors['completion_summary'] = (
                'Compromisso concluído exige resumo, evidência, hash, responsável e data.'
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.commitment_number


class RegulatoryEvidence(SingleInstanceModel):
    dossier = models.ForeignKey(
        RegulatoryDossier, on_delete=models.CASCADE, related_name='evidences', verbose_name='dossiê'
    )
    petition = models.ForeignKey(
        RegulatoryPetition,
        on_delete=models.CASCADE,
        related_name='evidences',
        null=True,
        blank=True,
        verbose_name='petição',
    )
    requirement = models.ForeignKey(
        RegulatoryRequirement,
        on_delete=models.CASCADE,
        related_name='evidences',
        null=True,
        blank=True,
        verbose_name='exigência',
    )
    commitment = models.ForeignKey(
        RegulatoryCommitment,
        on_delete=models.CASCADE,
        related_name='evidences',
        null=True,
        blank=True,
        verbose_name='compromisso',
    )
    title = models.CharField('título', max_length=180)
    file_reference = models.CharField('arquivo', max_length=255)
    content_hash = models.CharField('hash do conteúdo', max_length=128)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_regulatory_evidences',
        null=True,
        blank=True,
        verbose_name='enviado por',
    )
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['dossier__dossier_number', 'title']
        indexes = [
            models.Index(fields=['dossier']),
            models.Index(fields=['petition']),
            models.Index(fields=['requirement']),
            models.Index(fields=['commitment']),
            models.Index(fields=['content_hash']),
        ]
        verbose_name = 'evidência regulatória'
        verbose_name_plural = 'evidências regulatórias'

    def clean(self):
        super().clean()
        errors = {}
        for field in ('dossier', 'petition', 'requirement', 'commitment'):
            pass
        if self.petition and self.petition.dossier_id != self.dossier_id:
            errors['petition'] = 'A petição deve pertencer ao dossiê informado.'
        if self.requirement and self.requirement.dossier_id != self.dossier_id:
            errors['requirement'] = 'A exigência deve pertencer ao dossiê informado.'
        if self.commitment and self.commitment.dossier_id != self.dossier_id:
            errors['commitment'] = 'O compromisso deve pertencer ao dossiê informado.'
        if not self.content_hash:
            errors['content_hash'] = 'Evidência exige hash para integridade dos dados.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class RegulatoryLink(SingleInstanceModel):
    class LinkType(models.TextChoices):
        PRODUCT = 'product', 'Produto'
        PRESENTATION = 'presentation', 'Apresentação'
        LOT = 'lot', 'Lote'
        DOCUMENT = 'document', 'Documento'
        CHANGE = 'change', 'Mudança'
        DEVIATION = 'deviation', 'Desvio'
        CAPA = 'capa', 'CAPA'
        STUDY = 'study', 'Estudo'
        SUPPLIER = 'supplier', 'Fornecedor'
        MANUFACTURER = 'manufacturer', 'Fabricante'

    dossier = models.ForeignKey(
        RegulatoryDossier, on_delete=models.CASCADE, related_name='links', verbose_name='dossiê'
    )
    link_type = models.CharField('tipo de vínculo', max_length=24, choices=LinkType.choices)
    product = models.ForeignKey(
        'masters.Product',
        on_delete=models.PROTECT,
        related_name='regulatory_links',
        null=True,
        blank=True,
        verbose_name='produto',
    )
    stock_lot = models.ForeignKey(
        'inventory.StockLot',
        on_delete=models.PROTECT,
        related_name='regulatory_links',
        null=True,
        blank=True,
        verbose_name='lote',
    )
    document = models.ForeignKey(
        'documents.ControlledDocument',
        on_delete=models.PROTECT,
        related_name='regulatory_links',
        null=True,
        blank=True,
        verbose_name='documento',
    )
    change_control = models.ForeignKey(
        'changes.ChangeControl',
        on_delete=models.PROTECT,
        related_name='regulatory_links',
        null=True,
        blank=True,
        verbose_name='mudança',
    )
    deviation_event = models.ForeignKey(
        'deviations.QualityEvent',
        on_delete=models.PROTECT,
        related_name='regulatory_links',
        null=True,
        blank=True,
        verbose_name='desvio',
    )
    capa = models.ForeignKey(
        'capa.CapaRecord',
        on_delete=models.PROTECT,
        related_name='regulatory_links',
        null=True,
        blank=True,
        verbose_name='CAPA',
    )
    partner = models.ForeignKey(
        'masters.BusinessPartner',
        on_delete=models.PROTECT,
        related_name='regulatory_links',
        null=True,
        blank=True,
        verbose_name='parceiro',
    )
    reference_code = models.CharField('referência', max_length=120, blank=True)
    description = models.TextField('descrição')

    class Meta:
        ordering = ['dossier__dossier_number', 'link_type']
        indexes = [
            models.Index(fields=['dossier', 'link_type']),
            models.Index(fields=['product']),
            models.Index(fields=['stock_lot']),
            models.Index(fields=['document']),
            models.Index(fields=['change_control']),
            models.Index(fields=['deviation_event']),
            models.Index(fields=['capa']),
            models.Index(fields=['partner']),
        ]
        verbose_name = 'vínculo regulatório'
        verbose_name_plural = 'vínculos regulatórios'

    def clean(self):
        super().clean()
        errors = {}
        for field in (
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
        required_by_type = {
            self.LinkType.PRODUCT: ('product', self.product_id),
            self.LinkType.LOT: ('stock_lot', self.stock_lot_id),
            self.LinkType.DOCUMENT: ('document', self.document_id),
            self.LinkType.CHANGE: ('change_control', self.change_control_id),
            self.LinkType.DEVIATION: ('deviation_event', self.deviation_event_id),
            self.LinkType.CAPA: ('capa', self.capa_id),
            self.LinkType.SUPPLIER: ('partner', self.partner_id),
            self.LinkType.MANUFACTURER: ('partner', self.partner_id),
        }
        if self.link_type in required_by_type:
            field, value = required_by_type[self.link_type]
            if not value:
                errors[field] = 'Informe o cadastro relacionado ao tipo de vínculo.'
        if (
            self.link_type in {self.LinkType.PRESENTATION, self.LinkType.STUDY}
            and not self.reference_code
        ):
            errors['reference_code'] = 'Informe a referência do vínculo.'
        if (
            self.link_type == self.LinkType.SUPPLIER
            and self.partner
            and self.partner.partner_type
            not in {
                BusinessPartner.PartnerType.SUPPLIER,
                BusinessPartner.PartnerType.MANUFACTURER,
                BusinessPartner.PartnerType.OUTSOURCED_LAB,
            }
        ):
            errors['partner'] = (
                'Fornecedor deve ser fornecedor, fabricante ou laboratório terceirizado.'
            )
        if (
            self.link_type == self.LinkType.MANUFACTURER
            and self.partner
            and self.partner.partner_type != BusinessPartner.PartnerType.MANUFACTURER
        ):
            errors['partner'] = 'Fabricante deve usar parceiro do tipo fabricante.'
        if self.stock_lot and self.product and self.stock_lot.product_id != self.product_id:
            errors['stock_lot'] = 'O lote deve pertencer ao produto informado.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.dossier} - {self.get_link_type_display()}'


class RegulatoryReport(SingleInstanceModel):
    class ReportType(models.TextChoices):
        ANVISA_DOSSIER = 'anvisa_dossier', 'Dossiê ANVISA'
        AUDIT = 'audit', 'Auditoria'
        INSPECTION = 'inspection', 'Inspeção'
        RENEWAL = 'renewal', 'Renovação'
        SUMMARY = 'summary', 'Resumo'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        GENERATED = 'generated', 'Gerado'

    dossier = models.ForeignKey(
        RegulatoryDossier, on_delete=models.CASCADE, related_name='reports', verbose_name='dossiê'
    )
    report_type = models.CharField('tipo', max_length=32, choices=ReportType.choices)
    title = models.CharField('título', max_length=180)
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.DRAFT)
    content_reference = models.CharField('conteúdo gerado', max_length=255, blank=True)
    total_requirements = models.PositiveIntegerField('exigências totais', default=0)
    open_commitments = models.PositiveIntegerField('compromissos abertos', default=0)
    evidence_count = models.PositiveIntegerField('evidências', default=0)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='generated_regulatory_reports',
        null=True,
        blank=True,
        verbose_name='gerado por',
    )
    generated_at = models.DateTimeField('gerado em', null=True, blank=True)

    class Meta:
        ordering = ['dossier__dossier_number', '-created_at']
        indexes = [
            models.Index(fields=['dossier', 'status']),
            models.Index(fields=['report_type']),
            models.Index(fields=['generated_at']),
        ]
        verbose_name = 'relatório regulatório'
        verbose_name_plural = 'relatórios regulatórios'

    def generate(self, user=None, content_reference=''):
        if not content_reference:
            raise ValidationError(
                {'content_reference': 'Informe a referência do relatório gerado.'}
            )
        self.total_requirements = self.dossier.requirements.count()
        self.open_commitments = self.dossier.commitments.exclude(
            status__in=[
                RegulatoryCommitment.Status.COMPLETED,
                RegulatoryCommitment.Status.CANCELLED,
            ]
        ).count()
        self.evidence_count = self.dossier.evidences.count()
        self.content_reference = content_reference
        self.generated_by = user
        self.generated_at = timezone.now()
        self.status = self.Status.GENERATED
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'content_reference',
                'total_requirements',
                'open_commitments',
                'evidence_count',
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


class RegulatoryAlert(SingleInstanceModel):
    class AlertType(models.TextChoices):
        REGISTRATION_EXPIRY = 'registration_expiry', 'Vencimento de registro'
        RENEWAL_DUE = 'renewal_due', 'Renovação'
        COMMITMENT_DUE = 'commitment_due', 'Compromisso'
        REQUIREMENT_DUE = 'requirement_due', 'Exigência'
        RESPONSE_DUE = 'response_due', 'Prazo de resposta'

    class Severity(models.TextChoices):
        MEDIUM = 'medium', 'Média'
        HIGH = 'high', 'Alta'
        CRITICAL = 'critical', 'Crítica'

    class Status(models.TextChoices):
        OPEN = 'open', 'Aberto'
        SENT = 'sent', 'Enviado'
        ACKNOWLEDGED = 'acknowledged', 'Reconhecido'

    regulatory_product = models.ForeignKey(
        RegulatoryProduct,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True,
        verbose_name='produto regulatório',
    )
    dossier = models.ForeignKey(
        RegulatoryDossier,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True,
        verbose_name='dossiê',
    )
    registration = models.ForeignKey(
        RegulatoryRegistration,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True,
        verbose_name='registro',
    )
    petition = models.ForeignKey(
        RegulatoryPetition,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True,
        verbose_name='petição',
    )
    requirement = models.ForeignKey(
        RegulatoryRequirement,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True,
        verbose_name='exigência',
    )
    commitment = models.ForeignKey(
        RegulatoryCommitment,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True,
        verbose_name='compromisso',
    )
    alert_type = models.CharField('tipo', max_length=32, choices=AlertType.choices)
    severity = models.CharField('severidade', max_length=24, choices=Severity.choices)
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
        related_name='acknowledged_regulatory_alerts',
        null=True,
        blank=True,
        verbose_name='reconhecido por',
    )
    acknowledged_at = models.DateTimeField('reconhecido em', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['alert_type', 'status']),
            models.Index(fields=['regulatory_product']),
            models.Index(fields=['dossier']),
            models.Index(fields=['registration']),
            models.Index(fields=['petition']),
            models.Index(fields=['requirement']),
            models.Index(fields=['commitment']),
            models.Index(fields=['due_date']),
        ]
        verbose_name = 'alerta regulatório'
        verbose_name_plural = 'alertas regulatórios'

    @classmethod
    def generate_all(cls):
        generated = 0
        today = timezone.localdate()
        horizon = today + timezone.timedelta(days=90)
        response_horizon = today + timezone.timedelta(days=30)
        registrations = RegulatoryRegistration.objects.filter(
            status=RegulatoryRegistration.Status.ACTIVE
        )
        for registration in registrations:
            if registration.valid_until <= horizon:
                generated += cls._create_once(
                    alert_type=cls.AlertType.REGISTRATION_EXPIRY,
                    registration=registration,
                    regulatory_product=registration.regulatory_product,
                    dossier=registration.dossier,
                    severity=cls.Severity.CRITICAL
                    if registration.valid_until <= response_horizon
                    else cls.Severity.HIGH,
                    message=f'Registro próximo do vencimento: {registration.registration_number}',
                    due_date=registration.valid_until,
                )
            if registration.next_renewal_due_date <= horizon:
                generated += cls._create_once(
                    alert_type=cls.AlertType.RENEWAL_DUE,
                    registration=registration,
                    regulatory_product=registration.regulatory_product,
                    dossier=registration.dossier,
                    severity=cls.Severity.HIGH,
                    message=f'Renovação próxima: {registration.registration_number}',
                    due_date=registration.next_renewal_due_date,
                )
        for commitment in RegulatoryCommitment.objects.filter(
            status=RegulatoryCommitment.Status.OPEN, due_date__lte=response_horizon
        ):
            generated += cls._create_once(
                alert_type=cls.AlertType.COMMITMENT_DUE,
                commitment=commitment,
                dossier=commitment.dossier,
                regulatory_product=commitment.dossier.regulatory_product,
                severity=cls.Severity.HIGH,
                message=f'Compromisso regulatório pendente: {commitment.commitment_number}',
                due_date=commitment.due_date,
            )
        for requirement in RegulatoryRequirement.objects.filter(
            status=RegulatoryRequirement.Status.OPEN,
            response_due_date__lte=response_horizon,
        ):
            generated += cls._create_once(
                alert_type=cls.AlertType.REQUIREMENT_DUE,
                requirement=requirement,
                petition=requirement.petition,
                dossier=requirement.dossier,
                regulatory_product=requirement.dossier.regulatory_product,
                severity=cls.Severity.CRITICAL,
                message=f'Exigência regulatória pendente: {requirement.requirement_number}',
                due_date=requirement.response_due_date,
            )
        for petition in RegulatoryPetition.objects.filter(
            status__in=[
                RegulatoryPetition.Status.SUBMITTED,
                RegulatoryPetition.Status.UNDER_REVIEW,
            ],
            response_due_date__lte=response_horizon,
        ):
            generated += cls._create_once(
                alert_type=cls.AlertType.RESPONSE_DUE,
                petition=petition,
                dossier=petition.dossier,
                regulatory_product=petition.dossier.regulatory_product,
                severity=cls.Severity.MEDIUM,
                message=f'Prazo de resposta regulatória: {petition.petition_number}',
                due_date=petition.response_due_date,
            )
        return generated

    @classmethod
    def _create_once(cls, alert_type, message, severity, due_date=None, **relations):
        filters = {'alert_type': alert_type, 'status': cls.Status.OPEN}
        filters.update({field: value for field, value in relations.items() if value is not None})
        if cls.objects.filter(**filters).exists():
            return 0
        cls.objects.create(
            alert_type=alert_type,
            message=message,
            severity=severity,
            due_date=due_date,
            **relations,
        )
        return 1

    def acknowledge(self, user=None):
        self.status = self.Status.ACKNOWLEDGED
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        for field in (
            'regulatory_product',
            'dossier',
            'registration',
            'petition',
            'requirement',
            'commitment',
        ):
            pass
        if self.status == self.Status.ACKNOWLEDGED and (
            not self.acknowledged_by_id or not self.acknowledged_at
        ):
            errors['acknowledged_by'] = 'Reconhecimento exige usuário e data.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.get_alert_type_display()} - {self.due_date}'
