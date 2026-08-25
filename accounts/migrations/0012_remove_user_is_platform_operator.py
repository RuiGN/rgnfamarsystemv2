from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0011_update_platform_operator_help'),
        ('control_plane', '0005_preserve_evidence_and_delete_runtime_models'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='is_platform_operator',
        ),
    ]
