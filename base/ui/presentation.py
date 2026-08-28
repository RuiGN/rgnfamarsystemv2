from dataclasses import dataclass
from typing import Any


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
