import logging
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import FieldError
from django.db.models import Q
from django.urls import reverse

from base.ui.registry import get_visible_modules


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GlobalSearchResult:
    title: str
    module_label: str
    resource_label: str
    url: str
    icon: str

    def as_dict(self) -> dict[str, str]:
        return {
            'title': self.title,
            'module': self.module_label,
            'type': self.resource_label,
            'url': self.url,
            'icon': self.icon,
        }


def search_visible_resources(
    request: Any,
    query: str,
    *,
    limit: int = 20,
    per_resource_limit: int = 5,
) -> tuple[GlobalSearchResult, ...]:
    normalized_query = str(query or '').strip()
    if len(normalized_query) < 3:
        return ()

    limit = max(1, min(int(limit), 50))
    per_resource_limit = max(1, min(int(per_resource_limit), 10, limit))
    results = []
    for module in get_visible_modules(request.user):
        for resource in module.resources:
            if not resource.search_fields:
                continue
            criteria = Q()
            for field_name in resource.search_fields:
                criteria |= Q(**{f'{field_name}__icontains': normalized_query})
            remaining = limit - len(results)
            if remaining <= 0:
                return tuple(results)
            try:
                objects = (
                    resource.get_queryset(request)
                    .filter(criteria)
                    .distinct()[: min(per_resource_limit, remaining)]
                )
                results.extend(
                    GlobalSearchResult(
                        title=str(obj),
                        module_label=module.label,
                        resource_label=resource.label,
                        url=reverse(
                            'app:resource_detail',
                            args=(module.slug, resource.slug, obj.pk),
                        ),
                        icon=module.icon,
                    )
                    for obj in objects
                )
            except FieldError:
                logger.exception(
                    'Configuração de busca inválida para %s/%s.',
                    module.slug,
                    resource.slug,
                )
    return tuple(results)
