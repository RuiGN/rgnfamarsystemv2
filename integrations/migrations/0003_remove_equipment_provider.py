import logging

from django.db import migrations, models

logger = logging.getLogger(__name__)


def clean_legacy_values(apps, schema_editor):
    alias = schema_editor.connection.alias
    Connector = apps.get_model('integrations', 'IntegrationConnector')
    removed, _ = Connector.objects.using(alias).filter(provider_type='equipment').delete()
    logger.info('Removed %s legacy equipment integration connectors.', removed)


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0002_labelprintersettings'),
    ]

    operations = [
        migrations.RunPython(clean_legacy_values),
        migrations.AlterField(
            model_name='integrationconnector',
            name='provider_type',
            field=models.CharField(
                choices=[
                    ('erp', 'ERP externo'),
                    ('fiscal_system', 'Sistema fiscal'),
                    ('laboratory', 'Laboratorio'),
                    ('email_provider', 'Provedor de email'),
                    ('openai', 'OpenAI'),
                    ('bi', 'BI'),
                ],
                max_length=32,
                verbose_name='tipo de provedor',
            ),
        ),
    ]
