from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from base.models import SingleInstanceModel
from base.sequences import AutoCodeMixin


def _next_major_version(version):
    try:
        major = int(str(version).split('.', maxsplit=1)[0])
    except (TypeError, ValueError):
        major = 1
    return f'{major + 1}.0'


class ControlledDocument(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'DOC'
    class DocumentType(models.TextChoices):
        SOP = 'sop', 'POP'
        WORK_INSTRUCTION = 'work_instruction', 'Instrução de trabalho'
        SPECIFICATION = 'specification', 'Especificação'
        METHOD = 'method', 'Método'
        PROTOCOL = 'protocol', 'Protocolo'
        REPORT = 'report', 'Relatório'
        FORM = 'form', 'Formulário'
        RECORD = 'record', 'Registro'
        POLICY = 'policy', 'Política'
        MANUAL = 'manual', 'Manual'
        DOSSIER = 'dossier', 'Dossiê'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        IN_REVIEW = 'in_review', 'Em revisão'
        REVIEWED = 'reviewed', 'Revisado'
        APPROVED = 'approved', 'Aprovado'
        PUBLISHED = 'published', 'Publicado'
        OBSOLETE = 'obsolete', 'Obsoleto'
        CANCELLED = 'cancelled', 'Cancelado'
        ARCHIVED = 'archived', 'Arquivado'

    document_type = models.CharField('tipo', max_length=32, choices=DocumentType.choices)
    code = models.CharField('código', max_length=80, blank=True)
    title = models.CharField('título', max_length=180)
    area = models.CharField('área', max_length=120)
    area_ref = models.ForeignKey(
        'auxiliary.BusinessArea',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='área normalizada',
    )
    version = models.CharField('versão', max_length=40, default='1.0')
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.DRAFT)
    effective_from = models.DateField('vigência inicial')
    valid_until = models.DateField('validade', null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_controlled_documents',
        verbose_name='responsável',
    )
    content = models.TextField('conteúdo', blank=True)
    change_summary = models.TextField('histórico/justificativa da versão')
    supersedes = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='revisions',
        null=True,
        blank=True,
        verbose_name='substitui',
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='submitted_controlled_documents',
        null=True,
        blank=True,
        verbose_name='submetido por',
    )
    submitted_at = models.DateTimeField('submetido em', null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reviewed_controlled_documents',
        null=True,
        blank=True,
        verbose_name='revisado por',
    )
    reviewed_at = models.DateTimeField('revisado em', null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='approved_controlled_documents',
        null=True,
        blank=True,
        verbose_name='aprovado por',
    )
    approved_at = models.DateTimeField('aprovado em', null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='published_controlled_documents',
        null=True,
        blank=True,
        verbose_name='publicado por',
    )
    published_at = models.DateTimeField('publicado em', null=True, blank=True)
    obsoleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='obsoleted_controlled_documents',
        null=True,
        blank=True,
        verbose_name='obsoletado por',
    )
    obsoleted_at = models.DateTimeField('obsoletado em', null=True, blank=True)
    obsolete_reason = models.TextField('motivo da obsolescência', blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cancelled_controlled_documents',
        null=True,
        blank=True,
        verbose_name='cancelado por',
    )
    cancelled_at = models.DateTimeField('cancelado em', null=True, blank=True)
    cancel_reason = models.TextField('motivo do cancelamento', blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='archived_controlled_documents',
        null=True,
        blank=True,
        verbose_name='arquivado por',
    )
    archived_at = models.DateTimeField('arquivado em', null=True, blank=True)
    archive_reason = models.TextField('motivo do arquivamento', blank=True)

    class Meta:
        ordering = ['code', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['code', 'version'], name='unique_document_code_version'
            ),
        ]
        indexes = [
            models.Index(fields=['document_type', 'status']),
            models.Index(fields=['code']),
            models.Index(fields=['area']),
            models.Index(fields=['effective_from', 'valid_until']),
        ]
        verbose_name = 'documento controlado'
        verbose_name_plural = 'documentos controlados'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def submit_for_review(self, user=None):
        if self.status != self.Status.DRAFT:
            raise ValidationError(
                {'status': 'Somente documentos em rascunho podem ser submetidos para revisão.'}
            )
        self.status = self.Status.IN_REVIEW
        self.submitted_by = user
        self.submitted_at = timezone.now()
        self.save(update_fields=['status', 'submitted_by', 'submitted_at', 'updated_at'])
        self.record_audit(DocumentAuditTrail.Action.SUBMITTED, user=user)

    def review(self, user=None, comments=''):
        if self.status != self.Status.IN_REVIEW:
            raise ValidationError({'status': 'Somente documentos em revisão podem ser revisados.'})
        self.status = self.Status.REVIEWED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
        DocumentApproval.objects.create(
            document=self,
            role=DocumentApproval.Role.REVIEWER,
            user=user,
            decision=DocumentApproval.Decision.APPROVED,
            decided_at=self.reviewed_at,
            comments=comments,
        )
        self.record_audit(DocumentAuditTrail.Action.REVIEWED, user=user, reason=comments)

    def approve(self, user=None, comments=''):
        if self.status not in {self.Status.IN_REVIEW, self.Status.REVIEWED}:
            raise ValidationError(
                {'status': 'Somente documentos revisados ou em revisão podem ser aprovados.'}
            )
        self.status = self.Status.APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
        DocumentApproval.objects.create(
            document=self,
            role=DocumentApproval.Role.APPROVER,
            user=user,
            decision=DocumentApproval.Decision.APPROVED,
            decided_at=self.approved_at,
            comments=comments,
        )
        self.record_audit(DocumentAuditTrail.Action.APPROVED, user=user, reason=comments)

    def publish(self, user=None):
        if self.status != self.Status.APPROVED:
            raise ValidationError({'status': 'Somente documentos aprovados podem ser publicados.'})
        self.status = self.Status.PUBLISHED
        self.published_by = user
        self.published_at = timezone.now()
        self.save(update_fields=['status', 'published_by', 'published_at', 'updated_at'])
        self.record_audit(DocumentAuditTrail.Action.PUBLISHED, user=user)

    def obsolete(self, reason, user=None):
        if not reason:
            raise ValidationError({'obsolete_reason': 'Informe o motivo da obsolescência.'})
        if self.status != self.Status.PUBLISHED:
            raise ValidationError(
                {'status': 'Somente documentos publicados podem ser obsoletados.'}
            )
        self.status = self.Status.OBSOLETE
        self.obsolete_reason = reason
        self.obsoleted_by = user
        self.obsoleted_at = timezone.now()
        self.save(
            update_fields=[
                'status',
                'obsolete_reason',
                'obsoleted_by',
                'obsoleted_at',
                'updated_at',
            ]
        )
        self.record_audit(DocumentAuditTrail.Action.OBSOLETED, user=user, reason=reason)

    def cancel(self, reason, user=None):
        if not reason:
            raise ValidationError({'cancel_reason': 'Informe o motivo do cancelamento.'})
        if self.status == self.Status.PUBLISHED:
            raise ValidationError(
                {'status': 'Documento publicado deve ser obsoletado ou arquivado, não cancelado.'}
            )
        if self.status in {self.Status.OBSOLETE, self.Status.ARCHIVED}:
            raise ValidationError(
                {'status': 'Documento obsoleto ou arquivado não pode ser cancelado.'}
            )
        self.status = self.Status.CANCELLED
        self.cancel_reason = reason
        self.cancelled_by = user
        self.cancelled_at = timezone.now()
        self.save(
            update_fields=['status', 'cancel_reason', 'cancelled_by', 'cancelled_at', 'updated_at']
        )
        self.record_audit(DocumentAuditTrail.Action.CANCELLED, user=user, reason=reason)

    def archive(self, reason, user=None):
        if not reason:
            raise ValidationError({'archive_reason': 'Informe o motivo do arquivamento.'})
        if self.status not in {self.Status.OBSOLETE, self.Status.CANCELLED}:
            raise ValidationError(
                {'status': 'Somente documentos obsoletos ou cancelados podem ser arquivados.'}
            )
        self.status = self.Status.ARCHIVED
        self.archive_reason = reason
        self.archived_by = user
        self.archived_at = timezone.now()
        self.save(
            update_fields=['status', 'archive_reason', 'archived_by', 'archived_at', 'updated_at']
        )
        self.record_audit(DocumentAuditTrail.Action.ARCHIVED, user=user, reason=reason)

    @transaction.atomic
    def create_revision(self, user=None, change_summary=''):
        if self.status != self.Status.PUBLISHED:
            raise ValidationError(
                {'status': 'Nova revisão deve ser criada a partir de documento publicado.'}
            )
        revision = ControlledDocument.objects.create(
            document_type=self.document_type,
            code=self.code,
            title=self.title,
            area=self.area,
            version=_next_major_version(self.version),
            effective_from=timezone.localdate(),
            valid_until=self.valid_until,
            owner=user or self.owner,
            content=self.content,
            change_summary=change_summary or 'Nova revisão controlada.',
            supersedes=self,
        )
        self.record_audit(
            DocumentAuditTrail.Action.REVISION_CREATED, user=user, reason=revision.version
        )
        revision.record_audit(DocumentAuditTrail.Action.CREATED, user=user, reason=change_summary)
        return revision

    def record_audit(self, action, user=None, reason=''):
        snapshot = f'{self.code} v{self.version} - {self.get_status_display()}'
        return DocumentAuditTrail.objects.create(
            document=self,
            action=action,
            actor=user,
            reason=reason,
            snapshot=snapshot,
        )

    def clean(self):
        super().clean()
        errors = {}
        for field in (
            'owner',
            'submitted_by',
            'reviewed_by',
            'approved_by',
            'published_by',
            'obsoleted_by',
            'cancelled_by',
            'archived_by',
        ):
            pass
        if self.valid_until and self.valid_until < self.effective_from:
            errors['valid_until'] = 'A validade não pode ser anterior à vigência inicial.'
        if self.supersedes and self.supersedes.code != self.code:
            errors['supersedes'] = (
                'A nova revisão deve manter o mesmo código do documento substituído.'
            )
        if self.pk:
            original = ControlledDocument.objects.filter(pk=self.pk).first()
            locked_fields = (
                'document_type',
                'code',
                'title',
                'area',
                'version',
                'effective_from',
                'valid_until',
                'owner_id',
                'content',
                'change_summary',
                'supersedes_id',
            )
            if original and original.status == self.Status.PUBLISHED:
                for field in locked_fields:
                    if getattr(original, field) != getattr(self, field):
                        errors['status'] = (
                            'Documento publicado não pode ser editado diretamente; crie uma nova revisão.'
                        )
                        break
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.code} v{self.version}'


class DocumentAttachment(SingleInstanceModel):
    document = models.ForeignKey(
        ControlledDocument,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='documento',
    )
    file_name = models.CharField('arquivo', max_length=180)
    file_reference = models.CharField('referência do arquivo', max_length=255)
    content_hash = models.CharField('hash do conteúdo', max_length=128)
    description = models.TextField('descrição', blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_document_attachments',
        null=True,
        blank=True,
        verbose_name='enviado por',
    )

    class Meta:
        ordering = ['document__code', 'file_name']
        indexes = [
            models.Index(fields=['document']),
            models.Index(fields=['content_hash']),
        ]
        verbose_name = 'anexo documental'
        verbose_name_plural = 'anexos documentais'

    def clean(self):
        super().clean()
        errors = {}
        if not self.content_hash:
            errors['content_hash'] = 'Anexo exige hash para integridade ALCOA+.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.file_name


class DocumentRelationship(SingleInstanceModel):
    class RelationshipType(models.TextChoices):
        REFERENCES = 'references', 'Referencia'
        SUPERSEDES = 'supersedes', 'Substitui'
        IMPACTS = 'impacts', 'Impacta'
        SUPPORTS = 'supports', 'Suporta'
        REPLACES = 'replaces', 'Troca'

    source_document = models.ForeignKey(
        ControlledDocument,
        on_delete=models.CASCADE,
        related_name='outgoing_relationships',
        verbose_name='documento origem',
    )
    related_document = models.ForeignKey(
        ControlledDocument,
        on_delete=models.PROTECT,
        related_name='incoming_relationships',
        null=True,
        blank=True,
        verbose_name='documento relacionado',
    )
    relationship_type = models.CharField(
        'tipo de relação', max_length=24, choices=RelationshipType.choices
    )
    external_reference = models.CharField('referência externa', max_length=120, blank=True)
    rationale = models.TextField('justificativa', blank=True)

    class Meta:
        ordering = ['source_document__code', 'relationship_type']
        indexes = [
            models.Index(fields=['source_document', 'relationship_type']),
            models.Index(fields=['related_document']),
        ]
        verbose_name = 'relacionamento documental'
        verbose_name_plural = 'relacionamentos documentais'

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.source_document_id
            and self.related_document_id
            and self.source_document_id == self.related_document_id
        ):
            errors['related_document'] = 'Documento não pode se relacionar consigo mesmo.'
        if not self.related_document_id and not self.external_reference:
            errors['external_reference'] = 'Informe documento relacionado ou referência externa.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.source_document} -> {self.relationship_type}'


class DocumentApproval(SingleInstanceModel):
    class Role(models.TextChoices):
        REVIEWER = 'reviewer', 'Revisor'
        APPROVER = 'approver', 'Aprovador'

    class Decision(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        APPROVED = 'approved', 'Aprovado'
        REJECTED = 'rejected', 'Rejeitado'

    document = models.ForeignKey(
        ControlledDocument,
        on_delete=models.CASCADE,
        related_name='approvals',
        verbose_name='documento',
    )
    role = models.CharField('papel', max_length=24, choices=Role.choices)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='document_approvals',
        verbose_name='usuário',
    )
    decision = models.CharField(
        'decisão', max_length=24, choices=Decision.choices, default=Decision.PENDING
    )
    decided_at = models.DateTimeField('decidido em', null=True, blank=True)
    comments = models.TextField('comentários', blank=True)

    class Meta:
        ordering = ['document__code', 'role', 'created_at']
        indexes = [
            models.Index(fields=['document', 'role', 'decision']),
            models.Index(fields=['user']),
        ]
        verbose_name = 'aprovação documental'
        verbose_name_plural = 'aprovações documentais'

    def clean(self):
        super().clean()
        errors = {}
        if self.decision != self.Decision.PENDING and not self.decided_at:
            errors['decided_at'] = 'Decisão exige data/hora.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.document} - {self.get_role_display()}'


class DocumentDistribution(SingleInstanceModel):
    class Status(models.TextChoices):
        ASSIGNED = 'assigned', 'Distribuído'
        CONFIRMED = 'confirmed', 'Leitura confirmada'
        OVERDUE = 'overdue', 'Vencido'
        CANCELLED = 'cancelled', 'Cancelado'

    document = models.ForeignKey(
        ControlledDocument,
        on_delete=models.PROTECT,
        related_name='distributions',
        verbose_name='documento',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='document_distributions',
        verbose_name='destinatário',
    )
    distributed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_document_distributions',
        null=True,
        blank=True,
        verbose_name='distribuído por',
    )
    due_date = models.DateField('prazo de leitura', null=True, blank=True)
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.ASSIGNED
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='confirmed_document_distributions',
        null=True,
        blank=True,
        verbose_name='confirmado por',
    )
    confirmed_at = models.DateTimeField('confirmado em', null=True, blank=True)
    confirmation_text = models.TextField('texto da confirmação', blank=True)

    class Meta:
        ordering = ['due_date', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'recipient'],
                name='unique_document_distribution_recipient',
            ),
        ]
        indexes = [
            models.Index(fields=['document', 'status']),
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['due_date']),
        ]
        verbose_name = 'distribuição documental'
        verbose_name_plural = 'distribuições documentais'

    def confirm_read(self, user=None, confirmation_text=''):
        if user != self.recipient:
            raise ValidationError({'recipient': 'Somente o destinatário pode confirmar a leitura.'})
        if not confirmation_text:
            raise ValidationError({'confirmation_text': 'Informe a confirmação de leitura.'})
        self.status = self.Status.CONFIRMED
        self.confirmed_by = user
        self.confirmed_at = timezone.now()
        self.confirmation_text = confirmation_text
        self.save(
            update_fields=[
                'status',
                'confirmed_by',
                'confirmed_at',
                'confirmation_text',
                'updated_at',
            ]
        )
        self.document.record_audit(
            DocumentAuditTrail.Action.READ_CONFIRMED, user=user, reason=confirmation_text
        )

    def clean(self):
        super().clean()
        errors = {}
        if self.document and self.document.status != ControlledDocument.Status.PUBLISHED:
            errors['document'] = 'Somente documento publicado pode ser distribuído.'
        if self.confirmed_by_id and self.confirmed_by_id != self.recipient_id:
            errors['confirmed_by'] = 'A confirmação deve ser feita pelo destinatário.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.document} - {self.recipient}'


class DocumentAuditTrail(SingleInstanceModel):
    class Action(models.TextChoices):
        CREATED = 'created', 'Criado'
        SUBMITTED = 'submitted', 'Submetido'
        REVIEWED = 'reviewed', 'Revisado'
        APPROVED = 'approved', 'Aprovado'
        PUBLISHED = 'published', 'Publicado'
        OBSOLETED = 'obsoleted', 'Obsoletado'
        CANCELLED = 'cancelled', 'Cancelado'
        ARCHIVED = 'archived', 'Arquivado'
        REVISION_CREATED = 'revision_created', 'Nova revisão criada'
        READ_CONFIRMED = 'read_confirmed', 'Leitura confirmada'

    document = models.ForeignKey(
        ControlledDocument,
        on_delete=models.PROTECT,
        related_name='audit_trail',
        verbose_name='documento',
    )
    action = models.CharField('ação', max_length=32, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='document_audit_events',
        null=True,
        blank=True,
        verbose_name='ator',
    )
    reason = models.TextField('justificativa', blank=True)
    snapshot = models.TextField('registro congelado')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document', 'action']),
            models.Index(fields=['actor']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'trilha de auditoria documental'
        verbose_name_plural = 'trilhas de auditoria documentais'

    def clean(self):
        super().clean()
        errors = {}
        if not self.snapshot:
            errors['snapshot'] = 'Evento ALCOA+ exige registro congelado.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.document} - {self.action}'
