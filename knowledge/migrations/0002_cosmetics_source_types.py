from django.db import migrations, models


def migrate_source_type(apps, schema_editor):
    source = apps.get_model('knowledge', 'KnowledgeSource')
    source.objects.filter(source_type='pharmacopoeia').update(source_type='technical_reference')


def restore_source_type(apps, schema_editor):
    source = apps.get_model('knowledge', 'KnowledgeSource')
    source.objects.filter(source_type='technical_reference').update(source_type='pharmacopoeia')


class Migration(migrations.Migration):
    dependencies = [('knowledge', '0001_initial')]

    operations = [
        migrations.RunPython(migrate_source_type, restore_source_type),
        migrations.AlterField(
            model_name='knowledgesource',
            name='source_type',
            field=models.CharField(
                choices=[
                    ('regulation', 'Legislação'),
                    ('technical_reference', 'Referência técnica'),
                    ('guideline', 'Guia'),
                    ('standard', 'Norma'),
                    ('book_reference', 'Referência bibliográfica'),
                    ('web', 'Página web'),
                    ('system_manual', 'Manual do sistema'),
                    ('other', 'Outra'),
                ],
                max_length=32,
                verbose_name='tipo',
            ),
        ),
    ]
