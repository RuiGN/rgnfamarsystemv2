"""Validação e carga transacional dos catálogos mestres cosméticos."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models, transaction

from auxiliary.cosmetics_seed import ORGANIZATIONAL_ROLES
from auxiliary.models import BusinessArea, BusinessProcess, Department
from costing.models import CostElement
from crm.models import CustomerGroup, SalesChannel
from finance.models import ChartOfAccount, FinancialCategory
from fiscal.models import FiscalOperationCode, FiscalUnit
from masters.models import MasterCategory, UnitOfMeasure
from reference_data import cosmetics_catalogs
from reference_data.manifest import payload_hash
from training.models import Competency, JobPosition, WorkFunction


CATALOG_MODELS = (
    UnitOfMeasure,
    MasterCategory,
    CostElement,
    CustomerGroup,
    SalesChannel,
    ChartOfAccount,
    FinancialCategory,
    JobPosition,
    WorkFunction,
    Competency,
    FiscalUnit,
    FiscalOperationCode,
)


def _current_payload() -> dict[str, tuple[Any, ...]]:
    return {
        'masters.UnitOfMeasure': cosmetics_catalogs.UNITS,
        'masters.MasterCategory': cosmetics_catalogs.MASTER_CATEGORIES,
        'costing.CostElement': cosmetics_catalogs.COST_ELEMENTS,
        'crm.CustomerGroup': cosmetics_catalogs.CUSTOMER_GROUPS,
        'crm.SalesChannel': cosmetics_catalogs.SALES_CHANNELS,
        'finance.ChartOfAccount': cosmetics_catalogs.CHART_ACCOUNTS,
        'finance.FinancialCategory': cosmetics_catalogs.FINANCIAL_CATEGORIES,
        'training.JobPosition': cosmetics_catalogs.JOB_POSITIONS,
        'training.WorkFunction': cosmetics_catalogs.WORK_FUNCTIONS,
        'training.Competency': cosmetics_catalogs.COMPETENCIES,
        'fiscal.FiscalUnit': cosmetics_catalogs.FISCAL_UNITS,
        'fiscal.FiscalOperationCode': cosmetics_catalogs.CFOPS,
    }


def _validate_unique_codes(section: str, records: Iterable[tuple[Any, ...]]) -> set[str]:
    codes = [record[0] for record in records]
    duplicate_codes = sorted(code for code, count in Counter(codes).items() if count > 1)
    if duplicate_codes:
        raise ValidationError(f'{section}: código duplicado: {", ".join(duplicate_codes)}.')
    return set(codes)


def _validate_prefix(section: str, codes: Iterable[str], prefix: str) -> None:
    invalid_codes = sorted(code for code in codes if not code.startswith(prefix))
    if invalid_codes:
        raise ValidationError(
            f'{section}: código fora do prefixo reservado {prefix}: {", ".join(invalid_codes)}.'
        )


def _validate_numeric_codes(section: str, codes: Iterable[str]) -> None:
    invalid_codes = sorted(code for code in codes if not code.isdigit())
    if invalid_codes:
        raise ValidationError(
            f'{section}: código fora do padrão numérico: {", ".join(invalid_codes)}.'
        )


def _validate_choice(
    section: str,
    records: Iterable[tuple[Any, ...]],
    index: int,
    choices: type[models.TextChoices],
) -> None:
    allowed = set(choices.values)
    invalid = sorted({record[index] for record in records if record[index] not in allowed})
    if invalid:
        raise ValidationError(f'{section}: valor fora das choices: {", ".join(invalid)}.')


def _validate_parent_codes(
    section: str, records: Iterable[tuple[Any, ...]], parent_index: int
) -> None:
    records = tuple(records)
    codes = {record[0] for record in records}
    missing = sorted(
        {record[parent_index] for record in records if record[parent_index] not in codes | {None}}
    )
    if missing:
        raise ValidationError(f'{section}: parent inexistente: {", ".join(missing)}.')


def _validate_auxiliary_dependencies() -> None:
    relations = cosmetics_catalogs.ROLE_RELATIONS
    required_areas = {record[1] for record in relations}
    required_departments = {record[2] for record in relations}
    required_processes = {record[3] for record in relations}
    areas = BusinessArea.objects.in_bulk(required_areas, field_name='code')
    departments = Department.objects.in_bulk(required_departments, field_name='code')
    processes = BusinessProcess.objects.in_bulk(required_processes, field_name='code')
    missing = sorted(
        (required_areas - set(areas))
        | (required_departments - set(departments))
        | (required_processes - set(processes))
    )
    if missing:
        raise ValidationError(f'Dependência auxiliar inexistente: {", ".join(missing)}.')
    incompatible = []
    for role_code, area_code, department_code, process_code, _critical in relations:
        area = areas[area_code]
        if departments[department_code].area_id != area.pk:
            incompatible.append(f'{role_code}/{department_code}')
        if processes[process_code].area_id != area.pk:
            incompatible.append(f'{role_code}/{process_code}')
    if incompatible:
        raise ValidationError(f'Relação auxiliar com área incompatível: {", ".join(incompatible)}.')


def validate_catalogs(*, include_auxiliary_dependencies: bool = True) -> None:
    """Valida o manifesto e, por padrão, suas dependências auxiliares."""

    payload = _current_payload()
    manifest = cosmetics_catalogs.COSMETICS_CATALOG_MANIFEST
    codes_by_section = {
        section: _validate_unique_codes(section, records) for section, records in payload.items()
    }
    numeric_sections = (
        'masters.UnitOfMeasure',
        'masters.MasterCategory',
        'costing.CostElement',
        'crm.CustomerGroup',
        'crm.SalesChannel',
        'finance.FinancialCategory',
    )
    for section in numeric_sections:
        _validate_numeric_codes(section, codes_by_section[section])

    prefix_by_section = {
        'finance.ChartOfAccount': 'COA-COS-',
        'training.JobPosition': 'JP-COS-',
        'training.WorkFunction': 'WF-COS-',
        'training.Competency': 'CPT-COS-',
    }
    for section, prefix in prefix_by_section.items():
        _validate_prefix(section, codes_by_section[section], prefix)

    _validate_choice(
        'masters.MasterCategory', cosmetics_catalogs.MASTER_CATEGORIES, 2, MasterCategory.Kind
    )
    _validate_choice(
        'costing.CostElement', cosmetics_catalogs.COST_ELEMENTS, 2, CostElement.Category
    )
    _validate_choice(
        'crm.SalesChannel', cosmetics_catalogs.SALES_CHANNELS, 2, SalesChannel.ChannelType
    )
    _validate_choice(
        'finance.ChartOfAccount',
        cosmetics_catalogs.CHART_ACCOUNTS,
        2,
        ChartOfAccount.AccountType,
    )
    _validate_choice(
        'finance.FinancialCategory',
        cosmetics_catalogs.FINANCIAL_CATEGORIES,
        2,
        FinancialCategory.CategoryType,
    )
    _validate_choice(
        'training.Competency', cosmetics_catalogs.COMPETENCIES, 2, Competency.CompetencyType
    )
    _validate_choice(
        'fiscal.FiscalOperationCode',
        cosmetics_catalogs.CFOPS,
        2,
        FiscalOperationCode.Direction,
    )
    _validate_parent_codes('masters.MasterCategory', cosmetics_catalogs.MASTER_CATEGORIES, 3)
    _validate_parent_codes('finance.ChartOfAccount', cosmetics_catalogs.CHART_ACCOUNTS, 3)

    chart_codes = codes_by_section['finance.ChartOfAccount']
    missing_charts = sorted(
        {
            chart_code
            for _code, _name, _category_type, chart_code in cosmetics_catalogs.FINANCIAL_CATEGORIES
            if chart_code not in chart_codes
        }
    )
    if missing_charts:
        raise ValidationError(f'Conta contábil inexistente: {", ".join(missing_charts)}.')

    role_names = dict(ORGANIZATIONAL_ROLES)
    relation_role_codes = [record[0] for record in cosmetics_catalogs.ROLE_RELATIONS]
    if relation_role_codes != list(role_names):
        raise ValidationError('Cargos e funções não derivam exatamente de ORGANIZATIONAL_ROLES.')
    if [record[1] for record in cosmetics_catalogs.JOB_POSITIONS] != list(role_names.values()):
        raise ValidationError('Os títulos dos cargos divergem de ORGANIZATIONAL_ROLES.')
    if [record[1] for record in cosmetics_catalogs.WORK_FUNCTIONS] != list(role_names.values()):
        raise ValidationError('Os nomes das funções divergem de ORGANIZATIONAL_ROLES.')

    invalid_cfops = sorted(
        code
        for code, _description, direction in cosmetics_catalogs.CFOPS
        if len(code) != 4
        or not code.isdigit()
        or (direction == FiscalOperationCode.Direction.INBOUND and code[0] not in {'1', '2'})
        or (direction == FiscalOperationCode.Direction.OUTBOUND and code[0] not in {'5', '6'})
    )
    if invalid_cfops:
        raise ValidationError(f'CFOP incompatível com a direção: {", ".join(invalid_cfops)}.')

    if {section: len(records) for section, records in payload.items()} != manifest.expected_counts:
        raise ValidationError('As contagens dos catálogos divergem do manifesto.')
    if payload_hash(payload) != manifest.sha256:
        raise ValidationError('O conteúdo dos catálogos diverge do SHA-256 do manifesto.')
    if include_auxiliary_dependencies:
        _validate_auxiliary_dependencies()


def upsert_validated(
    model: type[models.Model], lookup: Mapping[str, Any], values: Mapping[str, Any]
) -> str:
    """Atualiza somente a chave explícita, validando a instância antes de salvar."""

    instance = model.objects.filter(**lookup).first()
    created = instance is None
    instance = instance or model(**lookup)
    changed = created
    for name, value in values.items():
        field = model._meta.get_field(name)
        current_value = (
            getattr(instance, field.attname)
            if field.is_relation and field.many_to_one
            else getattr(instance, name)
        )
        expected_value = (
            value.pk if field.is_relation and field.many_to_one and value is not None else value
        )
        if current_value != expected_value:
            setattr(instance, name, value)
            changed = True
    if hasattr(instance, 'is_active') and not instance.is_active:
        instance.is_active = True
        changed = True
    instance.full_clean()
    if changed:
        instance.save()
    return 'created' if created else ('updated' if changed else 'unchanged')


def _prepare_instance(
    model: type[models.Model],
    lookup: Mapping[str, Any],
    values: Mapping[str, Any],
    *,
    exclude: set[str] | None = None,
) -> models.Model:
    """Monta o estado final sem persistir e executa a validação do model."""

    instance = model.objects.filter(**lookup).first() or model(**lookup)
    for name, value in values.items():
        setattr(instance, name, value)
    if hasattr(instance, 'is_active'):
        instance.is_active = True
    instance.full_clean(exclude=exclude)
    return instance


def _prepare_flat(
    model: type[models.Model], records: Iterable[tuple[Any, ...]], fields: tuple[str, ...]
) -> list[models.Model]:
    prepared = []
    for record in records:
        code, *raw_values = record
        values = dict(zip(fields, raw_values, strict=True))
        prepared.append(_prepare_instance(model, {'code': code}, values))
    return prepared


def _prepare_hierarchy(
    model: type[models.Model],
    records: Iterable[tuple[str, str, str, str | None]],
    *,
    type_field: str,
) -> tuple[list[models.Model], dict[str, models.Model]]:
    prepared = []
    resolved: dict[str, models.Model] = {}
    pending = list(records)
    while pending:
        progress = False
        for record in pending[:]:
            code, name, record_type, parent_code = record
            if parent_code is not None and parent_code not in resolved:
                continue
            parent = resolved[parent_code] if parent_code is not None else None
            instance = _prepare_instance(
                model,
                {'code': code, type_field: record_type},
                {'name': name, type_field: record_type, 'parent': parent},
            )
            prepared.append(instance)
            resolved[code] = instance
            pending.remove(record)
            progress = True
        if not progress:
            missing = ', '.join(record[0] for record in pending)
            raise ValidationError(f'Hierarquia sem dependência resolvida: {missing}.')
    return prepared, resolved


def _prepare_training() -> list[models.Model]:
    areas = {item.code: item for item in BusinessArea.objects.filter(code__startswith='BA-COS-')}
    departments = {
        item.code: item for item in Department.objects.filter(code__startswith='DEP-COS-')
    }
    processes = {
        item.code: item for item in BusinessProcess.objects.filter(code__startswith='BPC-COS-')
    }
    prepared = []
    positions: dict[str, models.Model] = {}
    for code, title, area_code, department_code in cosmetics_catalogs.JOB_POSITIONS:
        area = areas[area_code]
        department = departments[department_code]
        position = _prepare_instance(
            JobPosition,
            {'code': code},
            {
                'title': title,
                'area': area.name,
                'area_ref': area,
                'department': department.name,
                'department_ref': department,
                'description': f'Cargo cosmético derivado da função organizacional {title}.',
            },
        )
        prepared.append(position)
        positions[code] = position

    for (
        code,
        name,
        position_code,
        area_code,
        process_code,
        critical,
    ) in cosmetics_catalogs.WORK_FUNCTIONS:
        area = areas[area_code]
        process = processes[process_code]
        position = positions[position_code]
        prepared.append(
            _prepare_instance(
                WorkFunction,
                {'code': code},
                {
                    'name': name,
                    'job_position': position,
                    'area': area.name,
                    'area_ref': area,
                    'process': process.name,
                    'process_ref': process,
                    'is_critical': critical,
                    'description': f'Função cosmética derivada da função organizacional {name}.',
                },
                exclude={'job_position'} if position.pk is None else None,
            )
        )
    return prepared


def _prepare_catalog_objects() -> list[models.Model]:
    """Prepara e valida todo o lote sem emitir nenhuma escrita."""

    prepared = []
    prepared.extend(_prepare_flat(UnitOfMeasure, cosmetics_catalogs.UNITS, ('name', 'symbol')))
    master_categories, _master_by_code = _prepare_hierarchy(
        MasterCategory, cosmetics_catalogs.MASTER_CATEGORIES, type_field='kind'
    )
    prepared.extend(master_categories)
    prepared.extend(
        _prepare_flat(CostElement, cosmetics_catalogs.COST_ELEMENTS, ('name', 'category'))
    )
    prepared.extend(
        _prepare_flat(CustomerGroup, cosmetics_catalogs.CUSTOMER_GROUPS, ('name', 'description'))
    )
    prepared.extend(
        _prepare_flat(SalesChannel, cosmetics_catalogs.SALES_CHANNELS, ('name', 'channel_type'))
    )
    chart_accounts, chart_by_code = _prepare_hierarchy(
        ChartOfAccount, cosmetics_catalogs.CHART_ACCOUNTS, type_field='account_type'
    )
    prepared.extend(chart_accounts)
    for code, name, category_type, chart_code in cosmetics_catalogs.FINANCIAL_CATEGORIES:
        chart_account = chart_by_code[chart_code]
        prepared.append(
            _prepare_instance(
                FinancialCategory,
                {'code': code},
                {
                    'name': name,
                    'category_type': category_type,
                    'chart_account': chart_account,
                },
                exclude={'chart_account'} if chart_account.pk is None else None,
            )
        )
    prepared.extend(_prepare_training())
    prepared.extend(
        _prepare_flat(Competency, cosmetics_catalogs.COMPETENCIES, ('name', 'competency_type'))
    )
    prepared.extend(_prepare_flat(FiscalUnit, cosmetics_catalogs.FISCAL_UNITS, ('description',)))
    prepared.extend(
        _prepare_flat(
            FiscalOperationCode,
            cosmetics_catalogs.CFOPS,
            ('description', 'direction'),
        )
    )
    return prepared


def _summary(managed: int, statuses: Counter[str]) -> dict[str, int]:
    return {
        'managed': managed,
        'created': statuses['created'],
        'updated': statuses['updated'],
        'unchanged': statuses['unchanged'],
    }


def _load_flat(
    model: type[models.Model], records: Iterable[tuple[Any, ...]], fields: tuple[str, ...]
) -> dict[str, int]:
    records = tuple(records)
    statuses: Counter[str] = Counter()
    for record in records:
        code, *raw_values = record
        values = dict(zip(fields, raw_values, strict=True))
        statuses[upsert_validated(model, {'code': code}, values)] += 1
    return _summary(len(records), statuses)


def _load_hierarchy(
    model: type[models.Model],
    records: Iterable[tuple[str, str, str, str | None]],
    *,
    type_field: str,
) -> dict[str, int]:
    records = tuple(records)
    statuses: Counter[str] = Counter()
    resolved: dict[str, models.Model] = {}
    pending = list(records)
    while pending:
        progress = False
        for record in pending[:]:
            code, name, record_type, parent_code = record
            if parent_code is not None and parent_code not in resolved:
                continue
            parent = resolved[parent_code] if parent_code is not None else None
            status = upsert_validated(
                model,
                {'code': code, type_field: record_type},
                {'name': name, type_field: record_type, 'parent': parent},
            )
            statuses[status] += 1
            resolved[code] = model.objects.get(code=code, **{type_field: record_type})
            pending.remove(record)
            progress = True
        if not progress:
            missing = ', '.join(record[0] for record in pending)
            raise ValidationError(f'Hierarquia sem dependência resolvida: {missing}.')
    return _summary(len(records), statuses)


def _load_training() -> dict[str, dict[str, int]]:
    areas = {item.code: item for item in BusinessArea.objects.filter(code__startswith='BA-COS-')}
    departments = {
        item.code: item for item in Department.objects.filter(code__startswith='DEP-COS-')
    }
    processes = {
        item.code: item for item in BusinessProcess.objects.filter(code__startswith='BPC-COS-')
    }
    position_statuses: Counter[str] = Counter()
    positions: dict[str, JobPosition] = {}
    for code, title, area_code, department_code in cosmetics_catalogs.JOB_POSITIONS:
        area = areas[area_code]
        department = departments[department_code]
        position_statuses[
            upsert_validated(
                JobPosition,
                {'code': code},
                {
                    'title': title,
                    'area': area.name,
                    'area_ref': area,
                    'department': department.name,
                    'department_ref': department,
                    'description': f'Cargo cosmético derivado da função organizacional {title}.',
                },
            )
        ] += 1
        positions[code] = JobPosition.objects.get(code=code)

    function_statuses: Counter[str] = Counter()
    for (
        code,
        name,
        position_code,
        area_code,
        process_code,
        critical,
    ) in cosmetics_catalogs.WORK_FUNCTIONS:
        area = areas[area_code]
        process = processes[process_code]
        function_statuses[
            upsert_validated(
                WorkFunction,
                {'code': code},
                {
                    'name': name,
                    'job_position': positions[position_code],
                    'area': area.name,
                    'area_ref': area,
                    'process': process.name,
                    'process_ref': process,
                    'is_critical': critical,
                    'description': f'Função cosmética derivada da função organizacional {name}.',
                },
            )
        ] += 1
    return {
        JobPosition._meta.label: _summary(len(cosmetics_catalogs.JOB_POSITIONS), position_statuses),
        WorkFunction._meta.label: _summary(
            len(cosmetics_catalogs.WORK_FUNCTIONS), function_statuses
        ),
    }


def _apply_catalogs() -> dict[str, dict[str, int]]:
    """Valida e aplica os catálogos curados em uma única transação."""

    validate_catalogs()
    _prepare_catalog_objects()
    result = {
        UnitOfMeasure._meta.label: _load_flat(
            UnitOfMeasure, cosmetics_catalogs.UNITS, ('name', 'symbol')
        ),
        MasterCategory._meta.label: _load_hierarchy(
            MasterCategory, cosmetics_catalogs.MASTER_CATEGORIES, type_field='kind'
        ),
        CostElement._meta.label: _load_flat(
            CostElement, cosmetics_catalogs.COST_ELEMENTS, ('name', 'category')
        ),
        CustomerGroup._meta.label: _load_flat(
            CustomerGroup, cosmetics_catalogs.CUSTOMER_GROUPS, ('name', 'description')
        ),
        SalesChannel._meta.label: _load_flat(
            SalesChannel, cosmetics_catalogs.SALES_CHANNELS, ('name', 'channel_type')
        ),
        ChartOfAccount._meta.label: _load_hierarchy(
            ChartOfAccount, cosmetics_catalogs.CHART_ACCOUNTS, type_field='account_type'
        ),
    }
    financial_statuses: Counter[str] = Counter()
    chart_accounts = {
        item.code: item for item in ChartOfAccount.objects.filter(code__startswith='COA-COS-')
    }
    for code, name, category_type, chart_code in cosmetics_catalogs.FINANCIAL_CATEGORIES:
        financial_statuses[
            upsert_validated(
                FinancialCategory,
                {'code': code},
                {
                    'name': name,
                    'category_type': category_type,
                    'chart_account': chart_accounts[chart_code],
                },
            )
        ] += 1
    result[FinancialCategory._meta.label] = _summary(
        len(cosmetics_catalogs.FINANCIAL_CATEGORIES), financial_statuses
    )
    result.update(_load_training())
    result[Competency._meta.label] = _load_flat(
        Competency, cosmetics_catalogs.COMPETENCIES, ('name', 'competency_type')
    )
    result[FiscalUnit._meta.label] = _load_flat(
        FiscalUnit, cosmetics_catalogs.FISCAL_UNITS, ('description',)
    )
    result[FiscalOperationCode._meta.label] = _load_flat(
        FiscalOperationCode, cosmetics_catalogs.CFOPS, ('description', 'direction')
    )
    return result


def apply_catalogs(*, use_current_transaction: bool = False) -> dict[str, dict[str, int]]:
    """Aplica catálogos, reutilizando opcionalmente a transação coordenadora."""

    if use_current_transaction:
        return _apply_catalogs()
    with transaction.atomic():
        return _apply_catalogs()


def catalog_model_counts() -> dict[str, int]:
    """Retorna as contagens atuais dos models de catálogo, incluindo dados locais."""

    return {model._meta.label: model.objects.count() for model in CATALOG_MODELS}
