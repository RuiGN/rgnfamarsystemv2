from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from base.models import SingleInstanceModel
from base.sequences import AutoCodeMixin, IdentifierSpec, sequence_code
from masters.models import BusinessPartner
from procurement.models import PurchaseOrder


MONEY_SCALE = Decimal('0.0001')
ZERO_MONEY = Decimal('0.0000')


def _money(value):
    try:
        amount = Decimal(str(value or ZERO_MONEY))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError('Informe um valor monetário válido.') from exc
    return amount.quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)


def _sequence_code(model, *args):
    if len(args) == 3:
        _legacy_scope, field_name, prefix = args
    else:
        field_name, prefix = args
    return sequence_code(model, field_name, prefix)


class ChartOfAccount(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'COA'

    class AccountType(models.TextChoices):
        ASSET = 'asset', 'Ativo'
        LIABILITY = 'liability', 'Passivo'
        REVENUE = 'revenue', 'Receita'
        EXPENSE = 'expense', 'Despesa'
        EQUITY = 'equity', 'Patrimônio líquido'

    code = models.CharField('código', max_length=40, blank=True)
    name = models.CharField('nome', max_length=160)
    account_type = models.CharField('tipo', max_length=24, choices=AccountType.choices)
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='children',
        null=True,
        blank=True,
        verbose_name='conta superior',
    )
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_chart_account_code'),
        ]
        indexes = [
            models.Index(fields=['account_type', 'is_active']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'plano de contas'
        verbose_name_plural = 'plano de contas'

    def clean(self):
        super().clean()
        if False:
            raise ValidationError({'parent': 'A conta superior é incompatível com o registro.'})

    def __str__(self):
        return f'{self.code} - {self.name}'


class FinancialCategory(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'FC'

    class CategoryType(models.TextChoices):
        PAYABLE = 'payable', 'Pagar'
        RECEIVABLE = 'receivable', 'Receber'
        BOTH = 'both', 'Ambos'

    code = models.CharField('código', max_length=40, blank=True)
    name = models.CharField('nome', max_length=160)
    category_type = models.CharField('tipo', max_length=24, choices=CategoryType.choices)
    chart_account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name='financial_categories',
        verbose_name='conta contábil',
    )
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['category_type', 'code']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_financial_category_code'),
        ]
        indexes = [
            models.Index(fields=['category_type', 'is_active']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'categoria financeira'
        verbose_name_plural = 'categorias financeiras'

    def clean(self):
        super().clean()
        if False:
            raise ValidationError(
                {'chart_account': 'A conta contábil é incompatível com o registro.'}
            )

    def __str__(self):
        return f'{self.code} - {self.name}'


class FinancialAccount(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX = 'FA'

    class AccountType(models.TextChoices):
        CASH = 'cash', 'Caixa'
        BANK = 'bank', 'Banco'

    code = models.CharField('código', max_length=40, blank=True)
    name = models.CharField('nome', max_length=160)
    account_type = models.CharField('tipo', max_length=24, choices=AccountType.choices)
    bank_name = models.CharField('banco', max_length=120, blank=True)
    agency_number = models.CharField('agência', max_length=40, blank=True)
    account_number = models.CharField('conta', max_length=40, blank=True)
    opening_balance = models.DecimalField(
        'saldo inicial', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    current_balance = models.DecimalField(
        'saldo atual', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_financial_account_code'),
        ]
        indexes = [
            models.Index(fields=['account_type', 'is_active']),
            models.Index(fields=['code']),
        ]
        verbose_name = 'conta financeira'
        verbose_name_plural = 'contas financeiras'

    def apply_movement(self, direction, amount):
        amount = _money(amount)
        if direction == CashFlowEntry.Direction.INFLOW:
            self.current_balance = _money(self.current_balance + amount)
        else:
            self.current_balance = _money(self.current_balance - amount)
        self.save(update_fields=['current_balance', 'updated_at'])

    def reverse_movement(self, direction, amount):
        inverse = (
            CashFlowEntry.Direction.OUTFLOW
            if direction == CashFlowEntry.Direction.INFLOW
            else CashFlowEntry.Direction.INFLOW
        )
        self.apply_movement(inverse, amount)

    def __str__(self):
        return f'{self.code} - {self.name}'


class FinancialTitle(SingleInstanceModel):
    AUTOMATIC_IDENTIFIERS = (IdentifierSpec('title_number', 'FIN'),)

    class TitleType(models.TextChoices):
        PAYABLE = 'payable', 'Conta a pagar'
        RECEIVABLE = 'receivable', 'Conta a receber'

    class SourceType(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        PURCHASE = 'purchase', 'Compra'
        FISCAL_NOTE = 'fiscal_note', 'Nota fiscal'
        SALE = 'sale', 'Venda'
        CONTRACT = 'contract', 'Contrato'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        APPROVED = 'approved', 'Aprovado'
        PARTIALLY_SETTLED = 'partially_settled', 'Baixado parcialmente'
        SETTLED = 'settled', 'Baixado'
        OVERDUE = 'overdue', 'Vencido'
        CANCELLED = 'cancelled', 'Cancelado'
        REVERSED = 'reversed', 'Estornado'

    title_number = models.CharField('título', max_length=80, blank=True)
    title_type = models.CharField('tipo', max_length=24, choices=TitleType.choices)
    source_type = models.CharField(
        'origem', max_length=24, choices=SourceType.choices, default=SourceType.MANUAL
    )
    partner = models.ForeignKey(
        BusinessPartner,
        on_delete=models.PROTECT,
        related_name='financial_titles',
        verbose_name='parceiro',
    )
    category = models.ForeignKey(
        FinancialCategory,
        on_delete=models.PROTECT,
        related_name='financial_titles',
        verbose_name='categoria',
    )
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='financial_titles',
        null=True,
        blank=True,
        verbose_name='conta financeira',
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name='financial_titles',
        null=True,
        blank=True,
        verbose_name='pedido de compra',
    )
    fiscal_document_number = models.CharField('documento fiscal', max_length=80, blank=True)
    contract_reference = models.CharField('contrato', max_length=80, blank=True)
    sale_reference = models.CharField('venda', max_length=80, blank=True)
    status = models.CharField(
        'status', max_length=32, choices=Status.choices, default=Status.PENDING
    )
    issue_date = models.DateField('emissão', default=timezone.localdate)
    due_date = models.DateField('vencimento')
    original_amount = models.DecimalField('valor original', max_digits=14, decimal_places=4)
    open_amount = models.DecimalField('valor em aberto', max_digits=14, decimal_places=4)
    paid_amount = models.DecimalField(
        'valor baixado', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='approved_financial_titles',
        null=True,
        blank=True,
        verbose_name='aprovado por',
    )
    approved_at = models.DateTimeField('aprovado em', null=True, blank=True)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['due_date', 'title_number']
        constraints = [
            models.UniqueConstraint(fields=['title_number'], name='unique_financial_title_number'),
        ]
        indexes = [
            models.Index(fields=['title_type', 'status']),
            models.Index(fields=['partner', 'status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['source_type']),
            models.Index(fields=['title_number']),
        ]
        verbose_name = 'título financeiro'
        verbose_name_plural = 'títulos financeiros'

    def save(self, *args, **kwargs):
        if not self.title_number:
            self.title_number = _sequence_code(FinancialTitle, 'title_number', 'FIN')
        if self.open_amount is None:
            self.open_amount = self.original_amount
        super().save(*args, **kwargs)

    @classmethod
    def create_from_purchase_order(cls, order, category, due_date):
        amount = _money(order.total_amount)
        if amount <= 0:
            amount = _money(order.recalculate_total())
        return cls.objects.create(
            title_type=cls.TitleType.PAYABLE,
            source_type=cls.SourceType.PURCHASE,
            partner=order.supplier,
            category=category,
            purchase_order=order,
            issue_date=order.issue_date,
            due_date=due_date,
            original_amount=amount,
            open_amount=amount,
            status=cls.Status.PENDING,
        )

    def approve(self, user=None):
        if self.status not in {self.Status.PENDING, self.Status.OVERDUE}:
            raise ValidationError(
                {'status': 'Somente títulos pendentes ou vencidos podem ser aprovados.'}
            )
        self.status = self.Status.APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

    def cancel(self):
        if self.status in {self.Status.PARTIALLY_SETTLED, self.Status.SETTLED}:
            raise ValidationError({'status': 'Títulos baixados não podem ser cancelados.'})
        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])

    def mark_overdue(self):
        if (
            self.status in {self.Status.PENDING, self.Status.APPROVED}
            and self.due_date < timezone.localdate()
        ):
            self.status = self.Status.OVERDUE
            self.save(update_fields=['status', 'updated_at'])

    def register_settlement(
        self,
        financial_account,
        amount,
        settlement_date,
        method,
        interest_amount=ZERO_MONEY,
        penalty_amount=ZERO_MONEY,
        discount_amount=ZERO_MONEY,
        reference='',
    ):
        if self.status not in {self.Status.APPROVED, self.Status.PARTIALLY_SETTLED}:
            raise ValidationError({'status': 'A baixa exige título aprovado.'})
        amount = _money(amount)
        interest_amount = _money(interest_amount)
        penalty_amount = _money(penalty_amount)
        discount_amount = _money(discount_amount)
        net_amount = _money(amount + interest_amount + penalty_amount - discount_amount)
        with transaction.atomic():
            settlement = FinancialSettlement(
                title=self,
                financial_account=financial_account,
                settlement_date=settlement_date,
                method=method,
                amount=amount,
                interest_amount=interest_amount,
                penalty_amount=penalty_amount,
                discount_amount=discount_amount,
                net_amount=net_amount,
                reference=reference,
            )
            settlement.full_clean()
            settlement.save()
            self.paid_amount = _money(self.paid_amount + amount)
            self.open_amount = _money(max(self.original_amount - self.paid_amount, ZERO_MONEY))
            self.status = (
                self.Status.SETTLED
                if self.open_amount == ZERO_MONEY
                else self.Status.PARTIALLY_SETTLED
            )
            self.save(update_fields=['paid_amount', 'open_amount', 'status', 'updated_at'])
            financial_account.apply_movement(self.cash_direction, net_amount)
            return settlement

    @property
    def cash_direction(self):
        if self.title_type == self.TitleType.RECEIVABLE:
            return CashFlowEntry.Direction.INFLOW
        return CashFlowEntry.Direction.OUTFLOW

    def clean(self):
        super().clean()
        errors = {}
        for field_name in (
            'partner',
            'category',
            'financial_account',
            'purchase_order',
        ):
            pass
        if self.original_amount <= 0:
            errors['original_amount'] = 'O valor original deve ser maior que zero.'
        for field_name in ('open_amount', 'paid_amount'):
            if getattr(self, field_name) < 0:
                errors[field_name] = 'O valor não pode ser negativo.'
        if self.open_amount > self.original_amount:
            errors['open_amount'] = 'O valor em aberto não pode superar o valor original.'
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            errors['due_date'] = 'O vencimento não pode ser anterior à emissão.'
        if self.source_type == self.SourceType.PURCHASE and self.purchase_order is None:
            errors['purchase_order'] = 'Títulos originados de compra exigem pedido de compra.'
        if errors:
            raise ValidationError(errors)

        return None

        return None

    def __str__(self):
        return self.title_number


class FinancialSettlement(SingleInstanceModel):
    class Method(models.TextChoices):
        BANK_TRANSFER = 'bank_transfer', 'Transferência'
        PIX = 'pix', 'PIX'
        BOLETO = 'boleto', 'Boleto'
        CASH = 'cash', 'Dinheiro'
        CARD = 'card', 'Cartão'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Ativa'
        REVERSED = 'reversed', 'Estornada'

    title = models.ForeignKey(
        FinancialTitle, on_delete=models.PROTECT, related_name='settlements', verbose_name='título'
    )
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='settlements',
        verbose_name='conta financeira',
    )
    settlement_date = models.DateField('data da baixa')
    method = models.CharField('método', max_length=24, choices=Method.choices)
    amount = models.DecimalField('valor baixado', max_digits=14, decimal_places=4)
    interest_amount = models.DecimalField(
        'juros', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    penalty_amount = models.DecimalField(
        'multa', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    discount_amount = models.DecimalField(
        'desconto', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    net_amount = models.DecimalField(
        'valor líquido', max_digits=14, decimal_places=4, default=ZERO_MONEY
    )
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.ACTIVE
    )
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reconciled_financial_settlements',
        null=True,
        blank=True,
        verbose_name='conciliado por',
    )
    reconciled_at = models.DateTimeField('conciliado em', null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reversed_financial_settlements',
        null=True,
        blank=True,
        verbose_name='estornado por',
    )
    reversed_at = models.DateTimeField('estornado em', null=True, blank=True)
    reversal_reason = models.TextField('justificativa de estorno', blank=True)
    reference = models.CharField('referência', max_length=120, blank=True)
    notes = models.TextField('observações', blank=True)

    class Meta:
        ordering = ['-settlement_date', '-created_at']
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['financial_account']),
            models.Index(fields=['settlement_date']),
            models.Index(fields=['status']),
        ]
        verbose_name = 'baixa financeira'
        verbose_name_plural = 'baixas financeiras'

    def save(self, *args, **kwargs):
        self.net_amount = _money(
            self.amount + self.interest_amount + self.penalty_amount - self.discount_amount
        )
        super().save(*args, **kwargs)

    def reconcile(self, user=None):
        if self.status == self.Status.REVERSED:
            raise ValidationError({'status': 'Baixas estornadas não podem ser conciliadas.'})
        self.reconciled_by = user
        self.reconciled_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['reconciled_by', 'reconciled_at', 'net_amount', 'updated_at'])

    def reverse(self, reason, user=None):
        if self.status == self.Status.REVERSED:
            raise ValidationError({'status': 'A baixa já está estornada.'})
        if not reason:
            raise ValidationError({'reversal_reason': 'Informe a justificativa do estorno.'})
        with transaction.atomic():
            title = self.title
            account = self.financial_account
            account.reverse_movement(title.cash_direction, self.net_amount)
            title.paid_amount = _money(max(title.paid_amount - self.amount, ZERO_MONEY))
            title.open_amount = _money(
                min(title.original_amount - title.paid_amount, title.original_amount)
            )
            title.status = (
                title.Status.APPROVED
                if title.paid_amount == ZERO_MONEY
                else title.Status.PARTIALLY_SETTLED
            )
            title.save(update_fields=['paid_amount', 'open_amount', 'status', 'updated_at'])
            self.status = self.Status.REVERSED
            self.reversal_reason = reason
            self.reversed_by = user
            self.reversed_at = timezone.now()
            self.full_clean()
            self.save(
                update_fields=[
                    'status',
                    'reversal_reason',
                    'reversed_by',
                    'reversed_at',
                    'net_amount',
                    'updated_at',
                ]
            )

    def clean(self):
        super().clean()
        errors = {}
        if self.amount <= 0:
            errors['amount'] = 'O valor da baixa deve ser maior que zero.'
        for field_name in ('interest_amount', 'penalty_amount', 'discount_amount'):
            if getattr(self, field_name) < 0:
                errors[field_name] = 'O valor não pode ser negativo.'
        if self.net_amount < 0:
            errors['net_amount'] = 'O valor líquido não pode ser negativo.'
        if (
            self.pk is None
            and self.title
            and self.status == self.Status.ACTIVE
            and self.amount > self.title.open_amount
        ):
            errors['amount'] = 'O valor da baixa não pode superar o saldo em aberto.'
        if self._period_is_closed():
            errors['settlement_date'] = 'O período financeiro está fechado.'
        if errors:
            raise ValidationError(errors)

    def _period_is_closed(self):
        if not self.settlement_date:
            return False
        return FinancialPeriodClosing.objects.filter(
            period_year=self.settlement_date.year,
            period_month=self.settlement_date.month,
            status=FinancialPeriodClosing.Status.CLOSED,
        ).exists()

        return None

        return None

    def __str__(self):
        return f'{self.title} - {self.amount}'


class CashFlowEntry(SingleInstanceModel):
    class FlowType(models.TextChoices):
        PLANNED = 'planned', 'Previsto'
        REALIZED = 'realized', 'Realizado'

    class Direction(models.TextChoices):
        INFLOW = 'inflow', 'Entrada'
        OUTFLOW = 'outflow', 'Saída'

    class Status(models.TextChoices):
        FORECAST = 'forecast', 'Previsto'
        REALIZED = 'realized', 'Realizado'
        CANCELLED = 'cancelled', 'Cancelado'

    flow_type = models.CharField('tipo', max_length=24, choices=FlowType.choices)
    direction = models.CharField('direção', max_length=24, choices=Direction.choices)
    title = models.ForeignKey(
        FinancialTitle,
        on_delete=models.PROTECT,
        related_name='cash_flow_entries',
        verbose_name='título',
    )
    settlement = models.ForeignKey(
        FinancialSettlement,
        on_delete=models.PROTECT,
        related_name='cash_flow_entries',
        null=True,
        blank=True,
        verbose_name='baixa',
    )
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='cash_flow_entries',
        null=True,
        blank=True,
        verbose_name='conta financeira',
    )
    cash_date = models.DateField('data do fluxo')
    amount = models.DecimalField('valor', max_digits=14, decimal_places=4)
    status = models.CharField('status', max_length=24, choices=Status.choices)
    description = models.CharField('descrição', max_length=200, blank=True)

    class Meta:
        ordering = ['cash_date', 'direction']
        indexes = [
            models.Index(fields=['flow_type', 'direction']),
            models.Index(fields=['cash_date']),
            models.Index(fields=['status']),
            models.Index(fields=['financial_account']),
        ]
        verbose_name = 'fluxo de caixa'
        verbose_name_plural = 'fluxos de caixa'

    @classmethod
    def create_from_title(cls, title):
        return cls.objects.create(
            flow_type=cls.FlowType.PLANNED,
            direction=title.cash_direction,
            title=title,
            cash_date=title.due_date,
            amount=_money(title.open_amount),
            status=cls.Status.FORECAST,
            description=f'Previsto {title.title_number}',
        )

    @classmethod
    def create_from_settlement(cls, settlement):
        title = settlement.title
        return cls.objects.create(
            flow_type=cls.FlowType.REALIZED,
            direction=title.cash_direction,
            title=title,
            settlement=settlement,
            financial_account=settlement.financial_account,
            cash_date=settlement.settlement_date,
            amount=_money(settlement.net_amount),
            status=cls.Status.REALIZED,
            description=f'Realizado {title.title_number}',
        )

    def clean(self):
        super().clean()
        errors = {}
        if self.amount < 0:
            errors['amount'] = 'O valor não pode ser negativo.'
        if self.settlement and self.title and self.settlement.title_id != self.title_id:
            errors['settlement'] = 'A baixa deve pertencer ao título informado.'
        if errors:
            raise ValidationError(errors)

        return None

    def __str__(self):
        return f'{self.get_flow_type_display()} - {self.cash_date} - {self.amount}'


class FinancialPeriodClosing(SingleInstanceModel):
    class Status(models.TextChoices):
        OPEN = 'open', 'Aberto'
        VALIDATED = 'validated', 'Validado'
        CLOSED = 'closed', 'Fechado'
        REOPENED = 'reopened', 'Reaberto'

    period_year = models.PositiveSmallIntegerField('ano')
    period_month = models.PositiveSmallIntegerField('mês')
    status = models.CharField('status', max_length=24, choices=Status.choices, default=Status.OPEN)
    validation_notes = models.TextField('observações de validação', blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='closed_financial_periods',
        null=True,
        blank=True,
        verbose_name='fechado por',
    )
    closed_at = models.DateTimeField('fechado em', null=True, blank=True)

    class Meta:
        ordering = ['-period_year', '-period_month']
        constraints = [
            models.UniqueConstraint(
                fields=['period_year', 'period_month'],
                name='unique_financial_period',
            ),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['period_year', 'period_month']),
        ]
        verbose_name = 'fechamento financeiro'
        verbose_name_plural = 'fechamentos financeiros'

    def validate_period(self, notes=''):
        if self.status not in {self.Status.OPEN, self.Status.REOPENED}:
            raise ValidationError(
                {'status': 'Somente períodos abertos ou reabertos podem ser validados.'}
            )
        self.status = self.Status.VALIDATED
        self.validation_notes = notes
        self.closed_by = None
        self.closed_at = None
        self.full_clean()
        self.save(
            update_fields=['status', 'validation_notes', 'closed_by', 'closed_at', 'updated_at']
        )

    def close(self, user=None):
        if self.status != self.Status.VALIDATED:
            raise ValidationError({'status': 'O fechamento exige período validado.'})
        self.status = self.Status.CLOSED
        self.closed_by = user
        self.closed_at = timezone.now()
        self.full_clean()
        self.save(update_fields=['status', 'closed_by', 'closed_at', 'updated_at'])

    def reopen(self, reason, user=None):
        if self.status != self.Status.CLOSED:
            raise ValidationError({'status': 'Somente períodos fechados podem ser reabertos.'})
        if not reason:
            raise ValidationError({'validation_notes': 'Informe a justificativa de reabertura.'})
        self.status = self.Status.REOPENED
        self.validation_notes = reason
        self.closed_by = None
        self.closed_at = None
        self.full_clean()
        self.save(
            update_fields=['status', 'validation_notes', 'closed_by', 'closed_at', 'updated_at']
        )

    def clean(self):
        super().clean()
        errors = {}
        if not 1 <= self.period_month <= 12:
            errors['period_month'] = 'O mês deve estar entre 1 e 12.'
        if self.period_year < 2000:
            errors['period_year'] = 'Informe um ano válido.'
        if self.status == self.Status.CLOSED and not self.closed_at:
            errors['closed_at'] = 'O fechamento deve registrar data e hora.'
        if errors:
            raise ValidationError(errors)

        return None

    def __str__(self):
        return f'{self.period_year:04d}-{self.period_month:02d} - {self.get_status_display()}'
