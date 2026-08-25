from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from base.modules import OperationalModule
from base.models import SingleInstanceModel
from base.normalized_locations import validate_normalized_location
from integrations.models import sanitize_safe_context


def institution_logo_path(instance, filename):
    return f'institution/logos/{filename}'


def _only_digits(value):
    return ''.join(character for character in str(value or '') if character.isdigit())


def _is_valid_cpf(value):
    digits = _only_digits(value)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False

    for size in (9, 10):
        total = sum(
            int(digit) * weight for digit, weight in zip(digits[:size], range(size + 1, 1, -1))
        )
        check_digit = (total * 10) % 11
        if check_digit == 10:
            check_digit = 0
        if check_digit != int(digits[size]):
            return False
    return True


class InstitutionSettings(SingleInstanceModel):
    """Dados institucionais da empresa que utiliza a instância do sistema.

    Como o RGN Farma System opera em modo single-instance, este modelo
    armazena as informações da organização proprietária da instância
    (razão social, CNPJ, endereço, contato e logo).
    """

    class TaxRegime(models.TextChoices):
        SIMPLES_NACIONAL = 'simples_nacional', 'Simples Nacional'
        LUCRO_PRESUMIDO = 'lucro_presumido', 'Lucro Presumido'
        LUCRO_REAL = 'lucro_real', 'Lucro Real'
        EXEMPT = 'exempt', 'Isento'

    trade_name = models.CharField('nome fantasia', max_length=255, blank=True)
    legal_name = models.CharField('razão social', max_length=255)
    document = models.CharField('CNPJ/CPF', max_length=32)
    state_registration = models.CharField('inscrição estadual', max_length=40, blank=True)
    municipal_registration = models.CharField('inscrição municipal', max_length=40, blank=True)
    tax_regime = models.CharField(
        'regime tributário', max_length=32, choices=TaxRegime.choices, blank=True
    )
    phone = models.CharField('telefone', max_length=40, blank=True)
    email = models.EmailField('e-mail institucional', blank=True)
    website = models.URLField('site', blank=True)
    zipcode = models.CharField('CEP', max_length=20, blank=True)
    street = models.CharField('logradouro', max_length=200, blank=True)
    street_number = models.CharField('número', max_length=20, blank=True)
    complement = models.CharField('complemento', max_length=100, blank=True)
    neighborhood = models.CharField('bairro', max_length=120, blank=True)
    country_ref = models.ForeignKey(
        'auxiliary.Country',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name='país',
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
    logo = models.ImageField('logo', upload_to=institution_logo_path, blank=True)
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['legal_name']
        verbose_name = 'dados da instituição'
        verbose_name_plural = 'dados da instituição'

    def clean(self):
        super().clean()
        validate_normalized_location(self, require=True)

    def __str__(self):
        return self.trade_name or self.legal_name


class TechnicalResponsible(SingleInstanceModel):
    class Profession(models.TextChoices):
        PHARMACIST = 'pharmacist', 'Farmacêutico'

    class ProfessionalCouncil(models.TextChoices):
        CRF = 'CRF', 'Conselho Regional de Farmácia'

    class RegistrationType(models.TextChoices):
        DEFINITIVE = 'definitive', 'Definitiva'
        PROVISIONAL = 'provisional', 'Provisória'
        SECONDARY = 'secondary', 'Secundária'
        SPECIALIST = 'specialist', 'Especialista/outro'

    class RegistrationStatus(models.TextChoices):
        ACTIVE = 'active', 'Ativa'
        SUSPENDED = 'suspended', 'Suspensa'
        CANCELLED = 'cancelled', 'Cancelada'
        EXPIRED = 'expired', 'Vencida'
        PENDING = 'pending', 'Pendente'

    class ResponsibilityType(models.TextChoices):
        PRIMARY = 'primary', 'Responsável técnico principal'
        SUBSTITUTE = 'substitute', 'Responsável técnico substituto'
        ASSISTANT = 'assistant', 'Assistente técnico'

    institution = models.ForeignKey(
        InstitutionSettings,
        on_delete=models.PROTECT,
        related_name='technical_responsibles',
        verbose_name='instituição',
    )
    fiscal_company = models.ForeignKey(
        'fiscal.FiscalCompany',
        on_delete=models.PROTECT,
        related_name='technical_responsibles',
        null=True,
        blank=True,
        verbose_name='empresa fiscal',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='technical_responsibilities',
        null=True,
        blank=True,
        verbose_name='usuário vinculado',
    )
    full_name = models.CharField('nome completo', max_length=255)
    cpf = models.CharField('CPF', max_length=14)
    email = models.EmailField('e-mail', blank=True)
    phone = models.CharField('telefone', max_length=40, blank=True)
    profession = models.CharField(
        'profissão',
        max_length=32,
        choices=Profession.choices,
        default=Profession.PHARMACIST,
    )
    council = models.CharField(
        'conselho profissional',
        max_length=16,
        choices=ProfessionalCouncil.choices,
        default=ProfessionalCouncil.CRF,
    )
    council_state = models.ForeignKey(
        'auxiliary.StateProvince',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='UF do conselho',
    )
    council_registration_number = models.CharField(
        'número de inscrição no conselho',
        max_length=40,
    )
    registration_type = models.CharField(
        'tipo de inscrição',
        max_length=24,
        choices=RegistrationType.choices,
        default=RegistrationType.DEFINITIVE,
    )
    registration_status = models.CharField(
        'status da inscrição',
        max_length=24,
        choices=RegistrationStatus.choices,
        default=RegistrationStatus.ACTIVE,
    )
    responsibility_type = models.CharField(
        'tipo de responsabilidade',
        max_length=24,
        choices=ResponsibilityType.choices,
        default=ResponsibilityType.PRIMARY,
    )
    start_date = models.DateField('data de início')
    end_date = models.DateField('data de término', null=True, blank=True)
    weekly_workload_hours = models.DecimalField(
        'carga horária semanal',
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    work_schedule = models.JSONField(
        'grade/horário de assistência farmacêutica', default=dict, blank=True
    )
    regularity_certificate_number = models.CharField(
        'número da certidão de regularidade',
        max_length=80,
        blank=True,
    )
    regularity_certificate_issued_at = models.DateField(
        'data de emissão da certidão',
        null=True,
        blank=True,
    )
    regularity_certificate_valid_until = models.DateField(
        'validade da certidão',
        null=True,
        blank=True,
    )
    certificate_file_reference = models.CharField(
        'arquivo/referência da certidão',
        max_length=255,
        blank=True,
    )
    verification_url = models.URLField('URL de verificação', blank=True)
    verified_at = models.DateTimeField('verificado em', null=True, blank=True)
    notes = models.TextField('observações', blank=True)
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['full_name']
        constraints = [
            models.UniqueConstraint(
                fields=['institution'],
                condition=models.Q(
                    fiscal_company__isnull=True,
                    is_active=True,
                    responsibility_type='primary',
                ),
                name='unique_active_primary_technical_responsible_institution',
            ),
            models.UniqueConstraint(
                fields=['institution', 'fiscal_company'],
                condition=models.Q(
                    fiscal_company__isnull=False,
                    is_active=True,
                    responsibility_type='primary',
                ),
                name='unique_active_primary_technical_responsible_company',
            ),
        ]
        indexes = [
            models.Index(fields=['institution', 'is_active']),
            models.Index(fields=['fiscal_company', 'is_active']),
            models.Index(fields=['user']),
            models.Index(fields=['cpf']),
            models.Index(fields=['council', 'council_registration_number']),
            models.Index(fields=['registration_status', 'is_active']),
            models.Index(fields=['responsibility_type', 'is_active']),
            models.Index(fields=['regularity_certificate_valid_until']),
        ]
        verbose_name = 'responsável técnico'
        verbose_name_plural = 'responsáveis técnicos'

    def clean(self):
        super().clean()
        errors = {}
        self.full_name = ' '.join(str(self.full_name or '').split())
        self.cpf = _only_digits(self.cpf)
        self.council = str(self.council or '').upper()
        self.council_registration_number = str(self.council_registration_number or '').strip()

        if not self.full_name:
            errors['full_name'] = 'Informe o nome completo.'
        if not _is_valid_cpf(self.cpf):
            errors['cpf'] = 'Informe um CPF válido.'
        if self.council == self.ProfessionalCouncil.CRF:
            if not self.council_state:
                errors['council_state'] = 'Informe a UF do CRF.'
            if not self.council_registration_number:
                errors['council_registration_number'] = 'Informe o número de inscrição no CRF.'
        if self.end_date and self.start_date and self.end_date < self.start_date:
            errors['end_date'] = 'A data de término não pode ser anterior à data de início.'
        if self.weekly_workload_hours is not None and self.weekly_workload_hours <= 0:
            errors['weekly_workload_hours'] = 'A carga horária semanal deve ser maior que zero.'
        if not isinstance(self.work_schedule or {}, dict):
            errors['work_schedule'] = 'A grade de assistência deve ser um objeto JSON.'
        if (
            self.regularity_certificate_issued_at
            and self.regularity_certificate_valid_until
            and self.regularity_certificate_valid_until < self.regularity_certificate_issued_at
        ):
            errors['regularity_certificate_valid_until'] = (
                'A validade da certidão não pode ser anterior à emissão.'
            )
        if self.is_active and not self.start_date:
            errors['start_date'] = 'Responsável técnico ativo exige data de início.'
        if (
            self.is_active
            and self.registration_status != self.RegistrationStatus.ACTIVE
            and self.responsibility_type == self.ResponsibilityType.PRIMARY
        ):
            errors['registration_status'] = (
                'Responsável técnico principal ativo exige inscrição ativa no conselho.'
            )
        if self._has_active_primary_duplicate():
            errors['responsibility_type'] = (
                'Já existe responsável técnico principal ativo para esta instituição/empresa fiscal.'
            )
        if errors:
            raise ValidationError(errors)

    def _has_active_primary_duplicate(self):
        if not self.is_active or self.responsibility_type != self.ResponsibilityType.PRIMARY:
            return False
        queryset = self.__class__.objects.filter(
            institution=self.institution,
            responsibility_type=self.ResponsibilityType.PRIMARY,
            is_active=True,
        )
        if self.fiscal_company_id:
            queryset = queryset.filter(fiscal_company=self.fiscal_company)
        else:
            queryset = queryset.filter(fiscal_company__isnull=True)
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        return queryset.exists()

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        council_state = self.council_state.name if self.council_state else ''
        council_label = f'{self.council}/{council_state}'.rstrip('/')
        return f'{self.full_name} - {council_label} {self.council_registration_number}'.strip()


class GovernanceParameter(SingleInstanceModel):
    class Scope(models.TextChoices):
        GLOBAL = 'global', 'Global'
        MODULE = 'module', 'Modulo'
        WORKFLOW = 'workflow', 'Workflow'
        RETENTION = 'retention', 'Retencao'
        ALERT = 'alert', 'Alerta'
        APPROVAL = 'approval', 'Alcada'
        INVENTORY = 'inventory', 'Estoque'
        QUALITY = 'quality', 'Qualidade'

    class ValueType(models.TextChoices):
        STRING = 'string', 'Texto'
        INTEGER = 'integer', 'Inteiro'
        DECIMAL = 'decimal', 'Decimal'
        BOOLEAN = 'boolean', 'Booleano'
        JSON = 'json', 'JSON'
        DAYS = 'days', 'Dias'
        CHOICE = 'choice', 'Escolha'

    scope = models.CharField('escopo', max_length=24, choices=Scope.choices)
    module = models.CharField('modulo', max_length=40, choices=OperationalModule.choices)
    module_ref = models.ForeignKey(
        'auxiliary.SystemModule',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='modulo normalizado',
    )
    key = models.CharField('chave', max_length=120)
    value_type = models.CharField('tipo de valor', max_length=24, choices=ValueType.choices)
    value = models.JSONField('valor', default=dict)
    default_value = models.JSONField('valor padrao', default=dict, blank=True)
    rules = models.JSONField('regras', default=dict, blank=True)
    description = models.TextField('descricao', blank=True)
    is_active = models.BooleanField('ativo', default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='updated_governance_parameters',
        null=True,
        blank=True,
        verbose_name='atualizado por',
    )

    class Meta:
        ordering = ['scope', 'module', 'key']
        constraints = [
            models.UniqueConstraint(
                fields=['scope', 'module', 'key'],
                name='unique_governance_parameter',
            ),
        ]
        indexes = [
            models.Index(fields=['scope', 'module', 'is_active']),
            models.Index(fields=['key']),
            models.Index(fields=['updated_by']),
        ]
        verbose_name = 'parametro de governanca'
        verbose_name_plural = 'parametros de governanca'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        if not self.key or not self.key.strip():
            errors['key'] = 'Informe a chave do parametro.'
        if not isinstance(self.rules or {}, dict):
            errors['rules'] = 'As regras devem ser um objeto chave/valor.'
        else:
            try:
                self._coerce_value(self.value)
                if self.default_value not in ({}, None):
                    self._coerce_value(self.default_value)
            except ValidationError as error:
                errors['value'] = error.message
        if errors:
            raise ValidationError(errors)

    def typed_value(self):
        return self._coerce_value(self.value)

    def _coerce_value(self, value):
        if self.value_type == self.ValueType.STRING:
            if not isinstance(value, str) or not value.strip():
                raise ValidationError('O valor deve ser um texto nao vazio.')
            return value.strip()
        if self.value_type in (self.ValueType.INTEGER, self.ValueType.DAYS):
            if isinstance(value, bool):
                raise ValidationError('O valor deve ser inteiro.')
            try:
                converted = int(value)
            except (TypeError, ValueError) as error:
                raise ValidationError('O valor deve ser inteiro.') from error
            self._validate_range(converted)
            return converted
        if self.value_type == self.ValueType.DECIMAL:
            if isinstance(value, bool) or isinstance(value, (dict, list)):
                raise ValidationError('O valor deve ser decimal.')
            try:
                decimal_value = Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError) as error:
                raise ValidationError('O valor deve ser decimal.') from error
            self._validate_range(decimal_value)
            return decimal_value
        if self.value_type == self.ValueType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, str) and value.lower() in {'true', 'false'}:
                return value.lower() == 'true'
            raise ValidationError('O valor deve ser booleano.')
        if self.value_type == self.ValueType.JSON:
            if not isinstance(value, (dict, list)):
                raise ValidationError('O valor deve ser um objeto ou lista JSON.')
            return value
        if self.value_type == self.ValueType.CHOICE:
            choices = (self.rules or {}).get('choices')
            if not isinstance(choices, list) or not choices:
                raise ValidationError('Parametros de escolha exigem rules.choices.')
            if value not in choices:
                raise ValidationError('O valor deve estar entre as escolhas permitidas.')
            return value
        return value

    def _validate_range(self, value):
        rules = self.rules or {}
        if 'min' in rules and value < Decimal(str(rules['min'])):
            raise ValidationError('O valor esta abaixo do minimo permitido.')
        if 'max' in rules and value > Decimal(str(rules['max'])):
            raise ValidationError('O valor esta acima do maximo permitido.')

    def __str__(self):
        return f'{self.module}.{self.key}'


class GovernanceCatalogItem(SingleInstanceModel):
    class CatalogType(models.TextChoices):
        DOCUMENT_TYPE = 'document_type', 'Tipo de documento'
        DEVIATION_TYPE = 'deviation_type', 'Tipo de desvio'
        CAPA_CATEGORY = 'capa_category', 'Categoria de CAPA'
        STATUS = 'status', 'Status'
        CRITICALITY = 'criticality', 'Criticidade'
        WORKFLOW_STEP = 'workflow_step', 'Etapa de workflow'
        BLOCK_REASON = 'block_reason', 'Motivo de bloqueio'
        LOT_STATUS = 'lot_status', 'Status de lote'
        INVENTORY_REASON = 'inventory_reason', 'Motivo de estoque'

    catalog_type = models.CharField('tipo de catalogo', max_length=40, choices=CatalogType.choices)
    module = models.CharField('modulo', max_length=40, choices=OperationalModule.choices)
    module_ref = models.ForeignKey(
        'auxiliary.SystemModule',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='modulo normalizado',
    )
    code = models.CharField('codigo', max_length=80)
    label = models.CharField('rotulo', max_length=180)
    value = models.CharField('valor', max_length=120)
    color = models.CharField('cor', max_length=40, blank=True)
    order = models.PositiveIntegerField('ordem', default=0)
    is_active = models.BooleanField('ativo', default=True)
    metadata = models.JSONField('metadados', default=dict, blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='children',
        null=True,
        blank=True,
        verbose_name='item pai',
    )

    class Meta:
        ordering = ['catalog_type', 'module', 'order', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['catalog_type', 'module', 'code'],
                name='unique_governance_catalog_code',
            ),
        ]
        indexes = [
            models.Index(fields=['catalog_type', 'module', 'is_active']),
            models.Index(fields=['code']),
            models.Index(fields=['parent']),
        ]
        verbose_name = 'item de catalogo de governanca'
        verbose_name_plural = 'itens de catalogo de governanca'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        for field in ('code', 'label', 'value'):
            if not getattr(self, field, '').strip():
                errors[field] = 'Informe um valor nao vazio.'
        if not isinstance(self.metadata or {}, dict):
            errors['metadata'] = 'Os metadados devem ser um objeto chave/valor.'
        if self.parent_id:
            if False:
                errors['parent'] = 'O item pai é incompatível com o registro.'
            if self.parent.catalog_type != self.catalog_type or self.parent.module != self.module:
                errors['parent'] = 'O item pai deve pertencer ao mesmo catalogo e modulo.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.get_catalog_type_display()} - {self.code}'


class GovernanceAuditLog(SingleInstanceModel):
    class LogType(models.TextChoices):
        TECHNICAL = 'technical', 'Tecnico'
        FUNCTIONAL = 'functional', 'Funcional'
        SECURITY = 'security', 'Seguranca'
        PARAMETER = 'parameter', 'Parametro'
        MODULE = 'module', 'Modulo'
        DEMO_LOAD = 'demo_load', 'Carga demo'

    class Severity(models.TextChoices):
        INFO = 'info', 'Informacao'
        WARNING = 'warning', 'Alerta'
        ERROR = 'error', 'Erro'
        CRITICAL = 'critical', 'Critico'

    log_type = models.CharField('tipo de log', max_length=24, choices=LogType.choices)
    severity = models.CharField(
        'severidade', max_length=16, choices=Severity.choices, default=Severity.INFO
    )
    severity_ref = models.ForeignKey(
        'auxiliary.ImpactLevel',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='severidade normalizada',
    )
    module = models.CharField('modulo', max_length=40, choices=OperationalModule.choices)
    module_ref = models.ForeignKey(
        'auxiliary.SystemModule',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='modulo normalizado',
    )
    action = models.CharField('acao', max_length=120)
    target_model = models.CharField('modelo alvo', max_length=120, blank=True)
    target_model_ref = models.ForeignKey(
        'auxiliary.SystemModel',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='model alvo normalizado',
    )
    target_record_id = models.CharField('registro alvo', max_length=120, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='governance_audit_logs',
        null=True,
        blank=True,
        verbose_name='usuario',
    )
    message = models.TextField('mensagem')
    safe_context = models.JSONField('contexto seguro', default=dict, blank=True)
    request_id = models.CharField('request id', max_length=120, blank=True)
    occurred_at = models.DateTimeField('ocorrido em', default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-occurred_at', '-created_at']
        indexes = [
            models.Index(fields=['log_type', 'severity', 'occurred_at']),
            models.Index(fields=['module', 'action']),
            models.Index(fields=['user']),
            models.Index(fields=['target_model', 'target_record_id']),
        ]
        verbose_name = 'log de governanca'
        verbose_name_plural = 'logs de governanca'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        if not self.action.strip():
            errors['action'] = 'Informe a acao registrada.'
        if not self.message.strip():
            errors['message'] = 'Informe a mensagem do log.'
        if not isinstance(self.safe_context or {}, dict):
            errors['safe_context'] = 'O contexto seguro deve ser um objeto chave/valor.'
        if errors:
            raise ValidationError(errors)

    @classmethod
    def record(
        cls,
        *,
        log_type,
        severity,
        module,
        action,
        message,
        target_model='',
        target_record_id='',
        user=None,
        safe_context=None,
        request_id='',
    ):
        return cls.objects.create(
            log_type=log_type,
            severity=severity,
            module=module,
            action=action,
            target_model=target_model,
            target_record_id=str(target_record_id or ''),
            user=user,
            message=message,
            safe_context=sanitize_safe_context(safe_context or {}),
            request_id=request_id or '',
        )

    def __str__(self):
        return self.action


class DemoScenarioLoad(SingleInstanceModel):
    class Scenario(models.TextChoices):
        BASE_MASTER_DATA = 'base_master_data', 'Cadastros base'
        QUALITY_DEVIATION = 'quality_deviation', 'Desvio de qualidade'
        CAPA_WORKFLOW = 'capa_workflow', 'Workflow CAPA'
        FINANCE_FISCAL = 'finance_fiscal', 'Financeiro e fiscal'
        FULL_DEMO = 'full_demo', 'Demonstracao completa'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        RUNNING = 'running', 'Executando'
        SUCCEEDED = 'succeeded', 'Concluido'
        FAILED = 'failed', 'Falhou'

    scenario = models.CharField('cenario', max_length=40, choices=Scenario.choices)
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.PENDING
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='requested_demo_scenario_loads',
        null=True,
        blank=True,
        verbose_name='solicitado por',
    )
    started_at = models.DateTimeField('iniciado em', null=True, blank=True)
    completed_at = models.DateTimeField('concluido em', null=True, blank=True)
    records_created = models.JSONField('registros criados ou atualizados', default=dict, blank=True)
    error_message = models.TextField('erro', blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['scenario', 'status']),
            models.Index(fields=['requested_by']),
            models.Index(fields=['started_at']),
        ]
        verbose_name = 'carga de cenario demo'
        verbose_name_plural = 'cargas de cenarios demo'

    def save(self, *args, **kwargs):
        if not getattr(self, '_skip_clean', False):
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        if not isinstance(self.records_created or {}, dict):
            errors['records_created'] = 'Os totais devem ser um objeto chave/valor.'
        if self.status == self.Status.FAILED and not self.error_message:
            errors['error_message'] = 'Carga com falha exige mensagem de erro.'
        if errors:
            raise ValidationError(errors)

    def run(self, user=None):
        actor = user or self.requested_by
        self.status = self.Status.RUNNING
        self.started_at = timezone.now()
        self.completed_at = None
        self.error_message = ''
        self.records_created = {}
        self.save(
            update_fields=[
                'status',
                'started_at',
                'completed_at',
                'error_message',
                'records_created',
                'updated_at',
            ]
        )
        try:
            with transaction.atomic():
                counts = seed_demo_scenario(self.scenario, user=actor)
                self.status = self.Status.SUCCEEDED
                self.completed_at = timezone.now()
                self.records_created = counts
                self.error_message = ''
                self.save(
                    update_fields=[
                        'status',
                        'completed_at',
                        'records_created',
                        'error_message',
                        'updated_at',
                    ]
                )
                GovernanceAuditLog.record(
                    log_type=GovernanceAuditLog.LogType.DEMO_LOAD,
                    severity=GovernanceAuditLog.Severity.INFO,
                    module=OperationalModule.GOVERNANCE,
                    action='demo.load.succeeded',
                    target_model=self.__class__.__name__,
                    target_record_id=self.pk,
                    user=actor,
                    message='Carga de cenario demo executada com sucesso.',
                    safe_context={'scenario': self.scenario, 'records_created': counts},
                )
        except Exception as error:
            self.status = self.Status.FAILED
            self.completed_at = timezone.now()
            self.error_message = str(error)
            self.save(update_fields=['status', 'completed_at', 'error_message', 'updated_at'])
            GovernanceAuditLog.record(
                log_type=GovernanceAuditLog.LogType.DEMO_LOAD,
                severity=GovernanceAuditLog.Severity.ERROR,
                module=OperationalModule.GOVERNANCE,
                action='demo.load.failed',
                target_model=self.__class__.__name__,
                target_record_id=self.pk,
                user=actor,
                message=self.error_message,
                safe_context={'scenario': self.scenario},
            )
            raise
        return self

    def __str__(self):
        return f'{self.get_scenario_display()} - {self.get_status_display()}'


def seed_demo_scenario(scenario, legacy_scenario=None, user=None):
    if legacy_scenario is not None:
        scenario = legacy_scenario
    counts = {'parameters': 0, 'catalog_items': 0}
    if scenario == DemoScenarioLoad.Scenario.FULL_DEMO:
        from governance.demo_seeders import seed_full_demo

        return seed_full_demo(user=user)
    for parameter in _scenario_parameters(scenario):
        GovernanceParameter.objects.update_or_create(
            scope=parameter['scope'],
            module=parameter['module'],
            key=parameter['key'],
            defaults={
                'value_type': parameter['value_type'],
                'value': parameter['value'],
                'default_value': parameter.get('default_value', parameter['value']),
                'rules': parameter.get('rules', {}),
                'description': parameter.get('description', ''),
                'is_active': True,
                'updated_by': user,
            },
        )
        counts['parameters'] += 1
    for item in _scenario_catalog_items(scenario):
        GovernanceCatalogItem.objects.update_or_create(
            catalog_type=item['catalog_type'],
            module=item['module'],
            code=item['code'],
            defaults={
                'label': item['label'],
                'value': item['value'],
                'color': item.get('color', ''),
                'order': item.get('order', 0),
                'is_active': True,
                'metadata': item.get('metadata', {}),
            },
        )
        counts['catalog_items'] += 1
    return counts


def _module_label(module):
    return dict(OperationalModule.choices).get(module, module)


def _module_order(module):
    order_map = {
        module: index * 10 for index, module in enumerate(OperationalModule.values, start=1)
    }
    return order_map.get(module, 999)


def _scenario_modules(scenario):
    if scenario == DemoScenarioLoad.Scenario.BASE_MASTER_DATA:
        return [
            OperationalModule.MASTERS,
            OperationalModule.FORMULATIONS,
            OperationalModule.PROCUREMENT,
            OperationalModule.INVENTORY,
            OperationalModule.GOVERNANCE,
        ]
    if scenario == DemoScenarioLoad.Scenario.QUALITY_DEVIATION:
        return [
            OperationalModule.QUALITY,
            OperationalModule.QA,
            OperationalModule.DOCUMENTS,
            OperationalModule.DEVIATIONS,
            OperationalModule.CAPA,
            OperationalModule.WORKFLOW,
            OperationalModule.GOVERNANCE,
        ]
    if scenario == DemoScenarioLoad.Scenario.CAPA_WORKFLOW:
        return [
            OperationalModule.CAPA,
            OperationalModule.DEVIATIONS,
            OperationalModule.QA,
            OperationalModule.DOCUMENTS,
            OperationalModule.WORKFLOW,
            OperationalModule.GOVERNANCE,
        ]
    if scenario == DemoScenarioLoad.Scenario.FINANCE_FISCAL:
        return [
            OperationalModule.FINANCE,
            OperationalModule.FISCAL,
            OperationalModule.REPORTS,
            OperationalModule.GOVERNANCE,
        ]
    return list(OperationalModule.values)


def _scenario_parameters(scenario):
    base = [
        {
            'scope': GovernanceParameter.Scope.RETENTION,
            'module': OperationalModule.DOCUMENTS,
            'key': 'document_retention_days',
            'value_type': GovernanceParameter.ValueType.DAYS,
            'value': 3650,
            'default_value': 1825,
            'rules': {'min': 365},
            'description': 'Retencao minima para documentos GMP e trilhas ALCOA+.',
        },
        {
            'scope': GovernanceParameter.Scope.ALERT,
            'module': OperationalModule.WORKFLOW,
            'key': 'default_alert_days_before_due',
            'value_type': GovernanceParameter.ValueType.DAYS,
            'value': 7,
            'default_value': 5,
            'rules': {'min': 1, 'max': 90},
            'description': 'Antecedencia padrao para alertas operacionais.',
        },
    ]
    quality = [
        {
            'scope': GovernanceParameter.Scope.WORKFLOW,
            'module': OperationalModule.DEVIATIONS,
            'key': 'deviation_investigation_due_days',
            'value_type': GovernanceParameter.ValueType.DAYS,
            'value': 30,
            'default_value': 30,
            'rules': {'min': 1, 'max': 120},
            'description': 'Prazo padrao para investigacao de desvio.',
        },
        {
            'scope': GovernanceParameter.Scope.WORKFLOW,
            'module': OperationalModule.CAPA,
            'key': 'capa_effectiveness_due_days',
            'value_type': GovernanceParameter.ValueType.DAYS,
            'value': 90,
            'default_value': 90,
            'rules': {'min': 1, 'max': 365},
            'description': 'Prazo padrao para verificacao de eficacia de CAPA.',
        },
        {
            'scope': GovernanceParameter.Scope.QUALITY,
            'module': OperationalModule.QA,
            'key': 'qa_block_requires_approval',
            'value_type': GovernanceParameter.ValueType.BOOLEAN,
            'value': True,
            'default_value': True,
            'description': 'Bloqueios de QA exigem aprovacao formal.',
        },
    ]
    finance = [
        {
            'scope': GovernanceParameter.Scope.APPROVAL,
            'module': OperationalModule.FINANCE,
            'key': 'approval_limit_brl',
            'value_type': GovernanceParameter.ValueType.DECIMAL,
            'value': '15000.00',
            'default_value': '5000.00',
            'rules': {'min': 0},
            'description': 'Alcada padrao para aprovacao financeira.',
        },
        {
            'scope': GovernanceParameter.Scope.MODULE,
            'module': OperationalModule.FISCAL,
            'key': 'fiscal_posting_mode',
            'value_type': GovernanceParameter.ValueType.CHOICE,
            'value': 'review_required',
            'default_value': 'review_required',
            'rules': {'choices': ['automatic', 'review_required']},
            'description': 'Modo de escrituracao fiscal para dados demo.',
        },
    ]
    if scenario == DemoScenarioLoad.Scenario.BASE_MASTER_DATA:
        return base
    if scenario in (
        DemoScenarioLoad.Scenario.QUALITY_DEVIATION,
        DemoScenarioLoad.Scenario.CAPA_WORKFLOW,
    ):
        return base + quality
    if scenario == DemoScenarioLoad.Scenario.FINANCE_FISCAL:
        return base + finance
    return base + quality + finance


def _scenario_catalog_items(scenario):
    document_items = [
        {
            'catalog_type': GovernanceCatalogItem.CatalogType.DOCUMENT_TYPE,
            'module': OperationalModule.DOCUMENTS,
            'code': 'SOP',
            'label': 'Procedimento operacional padrao',
            'value': 'sop',
            'order': 10,
        },
        {
            'catalog_type': GovernanceCatalogItem.CatalogType.DOCUMENT_TYPE,
            'module': OperationalModule.DOCUMENTS,
            'code': 'SPEC',
            'label': 'Especificacao tecnica',
            'value': 'specification',
            'order': 20,
        },
    ]
    quality_items = [
        {
            'catalog_type': GovernanceCatalogItem.CatalogType.DEVIATION_TYPE,
            'module': OperationalModule.DEVIATIONS,
            'code': 'PROCESS',
            'label': 'Desvio de processo',
            'value': 'process',
            'order': 10,
        },
        {
            'catalog_type': GovernanceCatalogItem.CatalogType.CAPA_CATEGORY,
            'module': OperationalModule.CAPA,
            'code': 'ROOT_CAUSE',
            'label': 'Causa raiz confirmada',
            'value': 'root_cause',
            'order': 10,
        },
        {
            'catalog_type': GovernanceCatalogItem.CatalogType.STATUS,
            'module': OperationalModule.DEVIATIONS,
            'code': 'OPEN',
            'label': 'Aberto',
            'value': 'open',
            'color': 'warning',
            'order': 10,
            'metadata': {'blocks_closure': True},
        },
        {
            'catalog_type': GovernanceCatalogItem.CatalogType.CRITICALITY,
            'module': OperationalModule.QUALITY,
            'code': 'CRITICAL',
            'label': 'Critico',
            'value': 'critical',
            'color': 'danger',
            'order': 30,
        },
        {
            'catalog_type': GovernanceCatalogItem.CatalogType.BLOCK_REASON,
            'module': OperationalModule.QA,
            'code': 'QA_HOLD',
            'label': 'Bloqueio QA preventivo',
            'value': 'qa_hold',
            'order': 10,
        },
        {
            'catalog_type': GovernanceCatalogItem.CatalogType.LOT_STATUS,
            'module': OperationalModule.INVENTORY,
            'code': 'QUARANTINE',
            'label': 'Quarentena',
            'value': 'quarantine',
            'order': 10,
        },
        {
            'catalog_type': GovernanceCatalogItem.CatalogType.WORKFLOW_STEP,
            'module': OperationalModule.WORKFLOW,
            'code': 'QA_REVIEW',
            'label': 'Revisao QA',
            'value': 'qa_review',
            'order': 20,
        },
    ]
    finance_items = [
        {
            'catalog_type': GovernanceCatalogItem.CatalogType.STATUS,
            'module': OperationalModule.FINANCE,
            'code': 'PENDING_APPROVAL',
            'label': 'Pendente de aprovacao',
            'value': 'pending_approval',
            'order': 10,
        },
        {
            'catalog_type': GovernanceCatalogItem.CatalogType.INVENTORY_REASON,
            'module': OperationalModule.INVENTORY,
            'code': 'FISCAL_ADJUSTMENT',
            'label': 'Ajuste fiscal',
            'value': 'fiscal_adjustment',
            'order': 20,
        },
    ]
    if scenario == DemoScenarioLoad.Scenario.BASE_MASTER_DATA:
        return document_items + quality_items[-2:]
    if scenario in (
        DemoScenarioLoad.Scenario.QUALITY_DEVIATION,
        DemoScenarioLoad.Scenario.CAPA_WORKFLOW,
    ):
        return document_items + quality_items
    if scenario == DemoScenarioLoad.Scenario.FINANCE_FISCAL:
        return document_items + finance_items
    return document_items + quality_items + finance_items
