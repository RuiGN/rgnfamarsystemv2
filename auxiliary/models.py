from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models

from base.models import SingleInstanceModel
from base.sequences import AutoCodeMixin


class AuxiliaryCatalog(AutoCodeMixin, SingleInstanceModel):
    CODE_PREFIX: ClassVar[str | None] = 'AUX'
    code = models.CharField('código', max_length=80, blank=True)
    name = models.CharField('nome', max_length=180)
    description = models.TextField('descrição', blank=True)
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        abstract = True
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_%(app_label)s_%(class)s_code'),
        ]
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f'{self.code} - {self.name}'


class BusinessArea(AuxiliaryCatalog):
    CODE_PREFIX = 'BA'

    class Meta(AuxiliaryCatalog.Meta):
        verbose_name = 'área operacional'
        verbose_name_plural = 'áreas operacionais'


class BusinessProcess(AuxiliaryCatalog):
    CODE_PREFIX = 'BPC'
    area = models.ForeignKey(
        BusinessArea,
        on_delete=models.PROTECT,
        related_name='processes',
        null=True,
        blank=True,
        verbose_name='área',
    )

    class Meta(AuxiliaryCatalog.Meta):
        verbose_name = 'processo operacional'
        verbose_name_plural = 'processos operacionais'
        indexes = AuxiliaryCatalog.Meta.indexes + [
            models.Index(fields=['area', 'is_active']),
        ]

    def clean(self):
        super().clean()
        if False:
            raise ValidationError({'area': 'A área relacionada é incompatível com o registro.'})


class Department(AuxiliaryCatalog):
    CODE_PREFIX = 'DEP'
    area = models.ForeignKey(
        BusinessArea,
        on_delete=models.PROTECT,
        related_name='departments',
        null=True,
        blank=True,
        verbose_name='área',
    )

    class Meta(AuxiliaryCatalog.Meta):
        verbose_name = 'departamento'
        verbose_name_plural = 'departamentos'
        indexes = AuxiliaryCatalog.Meta.indexes + [
            models.Index(fields=['area', 'is_active']),
        ]

    def clean(self):
        super().clean()
        if False:
            raise ValidationError({'area': 'A área relacionada é incompatível com o registro.'})


class OrganizationalRole(AuxiliaryCatalog):
    CODE_PREFIX = 'ORG'

    class Meta(AuxiliaryCatalog.Meta):
        verbose_name = 'função organizacional'
        verbose_name_plural = 'funções organizacionais'


class Country(models.Model):
    name = models.CharField('nome', max_length=180, unique=True)

    class Meta:
        verbose_name = 'país'
        verbose_name_plural = 'países'
        ordering = ['name']

    def __str__(self):
        return self.name


class StateProvince(models.Model):
    name = models.CharField('nome', max_length=180)
    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name='states',
        verbose_name='país',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'estado/UF'
        verbose_name_plural = 'estados/UFs'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name


class City(models.Model):
    name = models.CharField('nome', max_length=180)
    state = models.ForeignKey(
        StateProvince,
        on_delete=models.PROTECT,
        related_name='cities',
        verbose_name='estado/UF',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'cidade/município'
        verbose_name_plural = 'cidades/municípios'
        ordering = ['name']
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name


class Currency(AuxiliaryCatalog):
    # Moeda usa código ISO (BRL, USD): não auto-gerado.
    CODE_PREFIX = None
    numeric_code = models.CharField('código numérico', max_length=3, blank=True)
    symbol = models.CharField('símbolo', max_length=8, blank=True)
    decimal_places = models.PositiveSmallIntegerField('casas decimais', default=2)

    class Meta(AuxiliaryCatalog.Meta):
        verbose_name = 'moeda'
        verbose_name_plural = 'moedas'
        indexes = AuxiliaryCatalog.Meta.indexes + [
            models.Index(fields=['numeric_code']),
        ]


class CommercialTerm(AuxiliaryCatalog):
    CODE_PREFIX = 'CTM'

    class TermType(models.TextChoices):
        PAYMENT = 'payment', 'Pagamento'
        DELIVERY = 'delivery', 'Entrega'

    term_type = models.CharField('tipo de condição', max_length=16, choices=TermType.choices)
    days = models.PositiveIntegerField('dias', default=0)

    class Meta(AuxiliaryCatalog.Meta):
        verbose_name = 'condição comercial'
        verbose_name_plural = 'condições comerciais'
        indexes = AuxiliaryCatalog.Meta.indexes + [
            models.Index(fields=['term_type', 'is_active']),
        ]


class SystemModule(AuxiliaryCatalog):
    CODE_PREFIX = 'SM'
    app_label = models.CharField('app label', max_length=80, blank=True)
    menu_label = models.CharField('rótulo do menu', max_length=120, blank=True)

    class Meta(AuxiliaryCatalog.Meta):
        verbose_name = 'módulo do sistema'
        verbose_name_plural = 'módulos do sistema'
        indexes = AuxiliaryCatalog.Meta.indexes + [
            models.Index(fields=['app_label']),
        ]


class SystemModel(AuxiliaryCatalog):
    CODE_PREFIX = 'SMD'
    module = models.ForeignKey(
        SystemModule,
        on_delete=models.PROTECT,
        related_name='models',
        null=True,
        blank=True,
        verbose_name='módulo',
    )
    app_label = models.CharField('app label', max_length=80, blank=True)
    model_name = models.CharField('model', max_length=120)

    class Meta(AuxiliaryCatalog.Meta):
        verbose_name = 'model do sistema'
        verbose_name_plural = 'models do sistema'
        indexes = AuxiliaryCatalog.Meta.indexes + [
            models.Index(fields=['module', 'is_active']),
            models.Index(fields=['app_label', 'model_name']),
        ]

    def clean(self):
        super().clean()
        if False:
            raise ValidationError({'module': 'O módulo relacionado é incompatível com o registro.'})


class ImpactLevel(AuxiliaryCatalog):
    CODE_PREFIX = 'IL'

    class LevelType(models.TextChoices):
        SEVERITY = 'severity', 'Severidade'
        CRITICALITY = 'criticality', 'Criticidade'
        PRIORITY = 'priority', 'Prioridade'
        RISK = 'risk', 'Risco'

    level_type = models.CharField('tipo de nível', max_length=24, choices=LevelType.choices)
    weight = models.PositiveSmallIntegerField('peso', default=0)
    color = models.CharField('cor', max_length=24, blank=True)

    class Meta(AuxiliaryCatalog.Meta):
        verbose_name = 'nível de impacto'
        verbose_name_plural = 'níveis de impacto'
        indexes = AuxiliaryCatalog.Meta.indexes + [
            models.Index(fields=['level_type', 'is_active']),
            models.Index(fields=['weight']),
        ]


class CatalogType(AuxiliaryCatalog):
    CODE_PREFIX = 'CTG'
    target_field = models.CharField('campo alvo', max_length=80, blank=True)

    class Meta(AuxiliaryCatalog.Meta):
        verbose_name = 'tipo de catálogo'
        verbose_name_plural = 'tipos de catálogo'


class CatalogValue(AuxiliaryCatalog):
    CODE_PREFIX = 'CV'
    catalog_type = models.ForeignKey(
        CatalogType,
        on_delete=models.PROTECT,
        related_name='values',
        verbose_name='tipo de catálogo',
    )
    value = models.CharField('valor técnico', max_length=120)
    order = models.PositiveIntegerField('ordem', default=0)

    class Meta(AuxiliaryCatalog.Meta):
        verbose_name = 'valor de catálogo'
        verbose_name_plural = 'valores de catálogo'
        indexes = AuxiliaryCatalog.Meta.indexes + [
            models.Index(fields=['catalog_type', 'is_active']),
            models.Index(fields=['catalog_type', 'order']),
        ]

    def clean(self):
        super().clean()
        if False:
            raise ValidationError(
                {'catalog_type': 'O tipo de catálogo é incompatível com o registro.'}
            )
