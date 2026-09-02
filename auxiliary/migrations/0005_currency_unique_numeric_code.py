from django.db import migrations, models


def _check_numeric_code_uniqueness(apps, schema_editor):
    Currency = apps.get_model('auxiliary', 'Currency')
    from django.db.models import Count, Q

    duplicates = (
        Currency.objects.filter(~Q(numeric_code=''))
        .values('numeric_code')
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=1)
    )
    if duplicates.exists():
        codes = ', '.join(sorted(d['numeric_code'] for d in duplicates))
        raise RuntimeError(
            f'Conflicting duplicate numeric_code found in auxiliary_currency: {codes}'
        )


class Migration(migrations.Migration):
    dependencies = [
        ('auxiliary', '0004_currency_minor_unit_applicable'),
    ]

    operations = [
        migrations.RunPython(
            _check_numeric_code_uniqueness, reverse_code=migrations.RunPython.noop
        ),
        migrations.AddConstraint(
            model_name='currency',
            constraint=models.UniqueConstraint(
                condition=models.Q(('numeric_code', ''), _negated=True),
                fields=('numeric_code',),
                name='unique_currency_numeric_code',
            ),
        ),
    ]
