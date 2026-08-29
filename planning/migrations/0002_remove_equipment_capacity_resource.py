import logging

from django.db import migrations, models

logger = logging.getLogger(__name__)


def clean_legacy_values(apps, schema_editor):
    alias = schema_editor.connection.alias
    Resource = apps.get_model('planning', 'CapacityResource')
    Load = apps.get_model('planning', 'CapacityLoad')
    resource_ids = Resource.objects.using(alias).filter(
        resource_type='equipment'
    ).values_list('pk', flat=True)
    removed_loads, _ = Load.objects.using(alias).filter(
        resource_id__in=resource_ids
    ).delete()
    removed_resources, _ = Resource.objects.using(alias).filter(
        resource_type='equipment'
    ).delete()
    logger.info(
        'Removed %s legacy equipment capacity loads and %s resources.',
        removed_loads,
        removed_resources,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(clean_legacy_values),
        migrations.AlterField(
            model_name='capacityresource',
            name='resource_type',
            field=models.CharField(
                choices=[
                    ('line', 'Linha'),
                    ('work_center', 'Centro de trabalho'),
                    ('shift', 'Turno'),
                ],
                max_length=24,
                verbose_name='tipo de recurso',
            ),
        ),
    ]
