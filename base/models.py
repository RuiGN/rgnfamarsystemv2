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

    class Meta:
        abstract = True
