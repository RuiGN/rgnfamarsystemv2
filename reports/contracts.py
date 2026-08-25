from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol, TypeAlias

from django.contrib.auth.base_user import AbstractBaseUser


ColumnKind = Literal['text', 'date', 'datetime', 'decimal', 'integer', 'status']
ReportFilterValue: TypeAlias = str | int | float | bool | date
ReportFilters: TypeAlias = dict[str, ReportFilterValue]
ReportCellValue: TypeAlias = str | int | float | bool | Decimal | date | datetime | None
ReportRow: TypeAlias = Mapping[str, ReportCellValue]
ReportRows: TypeAlias = Iterable[ReportRow]


@dataclass(frozen=True, slots=True)
class ReportColumn:
    key: str
    label: str
    kind: ColumnKind = 'text'


@dataclass(frozen=True, slots=True)
class ReportDataset:
    title: str
    columns: tuple[ReportColumn, ...]
    rows: ReportRows


@dataclass(frozen=True, slots=True)
class ReportContext:
    filters: ReportFilters
    user: AbstractBaseUser


class ReportExecutor(Protocol):
    def __call__(self, context: ReportContext) -> ReportDataset: ...
