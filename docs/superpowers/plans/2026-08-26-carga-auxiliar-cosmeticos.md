# Carga de Dados Auxiliares para Cosméticos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preencher somente o app `auxiliary` com referências oficiais e cadastros pt-BR próprios de uma indústria cosmética, sem duplicar ou apagar registros.

**Architecture:** Traduzir nomes ISO por CLDR/Babel dentro do carregador oficial existente. Manter os dados cosméticos em um serviço declarativo e transacional, exposto por um management command idempotente; descobrir módulos e models a partir do registro real da UI.

**Tech Stack:** Python 3.14, Django 6, PostgreSQL, pytest-django, Babel, APIs oficiais IBGE e ISO 4217/SIX.

## Global Constraints

- Alterar exclusivamente registros de models do app `auxiliary`.
- Não apagar, desativar nem renomear registros fora do conjunto gerenciado.
- Não alterar `BackupRun`.
- Manter códigos e valores técnicos estáveis e nomes/descrições em pt-BR.
- Executar `full_clean()` antes de persistir cada registro curado.
- Não criar migrations.

---

### Task 1: Traduzir moedas oficiais para pt-BR

**Files:**
- Modify: `auxiliary/management/commands/load_official_reference_data.py`
- Modify: `tests/test_auxiliary_reference_data.py`

**Interfaces:**
- Consumes: XML ISO 4217 já processado por `Command._parse_currencies(payload)`.
- Produces: `Currency.name` localizado por `babel.numbers.get_currency_name(code, locale='pt_BR')` e descrição com a fonte oficial preservada.

- [ ] **Step 1: Escrever o teste falho de localização**

Alterar as asserções do teste existente para exigir:

```python
assert brl.name == 'Real brasileiro'
assert Currency.objects.get(code='USD').name == 'Dólar americano'
assert Currency.objects.get(code='USD').description == (
    'Entidades usuárias: PUERTO RICO; UNITED STATES OF AMERICA. '
    'Fonte: ISO 4217/SIX (lista vigente em 2026-01-01).'
)
```

- [ ] **Step 2: Confirmar RED**

Run: `.venv/bin/pytest tests/test_auxiliary_reference_data.py::OfficialReferenceDataCommandTests::test_loads_official_catalogs_and_is_idempotent -q`

Expected: FAIL porque `brl.name` ainda é `Brazilian Real`.

- [ ] **Step 3: Implementar localização CLDR**

Adicionar o import:

```python
from babel.numbers import get_currency_name
```

Em `_parse_currencies`, substituir o nome retornado pela fonte por:

```python
localized_name = str(get_currency_name(code, locale='pt_BR') or name).strip()
```

e usar `localized_name` no dicionário final, preservando os demais campos ISO.

- [ ] **Step 4: Confirmar GREEN**

Run: `.venv/bin/pytest tests/test_auxiliary_reference_data.py -q`

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add auxiliary/management/commands/load_official_reference_data.py tests/test_auxiliary_reference_data.py
git commit -m "feat: localize official currency names to pt-BR"
```

### Task 2: Criar o serviço de catálogo cosmético

**Files:**
- Create: `auxiliary/cosmetics_seed.py`
- Create: `tests/test_cosmetics_auxiliary_data.py`

**Interfaces:**
- Produces: `seed_cosmetics_auxiliary_data() -> dict[str, int]`.
- Consumes: models de `auxiliary`, `base.ui.registry.get_modules()` e transação Django.

- [ ] **Step 1: Escrever testes falhos do serviço**

Criar `tests/test_cosmetics_auxiliary_data.py`:

```python
import pytest
from django.core.exceptions import ValidationError

from auxiliary.cosmetics_seed import seed_cosmetics_auxiliary_data
from auxiliary.models import (
    BackupRun,
    BusinessArea,
    BusinessProcess,
    CatalogType,
    CatalogValue,
    CommercialTerm,
    Department,
    ImpactLevel,
    OrganizationalRole,
    SystemModel,
    SystemModule,
)
from masters.models import Product


pytestmark = pytest.mark.django_db


def managed_counts():
    models = (
        BusinessArea,
        BusinessProcess,
        Department,
        OrganizationalRole,
        CommercialTerm,
        SystemModule,
        SystemModel,
        ImpactLevel,
        CatalogType,
        CatalogValue,
    )
    return {model._meta.label: model.objects.count() for model in models}


def test_seed_creates_linked_cosmetics_catalogs_only_in_auxiliary():
    product_count = Product.objects.count()
    backup_count = BackupRun.objects.count()

    result = seed_cosmetics_auxiliary_data()

    production = BusinessArea.objects.get(code='BA-COS-PROD')
    assert production.name == 'Produção'
    assert BusinessProcess.objects.get(code='BPC-COS-FAB').area == production
    assert Department.objects.get(code='DEP-COS-ENV').area == production
    assert OrganizationalRole.objects.filter(code='ORG-COS-RT').exists()
    assert CommercialTerm.objects.get(code='CTM-COS-PG30').days == 30
    assert ImpactLevel.objects.get(code='IL-COS-RISK-4').name == 'Crítico'
    material_type = CatalogType.objects.get(code='CTG-COS-MATERIAL')
    assert CatalogValue.objects.get(code='CV-COS-MAT-MP').catalog_type == material_type
    assert SystemModule.objects.filter(app_label='auxiliary').exists()
    assert SystemModel.objects.filter(app_label='auxiliary', model_name='currency').exists()
    assert result['business_areas'] == BusinessArea.objects.filter(
        code__startswith='BA-COS-'
    ).count()
    assert Product.objects.count() == product_count
    assert BackupRun.objects.count() == backup_count


def test_seed_is_idempotent_and_preserves_unmanaged_records():
    BusinessArea.objects.create(code='BA-LOCAL', name='Área local')
    seed_cosmetics_auxiliary_data()
    first = managed_counts()

    seed_cosmetics_auxiliary_data()

    assert managed_counts() == first
    assert BusinessArea.objects.get(code='BA-LOCAL').name == 'Área local'


def test_seed_rolls_back_when_curated_record_is_invalid(monkeypatch):
    from auxiliary import cosmetics_seed

    monkeypatch.setattr(
        cosmetics_seed,
        'BUSINESS_AREAS',
        (*cosmetics_seed.BUSINESS_AREAS, ('BA-COS-INVALID', '', 'Inválido')),
    )

    with pytest.raises(ValidationError):
        seed_cosmetics_auxiliary_data()

    assert BusinessArea.objects.count() == 0
```

- [ ] **Step 2: Confirmar RED**

Run: `.venv/bin/pytest tests/test_cosmetics_auxiliary_data.py -q`

Expected: ERROR de importação porque `auxiliary.cosmetics_seed` ainda não existe.

- [ ] **Step 3: Criar dados declarativos completos**

Criar `auxiliary/cosmetics_seed.py` com tuplas imutáveis contendo:

```python
BUSINESS_AREAS = (
    ('BA-COS-DT', 'Direção Técnica', 'Governança técnica e responsabilidade sanitária.'),
    ('BA-COS-PD', 'Pesquisa e Desenvolvimento', 'Desenvolvimento e transferência de produtos cosméticos.'),
    ('BA-COS-PROD', 'Produção', 'Pesagem, fabricação, envase e embalagem.'),
    ('BA-COS-CQ', 'Controle da Qualidade', 'Ensaios físico-químicos e microbiológicos.'),
    ('BA-COS-GQ', 'Garantia da Qualidade', 'Sistema da qualidade, validação e liberação.'),
    ('BA-COS-AR', 'Assuntos Regulatórios', 'Regularização e manutenção de produtos cosméticos.'),
    ('BA-COS-SUP', 'Suprimentos', 'Compras e qualificação comercial de fornecedores.'),
    ('BA-COS-LOG', 'Armazenagem e Logística', 'Recebimento, armazenagem e expedição.'),
    ('BA-COS-COM', 'Comercial e Atendimento', 'Vendas, SAC e cosmetovigilância.'),
    ('BA-COS-FIN', 'Financeiro', 'Contas, tesouraria e controladoria.'),
    ('BA-COS-RH', 'Recursos Humanos', 'Pessoas, competências e treinamentos.'),
    ('BA-COS-ENG', 'Engenharia e Manutenção', 'Utilidades, equipamentos e manutenção.'),
    ('BA-COS-SSMA', 'Saúde, Segurança e Meio Ambiente', 'Segurança ocupacional e gestão ambiental.'),
    ('BA-COS-TI', 'Tecnologia da Informação', 'Sistemas, infraestrutura e segurança da informação.'),
)

BUSINESS_PROCESSES = (
    ('BPC-COS-DEV', 'Desenvolvimento de formulações', 'BA-COS-PD'),
    ('BPC-COS-TRANSF', 'Transferência de tecnologia', 'BA-COS-PD'),
    ('BPC-COS-QUAL-MP', 'Qualificação de matérias-primas', 'BA-COS-GQ'),
    ('BPC-COS-QUAL-ME', 'Qualificação de materiais de embalagem', 'BA-COS-GQ'),
    ('BPC-COS-PES', 'Pesagem e dispensação', 'BA-COS-PROD'),
    ('BPC-COS-FAB', 'Fabricação de cosméticos', 'BA-COS-PROD'),
    ('BPC-COS-ENV', 'Envase', 'BA-COS-PROD'),
    ('BPC-COS-EMB', 'Embalagem', 'BA-COS-PROD'),
    ('BPC-COS-FQ', 'Controle físico-químico', 'BA-COS-CQ'),
    ('BPC-COS-MICRO', 'Controle microbiológico', 'BA-COS-CQ'),
    ('BPC-COS-LIB', 'Liberação de lote', 'BA-COS-GQ'),
    ('BPC-COS-DESV', 'Gestão de desvios', 'BA-COS-GQ'),
    ('BPC-COS-CAPA', 'Gestão de CAPA', 'BA-COS-GQ'),
    ('BPC-COS-MUD', 'Controle de mudanças', 'BA-COS-GQ'),
    ('BPC-COS-REG', 'Regularização de cosméticos', 'BA-COS-AR'),
    ('BPC-COS-RECL', 'Tratamento de reclamações', 'BA-COS-COM'),
    ('BPC-COS-COSVIG', 'Cosmetovigilância', 'BA-COS-COM'),
    ('BPC-COS-REC', 'Recolhimento de produto', 'BA-COS-GQ'),
    ('BPC-COS-COMP', 'Compras', 'BA-COS-SUP'),
    ('BPC-COS-REC-MAT', 'Recebimento de materiais', 'BA-COS-LOG'),
    ('BPC-COS-ARM', 'Armazenagem', 'BA-COS-LOG'),
    ('BPC-COS-EXP', 'Expedição', 'BA-COS-LOG'),
)

DEPARTMENTS = (
    ('DEP-COS-FORM', 'Desenvolvimento de Formulações', 'BA-COS-PD'),
    ('DEP-COS-FAB', 'Fabricação', 'BA-COS-PROD'),
    ('DEP-COS-ENV', 'Envase', 'BA-COS-PROD'),
    ('DEP-COS-EMB', 'Embalagem', 'BA-COS-PROD'),
    ('DEP-COS-FQ', 'Laboratório Físico-Químico', 'BA-COS-CQ'),
    ('DEP-COS-MICRO', 'Laboratório de Microbiologia', 'BA-COS-CQ'),
    ('DEP-COS-VALID', 'Validação e Qualificação', 'BA-COS-GQ'),
    ('DEP-COS-LIB', 'Liberação e Documentação', 'BA-COS-GQ'),
    ('DEP-COS-FORN', 'Qualificação de Fornecedores', 'BA-COS-GQ'),
    ('DEP-COS-REG', 'Regularização de Produtos', 'BA-COS-AR'),
    ('DEP-COS-SAC', 'SAC e Cosmetovigilância', 'BA-COS-COM'),
    ('DEP-COS-COMP', 'Compras', 'BA-COS-SUP'),
    ('DEP-COS-ALMOX', 'Almoxarifado', 'BA-COS-LOG'),
    ('DEP-COS-EXP', 'Expedição', 'BA-COS-LOG'),
    ('DEP-COS-MAN', 'Manutenção', 'BA-COS-ENG'),
    ('DEP-COS-TI', 'Sistemas e Infraestrutura', 'BA-COS-TI'),
)

ORGANIZATIONAL_ROLES = (
    ('ORG-COS-RT', 'Responsável Técnico'),
    ('ORG-COS-GGQ', 'Gerente de Garantia da Qualidade'),
    ('ORG-COS-AGQ', 'Analista de Garantia da Qualidade'),
    ('ORG-COS-GCQ', 'Gerente de Controle da Qualidade'),
    ('ORG-COS-ACQ', 'Analista de Controle da Qualidade'),
    ('ORG-COS-FORM', 'Formulador Cosmético'),
    ('ORG-COS-MICRO', 'Microbiologista'),
    ('ORG-COS-SPROD', 'Supervisor de Produção'),
    ('ORG-COS-OFAB', 'Operador de Fabricação'),
    ('ORG-COS-OENV', 'Operador de Envase'),
    ('ORG-COS-IEMB', 'Inspetor de Embalagem'),
    ('ORG-COS-REG', 'Analista de Assuntos Regulatórios'),
    ('ORG-COS-COMP', 'Comprador'),
    ('ORG-COS-ALMOX', 'Almoxarife'),
    ('ORG-COS-PCP', 'Planejador de Produção'),
    ('ORG-COS-MAN', 'Técnico de Manutenção'),
    ('ORG-COS-COSVIG', 'Analista de SAC e Cosmetovigilância'),
    ('ORG-COS-AUD', 'Auditor Interno'),
)

COMMERCIAL_TERMS = (
    ('CTM-COS-PG0', 'Pagamento à vista', 'payment', 0),
    ('CTM-COS-PG7', 'Pagamento em 7 dias', 'payment', 7),
    ('CTM-COS-PG14', 'Pagamento em 14 dias', 'payment', 14),
    ('CTM-COS-PG21', 'Pagamento em 21 dias', 'payment', 21),
    ('CTM-COS-PG28', 'Pagamento em 28 dias', 'payment', 28),
    ('CTM-COS-PG30', 'Pagamento em 30 dias', 'payment', 30),
    ('CTM-COS-PG45', 'Pagamento em 45 dias', 'payment', 45),
    ('CTM-COS-PG60', 'Pagamento em 60 dias', 'payment', 60),
    ('CTM-COS-PG90', 'Pagamento em 90 dias', 'payment', 90),
    ('CTM-COS-RET', 'Retirada pelo comprador', 'delivery', 0),
    ('CTM-COS-CIF', 'Entrega CIF', 'delivery', 7),
    ('CTM-COS-FOB', 'Entrega FOB', 'delivery', 0),
)
```

Definir também, no mesmo arquivo, quatro níveis para cada tipo de impacto e os
catálogos completos:

```python
IMPACT_NAMES = (
    (1, 'Baixo', 'success'),
    (2, 'Médio', 'warning'),
    (3, 'Alto', 'danger'),
    (4, 'Crítico', 'dark'),
)
IMPACT_TYPES = ('severity', 'criticality', 'priority', 'risk')

CATALOGS = (
    ('CTG-COS-MATERIAL', 'Tipo de material cosmético', 'material_type', (
        ('CV-COS-MAT-MP', 'Matéria-prima', 'raw_material'),
        ('CV-COS-MAT-ME', 'Material de embalagem', 'packaging_material'),
        ('CV-COS-MAT-SEMI', 'Produto semielaborado', 'semi_finished'),
        ('CV-COS-MAT-PA', 'Produto acabado', 'finished_product'),
    )),
    ('CTG-COS-APRESENT', 'Apresentação cosmética', 'presentation', (
        ('CV-COS-APR-CREME', 'Creme', 'cream'),
        ('CV-COS-APR-LOCAO', 'Loção', 'lotion'),
        ('CV-COS-APR-GEL', 'Gel', 'gel'),
        ('CV-COS-APR-SHAMPOO', 'Xampu', 'shampoo'),
        ('CV-COS-APR-COND', 'Condicionador', 'conditioner'),
        ('CV-COS-APR-SAB', 'Sabonete líquido', 'liquid_soap'),
        ('CV-COS-APR-SERUM', 'Sérum', 'serum'),
        ('CV-COS-APR-AERO', 'Aerossol', 'aerosol'),
    )),
    ('CTG-COS-RECL-ORIG', 'Origem da reclamação', 'complaint_origin', (
        ('CV-COS-REC-CONS', 'Consumidor', 'consumer'),
        ('CV-COS-REC-CLI', 'Cliente', 'customer'),
        ('CV-COS-REC-DIST', 'Distribuidor', 'distributor'),
        ('CV-COS-REC-VIG', 'Autoridade sanitária', 'health_authority'),
    )),
    ('CTG-COS-DESV', 'Classificação de desvio', 'deviation_class', (
        ('CV-COS-DESV-MEN', 'Menor', 'minor'),
        ('CV-COS-DESV-MAI', 'Maior', 'major'),
        ('CV-COS-DESV-CRI', 'Crítico', 'critical'),
    )),
    ('CTG-COS-EMB', 'Tipo de embalagem', 'packaging_type', (
        ('CV-COS-EMB-PRIM', 'Embalagem primária', 'primary'),
        ('CV-COS-EMB-SEC', 'Embalagem secundária', 'secondary'),
        ('CV-COS-EMB-TER', 'Embalagem de transporte', 'tertiary'),
    )),
    ('CTG-COS-ARM', 'Condição de armazenamento', 'storage_condition', (
        ('CV-COS-ARM-AMB', 'Temperatura ambiente', 'ambient'),
        ('CV-COS-ARM-15-30', 'Entre 15 °C e 30 °C', '15_30_c'),
        ('CV-COS-ARM-2-8', 'Refrigerado entre 2 °C e 8 °C', '2_8_c'),
        ('CV-COS-ARM-LUZ', 'Protegido da luz', 'protected_from_light'),
    )),
    ('CTG-COS-UNID', 'Unidade organizacional', 'organizational_unit', (
        ('CV-COS-UNID-PD', 'Pesquisa e Desenvolvimento', 'research_development'),
        ('CV-COS-UNID-PROD', 'Produção', 'production'),
        ('CV-COS-UNID-CQ', 'Controle da Qualidade', 'quality_control'),
        ('CV-COS-UNID-GQ', 'Garantia da Qualidade', 'quality_assurance'),
        ('CV-COS-UNID-AR', 'Assuntos Regulatórios', 'regulatory_affairs'),
        ('CV-COS-UNID-LOG', 'Armazenagem e Logística', 'logistics'),
    )),
)
```

- [ ] **Step 4: Implementar upsert validado e descoberta do sistema**

Adicionar ao mesmo arquivo, depois das constantes:

```python
from collections import defaultdict

from django.db import transaction

from auxiliary.models import (
    BusinessArea,
    BusinessProcess,
    CatalogType,
    CatalogValue,
    CommercialTerm,
    Department,
    ImpactLevel,
    OrganizationalRole,
    SystemModel,
    SystemModule,
)
from base.ui.registry import get_modules


IMPACT_CODE_PARTS = {
    'severity': 'SEV',
    'criticality': 'CRIT',
    'priority': 'PRI',
    'risk': 'RISK',
}


def _upsert(model, code, **values):
    instance = model.objects.filter(code=code).first() or model(code=code)
    for field_name, value in values.items():
        setattr(instance, field_name, value)
    instance.is_active = True
    instance.full_clean()
    instance.save()
    return instance


@transaction.atomic
def seed_cosmetics_auxiliary_data():
    counts = defaultdict(int)
    areas = {}
    for code, name, description in BUSINESS_AREAS:
        areas[code] = _upsert(
            BusinessArea, code, name=name, description=description
        )
        counts['business_areas'] += 1

    for code, name, area_code in BUSINESS_PROCESSES:
        _upsert(
            BusinessProcess,
            code,
            name=name,
            description=f'Processo cosmético: {name}.',
            area=areas[area_code],
        )
        counts['business_processes'] += 1

    for code, name, area_code in DEPARTMENTS:
        _upsert(
            Department,
            code,
            name=name,
            description=f'Departamento da indústria cosmética: {name}.',
            area=areas[area_code],
        )
        counts['departments'] += 1

    for code, name in ORGANIZATIONAL_ROLES:
        _upsert(
            OrganizationalRole,
            code,
            name=name,
            description=f'Função organizacional cosmética: {name}.',
        )
        counts['organizational_roles'] += 1

    for code, name, term_type, days in COMMERCIAL_TERMS:
        _upsert(
            CommercialTerm,
            code,
            name=name,
            description=(
                f'Condição comercial de {name.lower()}; validar o instrumento '
                'contratual aplicável.'
            ),
            term_type=term_type,
            days=days,
        )
        counts['commercial_terms'] += 1

    for level_type in IMPACT_TYPES:
        for weight, name, color in IMPACT_NAMES:
            code = f'IL-COS-{IMPACT_CODE_PARTS[level_type]}-{weight}'
            _upsert(
                ImpactLevel,
                code,
                name=name,
                description=f'{name} para classificação de {level_type}.',
                level_type=level_type,
                weight=weight,
                color=color,
            )
            counts['impact_levels'] += 1

    for type_code, type_name, target_field, values in CATALOGS:
        catalog_type = _upsert(
            CatalogType,
            type_code,
            name=type_name,
            description=f'Catálogo cosmético: {type_name}.',
            target_field=target_field,
        )
        counts['catalog_types'] += 1
        for order, (value_code, value_name, technical_value) in enumerate(
            values, start=1
        ):
            _upsert(
                CatalogValue,
                value_code,
                name=value_name,
                description=f'Valor de {type_name.lower()}: {value_name}.',
                catalog_type=catalog_type,
                value=technical_value,
                order=order * 10,
            )
            counts['catalog_values'] += 1

    module_refs = {}
    for module in get_modules():
        code = f'SM-{module.slug.upper().replace("-", "_")}'
        module_refs[module.slug] = _upsert(
            SystemModule,
            code,
            name=module.label,
            description=module.description,
            app_label=module.slug,
            menu_label=module.label,
        )
        counts['system_modules'] += 1

    seen_models = set()
    for module in get_modules():
        for resource in module.resources:
            model = resource.model
            key = (model._meta.app_label, model._meta.model_name)
            if key in seen_models:
                continue
            seen_models.add(key)
            app_label, model_name = key
            code = f'SMD-{app_label}.{model_name}'
            _upsert(
                SystemModel,
                code,
                name=str(model._meta.verbose_name).capitalize(),
                description=f'Model do recurso {resource.label}.',
                module=module_refs[module.slug],
                app_label=app_label,
                model_name=model_name,
            )
            counts['system_models'] += 1

    return dict(sorted(counts.items()))
```

- [ ] **Step 5: Confirmar GREEN e idempotência**

Run: `.venv/bin/pytest tests/test_cosmetics_auxiliary_data.py -q`

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add auxiliary/cosmetics_seed.py tests/test_cosmetics_auxiliary_data.py
git commit -m "feat: add cosmetics auxiliary reference catalog"
```

### Task 3: Expor comando, documentar e carregar o banco

**Files:**
- Create: `auxiliary/management/commands/load_cosmetics_auxiliary_data.py`
- Modify: `tests/test_cosmetics_auxiliary_data.py`
- Modify: `docs/architecture/auxiliary.md`

**Interfaces:**
- Consumes: `seed_cosmetics_auxiliary_data()` e comando `load_official_reference_data`.
- Produces: `manage.py load_cosmetics_auxiliary_data [--with-official-references] [--timeout N]`.

- [ ] **Step 1: Escrever teste falho do comando**

Adicionar:

```python
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command


def test_command_can_run_official_references_before_cosmetics_catalog():
    stdout = StringIO()
    with patch(
        'auxiliary.management.commands.load_cosmetics_auxiliary_data.call_command'
    ) as nested_call:
        call_command(
            'load_cosmetics_auxiliary_data',
            with_official_references=True,
            timeout=45,
            stdout=stdout,
        )

    nested_call.assert_called_once_with('load_official_reference_data', timeout=45)
    assert 'Carga auxiliar cosmética concluída' in stdout.getvalue()
```

- [ ] **Step 2: Confirmar RED**

Run: `.venv/bin/pytest tests/test_cosmetics_auxiliary_data.py::test_command_can_run_official_references_before_cosmetics_catalog -q`

Expected: `Unknown command: 'load_cosmetics_auxiliary_data'`.

- [ ] **Step 3: Implementar comando**

Criar `auxiliary/management/commands/load_cosmetics_auxiliary_data.py`:

```python
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from auxiliary.cosmetics_seed import seed_cosmetics_auxiliary_data


class Command(BaseCommand):
    help = 'Carrega referências auxiliares pt-BR para uma indústria cosmética.'

    def add_arguments(self, parser):
        parser.add_argument('--with-official-references', action='store_true')
        parser.add_argument('--timeout', type=int, default=60)

    def handle(self, *args, **options):
        timeout = options['timeout']
        if timeout < 1 or timeout > 300:
            raise CommandError('--timeout deve estar entre 1 e 300 segundos.')
        if options['with_official_references']:
            call_command('load_official_reference_data', timeout=timeout)

        counts = seed_cosmetics_auxiliary_data()
        summary = ', '.join(f'{key}={value}' for key, value in counts.items())
        self.stdout.write(
            self.style.SUCCESS(f'Carga auxiliar cosmética concluída: {summary}.')
        )
```

- [ ] **Step 4: Documentar operação**

Criar uma seção `## Carga de referências auxiliares` em
`docs/architecture/auxiliary.md` com o texto: a carga oficial usa IBGE e ISO
4217/SIX, os nomes das moedas são localizados por CLDR/Babel, a carga cosmética
é idempotente e não altera outros apps nem `BackupRun`. Incluir os comandos:

```bash
.venv/bin/python manage.py load_official_reference_data
.venv/bin/python manage.py load_cosmetics_auxiliary_data
```

e a execução combinada:

```bash
.venv/bin/python manage.py load_cosmetics_auxiliary_data --with-official-references
```

- [ ] **Step 5: Executar testes e checks**

Run:

```bash
.venv/bin/pytest tests/test_auxiliary.py tests/test_auxiliary_reference_data.py tests/test_cosmetics_auxiliary_data.py -q
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
```

Expected: todos os testes passam, check sem problemas e `No changes detected`.

- [ ] **Step 6: Carregar banco local com fontes oficiais**

Run:

```bash
.venv/bin/python manage.py load_cosmetics_auxiliary_data --with-official-references --timeout 120
```

Expected: cardinalidades oficiais validadas e resumo cosmético sem falhas.

- [ ] **Step 7: Verificar banco e aplicação**

Consultar contagens de todos os models do app `auxiliary`, confirmar
`BackupRun=0`, confirmar amostras pt-BR e `curl` HTTP 200 em
`http://127.0.0.1:8000/`.

- [ ] **Step 8: Commit**

```bash
git add auxiliary/management/commands/load_cosmetics_auxiliary_data.py tests/test_cosmetics_auxiliary_data.py docs/architecture/auxiliary.md
git commit -m "feat: load official cosmetics auxiliary data"
```
