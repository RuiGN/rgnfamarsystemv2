from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0010_username_login'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='is_platform_operator',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    'Permite acesso à administração interna quando os demais controles '
                    'de segurança forem atendidos.'
                ),
                verbose_name='operador da plataforma',
            ),
        ),
    ]
