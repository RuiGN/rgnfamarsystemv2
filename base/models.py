from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField('criado em', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        abstract = True


class SingleInstanceModel(TimeStampedModel):
    """Base for operational records in the single-instance runtime."""

    def _validate_related_record(self, *_args):
        return None

    def _validate_related_user(self, *_args):
        return None

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            generated_fields = {
                spec.field_name
                for spec in getattr(type(self), 'AUTOMATIC_IDENTIFIERS', ())
                if getattr(self, spec.field_name, None)
            }
            kwargs['update_fields'] = set(update_fields) | generated_fields
        return super().save(*args, **kwargs)

    class Meta:
        abstract = True


class IdentifierSequence(TimeStampedModel):
    """Último número alocado para um namespace de identificador automático."""

    namespace = models.CharField('namespace', max_length=180, primary_key=True)
    value = models.PositiveBigIntegerField('último valor', default=0)

    class Meta:
        ordering = ['namespace']
        verbose_name = 'sequência de identificador'
        verbose_name_plural = 'sequências de identificadores'

    def __str__(self):
        return f'{self.namespace}: {self.value}'
