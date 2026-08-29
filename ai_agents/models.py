from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from base.models import SingleInstanceModel
from base.sequences import AutoCodeMixin, IdentifierSpec, sequence_code


def _sequence_code(model, *args):
    if len(args) == 3:
        _legacy_scope, field_name, prefix = args
    else:
        field_name, prefix = args
    return sequence_code(model, field_name, prefix)


class AIAgentProfile(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'AGT'

    class AgentType(models.TextChoices):
        SUMMARY = 'summary', 'Resumo'
        CLASSIFICATION = 'classification', 'Classificação'
        DOCUMENT_SEARCH = 'document_search', 'Busca documental'
        ROOT_CAUSE = 'root_cause', 'Causa raiz'
        ACTION_SUGGESTION = 'action_suggestion', 'Sugestão de ação'
        RISK_INSIGHT = 'risk_insight', 'Insight de risco'
        REGULATORY_REVIEW = 'regulatory_review', 'Revisão regulatória'
        PROCESS_INSIGHT = 'process_insight', 'Insight de processo'
        WORKFLOW_GATE = 'workflow_gate', 'Controle de workflow'
        COMPLIANCE_CHECK = 'compliance_check', 'Verificação de conformidade'

    class SourceModule(models.TextChoices):
        DOCUMENTS = 'documents', 'Documentos'
        DEVIATIONS = 'deviations', 'Desvios'
        CAPA = 'capa', 'CAPA'
        AUDITS = 'audits', 'Auditorias'
        COMPLAINTS = 'complaints', 'Reclamações'
        RISKS = 'risks', 'Riscos'
        QA = 'qa', 'Análise de Qualidade'
        PRODUCTION = 'production', 'Produção'
        GENERAL = 'general', 'Geral'

    class Provider(models.TextChoices):
        OPENAI = 'openai', 'OpenAI'
        GEMINI = 'gemini', 'Gemini'
        LOCAL = 'local', 'Local determinístico'

    code = models.CharField('código', max_length=80, blank=True)
    name = models.CharField('nome', max_length=180)
    agent_type = models.CharField('tipo de agente', max_length=32, choices=AgentType.choices)
    source_module = models.CharField(
        'módulo principal', max_length=32, choices=SourceModule.choices
    )
    source_module_ref = models.ForeignKey(
        'auxiliary.SystemModule',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='módulo principal normalizado',
    )
    provider = models.CharField(
        'provedor', max_length=32, choices=Provider.choices, default=Provider.OPENAI
    )
    model_name = models.CharField(
        'modelo', max_length=120, default=getattr(settings, 'OPENAI_MODEL', 'gpt-5.5-mini')
    )
    system_prompt = models.TextField('prompt de sistema')
    allowed_source_modules = models.JSONField('módulos permitidos', default=list)
    configuration = models.JSONField('configuração', default=dict, blank=True)
    requires_human_review = models.BooleanField('exige revisão humana', default=True)
    is_active = models.BooleanField('ativo', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_ai_agent_profiles',
        null=True,
        blank=True,
        verbose_name='criado por',
    )

    class Meta:
        ordering = ['source_module', 'code']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_ai_agent_profile_code'),
        ]
        indexes = [
            models.Index(fields=['agent_type', 'is_active']),
            models.Index(fields=['source_module']),
            models.Index(fields=['created_by']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'perfil de agente de IA'
        verbose_name_plural = 'perfis de agentes de IA'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        if not self.system_prompt.strip():
            errors['system_prompt'] = 'Informe o prompt de sistema.'
        if (
            not isinstance(self.allowed_source_modules or [], list)
            or not self.allowed_source_modules
        ):
            errors['allowed_source_modules'] = 'Informe ao menos um módulo permitido.'
        else:
            unsupported = sorted(set(self.allowed_source_modules) - set(self.SourceModule.values))
            if unsupported:
                errors['allowed_source_modules'] = (
                    f'Módulos não suportados: {", ".join(unsupported)}.'
                )
        if not isinstance(self.configuration or {}, dict):
            errors['configuration'] = 'A configuração deve ser um objeto chave/valor.'
        if self.requires_human_review is not True:
            errors['requires_human_review'] = 'Sugestões de IA exigem revisão humana obrigatória.'
        if errors:
            raise ValidationError(errors)

    def create_run(
        self, *, source_module, source_model, source_record_id, input_payload, requested_by=None
    ):
        run = AIAgentRun(
            agent=self,
            source_module=source_module,
            source_model=source_model,
            source_record_id=str(source_record_id),
            input_payload=input_payload or {},
            prompt_text=self.build_prompt(
                source_module, source_model, source_record_id, input_payload or {}
            ),
            model_name=self.model_name,
            requested_by=requested_by,
        )
        run.full_clean()
        run.save()
        return run

    def build_prompt(self, source_module, source_model, source_record_id, input_payload):
        return (
            f'{self.system_prompt.strip()}\n\n'
            f'Módulo: {source_module}\n'
            f'Modelo de origem: {source_model}\n'
            f'Registro: {source_record_id}\n'
            f'Entrada segura: {input_payload}'
        )

    def __str__(self):
        return f'{self.code} - {self.name}'


class AIAgentRun(SingleInstanceModel):
    AUTOMATIC_IDENTIFIERS = (IdentifierSpec('run_number', 'AIRUN'),)

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        QUEUED = 'queued', 'Enfileirado'
        RUNNING = 'running', 'Executando'
        SUCCEEDED = 'succeeded', 'Concluído'
        FAILED = 'failed', 'Falhou'
        CANCELLED = 'cancelled', 'Cancelado'

    class ExecutionMode(models.TextChoices):
        SYNC = 'sync', 'Síncrono'
        ASYNC = 'async', 'Assíncrono'

    run_number = models.CharField('execução', max_length=80, blank=True)
    agent = models.ForeignKey(
        AIAgentProfile, on_delete=models.PROTECT, related_name='runs', verbose_name='agente'
    )
    source_module = models.CharField(
        'módulo de origem', max_length=32, choices=AIAgentProfile.SourceModule.choices
    )
    source_module_ref = models.ForeignKey(
        'auxiliary.SystemModule',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='módulo de origem normalizado',
    )
    source_model = models.CharField('modelo de origem', max_length=120)
    source_model_ref = models.ForeignKey(
        'auxiliary.SystemModel',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='model de origem normalizado',
    )
    source_record_id = models.CharField('id do registro', max_length=120)
    execution_mode = models.CharField(
        'modo de execução', max_length=16, choices=ExecutionMode.choices, default=ExecutionMode.SYNC
    )
    celery_task_name = models.CharField('task Celery', max_length=180, blank=True)
    task_id = models.CharField('id da task', max_length=180, blank=True)
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.DRAFT)
    graph_engine = models.CharField('engine do grafo', max_length=80, blank=True)
    prompt_text = models.TextField('prompt')
    model_name = models.CharField('modelo', max_length=120)
    input_payload = models.JSONField('entrada', default=dict)
    output_payload = models.JSONField('saída estruturada', default=dict, blank=True)
    output_text = models.TextField('saída textual', blank=True)
    error_message = models.TextField('erro', blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='requested_ai_agent_runs',
        null=True,
        blank=True,
        verbose_name='solicitado por',
    )
    started_at = models.DateTimeField('iniciado em', null=True, blank=True)
    completed_at = models.DateTimeField('concluído em', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['run_number'], name='unique_ai_agent_run_number'),
        ]
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['source_module', 'source_model', 'source_record_id']),
            models.Index(fields=['agent']),
            models.Index(fields=['requested_by']),
            models.Index(fields=['run_number']),
        ]
        verbose_name = 'execução de agente de IA'
        verbose_name_plural = 'execuções de agentes de IA'

    def save(self, *args, **kwargs):
        if not self.run_number:
            self.run_number = _sequence_code(AIAgentRun, 'run_number', 'AIRUN')
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        if self.agent_id and self.source_module not in (self.agent.allowed_source_modules or []):
            errors['source_module'] = 'O agente não está autorizado para este módulo de origem.'
        if not isinstance(self.input_payload or {}, dict):
            errors['input_payload'] = 'A entrada deve ser um objeto chave/valor.'
        if not isinstance(self.output_payload or {}, dict):
            errors['output_payload'] = 'A saída deve ser um objeto chave/valor.'
        if self.status == self.Status.SUCCEEDED and not self.output_payload:
            errors['output_payload'] = 'Execução concluída exige saída estruturada.'
        if self.status == self.Status.FAILED and not self.error_message:
            errors['error_message'] = 'Execução com falha exige mensagem de erro.'
        if errors:
            raise ValidationError(errors)

    def enqueue(self, dispatch=True):
        self.execution_mode = self.ExecutionMode.ASYNC
        self.status = self.Status.QUEUED
        self.celery_task_name = 'ai_agents.tasks.process_ai_agent_run'
        self.save(update_fields=['execution_mode', 'status', 'celery_task_name', 'updated_at'])
        if dispatch:
            from ai_agents.tasks import process_ai_agent_run

            result = process_ai_agent_run.delay(self.pk)
            self.task_id = result.id or ''
            self.save(update_fields=['task_id', 'updated_at'])
        return self

    def execute(self, user=None):
        self.status = self.Status.RUNNING
        self.started_at = timezone.now()
        self.error_message = ''
        self.save(update_fields=['status', 'started_at', 'error_message', 'updated_at'])
        try:
            from ai_agents.services import run_ai_agent_graph

            result = run_ai_agent_graph(self)
            self.status = self.Status.SUCCEEDED
            self.graph_engine = result.get('graph_engine', 'langgraph')
            self.output_payload = result.get('output_payload') or {}
            self.output_text = result.get('output_text') or ''
            self.completed_at = timezone.now()
            self.error_message = ''
            self.save(
                update_fields=[
                    'status',
                    'graph_engine',
                    'output_payload',
                    'output_text',
                    'completed_at',
                    'error_message',
                    'updated_at',
                ]
            )
            self.replace_suggestions(result.get('suggestions') or [])
            self.record_audit(status=self.Status.SUCCEEDED, user=user or self.requested_by)
        except Exception as error:
            self.status = self.Status.FAILED
            self.error_message = str(error)
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
            self.record_audit(status=self.Status.FAILED, user=user or self.requested_by)
            raise
        return self

    def replace_suggestions(self, suggestions):
        self.suggestions.all().delete()
        for suggestion in suggestions:
            AIInsightSuggestion.objects.create(
                run=self,
                suggestion_type=suggestion.get(
                    'suggestion_type', AIInsightSuggestion.SuggestionType.ATTENTION
                ),
                title=suggestion.get('title', 'Sugestão de IA'),
                description=suggestion.get('description', ''),
                confidence=Decimal(str(suggestion.get('confidence', '0.70'))),
                source_module=self.source_module,
                source_model=self.source_model,
                source_record_id=self.source_record_id,
            )

    def record_audit(self, status, user=None):
        return AIPromptAuditLog.objects.create(
            run=self,
            agent=self.agent,
            user=user,
            prompt_text=self.prompt_text,
            model_name=self.model_name,
            input_payload=self.input_payload,
            output_payload=self.output_payload,
            output_text=self.output_text,
            status=status,
            error_message=self.error_message,
        )

    def __str__(self):
        return self.run_number


class AIInsightSuggestion(SingleInstanceModel):
    class SuggestionType(models.TextChoices):
        ROOT_CAUSE = 'root_cause', 'Causa raiz'
        ACTION = 'action', 'Ação'
        ATTENTION = 'attention', 'Ponto de atenção'
        RISK = 'risk', 'Risco'
        INCONSISTENCY = 'inconsistency', 'Inconsistência'
        SUMMARY = 'summary', 'Resumo'
        CLASSIFICATION = 'classification', 'Classificação'

    class Status(models.TextChoices):
        PENDING_REVIEW = 'pending_review', 'Pendente de revisão'
        APPROVED = 'approved', 'Aprovada'
        REJECTED = 'rejected', 'Rejeitada'
        APPLIED = 'applied', 'Aplicada'

    run = models.ForeignKey(
        AIAgentRun, on_delete=models.CASCADE, related_name='suggestions', verbose_name='execução'
    )
    suggestion_type = models.CharField(
        'tipo de sugestão', max_length=32, choices=SuggestionType.choices
    )
    title = models.CharField('título', max_length=180)
    description = models.TextField('descrição')
    confidence = models.DecimalField(
        'confiança', max_digits=5, decimal_places=2, default=Decimal('0.70')
    )
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.PENDING_REVIEW
    )
    source_module = models.CharField(
        'módulo de origem', max_length=32, choices=AIAgentProfile.SourceModule.choices
    )
    source_module_ref = models.ForeignKey(
        'auxiliary.SystemModule',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='módulo de origem normalizado',
    )
    source_model = models.CharField('modelo de origem', max_length=120)
    source_model_ref = models.ForeignKey(
        'auxiliary.SystemModel',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='model de origem normalizado',
    )
    source_record_id = models.CharField('id do registro', max_length=120)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reviewed_ai_suggestions',
        null=True,
        blank=True,
        verbose_name='revisado por',
    )
    reviewed_at = models.DateTimeField('revisado em', null=True, blank=True)
    review_comments = models.TextField('comentários da revisão', blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'suggestion_type']),
            models.Index(fields=['source_module', 'source_model', 'source_record_id']),
            models.Index(fields=['reviewed_by']),
            models.Index(fields=['run']),
        ]
        verbose_name = 'sugestão de IA'
        verbose_name_plural = 'sugestões de IA'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        if self.confidence < Decimal('0') or self.confidence > Decimal('1'):
            errors['confidence'] = 'A confiança deve ficar entre 0 e 1.'
        if (
            self.status in {self.Status.APPROVED, self.Status.REJECTED, self.Status.APPLIED}
            and not self.reviewed_by
        ):
            errors['reviewed_by'] = 'Revisão humana é obrigatória.'
        if errors:
            raise ValidationError(errors)

    def approve(self, user, comments=''):
        self._review(self.Status.APPROVED, user, comments)
        return self

    def reject(self, user, comments=''):
        self._review(self.Status.REJECTED, user, comments)
        return self

    def apply(self, user, comments=''):
        self._review(self.Status.APPLIED, user, comments)
        return self

    def _review(self, status, user, comments):
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.review_comments = comments or ''
        self.status = status
        self.full_clean()
        self.save(
            update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_comments', 'updated_at']
        )

    def __str__(self):
        return f'{self.get_suggestion_type_display()} - {self.title}'


class AIPromptAuditLog(SingleInstanceModel):
    run = models.ForeignKey(
        AIAgentRun, on_delete=models.PROTECT, related_name='audit_logs', verbose_name='execução'
    )
    agent = models.ForeignKey(
        AIAgentProfile, on_delete=models.PROTECT, related_name='audit_logs', verbose_name='agente'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ai_prompt_audit_logs',
        null=True,
        blank=True,
        verbose_name='usuário',
    )
    prompt_text = models.TextField('prompt')
    model_name = models.CharField('modelo', max_length=120)
    input_payload = models.JSONField('entrada', default=dict)
    output_payload = models.JSONField('saída estruturada', default=dict, blank=True)
    output_text = models.TextField('saída textual', blank=True)
    status = models.CharField('status', max_length=24, choices=AIAgentRun.Status.choices)
    error_message = models.TextField('erro', blank=True)
    occurred_at = models.DateTimeField('ocorrido em', default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['status', 'occurred_at']),
            models.Index(fields=['agent', 'occurred_at']),
            models.Index(fields=['run']),
            models.Index(fields=['user', 'occurred_at']),
        ]
        verbose_name = 'auditoria de prompt de IA'
        verbose_name_plural = 'auditorias de prompts de IA'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        if not isinstance(self.input_payload or {}, dict):
            errors['input_payload'] = 'A entrada deve ser um objeto chave/valor.'
        if not isinstance(self.output_payload or {}, dict):
            errors['output_payload'] = 'A saída deve ser um objeto chave/valor.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.model_name} - {self.status} - {self.occurred_at:%Y-%m-%d %H:%M}'
