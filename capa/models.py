from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from base.models import SingleInstanceModel
from base.sequences import sequence_code


def _sequence_code(model, *args):
    if len(args) == 3:
        _legacy_scope, field_name, prefix = args
    else:
        field_name, prefix = args
    return sequence_code(model, field_name, prefix)


class CapaRecord(SingleInstanceModel):
    class SourceType(models.TextChoices):
        DEVIATION = 'deviation', 'Desvio'
        AUDIT = 'audit', 'Auditoria'
        COMPLAINT = 'complaint', 'Reclamação'
        RISK = 'risk', 'Risco'
        OOS_OOT = 'oos_oot', 'OOS/OOT'
        CHANGE = 'change', 'Mudança'
        IMPROVEMENT = 'improvement', 'Melhoria'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        OPEN = 'open', 'Aberta'
        IN_PROGRESS = 'in_progress', 'Em andamento'
        PENDING_EFFECTIVENESS = 'pending_effectiveness', 'Aguardando eficácia'
        PENDING_APPROVAL = 'pending_approval', 'Aguardando aprovação'
        CLOSED = 'closed', 'Encerrada'
        CANCELLED = 'cancelled', 'Cancelada'

    capa_number = models.CharField('CAPA', max_length=80, blank=True)
    source_type = models.CharField('origem', max_length=24, choices=SourceType.choices)
    deviation_event = models.ForeignKey(
        'deviations.QualityEvent',
        on_delete=models.PROTECT,
        related_name='capa_records',
        null=True,
        blank=True,
        verbose_name='desvio/não conformidade',
    )
    customer_complaint = models.ForeignKey(
        'crm.CustomerComplaint',
        on_delete=models.PROTECT,
        related_name='capa_records',
        null=True,
        blank=True,
        verbose_name='reclamação',
    )
    quality_result = models.ForeignKey(
        'quality.QualityResult',
        on_delete=models.PROTECT,
        related_name='capa_records',
        null=True,
        blank=True,
        verbose_name='resultado OOS/OOT',
    )
    source_reference = models.CharField('referência de origem', max_length=120, blank=True)
    title = models.CharField('título', max_length=180)
    root_cause = models.TextField('causa raiz')
    action_plan = models.TextField('plano de ação')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_capas',
        verbose_name='responsável',
    )
    due_date = models.DateField('prazo')
    status = models.CharField('status', max_length=32, choices=Status.choices, default=Status.DRAFT)
    requires_effectiveness_check = models.BooleanField('exige eficácia', default=True)
    effectiveness_criteria = models.TextField('critério de eficácia', blank=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='opened_capas',
        null=True,
        blank=True,
        verbose_name='aberta por',
    )
    opened_at = models.DateTimeField('aberta em', null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='closed_capas',
        null=True,
        blank=True,
        verbose_name='encerrada por',
    )
    closed_at = models.DateTimeField('encerrada em', null=True, blank=True)
    closure_summary = models.TextField('resumo de encerramento', blank=True)
    cancel_reason = models.TextField('motivo do cancelamento', blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['capa_number'], name='unique_capa_number'),
        ]
        indexes = [
            models.Index(fields=['source_type', 'status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['owner']),
            models.Index(fields=['deviation_event']),
            models.Index(fields=['customer_complaint']),
            models.Index(fields=['quality_result']),
            models.Index(fields=['capa_number']),
        ]
        verbose_name = 'CAPA'
        verbose_name_plural = 'CAPAs'

    def save(self, *args, **kwargs):
        if not self.capa_number:
            self.capa_number = _sequence_code(CapaRecord, 'capa_number', 'CAPA')
        super().save(*args, **kwargs)

    def submit(self, user=None):
        if self.status != self.Status.DRAFT:
            raise ValidationError({'status': 'Somente CAPAs em rascunho podem ser submetidas.'})
        self.status = self.Status.OPEN
        self.opened_by = user or self.opened_by
        self.opened_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'opened_by', 'opened_at', 'updated_at'])

    def start(self, user=None):
        if self.status not in {self.Status.DRAFT, self.Status.OPEN}:
            raise ValidationError(
                {'status': 'Somente CAPAs em rascunho ou abertas podem iniciar execução.'}
            )
        self.status = self.Status.IN_PROGRESS
        self.owner = self.owner or user
        self.full_clean()
        self.save(update_fields=['status', 'owner', 'updated_at'])

    def close(self, summary, user=None):
        if not summary:
            raise ValidationError({'closure_summary': 'Informe o resumo de encerramento.'})
        if (
            not self.actions.exists()
            or self.actions.exclude(status=CapaAction.Status.COMPLETED).exists()
        ):
            raise ValidationError({'actions': 'Encerramento exige todas as ações concluídas.'})
        missing_evidence = (
            self.actions.filter(evidence_required=True).exclude(evidences__isnull=False).exists()
        )
        if missing_evidence:
            raise ValidationError(
                {'evidences': 'Encerramento exige evidências para ações que requerem evidência.'}
            )
        if (
            self.requires_effectiveness_check
            and not self.effectiveness_checks.filter(
                status=EffectivenessCheck.Status.EFFECTIVE
            ).exists()
        ):
            raise ValidationError(
                {'effectiveness': 'Encerramento exige avaliação de eficácia efetiva.'}
            )
        has_required_approval = self.approvals.filter(required=True).exists()
        has_pending_required_approval = (
            self.approvals.filter(required=True)
            .exclude(decision=CapaApproval.Decision.APPROVED)
            .exists()
        )
        if not has_required_approval or has_pending_required_approval:
            raise ValidationError(
                {'approvals': 'Encerramento exige aprovações obrigatórias aprovadas.'}
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
            raise ValidationError({'status': 'CAPA encerrada não pode ser cancelada.'})
        self.status = self.Status.CANCELLED
        self.cancel_reason = reason
        self.save(update_fields=['status', 'cancel_reason', 'updated_at'])

    def generate_notifications(self, today=None, due_soon_days=7):
        today = today or timezone.localdate()
        notifications = []
        for action in self.actions.exclude(status=CapaAction.Status.COMPLETED):
            if action.due_date < today:
                notifications.append(
                    self._ensure_notification(
                        CapaNotification.NotificationType.OVERDUE,
                        action=action,
                        recipient=action.responsible,
                        due_date=action.due_date,
                    )
                )
            elif action.due_date <= today + timedelta(days=due_soon_days):
                notifications.append(
                    self._ensure_notification(
                        CapaNotification.NotificationType.DUE_SOON,
                        action=action,
                        recipient=action.responsible,
                        due_date=action.due_date,
                    )
                )
        for approval in self.approvals.filter(
            required=True, decision=CapaApproval.Decision.PENDING
        ):
            notifications.append(
                self._ensure_notification(
                    CapaNotification.NotificationType.APPROVAL_REQUIRED,
                    approval=approval,
                    recipient=approval.approver,
                    due_date=today,
                )
            )
        for check in self.effectiveness_checks.filter(
            status=EffectivenessCheck.Status.PENDING, planned_date__lte=today
        ):
            notifications.append(
                self._ensure_notification(
                    CapaNotification.NotificationType.EFFECTIVENESS_DUE,
                    effectiveness_check=check,
                    recipient=self.owner,
                    due_date=check.planned_date,
                )
            )
        return notifications

    def _ensure_notification(
        self,
        notification_type,
        recipient,
        due_date,
        action=None,
        approval=None,
        effectiveness_check=None,
    ):
        notification, _created = CapaNotification.objects.get_or_create(
            capa=self,
            notification_type=notification_type,
            action=action,
            approval=approval,
            effectiveness_check=effectiveness_check,
            defaults={
                'recipient': recipient,
                'due_date': due_date,
                'message': f'{self.capa_number}: {CapaNotification.NotificationType(notification_type).label}',
            },
        )
        return notification

    def clean(self):
        super().clean()
        errors = {}
        for field in ('deviation_event', 'customer_complaint', 'quality_result'):
            pass
        for field in ('owner', 'opened_by', 'closed_by'):
            pass
        if not any(
            (
                self.deviation_event_id,
                self.customer_complaint_id,
                self.quality_result_id,
                self.source_reference,
            )
        ):
            errors['source_reference'] = 'Informe uma origem ou referência para a CAPA.'
        if self.requires_effectiveness_check and not self.effectiveness_criteria:
            errors['effectiveness_criteria'] = (
                'Informe critérios de eficácia quando a verificação for exigida.'
            )
        if self.closed_at and self.opened_at and self.closed_at < self.opened_at:
            errors['closed_at'] = 'A data de encerramento não pode ser anterior à abertura.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.capa_number


class CapaAction(SingleInstanceModel):
    class ActionType(models.TextChoices):
        CORRECTIVE = 'corrective', 'Corretiva'
        PREVENTIVE = 'preventive', 'Preventiva'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        IN_PROGRESS = 'in_progress', 'Em andamento'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'

    capa = models.ForeignKey(
        CapaRecord, on_delete=models.CASCADE, related_name='actions', verbose_name='CAPA'
    )
    action_type = models.CharField('tipo', max_length=24, choices=ActionType.choices)
    title = models.CharField('título', max_length=180)
    description = models.TextField('descrição')
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='capa_actions',
        verbose_name='responsável',
    )
    due_date = models.DateField('prazo')
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.PENDING
    )
    evidence_required = models.BooleanField('exige evidência', default=True)
    completion_notes = models.TextField('observações de conclusão', blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='completed_capa_actions',
        null=True,
        blank=True,
        verbose_name='concluída por',
    )
    completed_at = models.DateTimeField('concluída em', null=True, blank=True)

    class Meta:
        ordering = ['capa__capa_number', 'due_date']
        indexes = [
            models.Index(fields=['capa', 'status']),
            models.Index(fields=['responsible', 'due_date']),
            models.Index(fields=['action_type']),
        ]
        verbose_name = 'ação CAPA'
        verbose_name_plural = 'ações CAPA'

    def start(self):
        if self.status != self.Status.PENDING:
            raise ValidationError({'status': 'Somente ações pendentes podem iniciar.'})
        self.status = self.Status.IN_PROGRESS
        self.save(update_fields=['status', 'updated_at'])

    def complete(self, user=None, completion_notes=''):
        if not completion_notes:
            raise ValidationError({'completion_notes': 'Informe as observações de conclusão.'})
        self.status = self.Status.COMPLETED
        self.completed_by = user
        self.completed_at = timezone.now()
        self.completion_notes = completion_notes
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'completed_by',
                'completed_at',
                'completion_notes',
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
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class CapaEvidence(SingleInstanceModel):
    capa = models.ForeignKey(
        CapaRecord, on_delete=models.CASCADE, related_name='evidences', verbose_name='CAPA'
    )
    action = models.ForeignKey(
        CapaAction,
        on_delete=models.CASCADE,
        related_name='evidences',
        null=True,
        blank=True,
        verbose_name='ação',
    )
    title = models.CharField('título', max_length=160)
    file_reference = models.CharField('arquivo', max_length=255)
    content_hash = models.CharField('hash do conteúdo', max_length=128)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_capa_evidences',
        null=True,
        blank=True,
        verbose_name='enviado por',
    )
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['capa__capa_number', 'title']
        indexes = [
            models.Index(fields=['capa']),
            models.Index(fields=['action']),
            models.Index(fields=['content_hash']),
        ]
        verbose_name = 'evidência CAPA'
        verbose_name_plural = 'evidências CAPA'

    def clean(self):
        super().clean()
        errors = {}
        if self.action and self.capa and self.action.capa_id != self.capa_id:
            errors['action'] = 'A evidência deve pertencer a uma ação da mesma CAPA.'
        if not self.content_hash:
            errors['content_hash'] = 'Evidência exige hash para integridade dos dados.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class EffectivenessCheck(SingleInstanceModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        EFFECTIVE = 'effective', 'Eficaz'
        INEFFECTIVE = 'ineffective', 'Ineficaz'

    capa = models.ForeignKey(
        CapaRecord,
        on_delete=models.CASCADE,
        related_name='effectiveness_checks',
        verbose_name='CAPA',
    )
    criteria = models.TextField('critérios')
    planned_date = models.DateField('data planejada')
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.PENDING
    )
    result = models.TextField('resultado', blank=True)
    evidence_reference = models.CharField('evidência', max_length=255, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='verified_capa_effectiveness',
        null=True,
        blank=True,
        verbose_name='verificado por',
    )
    verified_at = models.DateTimeField('verificado em', null=True, blank=True)

    class Meta:
        ordering = ['planned_date']
        indexes = [
            models.Index(fields=['capa', 'status']),
            models.Index(fields=['planned_date']),
        ]
        verbose_name = 'verificação de eficácia CAPA'
        verbose_name_plural = 'verificações de eficácia CAPA'

    def verify(self, result, effective, user=None, evidence_reference=''):
        if not result:
            raise ValidationError({'result': 'Informe o resultado da verificação de eficácia.'})
        if effective and not evidence_reference:
            raise ValidationError({'evidence_reference': 'Eficácia aprovada exige evidência.'})
        self.status = self.Status.EFFECTIVE if effective else self.Status.INEFFECTIVE
        self.result = result
        self.evidence_reference = evidence_reference
        self.verified_by = user
        self.verified_at = timezone.now()
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'result',
                'evidence_reference',
                'verified_by',
                'verified_at',
                'updated_at',
            ]
        )

    def clean(self):
        super().clean()
        errors = {}
        if self.status != self.Status.PENDING and (
            not self.result or not self.verified_by_id or not self.verified_at
        ):
            errors['result'] = 'Verificação concluída exige resultado, responsável e data.'
        if self.status == self.Status.EFFECTIVE and not self.evidence_reference:
            errors['evidence_reference'] = 'Eficácia aprovada exige evidência.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.capa} - {self.get_status_display()}'


class CapaApproval(SingleInstanceModel):
    class Role(models.TextChoices):
        QA = 'qa', 'Garantia da Qualidade'
        OWNER = 'owner', 'Responsável'
        REGULATORY = 'regulatory', 'Regulatório'
        RESPONSIBLE_AREA = 'responsible_area', 'Área responsável'

    class Decision(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        APPROVED = 'approved', 'Aprovado'
        REJECTED = 'rejected', 'Rejeitado'

    capa = models.ForeignKey(
        CapaRecord, on_delete=models.CASCADE, related_name='approvals', verbose_name='CAPA'
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='capa_approvals',
        verbose_name='aprovador',
    )
    role = models.CharField('papel', max_length=32, choices=Role.choices)
    required = models.BooleanField('obrigatória', default=True)
    decision = models.CharField(
        'decisão', max_length=24, choices=Decision.choices, default=Decision.PENDING
    )
    comments = models.TextField('comentários', blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='decided_capa_approvals',
        null=True,
        blank=True,
        verbose_name='decidido por',
    )
    decided_at = models.DateTimeField('decidido em', null=True, blank=True)

    class Meta:
        ordering = ['capa__capa_number', 'role']
        constraints = [
            models.UniqueConstraint(
                fields=['capa', 'role', 'approver'],
                name='unique_capa_approval_role_user',
            ),
        ]
        indexes = [
            models.Index(fields=['capa', 'decision']),
            models.Index(fields=['approver']),
        ]
        verbose_name = 'aprovação CAPA'
        verbose_name_plural = 'aprovações CAPA'

    def approve(self, user=None, comments=''):
        self.decision = self.Decision.APPROVED
        self.comments = comments or self.comments
        self.decided_by = user or self.approver
        self.decided_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['decision', 'comments', 'decided_by', 'decided_at', 'updated_at'])

    def reject(self, user=None, comments=''):
        if not comments:
            raise ValidationError({'comments': 'Informe o motivo da rejeição.'})
        self.decision = self.Decision.REJECTED
        self.comments = comments
        self.decided_by = user or self.approver
        self.decided_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['decision', 'comments', 'decided_by', 'decided_at', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        if self.decision != self.Decision.PENDING and not self.decided_at:
            errors['decided_at'] = 'Decisão exige data/hora.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.capa} - {self.get_role_display()}'


class CapaNotification(SingleInstanceModel):
    class NotificationType(models.TextChoices):
        DUE_SOON = 'due_soon', 'Prazo próximo'
        OVERDUE = 'overdue', 'Atrasada'
        APPROVAL_REQUIRED = 'approval_required', 'Aprovação pendente'
        EFFECTIVENESS_DUE = 'effectiveness_due', 'Eficácia pendente'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        SENT = 'sent', 'Enviada'
        ACKNOWLEDGED = 'acknowledged', 'Ciente'

    capa = models.ForeignKey(
        CapaRecord, on_delete=models.CASCADE, related_name='notifications', verbose_name='CAPA'
    )
    action = models.ForeignKey(
        CapaAction,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        verbose_name='ação',
    )
    approval = models.ForeignKey(
        CapaApproval,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        verbose_name='aprovação',
    )
    effectiveness_check = models.ForeignKey(
        EffectivenessCheck,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        verbose_name='verificação de eficácia',
    )
    notification_type = models.CharField('tipo', max_length=32, choices=NotificationType.choices)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='capa_notifications',
        verbose_name='destinatário',
    )
    due_date = models.DateField('data de referência')
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.PENDING
    )
    message = models.TextField('mensagem')
    sent_at = models.DateTimeField('enviada em', null=True, blank=True)

    class Meta:
        ordering = ['due_date', 'notification_type']
        indexes = [
            models.Index(fields=['capa', 'notification_type']),
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['due_date']),
        ]
        verbose_name = 'notificação CAPA'
        verbose_name_plural = 'notificações CAPA'

    def mark_sent(self):
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        for field in ('capa', 'action', 'approval', 'effectiveness_check'):
            pass
        if self.action and self.action.capa_id != self.capa_id:
            errors['action'] = 'A ação deve pertencer à CAPA informada.'
        if self.approval and self.approval.capa_id != self.capa_id:
            errors['approval'] = 'A aprovação deve pertencer à CAPA informada.'
        if self.effectiveness_check and self.effectiveness_check.capa_id != self.capa_id:
            errors['effectiveness_check'] = 'A verificação deve pertencer à CAPA informada.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.capa} - {self.get_notification_type_display()}'
