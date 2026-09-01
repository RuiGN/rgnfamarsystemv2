from django.db import migrations


def purge_existing_local_agent_records(apps, schema_editor):
    database_alias = schema_editor.connection.alias
    AgentProfile = apps.get_model('ai_agents', 'AIAgentProfile')
    AgentRun = apps.get_model('ai_agents', 'AIAgentRun')
    Suggestion = apps.get_model('ai_agents', 'AIInsightSuggestion')
    AuditLog = apps.get_model('ai_agents', 'AIPromptAuditLog')

    profile_ids = list(
        AgentProfile.objects.using(database_alias)
        .filter(provider='local')
        .values_list('pk', flat=True)
    )
    if not profile_ids:
        return

    run_ids = list(
        AgentRun.objects.using(database_alias)
        .filter(agent_id__in=profile_ids)
        .values_list('pk', flat=True)
    )
    AuditLog.objects.using(database_alias).filter(run_id__in=run_ids).delete()
    AuditLog.objects.using(database_alias).filter(agent_id__in=profile_ids).delete()
    Suggestion.objects.using(database_alias).filter(run_id__in=run_ids).delete()
    AgentRun.objects.using(database_alias).filter(pk__in=run_ids).delete()
    AgentProfile.objects.using(database_alias).filter(pk__in=profile_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ai_agents', '0002_normalize_agent_profile_providers'),
    ]

    operations = [
        migrations.RunPython(
            purge_existing_local_agent_records,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
