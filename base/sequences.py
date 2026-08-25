from django.db import IntegrityError
from django.utils import timezone


def sequence_code(model, field_name, prefix):
    today = timezone.localdate()
    startswith = f'{prefix}-{today:%Y%m%d}-'
    existing_count = model.objects.filter(**{f'{field_name}__startswith': startswith}).count()
    return f'{startswith}{existing_count + 1:04d}'


def generate_code(model, prefix, *, width=4, field_name='code'):
    """Gera um código único no formato ``PREFIX-NNNN`` (sequencial por modelo).

    Localiza o maior número existente entre os códigos ``PREFIX-NNNN`` do modelo e
    incrementa, com retry em caso de colisão. A largura dos dígitos é ajustada para
    caber no ``max_length`` do campo.
    """
    startswith = f'{prefix}-'
    highest = 0
    for value in (
        model.objects.filter(**{f'{field_name}__startswith': startswith})
        .values_list(field_name, flat=True)
        .iterator()
    ):
        tail = value[len(startswith):]
        try:
            n = int(tail)
        except (ValueError, TypeError):
            continue
        if n > highest:
            highest = n
    seq = highest + 1
    max_length = model._meta.get_field(field_name).max_length or 40
    available = max_length - len(prefix) - 1
    if width > available:
        width = max(2, available)
    for _ in range(100):
        candidate = f'{prefix}-{seq:0{width}d}'
        if not model.objects.filter(**{field_name: candidate}).exists():
            return candidate
        seq += 1
    raise IntegrityError(f'Não foi possível gerar um código único para {model.__name__}.')


class AutoCodeMixin:
    """Mixin que gera ``code`` automaticamente no ``save()`` quando vazio.

    O modelo deve definir ``CODE_PREFIX`` (str). Se ``code`` já vier preenchido,
    é preservado.
    """

    CODE_PREFIX = None

    def save(self, *args, **kwargs):
        if not self.code and self.CODE_PREFIX:
            self.code = generate_code(type(self), self.CODE_PREFIX)
        return super().save(*args, **kwargs)
