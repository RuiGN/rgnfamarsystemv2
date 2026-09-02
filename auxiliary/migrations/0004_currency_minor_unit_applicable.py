from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('auxiliary', '0003_official_location_codes'),
    ]

    operations = [
        migrations.AddField(
            model_name='currency',
            name='minor_unit_applicable',
            field=models.BooleanField(
                default=True,
                verbose_name='unidade monetária menor aplicável',
            ),
        ),
    ]
