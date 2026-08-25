import accounts.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0012_remove_user_is_platform_operator'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar',
            field=models.ImageField(blank=True, upload_to=accounts.models.user_avatar_path, verbose_name='avatar'),
        ),
    ]
