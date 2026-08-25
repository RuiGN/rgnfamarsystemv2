from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from base.models import SingleInstanceModel
from base.normalized_locations import validate_normalized_location
from base.sequences import sequence_code, AutoCodeMixin
from masters.models import BusinessPartner, Product


MONEY_SCALE = Decimal('0.0001')
QUANTITY_SCALE = Decimal('0.0001')
ZERO_MONEY = Decimal('0.0000')
PERCENT_BASE = Decimal('100.0000')
CRM_PARTNER_TYPES = (
    BusinessPartner.PartnerType.CUSTOMER,
    BusinessPartner.PartnerType.DISTRIBUTOR,
    BusinessPartner.PartnerType.PARTNER,
)


def _money(value):
    try:
        amount = Decimal(str(value or ZERO_MONEY))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError('Informe um valor monetário válido.') from exc
    return amount.quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)


def _quantity(value):
    try:
        amount = Decimal(str(value or '0.0000'))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError('Informe uma quantidade válida.') from exc
    return amount.quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)


def _percent_factor(value):
    return Decimal(str(value or ZERO_MONEY)) / PERCENT_BASE


def _sequence_code(model, *args):
    if len(args) == 3:
        _legacy_scope, field_name, prefix = args
    else:
        field_name, prefix = args
    return sequence_code(model, field_name, prefix)


def _validate_customer_partner(errors, field, partner):
    if partner and partner.partner_type not in CRM_PARTNER_TYPES:
        errors[field] = 'O parceiro deve ser cliente, distribuidor ou parceiro comercial.'


def _validate_percent(errors, field, value):
    if value < 0 or value > PERCENT_BASE:
        errors[field] = 'O percentual deve estar entre 0 e 100.'


class CustomerGroup(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'CG'
    code = models.CharField('código', max_length=40, blank=True)
    name = models.CharField('nome', max_length=160)
    description = models.TextField('descrição', blank=True)
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_customer_group_code'),
        ]
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'grupo econômico'
        verbose_name_plural = 'grupos econômicos'

    def __str__(self):
        return f'{self.code} - {self.name}'


class SalesChannel(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'SC'
    class ChannelType(models.TextChoices):
        DIRECT = 'direct', 'Venda direta'
        DISTRIBUTOR = 'distributor', 'Distribuidor'
        ECOMMERCE = 'ecommerce', 'E-commerce'
        TENDER = 'tender', 'Licitação'
        REPRESENTATIVE = 'representative', 'Representante'
        PARTNER = 'partner', 'Parceiro'
        OTHER = 'other', 'Outro'

    code = models.CharField('código', max_length=40, blank=True)
    name = models.CharField('nome', max_length=160)
    channel_type = models.CharField('tipo', max_length=24, choices=ChannelType.choices)
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_sales_channel_code'),
        ]
        indexes = [
            models.Index(fields=['channel_type', 'is_active']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'canal de venda'
        verbose_name_plural = 'canais de venda'

    def __str__(self):
        return f'{self.code} - {self.name}'


class SalesRepresentative(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'SR'
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sales_representative_profiles',
        null=True,
        blank=True,
        verbose_name='usuário',
    )
    partner = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='sales_representative_profiles',
        null=True,
        blank=True,
        verbose_name='parceiro',
    )
    code = models.CharField('código', max_length=40, blank=True)
    name = models.CharField('nome', max_length=160)
    email = models.EmailField('email', blank=True)
    phone = models.CharField('telefone', max_length=40, blank=True)
    territory = models.CharField('território', max_length=120, blank=True)
    commission_percent = models.DecimalField(
        'comissão (%)', max_digits=9, decimal_places=4, default=ZERO_MONEY
    )
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_sales_representative_code'),
        ]
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'representante comercial'
        verbose_name_plural = 'representantes comerciais'

    def clean(self):
        super().clean()
        errors = {}
        _validate_percent(errors, 'commission_percent', self.commission_percent)
        if self.partner and self.partner.partner_type not in CRM_PARTNER_TYPES:
            errors['partner'] = (
                'O representante deve estar vinculado a cliente, distribuidor ou parceiro comercial.'
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.code} - {self.name}'


class CustomerProfile(SingleInstanceModel):
    customer = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='customer_profiles',
        verbose_name='cliente',
    )
    group = models.ForeignKey(
        CustomerGroup,
        on_delete=models.PROTECT,
        related_name='customer_profiles',
        null=True,
        blank=True,
        verbose_name='grupo econômico',
    )
    default_channel = models.ForeignKey(
        SalesChannel,
        on_delete=models.PROTECT,
        related_name='customer_profiles',
        null=True,
        blank=True,
        verbose_name='canal padrão',
    )
    representative = models.ForeignKey(
        SalesRepresentative,
        on_delete=models.PROTECT,
        related_name='customer_profiles',
        null=True,
        blank=True,
        verbose_name='representante',
    )
    credit_limit = models.DecimalField(
        'limite de crédito', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    credit_hold = models.BooleanField('bloqueio de crédito', default=False)
    regulatory_hold = models.BooleanField('bloqueio regulatório', default=False)
    payment_terms_days = models.PositiveIntegerField('prazo comercial em dias', default=0)
    price_list_code = models.CharField('tabela de preço', max_length=40, blank=True)
    notes = models.TextField('observações', blank=True)
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['customer__legal_name']
        constraints = [
            models.UniqueConstraint(fields=['customer'], name='unique_customer_profile_partner'),
        ]
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['credit_hold', 'regulatory_hold']),
            models.Index(fields=['group']),
        ]
        verbose_name = 'perfil comercial do cliente'
        verbose_name_plural = 'perfis comerciais de clientes'

    def clean(self):
        super().clean()
        errors = {}
        _validate_customer_partner(errors, 'customer', self.customer)
        for field in ('group', 'default_channel', 'representative'):
            pass
        if self.credit_limit < 0:
            errors['credit_limit'] = 'O limite de crédito não pode ser negativo.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.customer} - perfil comercial'


class CustomerContact(SingleInstanceModel):
    customer = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='customer_contacts',
        verbose_name='cliente',
    )
    name = models.CharField('nome', max_length=160)
    role = models.CharField('cargo/função', max_length=120, blank=True)
    role_ref = models.ForeignKey(
        'auxiliary.OrganizationalRole',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='cargo/função normalizado',
    )
    email = models.EmailField('email', blank=True)
    phone = models.CharField('telefone', max_length=40, blank=True)
    is_primary = models.BooleanField('contato principal', default=False)
    is_active = models.BooleanField('ativo', default=True)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['customer__legal_name', 'name']
        indexes = [
            models.Index(fields=['customer', 'is_active']),
            models.Index(fields=['is_primary']),
        ]
        verbose_name = 'contato de cliente'
        verbose_name_plural = 'contatos de clientes'

    def clean(self):
        super().clean()
        errors = {}
        _validate_customer_partner(errors, 'customer', self.customer)
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.name} - {self.customer}'


class Campaign(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'CMP'
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        ACTIVE = 'active', 'Ativa'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'

    code = models.CharField('código', max_length=40, blank=True)
    name = models.CharField('nome', max_length=160)
    channel = models.ForeignKey(
        SalesChannel,
        on_delete=models.PROTECT,
        related_name='campaigns',
        null=True,
        blank=True,
        verbose_name='canal',
    )
    start_date = models.DateField('início')
    end_date = models.DateField('fim', null=True, blank=True)
    budget_amount = models.DecimalField(
        'orçamento', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['-start_date', 'name']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_campaign_code'),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        verbose_name = 'campanha comercial'
        verbose_name_plural = 'campanhas comerciais'

    def clean(self):
        super().clean()
        errors = {}
        if self.end_date and self.end_date < self.start_date:
            errors['end_date'] = 'A data final não pode ser anterior ao início.'
        if self.budget_amount < 0:
            errors['budget_amount'] = 'O orçamento não pode ser negativo.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.code} - {self.name}'


class Opportunity(SingleInstanceModel):
    class Stage(models.TextChoices):
        LEAD = 'lead', 'Lead'
        QUALIFIED = 'qualified', 'Qualificada'
        PROPOSAL = 'proposal', 'Proposta'
        NEGOTIATION = 'negotiation', 'Negociação'
        WON = 'won', 'Ganha'
        LOST = 'lost', 'Perdida'

    customer = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='opportunities',
        verbose_name='cliente',
    )
    contact = models.ForeignKey(
        CustomerContact,
        on_delete=models.PROTECT,
        related_name='opportunities',
        null=True,
        blank=True,
        verbose_name='contato',
    )
    channel = models.ForeignKey(
        SalesChannel,
        on_delete=models.PROTECT,
        related_name='opportunities',
        null=True,
        blank=True,
        verbose_name='canal',
    )
    representative = models.ForeignKey(
        SalesRepresentative,
        on_delete=models.PROTECT,
        related_name='opportunities',
        null=True,
        blank=True,
        verbose_name='representante',
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name='opportunities',
        null=True,
        blank=True,
        verbose_name='campanha',
    )
    title = models.CharField('título', max_length=180)
    stage = models.CharField('etapa', max_length=24, choices=Stage.choices, default=Stage.LEAD)
    expected_close_date = models.DateField('previsão de fechamento', null=True, blank=True)
    probability_percent = models.DecimalField(
        'probabilidade (%)', max_digits=9, decimal_places=4, default=ZERO_MONEY
    )
    estimated_amount = models.DecimalField(
        'valor estimado', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    won_at = models.DateTimeField('ganha em', null=True, blank=True)
    lost_at = models.DateTimeField('perdida em', null=True, blank=True)
    loss_reason = models.TextField('motivo da perda', blank=True)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stage']),
            models.Index(fields=['customer']),
            models.Index(fields=['expected_close_date']),
            models.Index(fields=['campaign']),
        ]
        verbose_name = 'oportunidade'
        verbose_name_plural = 'oportunidades'

    def advance_to(self, stage):
        valid_stages = {'lead', 'qualified', 'proposal', 'negotiation', 'won', 'lost'}
        if stage not in valid_stages:
            raise ValidationError({'stage': 'Etapa de oportunidade inválida.'})
        if stage == self.Stage.WON:
            return self.mark_won()
        if stage == self.Stage.LOST:
            return self.mark_lost(reason=self.loss_reason or 'Oportunidade perdida.')
        self.stage = stage
        self.full_clean()
        self.save(update_fields=['stage', 'updated_at'])

    def mark_won(self):
        self.stage = self.Stage.WON
        self.probability_percent = PERCENT_BASE
        self.won_at = timezone.now()
        self.lost_at = None
        self.loss_reason = ''
        self.full_clean()
        self.save(
            update_fields=[
                'stage',
                'probability_percent',
                'won_at',
                'lost_at',
                'loss_reason',
                'updated_at',
            ]
        )

    def mark_lost(self, reason):
        if not reason:
            raise ValidationError({'loss_reason': 'Informe o motivo da perda.'})
        self.stage = self.Stage.LOST
        self.lost_at = timezone.now()
        self.loss_reason = reason
        self.full_clean()
        self.save(update_fields=['stage', 'lost_at', 'loss_reason', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        _validate_customer_partner(errors, 'customer', self.customer)
        for field in ('contact', 'channel', 'representative', 'campaign'):
            pass
        if self.contact and self.customer and self.contact.customer_id != self.customer_id:
            errors['contact'] = 'O contato deve pertencer ao cliente da oportunidade.'
        if self.estimated_amount < 0:
            errors['estimated_amount'] = 'O valor estimado não pode ser negativo.'
        _validate_percent(errors, 'probability_percent', self.probability_percent)
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class SalesProposal(SingleInstanceModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        SENT = 'sent', 'Enviada'
        ACCEPTED = 'accepted', 'Aceita'
        REJECTED = 'rejected', 'Rejeitada'
        EXPIRED = 'expired', 'Expirada'
        CANCELLED = 'cancelled', 'Cancelada'

    proposal_number = models.CharField('proposta', max_length=80, blank=True)
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.PROTECT,
        related_name='proposals',
        null=True,
        blank=True,
        verbose_name='oportunidade',
    )
    customer = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='sales_proposals',
        verbose_name='cliente',
    )
    valid_until = models.DateField('válida até')
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.DRAFT)
    total_amount = models.DecimalField(
        'valor total', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    sent_at = models.DateTimeField('enviada em', null=True, blank=True)
    accepted_at = models.DateTimeField('aceita em', null=True, blank=True)
    rejected_at = models.DateTimeField('rejeitada em', null=True, blank=True)
    rejected_reason = models.TextField('motivo da rejeição', blank=True)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['proposal_number'], name='unique_sales_proposal_number'
            ),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['customer']),
            models.Index(fields=['proposal_number']),
        ]
        verbose_name = 'proposta comercial'
        verbose_name_plural = 'propostas comerciais'

    def save(self, *args, **kwargs):
        if not self.proposal_number:
            self.proposal_number = _sequence_code(SalesProposal, 'proposal_number', 'PROP')
        super().save(*args, **kwargs)

    def recalculate_total(self, save=True):
        self.total_amount = _money(sum((item.line_total for item in self.items.all()), ZERO_MONEY))
        self.full_clean(validate_unique=False)
        if save:
            self.save(update_fields=['total_amount', 'updated_at'])
        return self.total_amount

    def send(self):
        if self.status != self.Status.DRAFT:
            raise ValidationError({'status': 'Somente propostas em rascunho podem ser enviadas.'})
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'sent_at', 'updated_at'])

    def accept(self):
        if self.status not in (self.Status.DRAFT, self.Status.SENT):
            raise ValidationError(
                {'status': 'Somente propostas em rascunho ou enviadas podem ser aceitas.'}
            )
        self.status = self.Status.ACCEPTED
        self.accepted_at = timezone.now()
        self.rejected_at = None
        self.rejected_reason = ''
        self.full_clean()
        self.save(
            update_fields=['status', 'accepted_at', 'rejected_at', 'rejected_reason', 'updated_at']
        )

    def reject(self, reason):
        if not reason:
            raise ValidationError({'rejected_reason': 'Informe o motivo da rejeição.'})
        if self.status not in (self.Status.DRAFT, self.Status.SENT):
            raise ValidationError(
                {'status': 'Somente propostas em rascunho ou enviadas podem ser rejeitadas.'}
            )
        self.status = self.Status.REJECTED
        self.rejected_at = timezone.now()
        self.rejected_reason = reason
        self.full_clean()
        self.save(update_fields=['status', 'rejected_at', 'rejected_reason', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        _validate_customer_partner(errors, 'customer', self.customer)
        if self.opportunity and self.customer and self.opportunity.customer_id != self.customer_id:
            errors['opportunity'] = 'A oportunidade deve pertencer ao cliente da proposta.'
        if self.total_amount < 0:
            errors['total_amount'] = 'O valor total não pode ser negativo.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.proposal_number


class SalesProposalItem(SingleInstanceModel):
    proposal = models.ForeignKey(
        SalesProposal, on_delete=models.CASCADE, related_name='items', verbose_name='proposta'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='sales_proposal_items',
        verbose_name='produto',
    )
    quantity = models.DecimalField('quantidade', max_digits=14, decimal_places=4)
    unit_price = models.DecimalField('preço unitário', max_digits=14, decimal_places=4)
    discount_percent = models.DecimalField(
        'desconto (%)', max_digits=9, decimal_places=4, default=ZERO_MONEY
    )
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['proposal', 'product__code']
        constraints = [
            models.UniqueConstraint(
                fields=['proposal', 'product'],
                name='unique_sales_proposal_item_product',
            ),
        ]
        indexes = [
            models.Index(fields=['proposal']),
            models.Index(fields=['product']),
        ]
        verbose_name = 'item de proposta'
        verbose_name_plural = 'itens de propostas'

    @property
    def line_subtotal(self):
        return _money(self.quantity * self.unit_price)

    @property
    def discount_amount(self):
        return _money(self.line_subtotal * _percent_factor(self.discount_percent))

    @property
    def line_total(self):
        return _money(self.line_subtotal - self.discount_amount)

    def clean(self):
        super().clean()
        errors = {}
        for field in ('proposal', 'product'):
            pass
        if self.product and not self.product.is_operationally_available:
            errors['product'] = 'O produto precisa estar aprovado e operacional.'
        if self.quantity <= 0:
            errors['quantity'] = 'A quantidade deve ser maior que zero.'
        if self.unit_price < 0:
            errors['unit_price'] = 'O preço unitário não pode ser negativo.'
        _validate_percent(errors, 'discount_percent', self.discount_percent)
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.proposal} - {self.product}'


class SalesContract(SingleInstanceModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        ACTIVE = 'active', 'Ativo'
        SUSPENDED = 'suspended', 'Suspenso'
        EXPIRED = 'expired', 'Expirado'
        CANCELLED = 'cancelled', 'Cancelado'

    contract_number = models.CharField('contrato', max_length=80, blank=True)
    customer = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='sales_contracts',
        verbose_name='cliente',
    )
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.PROTECT,
        related_name='contracts',
        null=True,
        blank=True,
        verbose_name='oportunidade',
    )
    proposal = models.ForeignKey(
        SalesProposal,
        on_delete=models.PROTECT,
        related_name='contracts',
        null=True,
        blank=True,
        verbose_name='proposta',
    )
    start_date = models.DateField('início')
    end_date = models.DateField('fim', null=True, blank=True)
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.DRAFT)
    contract_value = models.DecimalField(
        'valor do contrato', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    payment_terms_days = models.PositiveIntegerField('prazo de pagamento em dias', default=0)
    regulatory_requirements = models.TextField('requisitos regulatórios', blank=True)
    notes = models.TextField('observações', blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='approved_sales_contracts',
        null=True,
        blank=True,
        verbose_name='aprovado por',
    )
    approved_at = models.DateTimeField('aprovado em', null=True, blank=True)

    class Meta:
        ordering = ['-start_date', 'contract_number']
        constraints = [
            models.UniqueConstraint(
                fields=['contract_number'], name='unique_sales_contract_number'
            ),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['customer']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['contract_number']),
        ]
        verbose_name = 'contrato comercial'
        verbose_name_plural = 'contratos comerciais'

    def save(self, *args, **kwargs):
        if not self.contract_number:
            self.contract_number = _sequence_code(SalesContract, 'contract_number', 'CTR')
        super().save(*args, **kwargs)

    def activate(self, user=None):
        if self.status not in (self.Status.DRAFT, self.Status.SUSPENDED):
            raise ValidationError(
                {'status': 'Somente contratos em rascunho ou suspensos podem ser ativados.'}
            )
        self.status = self.Status.ACTIVE
        self.approved_by = user
        self.approved_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

    def suspend(self):
        if self.status != self.Status.ACTIVE:
            raise ValidationError({'status': 'Somente contratos ativos podem ser suspensos.'})
        self.status = self.Status.SUSPENDED
        self.save(update_fields=['status', 'updated_at'])

    def cancel(self):
        if self.status == self.Status.CANCELLED:
            raise ValidationError({'status': 'O contrato já está cancelado.'})
        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])

    def clean(self):
        super().clean()
        errors = {}
        _validate_customer_partner(errors, 'customer', self.customer)
        for field in ('opportunity', 'proposal'):
            pass
        if self.opportunity and self.customer and self.opportunity.customer_id != self.customer_id:
            errors['opportunity'] = 'A oportunidade deve pertencer ao cliente do contrato.'
        if self.proposal and self.customer and self.proposal.customer_id != self.customer_id:
            errors['proposal'] = 'A proposta deve pertencer ao cliente do contrato.'
        if self.end_date and self.end_date < self.start_date:
            errors['end_date'] = 'A data final não pode ser anterior ao início.'
        if self.contract_value < 0:
            errors['contract_value'] = 'O valor do contrato não pode ser negativo.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.contract_number


class SalesOrder(SingleInstanceModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        APPROVED = 'approved', 'Aprovado'
        BLOCKED = 'blocked', 'Bloqueado'
        FULFILLED = 'fulfilled', 'Atendido'
        CANCELLED = 'cancelled', 'Cancelado'

    order_number = models.CharField('pedido', max_length=80, blank=True)
    customer = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='sales_orders',
        verbose_name='cliente',
    )
    proposal = models.ForeignKey(
        SalesProposal,
        on_delete=models.PROTECT,
        related_name='orders',
        null=True,
        blank=True,
        verbose_name='proposta',
    )
    contract = models.ForeignKey(
        SalesContract,
        on_delete=models.PROTECT,
        related_name='orders',
        null=True,
        blank=True,
        verbose_name='contrato',
    )
    channel = models.ForeignKey(
        SalesChannel,
        on_delete=models.PROTECT,
        related_name='orders',
        null=True,
        blank=True,
        verbose_name='canal',
    )
    representative = models.ForeignKey(
        SalesRepresentative,
        on_delete=models.PROTECT,
        related_name='orders',
        null=True,
        blank=True,
        verbose_name='representante',
    )
    requested_delivery_date = models.DateField('data solicitada de entrega')
    payment_terms_days = models.PositiveIntegerField('prazo de pagamento em dias', default=0)
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.DRAFT)
    total_amount = models.DecimalField(
        'valor total', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='approved_sales_orders',
        null=True,
        blank=True,
        verbose_name='aprovado por',
    )
    approved_at = models.DateTimeField('aprovado em', null=True, blank=True)
    block_reason = models.TextField('motivo de bloqueio', blank=True)
    notes = models.TextField('observações', blank=True)
    shipping_zipcode = models.CharField('CEP de entrega', max_length=20, blank=True)
    shipping_street = models.CharField('logradouro de entrega', max_length=200, blank=True)
    shipping_street_number = models.CharField('número', max_length=20, blank=True)
    shipping_complement = models.CharField('complemento', max_length=100, blank=True)
    shipping_neighborhood = models.CharField('bairro de entrega', max_length=120, blank=True)
    shipping_country_ref = models.ForeignKey(
        'auxiliary.Country',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name='país',
    )
    shipping_state_ref = models.ForeignKey(
        'auxiliary.StateProvince',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='UF',
    )
    shipping_city_ref = models.ForeignKey(
        'auxiliary.City',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='Cidade',
    )

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['order_number'], name='unique_sales_order_number'),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['customer']),
            models.Index(fields=['requested_delivery_date']),
            models.Index(fields=['order_number']),
        ]
        verbose_name = 'pedido de venda'
        verbose_name_plural = 'pedidos de venda'

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = _sequence_code(SalesOrder, 'order_number', 'PV')
        super().save(*args, **kwargs)

    def recalculate_total(self, save=True):
        self.total_amount = _money(sum((item.line_total for item in self.items.all()), ZERO_MONEY))
        self.full_clean(validate_unique=False)
        if save:
            self.save(update_fields=['total_amount', 'updated_at'])
        return self.total_amount

    def validate_commercial_rules(self):
        errors = {}
        items = list(self.items.select_related('product'))
        profile = CustomerProfile.objects.filter(customer=self.customer, is_active=True).first()
        if not items:
            errors['items'] = 'Inclua ao menos um item no pedido.'
        if profile is None:
            errors['customer'] = 'Cliente sem perfil comercial ativo.'
        else:
            if profile.credit_hold:
                errors['credit_hold'] = 'Cliente com bloqueio de crédito.'
            if profile.regulatory_hold:
                errors['regulatory_hold'] = 'Cliente com bloqueio regulatório.'
            if self.payment_terms_days > profile.payment_terms_days:
                errors['payment_terms_days'] = (
                    'O prazo do pedido excede a condição comercial aprovada.'
                )
            if profile.credit_limit > 0 and self.total_amount > profile.credit_limit:
                errors['credit_limit'] = 'O pedido excede o limite de crédito aprovado.'

        required_by_product = {}
        products_by_id = {}
        for item in items:
            if item.unit_price <= 0:
                errors['price'] = 'Todos os itens do pedido devem ter preço maior que zero.'
            if item.product and not item.product.is_operationally_available:
                errors['product'] = (
                    'Todos os produtos do pedido precisam estar aprovados e operacionais.'
                )
            if item.product and item.product.item_type != Product.ItemType.SERVICE:
                products_by_id[item.product_id] = item.product
                required_by_product[item.product_id] = (
                    required_by_product.get(item.product_id, Decimal('0.0000')) + item.quantity
                )

        stock_errors = []
        for product_id, required_quantity in required_by_product.items():
            product = products_by_id[product_id]
            available_quantity = self._available_stock_for(product)
            if available_quantity < required_quantity:
                stock_errors.append(
                    f'{product.code}: disponível {available_quantity}, necessário {_quantity(required_quantity)}'
                )
        if stock_errors:
            errors['stock'] = 'Estoque aprovado insuficiente: ' + '; '.join(stock_errors)

        if errors:
            raise ValidationError(errors)

    def _available_stock_for(self, product):
        from inventory.models import StockBalance

        balances = StockBalance.objects.filter(product=product).select_related('lot')
        total_available = sum(
            (balance.available_quantity for balance in balances if balance.can_issue),
            Decimal('0.0000'),
        )
        return _quantity(total_available)

    def approve(self, user=None):
        self.recalculate_total()
        try:
            self.validate_commercial_rules()
        except ValidationError as error:
            self.status = self.Status.BLOCKED
            self.block_reason = '; '.join(
                message for messages in error.message_dict.values() for message in messages
            )
            self.save(update_fields=['status', 'block_reason', 'total_amount', 'updated_at'])
            raise
        self.status = self.Status.APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.block_reason = ''
        self.full_clean()
        self.save(
            update_fields=[
                'status',
                'approved_by',
                'approved_at',
                'block_reason',
                'total_amount',
                'updated_at',
            ]
        )

    def cancel(self, reason):
        if self.status == self.Status.CANCELLED:
            raise ValidationError({'status': 'O pedido já está cancelado.'})
        if not reason:
            raise ValidationError({'block_reason': 'Informe a justificativa do cancelamento.'})
        self.status = self.Status.CANCELLED
        self.block_reason = reason
        self.save(update_fields=['status', 'block_reason', 'updated_at'])

    def clean(self):
        super().clean()
        validate_normalized_location(
            self,
            city_ref_field='shipping_city_ref',
            state_ref_field='shipping_state_ref',
        )
        errors = {}
        _validate_customer_partner(errors, 'customer', self.customer)
        for field in ('proposal', 'contract', 'channel', 'representative'):
            pass
        if self.proposal and self.customer and self.proposal.customer_id != self.customer_id:
            errors['proposal'] = 'A proposta deve pertencer ao cliente do pedido.'
        if self.contract and self.customer and self.contract.customer_id != self.customer_id:
            errors['contract'] = 'O contrato deve pertencer ao cliente do pedido.'
        if self.total_amount < 0:
            errors['total_amount'] = 'O valor total não pode ser negativo.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.order_number


class SalesOrderItem(SingleInstanceModel):
    order = models.ForeignKey(
        SalesOrder, on_delete=models.CASCADE, related_name='items', verbose_name='pedido'
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='sales_order_items', verbose_name='produto'
    )
    quantity = models.DecimalField('quantidade', max_digits=14, decimal_places=4)
    unit_price = models.DecimalField('preço unitário', max_digits=14, decimal_places=4)
    discount_percent = models.DecimalField(
        'desconto (%)', max_digits=9, decimal_places=4, default=ZERO_MONEY
    )
    promised_date = models.DateField('data prometida', null=True, blank=True)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['order', 'product__code']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['product']),
        ]
        verbose_name = 'item de pedido de venda'
        verbose_name_plural = 'itens de pedidos de venda'

    @property
    def line_subtotal(self):
        return _money(self.quantity * self.unit_price)

    @property
    def discount_amount(self):
        return _money(self.line_subtotal * _percent_factor(self.discount_percent))

    @property
    def line_total(self):
        return _money(self.line_subtotal - self.discount_amount)

    def clean(self):
        super().clean()
        errors = {}
        for field in ('order', 'product'):
            pass
        if self.product and not self.product.is_operationally_available:
            errors['product'] = 'O produto precisa estar aprovado e operacional.'
        if self.quantity <= 0:
            errors['quantity'] = 'A quantidade deve ser maior que zero.'
        if self.unit_price < 0:
            errors['unit_price'] = 'O preço unitário não pode ser negativo.'
        _validate_percent(errors, 'discount_percent', self.discount_percent)
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.order} - {self.product}'


class CustomerInteraction(SingleInstanceModel):
    class InteractionType(models.TextChoices):
        EMAIL = 'email', 'Email'
        PHONE = 'phone', 'Telefone'
        MEETING = 'meeting', 'Reunião'
        VISIT = 'visit', 'Visita'
        TASK = 'task', 'Tarefa'
        NOTE = 'note', 'Observação'

    customer = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='customer_interactions',
        verbose_name='cliente',
    )
    contact = models.ForeignKey(
        CustomerContact,
        on_delete=models.PROTECT,
        related_name='interactions',
        null=True,
        blank=True,
        verbose_name='contato',
    )
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.PROTECT,
        related_name='interactions',
        null=True,
        blank=True,
        verbose_name='oportunidade',
    )
    interaction_type = models.CharField('tipo', max_length=24, choices=InteractionType.choices)
    occurred_at = models.DateTimeField('ocorrida em', default=timezone.now)
    subject = models.CharField('assunto', max_length=180)
    description = models.TextField('descrição', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='customer_interactions',
        null=True,
        blank=True,
        verbose_name='criado por',
    )

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['customer', 'occurred_at']),
            models.Index(fields=['interaction_type']),
            models.Index(fields=['opportunity']),
        ]
        verbose_name = 'interação com cliente'
        verbose_name_plural = 'interações com clientes'

    def clean(self):
        super().clean()
        errors = {}
        _validate_customer_partner(errors, 'customer', self.customer)
        if self.contact and self.customer and self.contact.customer_id != self.customer_id:
            errors['contact'] = 'O contato deve pertencer ao cliente informado.'
        if self.opportunity and self.customer and self.opportunity.customer_id != self.customer_id:
            errors['opportunity'] = 'A oportunidade deve pertencer ao cliente informado.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.get_interaction_type_display()} - {self.subject}'


class CustomerComplaint(SingleInstanceModel):
    class Severity(models.TextChoices):
        LOW = 'low', 'Baixa'
        MEDIUM = 'medium', 'Média'
        HIGH = 'high', 'Alta'
        CRITICAL = 'critical', 'Crítica'

    class Status(models.TextChoices):
        OPEN = 'open', 'Aberta'
        UNDER_INVESTIGATION = 'under_investigation', 'Em investigação'
        CLOSED = 'closed', 'Encerrada'
        CANCELLED = 'cancelled', 'Cancelada'

    complaint_number = models.CharField('reclamação', max_length=80, blank=True)
    customer = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='customer_complaints',
        verbose_name='cliente',
    )
    contact = models.ForeignKey(
        CustomerContact,
        on_delete=models.PROTECT,
        related_name='complaints',
        null=True,
        blank=True,
        verbose_name='contato',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='customer_complaints',
        null=True,
        blank=True,
        verbose_name='produto',
    )
    stock_lot = models.ForeignKey(
        'inventory.StockLot',
        on_delete=models.PROTECT,
        related_name='customer_complaints',
        null=True,
        blank=True,
        verbose_name='lote',
    )
    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.PROTECT,
        related_name='customer_complaints',
        null=True,
        blank=True,
        verbose_name='pedido de venda',
    )
    fiscal_document = models.ForeignKey(
        'fiscal.FiscalDocument',
        on_delete=models.PROTECT,
        related_name='customer_complaints',
        null=True,
        blank=True,
        verbose_name='documento fiscal',
    )
    quality_reference = models.CharField('referência da qualidade', max_length=80, blank=True)
    capa_reference = models.CharField('referência CAPA', max_length=80, blank=True)
    description = models.TextField('descrição')
    severity = models.CharField(
        'criticidade', max_length=24, choices=Severity.choices, default=Severity.MEDIUM
    )
    severity_ref = models.ForeignKey(
        'auxiliary.ImpactLevel',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='criticidade normalizada',
    )
    status = models.CharField('status', max_length=32, choices=Status.choices, default=Status.OPEN)
    received_at = models.DateTimeField('recebida em', default=timezone.now)
    closed_at = models.DateTimeField('encerrada em', null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='closed_customer_complaints',
        null=True,
        blank=True,
        verbose_name='encerrada por',
    )
    resolution = models.TextField('resolução', blank=True)
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

    class Meta:
        ordering = ['-received_at']
        constraints = [
            models.UniqueConstraint(
                fields=['complaint_number'],
                name='unique_customer_complaint_number',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['customer']),
            models.Index(fields=['product']),
            models.Index(fields=['stock_lot']),
            models.Index(fields=['complaint_number']),
        ]
        verbose_name = 'reclamação de cliente'
        verbose_name_plural = 'reclamações de clientes'

    def save(self, *args, **kwargs):
        if not self.complaint_number:
            self.complaint_number = _sequence_code(CustomerComplaint, 'complaint_number', 'RCL')
        super().save(*args, **kwargs)

    def start_investigation(self):
        if self.status != self.Status.OPEN:
            raise ValidationError(
                {'status': 'Somente reclamações abertas podem entrar em investigação.'}
            )
        self.status = self.Status.UNDER_INVESTIGATION
        self.save(update_fields=['status', 'updated_at'])

    def close(self, resolution, user=None):
        if not resolution:
            raise ValidationError({'resolution': 'Informe a resolução da reclamação.'})
        if self.status == self.Status.CANCELLED:
            raise ValidationError({'status': 'Reclamações canceladas não podem ser encerradas.'})
        self.status = self.Status.CLOSED
        self.resolution = resolution
        self.closed_by = user
        self.closed_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'resolution', 'closed_by', 'closed_at', 'updated_at'])

    def cancel(self, reason):
        if not reason:
            raise ValidationError({'resolution': 'Informe a justificativa do cancelamento.'})
        self.status = self.Status.CANCELLED
        self.resolution = reason
        self.save(update_fields=['status', 'resolution', 'updated_at'])

    def clean(self):
        super().clean()
        validate_normalized_location(self)
        errors = {}
        _validate_customer_partner(errors, 'customer', self.customer)
        for field in ('contact', 'product', 'stock_lot', 'sales_order', 'fiscal_document'):
            pass
        if self.contact and self.customer and self.contact.customer_id != self.customer_id:
            errors['contact'] = 'O contato deve pertencer ao cliente informado.'
        if self.sales_order and self.customer and self.sales_order.customer_id != self.customer_id:
            errors['sales_order'] = 'O pedido deve pertencer ao cliente informado.'
        if (
            self.fiscal_document
            and self.customer
            and self.fiscal_document.partner_id != self.customer_id
        ):
            errors['fiscal_document'] = 'A nota fiscal deve pertencer ao cliente informado.'
        if self.stock_lot and self.product and self.stock_lot.product_id != self.product_id:
            errors['stock_lot'] = 'O lote deve pertencer ao produto informado.'
        if self.status == self.Status.CLOSED and not self.resolution:
            errors['resolution'] = 'Informe a resolução para encerrar a reclamação.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.complaint_number
