from django.db import migrations


def remove_backup_run_metadata(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    ContentType.objects.using(schema_editor.connection.alias).filter(
        app_label='auxiliary',
        model='backuprun',
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('auxiliary', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.DeleteModel(name='BackupRun'),
        migrations.RunPython(
            remove_backup_run_metadata,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
