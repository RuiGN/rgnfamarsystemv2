from collections.abc import Iterable
from typing import cast

from django.core.exceptions import ValidationError

from reports.contracts import ReportFilters


BIG_AUTO_FIELD_MAX = 9_223_372_036_854_775_807
BIG_AUTO_FIELD_MAX_DIGITS = 19


def positive_integer_filter(filters: ReportFilters, field: str) -> int:
    value = filters[field]
    if type(value) is int and 0 < value <= BIG_AUTO_FIELD_MAX:
        return cast(int, value)
    if (
        type(value) is str
        and len(value) <= BIG_AUTO_FIELD_MAX_DIGITS
        and value.isascii()
        and value.isdecimal()
    ):
        try:
            identifier = int(value)
        except ValueError:
            pass
        else:
            if 0 < identifier <= BIG_AUTO_FIELD_MAX:
                return identifier
    raise ValidationError({field: 'Informe um identificador inteiro positivo válido.'})


def choice_filter(
    filters: ReportFilters,
    field: str,
    choices: Iterable[tuple[str, str]],
) -> str:
    value = filters[field]
    valid_values = {choice_value for choice_value, _label in choices}
    if type(value) is str and value in valid_values:
        return cast(str, value)
    raise ValidationError({field: 'Informe uma opção válida.'})
