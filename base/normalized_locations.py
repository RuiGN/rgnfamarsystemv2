from django.core.exceptions import ValidationError


def normalized_state_code(state):
    if not state:
        return ''
    return str(state.name or '').strip()


def normalized_city_name(city):
    if not city:
        return ''
    return str(city.name or '').strip()


def validate_normalized_location(
    instance,
    *,
    city_ref_field='city_ref',
    state_ref_field='state_ref',
    require=False,
):
    city = getattr(instance, city_ref_field, None)
    state = getattr(instance, state_ref_field, None)
    errors = {}

    if require and not state:
        errors[state_ref_field] = 'Informe a UF.'
    if require and not city:
        errors[city_ref_field] = 'Informe a cidade.'

    if city and state and city.state_id and city.state_id != state.pk:
        errors[city_ref_field] = 'A cidade deve pertencer à UF informada.'

    if errors:
        raise ValidationError(errors)


def sync_normalized_location(
    instance,
    *,
    city_text_field='city',
    state_text_field='state',
    city_ref_field='city_ref',
    state_ref_field='state_ref',
    require=False,
):
    city = getattr(instance, city_ref_field, None)
    state = getattr(instance, state_ref_field, None)
    errors = {}

    if require and not state:
        errors[state_ref_field] = 'Informe a UF normalizada.'
    if require and not city:
        errors[city_ref_field] = 'Informe o município normalizado.'

    if city and state and city.state_id and city.state_id != state.pk:
        errors[city_ref_field] = 'O município normalizado deve pertencer à UF normalizada.'

    if errors:
        raise ValidationError(errors)

    city_name = normalized_city_name(city)
    state_code = normalized_state_code(state)
    if city_name and city_text_field:
        setattr(instance, city_text_field, city_name)
    if state_code and state_text_field:
        setattr(instance, state_text_field, state_code)
