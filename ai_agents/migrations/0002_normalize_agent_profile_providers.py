from django.db import migrations, models


def normalize_unsupported_provider_profiles(apps, schema_editor):
    AgentProfile = apps.get_model('ai_agents', 'AIAgentProfile')
    AgentProfile.objects.using(schema_editor.connection.alias).exclude(
        provider__in=('openai', 'local')
    ).update(
        provider='local',
        model_name='local',
    )


class Migration(migrations.Migration):
    dependencies = [
        ('ai_agents', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            normalize_unsupported_provider_profiles,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='aiagentprofile',
            name='provider',
            field=models.CharField(
                choices=[('openai', 'OpenAI'), ('local', 'Local determinístico')],
                default='openai',
                max_length=32,
                verbose_name='provedor',
            ),
        ),
    ]
