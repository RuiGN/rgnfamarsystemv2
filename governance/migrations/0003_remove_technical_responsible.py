from django.db import migrations


def remove_technical_responsible_metadata(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    ContentType.objects.using(schema_editor.connection.alias).filter(
        app_label='governance',
        model='technicalresponsible',
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('governance', '0002_alter_governanceauditlog_module_and_more'),
    ]

    operations = [
        migrations.DeleteModel(name='TechnicalResponsible'),
        migrations.RunPython(
            remove_technical_responsible_metadata,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
