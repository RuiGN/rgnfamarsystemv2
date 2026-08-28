from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from django.utils import timezone
from django.utils.formats import date_format


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
