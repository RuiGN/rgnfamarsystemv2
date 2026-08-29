import logging

from django.db import migrations, models

logger = logging.getLogger(__name__)


def clean_legacy_values(apps, schema_editor):
    alias = schema_editor.connection.alias
    Requisition = apps.get_model('procurement', 'PurchaseRequisition')
    updated = Requisition.objects.using(alias).filter(source='maintenance').update(
        source='manual'
    )
    logger.info('Converted %s legacy maintenance purchase requisitions to manual.', updated)


class Migration(migrations.Migration):

    dependencies = [
        ('procurement', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(clean_legacy_values),
        migrations.AlterField(
            model_name='purchaserequisition',
            name='source',
            field=models.CharField(
                choices=[
                    ('manual', 'Manual'),
                    ('mrp', 'MRP'),
                    ('stock_minimum', 'Estoque mínimo'),
                    ('laboratory', 'Laboratório'),
                    ('administrative', 'Administrativa'),
                ],
                default='manual',
                max_length=24,
                verbose_name='origem',
            ),
        ),
    ]
