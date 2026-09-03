from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from base.models import IdentifierSequence


SEQUENCE_ALLOCATION_ATTEMPTS = 3
IDENTIFIER_COLLISION_ATTEMPTS = 100


@dataclass(frozen=True, slots=True)
class IdentifierSpec:
    field_name: str
    prefix: str
    width: int = 4
    date_scoped: bool = True
    immutable: bool = True
    trigger: str = 'create'


def _highest_existing_suffix(model: type[models.Model], field_name: str, startswith: str) -> int:
    highest = 0
    values = model.objects.filter(**{f'{field_name}__startswith': startswith}).values_list(
        field_name, flat=True
    )
    for value in values.iterator():
        try:
            number = int(value[len(startswith) :])
        except TypeError, ValueError:
            continue
        highest = max(highest, number)
    return highest


def allocate_identifier_number(namespace: str, *, initial_value: Callable[[], int]) -> int:
    """Aloca atomicamente o próximo número de um namespace persistente."""

    for attempt in range(SEQUENCE_ALLOCATION_ATTEMPTS):
        try:
            with transaction.atomic():
                try:
                    sequence = IdentifierSequence.objects.select_for_update().get(
                        namespace=namespace
                    )
                except IdentifierSequence.DoesNotExist:
                    sequence = IdentifierSequence.objects.create(
                        namespace=namespace,
                        value=initial_value(),
                    )
                sequence.value += 1
                sequence.save(update_fields=['value', 'updated_at'])
                return sequence.value
        except IntegrityError:
            if attempt + 1 == SEQUENCE_ALLOCATION_ATTEMPTS:
                raise

    raise RuntimeError(f'Não foi possível alocar a sequência {namespace}.')


def generate_identifier(model: type[models.Model], spec: IdentifierSpec) -> str:
    """Gera um identificador usando contador persistente e formato declarativo."""

    if not spec.prefix.strip():
        raise ImproperlyConfigured(
            f'O prefixo de {model._meta.label}.{spec.field_name} é obrigatório.'
        )
    if spec.width < 1:
        raise ImproperlyConfigured(
            f'A largura de {model._meta.label}.{spec.field_name} deve ser positiva.'
        )

    period = f'{timezone.localdate():%Y%m%d}' if spec.date_scoped else 'global'
    startswith = f'{spec.prefix}-{period}-' if spec.date_scoped else f'{spec.prefix}-'
    namespace = f'{model._meta.label_lower}:{spec.field_name}:{period}'
    field = model._meta.get_field(spec.field_name)
    max_length = getattr(field, 'max_length', None)
    for _attempt in range(IDENTIFIER_COLLISION_ATTEMPTS):
        number = allocate_identifier_number(
            namespace,
            initial_value=lambda: _highest_existing_suffix(model, spec.field_name, startswith),
        )
        candidate = f'{startswith}{number:0{spec.width}d}'
        if max_length is not None and len(candidate) > max_length:
            raise ImproperlyConfigured(
                f'{model._meta.label}.{spec.field_name} não comporta {candidate!r}; '
                f'max_length={max_length}.'
            )
        if not model.objects.filter(**{spec.field_name: candidate}).exists():
            return candidate

    raise IntegrityError(
        f'Não foi possível gerar um identificador disponível para '
        f'{model._meta.label}.{spec.field_name}.'
    )


def sequence_code(model: type[models.Model], field_name: str, prefix: str) -> str:
    declared_spec = next(
        (
            spec
            for spec in getattr(model, 'AUTOMATIC_IDENTIFIERS', ())
            if spec.field_name == field_name
        ),
        None,
    )
    if declared_spec is not None:
        if declared_spec.prefix != prefix:
            raise ImproperlyConfigured(
                f'O prefixo declarado para {model._meta.label}.{field_name} é '
                f'{declared_spec.prefix!r}, não {prefix!r}.'
            )
        return generate_identifier(model, declared_spec)
    return generate_identifier(
        model,
        IdentifierSpec(field_name=field_name, prefix=prefix, date_scoped=True),
    )


def generate_code(
    model: type[models.Model],
    prefix: str,
    *,
    width: int = 4,
    field_name: str = 'code',
) -> str:
    """Gera um código único no formato ``PREFIX-NNNN``."""

    return generate_identifier(
        model,
        IdentifierSpec(
            field_name=field_name,
            prefix=prefix,
            width=width,
            date_scoped=False,
        ),
    )


class AutoCodeMixin:
    """Mixin que gera ``code`` automaticamente no ``save()`` quando vazio.

    O modelo deve definir ``CODE_PREFIX`` (str). Se ``code`` já vier preenchido,
    é preservado.
    """

    CODE_PREFIX: ClassVar[str | None] = None
    code: str

    def save(self, *args, **kwargs):
        generated = False
        if not self.code and self.CODE_PREFIX:
            self.code = generate_code(type(self), self.CODE_PREFIX)
            generated = True
        if generated and kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'code'}
        parent_save = getattr(super(), 'save')
        return parent_save(*args, **kwargs)
