from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_tenantmembership'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_platform_operator',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    'Permite acesso ao control plane SaaS quando os demais controles '
                    'de segurança forem atendidos.'
                ),
                verbose_name='operador da plataforma',
            ),
        ),
    ]
