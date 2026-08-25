from dataclasses import dataclass
from datetime import date

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date


SUPPORTED_FILTER_TYPES = frozenset({'date', 'choice', 'text', 'integer'})


class InvalidReportFilterSchema(ValueError):
    """Raised when a server-owned report filter schema is not deterministic."""


@dataclass(frozen=True)
class ReportFilterSpec:
    name: str
    field_type: str
    label: str
    required: bool
    choices: tuple[tuple[str | int, str], ...] = ()


def _compile_choices(config):
    configured = config.get('choices')
    if type(configured) is not list or not configured:
        raise InvalidReportFilterSchema
    choices = []
    serialized_values = set()
    for item in configured:
        if type(item) is not dict or set(item) != {'value', 'label'}:
            raise InvalidReportFilterSchema
        value = item['value']
        label = item['label']
        if type(value) not in {str, int} or type(label) is not str or not label.strip():
            raise InvalidReportFilterSchema
        serialized_value = str(value)
        if serialized_value in serialized_values:
            raise InvalidReportFilterSchema
        serialized_values.add(serialized_value)
        choices.append((value, label.strip()))
    return tuple(choices)


def compile_filter_schema(schema, required_filters, *, allowed_fields):
    if type(schema) is not dict or type(required_filters) is not list:
        raise InvalidReportFilterSchema
    if any(type(name) is not str for name in required_filters):
        raise InvalidReportFilterSchema
    if len(required_filters) != len(set(required_filters)):
        raise InvalidReportFilterSchema
    if not set(required_filters) <= set(schema) or not set(schema) <= set(allowed_fields):
        raise InvalidReportFilterSchema

    specifications = []
    for name, config in schema.items():
        if type(config) is not dict:
            raise InvalidReportFilterSchema
        field_type = config.get('type')
        label = config.get('label')
        if field_type not in SUPPORTED_FILTER_TYPES:
            raise InvalidReportFilterSchema
        if type(label) is not str or not label.strip():
            raise InvalidReportFilterSchema
        expected_keys = (
            {'type', 'label', 'choices'}
            if field_type == 'choice'
            else {
                'type',
                'label',
            }
        )
        if set(config) != expected_keys:
            raise InvalidReportFilterSchema
        choices = _compile_choices(config) if field_type == 'choice' else ()
        specifications.append(
            ReportFilterSpec(
                name=name,
                field_type=field_type,
                label=label.strip(),
                required=name in required_filters,
                choices=choices,
            )
        )
    return tuple(specifications)


def _is_missing(value):
    return value is None or value == ''


def _normalize_value(specification, value):
    if specification.field_type == 'date':
        if type(value) is not str or parse_date(value) is None:
            raise ValidationError({specification.name: 'Informe uma data válida.'})
        return value
    if specification.field_type == 'integer':
        if type(value) is not int:
            raise ValidationError({specification.name: 'Informe um número inteiro válido.'})
        return value
    if specification.field_type == 'text':
        if type(value) is not str:
            raise ValidationError({specification.name: 'Informe um texto válido.'})
        return value
    allowed_values = tuple(choice[0] for choice in specification.choices)
    if type(value) not in {str, int} or not any(
        type(value) is type(allowed) and value == allowed for allowed in allowed_values
    ):
        raise ValidationError({specification.name: 'Selecione uma opção válida.'})
    return value


def normalize_system_filters(
    *,
    schema,
    required_filters,
    default_filters,
    incoming_filters,
    allowed_fields,
    clone_json_object,
):
    try:
        specifications = compile_filter_schema(
            schema,
            required_filters,
            allowed_fields=allowed_fields,
        )
    except InvalidReportFilterSchema:
        raise ValidationError(
            {'filter_schema': 'O esquema de filtros do relatório é inválido.'}
        ) from None

    try:
        defaults = clone_json_object(default_filters)
        incoming = clone_json_object({} if incoming_filters is None else incoming_filters)
    except (TypeError, ValueError):
        raise ValidationError({'filters': 'Filtros devem ser um objeto JSON seguro.'}) from None

    known_names = {specification.name for specification in specifications}
    unsupported = sorted((set(defaults) | set(incoming)) - known_names)
    if unsupported:
        raise ValidationError(
            {'filters': f'Filtros não previstos no esquema: {", ".join(unsupported)}.'}
        )

    merged = {**defaults, **incoming}
    normalized = {}
    errors = {}
    for specification in specifications:
        if specification.name not in merged or _is_missing(merged[specification.name]):
            if specification.required:
                errors[specification.name] = 'Este filtro é obrigatório.'
            continue
        try:
            normalized[specification.name] = _normalize_value(
                specification,
                merged[specification.name],
            )
        except ValidationError as error:
            errors.update(error.message_dict)

    period_start = parse_date(normalized['period_start']) if 'period_start' in normalized else None
    period_end = parse_date(normalized['period_end']) if 'period_end' in normalized else None
    if period_start and period_end and period_end < period_start:
        errors['period_end'] = 'Data final não pode ser anterior à data inicial.'
    if errors:
        raise ValidationError(errors)
    return normalized


def form_value(value):
    return value.isoformat() if isinstance(value, date) else value
