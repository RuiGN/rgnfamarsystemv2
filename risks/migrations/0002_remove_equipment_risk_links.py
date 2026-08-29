import logging

from django.db import migrations, models

logger = logging.getLogger(__name__)


def clean_legacy_values(apps, schema_editor):
    alias = schema_editor.connection.alias
    Link = apps.get_model('risks', 'RiskLink')
    removed, _ = Link.objects.using(alias).filter(link_type='equipment').delete()
    logger.info('Removed %s legacy equipment risk links.', removed)


class Migration(migrations.Migration):

    dependencies = [
        ('risks', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(clean_legacy_values),
        migrations.AlterField(
            model_name='risklink',
            name='link_type',
            field=models.CharField(
                choices=[
                    ('process', 'Processo'),
                    ('product', 'Produto'),
                    ('document', 'Documento'),
                    ('deviation', 'Desvio'),
                    ('capa', 'CAPA'),
                    ('change', 'Mudança'),
                    ('audit', 'Auditoria'),
                    ('supplier', 'Fornecedor'),
                ],
                max_length=24,
                verbose_name='tipo de vínculo',
            ),
        ),
    ]
