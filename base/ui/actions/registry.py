from collections.abc import Iterable

from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.urls import NoReverseMatch

from base.ui.actions.factory import action_config
from base.ui.actions.modules import ACTION_KEYS, PRODUCTION_ACTIONS
from base.ui.actions.types import ActionConfig
from base.ui.registry import get_resource


class ActionRegistry:
    def __init__(self, configs: Iterable[ActionConfig]):
        self._by_key: dict[tuple[str, str, str], ActionConfig] = {}
        for config in configs:
            self._validate(config)
            if config.key in self._by_key:
                raise ImproperlyConfigured(f'Ação duplicada: {config.key!r}.')
            self._by_key[config.key] = config

    def all(self) -> tuple[ActionConfig, ...]:
        return tuple(self._by_key.values())

    def get(self, module_slug: str, resource_slug: str, action_name: str) -> ActionConfig:
        try:
            return self._by_key[(module_slug, resource_slug, action_name)]
        except KeyError as exc:
            raise Http404('Ação não encontrada.') from exc

    def for_resource(self, module_slug: str, resource_slug: str) -> tuple[ActionConfig, ...]:
        return tuple(
            config
            for config in self._by_key.values()
            if config.key[:2] == (module_slug, resource_slug)
        )

    def _validate(self, config: ActionConfig) -> None:
        resource = get_resource(config.module_slug, config.resource_slug)
        if resource is None:
            raise ImproperlyConfigured(f'Ação aponta para recurso inexistente: {config.key!r}.')
        if resource.model is not config.model or config.app_label != resource.app_label:
            raise ImproperlyConfigured(f'Ação aponta para model incompatível: {config.key!r}.')
        if not config.permissions:
            raise ImproperlyConfigured(f'Ação sem permissão declarada: {config.key!r}.')
        if not all((config.label, config.description, config.success_message)):
            raise ImproperlyConfigured(f'Ação possui texto obrigatório vazio: {config.key!r}.')
        if config.tone in {'danger', 'warning'} and config.confirmation is None:
            raise ImproperlyConfigured(f'Ação crítica sem confirmação: {config.key!r}.')

        field_names = tuple(field.name for field in config.fields)
        if len(field_names) != len(set(field_names)):
            raise ImproperlyConfigured(f'Ação possui campo duplicado: {config.key!r}.')

        try:
            config.api_url(pk=1 if config.detail else None)
        except NoReverseMatch as exc:
            raise ImproperlyConfigured(f'Ação possui rota inválida: {config.key!r}.') from exc

        if config.allowed_states:
            try:
                state_field = config.model._meta.get_field(config.state_field)
            except Exception as exc:
                raise ImproperlyConfigured(
                    f'Ação possui campo de estado inválido: {config.key!r}.'
                ) from exc
            valid_states = {str(value) for value, _label in state_field.flatchoices}
            unknown_states = {str(value) for value in config.allowed_states} - valid_states
            if unknown_states:
                raise ImproperlyConfigured(
                    f'Ação possui estado inválido: {config.key!r}: {sorted(unknown_states)!r}.'
                )


class LazyActionRegistry:
    _registry = None

    def _get_registry(self):
        if self._registry is None:
            production_by_key = {config.key: config for config in PRODUCTION_ACTIONS}
            configs = tuple(
                production_by_key.get((module_slug, resource_slug, action_name))
                or action_config(module_slug, resource_slug, action_name)
                for module_slug, resource_slug, action_name in ACTION_KEYS
            )
            self._registry = ActionRegistry(configs)
        return self._registry

    def all(self):
        return self._get_registry().all()

    def get(self, module_slug, resource_slug, action_name):
        return self._get_registry().get(module_slug, resource_slug, action_name)

    def for_resource(self, module_slug, resource_slug):
        return self._get_registry().for_resource(module_slug, resource_slug)


action_registry = LazyActionRegistry()
