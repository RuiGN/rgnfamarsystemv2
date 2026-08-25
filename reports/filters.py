from collections.abc import Iterable
from datetime import date
from math import isfinite
from typing import TypeGuard

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date

from reports.contracts import ReportFilters


DATE_FILTERS = frozenset({'period_start', 'period_end', 'due_start', 'due_end'})


def _is_exact_string(value: object) -> TypeGuard[str]:
    return type(value) is str


def _is_exact_integer(value: object) -> TypeGuard[int]:
    return type(value) is int


def _is_exact_float(value: object) -> TypeGuard[float]:
    return type(value) is float


def _is_exact_boolean(value: object) -> TypeGuard[bool]:
    return type(value) is bool


def _is_exact_date(value: object) -> TypeGuard[date]:
    return type(value) is date


def _is_blank_filter_value(value: object) -> bool:
    return value is None or (_is_exact_string(value) and value == '')


def _normalize_configured_keys(
    keys: Iterable[str],
    *,
    field: str,
) -> frozenset[str]:
    normalized: list[str] = []
    for key in keys:
        if not _is_exact_string(key):
            raise ValidationError({field: 'As chaves de filtros configuradas devem ser textos.'})
        normalized.append(key)
    return frozenset(normalized)


def normalize_report_filters(
    filters: ReportFilters | None,
    *,
    allowed: Iterable[str],
    required: Iterable[str] = (),
) -> ReportFilters:
    allowed_keys = _normalize_configured_keys(allowed, field='allowed')
    required_keys = _normalize_configured_keys(required, field='required')

    if filters is None:
        source: ReportFilters = {}
    elif type(filters) is dict:
        source = filters
    else:
        raise ValidationError({'filters': 'Filtros devem ser um objeto.'})

    input_values: dict[str, object] = {}
    for source_key, source_value in source.items():
        if not _is_exact_string(source_key):
            raise ValidationError({'filters': 'As chaves dos filtros devem ser textos.'})
        input_values[source_key] = source_value

    errors: dict[str, str] = {}

    unknown = sorted(key for key in input_values if key not in allowed_keys)
    if unknown:
        errors['filters'] = f'Filtros não suportados: {", ".join(unknown)}.'

    missing = sorted(
        key
        for key in required_keys
        if key not in input_values or _is_blank_filter_value(input_values[key])
    )
    if missing:
        errors['required_filters'] = f'Filtros obrigatórios ausentes: {", ".join(missing)}.'

    normalized: ReportFilters = {}
    for key, input_value in input_values.items():
        if key not in allowed_keys or _is_blank_filter_value(input_value):
            continue

        if key in DATE_FILTERS:
            if _is_exact_string(input_value):
                parsed = parse_date(input_value)
                if parsed is None:
                    errors[key] = 'Informe uma data válida.'
                else:
                    normalized[key] = parsed
            elif _is_exact_date(input_value):
                normalized[key] = input_value
            elif (
                _is_exact_integer(input_value)
                or _is_exact_float(input_value)
                or _is_exact_boolean(input_value)
            ):
                errors[key] = 'Informe uma data válida.'
            else:
                errors[key] = 'Informe um valor de filtro primitivo.'
            continue

        if (
            _is_exact_string(input_value)
            or _is_exact_integer(input_value)
            or _is_exact_boolean(input_value)
        ):
            normalized[key] = input_value
        elif _is_exact_float(input_value):
            if isfinite(input_value):
                normalized[key] = input_value
            else:
                errors[key] = 'Informe um valor de filtro primitivo.'
        else:
            errors[key] = 'Informe um valor de filtro primitivo.'

    for start_key, end_key in (
        ('period_start', 'period_end'),
        ('due_start', 'due_end'),
    ):
        start = normalized.get(start_key)
        end = normalized.get(end_key)
        if _is_exact_date(start) and _is_exact_date(end) and end < start:
            errors[end_key] = 'Data final não pode ser anterior à inicial.'

    if errors:
        raise ValidationError(errors)
    return normalized
