from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from django import forms
from django.db.models import Model, QuerySet
from django.http import HttpRequest
from django.urls import reverse


class FieldKind(StrEnum):
    TEXT = 'text'
    TEXTAREA = 'textarea'
    INTEGER = 'integer'
    DECIMAL = 'decimal'
    BOOLEAN = 'boolean'
    DATE = 'date'
    DATETIME = 'datetime'
    CHOICE = 'choice'
    RELATION = 'relation'
    FILE = 'file'
    HIDDEN = 'hidden'
    JSON = 'json'


class SubmissionFormat(StrEnum):
    JSON = 'json'
    MULTIPART = 'multipart'


class SuccessBehavior(StrEnum):
    RELOAD = 'reload'
    REDIRECT = 'redirect'
    DOWNLOAD = 'download'


@dataclass(frozen=True, slots=True)
class ActionField:
    name: str
    label: str
    kind: FieldKind = FieldKind.TEXT
    required: bool = False
    help_text: str = ''
    placeholder: str = ''
    min_value: Decimal | int | None = None
    max_value: Decimal | int | None = None
    max_length: int | None = None
    choices: tuple[tuple[str, str], ...] = ()
    queryset_factory: Callable[[HttpRequest], QuerySet] | None = None
    initial_factory: Callable[[HttpRequest, Model | None], Any] | None = None
    widget_factory: Callable[[], forms.Widget] | None = None


@dataclass(frozen=True, slots=True)
class ActionConfirmation:
    title: str
    message: str
    typed_phrase: str = ''
    acknowledge_label: str = ''


@dataclass(frozen=True, slots=True)
class ActionConfig:
    module_slug: str
    resource_slug: str
    app_label: str
    model: type[Model]
    action_name: str
    route_name: str
    detail: bool
    label: str
    description: str
    success_message: str
    permissions: tuple[str, ...]
    icon: str = 'feather-play'
    tone: str = 'primary'
    fields: tuple[ActionField, ...] = ()
    allowed_states: tuple[str, ...] = ()
    state_field: str = 'status'
    confirmation: ActionConfirmation | None = None
    submission_format: SubmissionFormat = SubmissionFormat.JSON
    success_behavior: SuccessBehavior = SuccessBehavior.RELOAD
    redirect_route: str = ''

    @property
    def key(self) -> tuple[str, str, str]:
        return self.module_slug, self.resource_slug, self.action_name

    def api_url(self, pk=None) -> str:
        if self.detail:
            return reverse(self.route_name, kwargs={'pk': pk})
        return reverse(self.route_name)

    def is_available(self, user, obj: Model | None = None) -> bool:
        if not user.has_perms(self.permissions):
            return False
        if not self.allowed_states:
            return True
        if obj is None:
            return False
        state = str(getattr(obj, self.state_field, ''))
        return state in {str(allowed_state) for allowed_state in self.allowed_states}
