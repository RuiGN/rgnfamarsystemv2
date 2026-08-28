from django import template
from django.http import QueryDict


register = template.Library()


def build_query_string(source, allowed_query_params, **updates):
    """Return only allowlisted parameters while preserving repeated values."""
    query = QueryDict(mutable=True)
    for key in allowed_query_params:
        query.setlist(key, source.getlist(key))
    for key, value in updates.items():
        if value in (None, ''):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()


@register.simple_tag(takes_context=True)
def query_transform(context, **updates):
    return build_query_string(
        context['request'].GET,
        context.get('allowed_query_params', ()),
        **updates,
    )
