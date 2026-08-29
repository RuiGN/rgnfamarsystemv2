from base.sequences import AutoCodeMixin


def automatic_generated_fields(model: type) -> tuple[str, ...]:
    fields = []
    if issubclass(model, AutoCodeMixin) and model.CODE_PREFIX:
        fields.append('code')
    fields.extend(spec.field_name for spec in getattr(model, 'AUTOMATIC_IDENTIFIERS', ()))
    return tuple(dict.fromkeys(fields))
