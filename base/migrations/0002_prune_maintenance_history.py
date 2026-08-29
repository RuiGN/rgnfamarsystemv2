from django.db import migrations
from django.db.migrations.recorder import MigrationRecorder


def prune_maintenance_history(apps, schema_editor):
    connection = schema_editor.connection
    remaining = sorted(
        table
        for table in connection.introspection.table_names()
        if table.startswith('maintenance_')
    )
    if remaining:
        raise RuntimeError(
            'Fase A obrigatória não aplicada; tabelas maintenance restantes: '
            + ', '.join(remaining)
        )

    alias = connection.alias
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    content_types = ContentType.objects.using(alias).filter(app_label='maintenance')
    Permission.objects.using(alias).filter(content_type__in=content_types).delete()
    content_types.delete()
    MigrationRecorder.Migration.objects.using(alias).filter(app='maintenance').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [migrations.RunPython(prune_maintenance_history)]
