from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from django.core.exceptions import FieldDoesNotExist
from django.utils import timezone
from django.utils.formats import date_format


@dataclass(frozen=True)
class DetailSummaryItem:
    """Dado lateral de um registro, já pronto para apresentação."""

    field_name: str
    label: str
    value: str
    icon: str
    is_status: bool = False


_DETAIL_IDENTIFIER_FIELDS = ('code', 'order_number', 'batch_number', 'document_number')
_DETAIL_PERSON_FIELDS = ('responsible', 'owner', 'assigned_to')
_DETAIL_DATE_FIELDS = (
    'due_date',
    'due_at',
    'scheduled_end',
    'valid_until',
    'expiry_date',
    'created_at',
    'updated_at',
)
_DETAIL_SUMMARY_FIELDS = (
    *_DETAIL_IDENTIFIER_FIELDS,
    *_DETAIL_PERSON_FIELDS,
    *_DETAIL_DATE_FIELDS,
)


def _format_detail_summary_value(value: Any) -> str:
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return date_format(value, 'd/m/Y H:i')
    if isinstance(value, date):
        return date_format(value, 'd/m/Y')
    return str(value)


def build_detail_summary(obj: Any, status: Any) -> tuple[DetailSummaryItem, ...]:
    """Extrai somente os dados operacionais autorizados para a lateral."""

    items = []
    for field_name in _DETAIL_SUMMARY_FIELDS:
        try:
            field = obj._meta.get_field(field_name)
        except FieldDoesNotExist:
            continue

        value = getattr(obj, field_name, None)
        if value in (None, ''):
            continue

        icon = (
            'feather-hash'
            if field_name in _DETAIL_IDENTIFIER_FIELDS
            else 'feather-user'
            if field_name in _DETAIL_PERSON_FIELDS
            else 'feather-calendar'
        )
        items.append(
            DetailSummaryItem(
                field_name=field_name,
                label=str(field.verbose_name),
                value=_format_detail_summary_value(value),
                icon=icon,
            )
        )

    if status not in (None, '', '-'):
        try:
            status_label = str(obj._meta.get_field('status').verbose_name)
        except FieldDoesNotExist:
            status_label = 'status'
        items.append(
            DetailSummaryItem(
                field_name='status',
                label=status_label,
                value=str(status),
                icon='feather-activity',
                is_status=True,
            )
        )

    return tuple(items)


@dataclass(frozen=True)
class ProgressMetric:
    label: str
    value: int | float
    icon: str
    tone: str
    badge: str
    url: str
    target: int | float | None = None
    helper: str = ''
    required_permission: str = ''

    @property
    def has_progress(self) -> bool:
        return self.target is not None and self.target > 0

    @property
    def percent(self) -> int:
        if not self.has_progress:
            return 0
        return max(0, min(100, round(float(self.value) / float(self.target) * 100)))

    def can_view(self, user: Any) -> bool:
        return not self.required_permission or user.has_perm(self.required_permission)


@dataclass(frozen=True)
class DeadlineItem:
    """Representa um prazo operacional que pode ser exibido no workspace."""

    title: str
    description: str
    due_at: date | datetime
    tone: str
    icon: str
    url: str

    @property
    def temporal_label(self) -> str:
        due_date = self.due_at.date() if isinstance(self.due_at, datetime) else self.due_at
        today = timezone.localdate()
        if due_date < today:
            return 'Vencido'
        if due_date == today:
            return 'Vence hoje'
        return f'Vence em {date_format(due_date, "d/m/Y")}'
