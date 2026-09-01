import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.fixture
def restore_latest_migrations():
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def _create_profile(AgentProfile, *, code, provider):
    return AgentProfile.objects.create(
        code=code,
        name=f'Agente {provider}',
        agent_type='summary',
        source_module='documents',
        provider=provider,
        model_name='local' if provider == 'local' else 'gpt-5.5-mini',
        system_prompt='Resuma o documento.',
        allowed_source_modules=['documents'],
    )


def _create_run(AgentRun, profile, run_number):
    return AgentRun.objects.create(
        run_number=run_number,
        agent=profile,
        source_module='documents',
        source_model='ControlledDocument',
        source_record_id=run_number,
        status='succeeded',
        prompt_text='Resuma o documento.',
        model_name=profile.model_name,
        input_payload={'document_id': run_number},
        output_payload={'summary': 'Resumo sintético.'},
        output_text='Resumo sintético.',
    )


def _create_dependents(Suggestion, AuditLog, profile, run):
    suggestion = Suggestion.objects.create(
        run=run,
        suggestion_type='summary',
        title=f'Sugestão {run.run_number}',
        description='Descrição sintética.',
        confidence='0.80',
        source_module='documents',
        source_model='ControlledDocument',
        source_record_id=run.source_record_id,
    )
    audit_log = AuditLog.objects.create(
        run=run,
        agent=profile,
        prompt_text=run.prompt_text,
        model_name=run.model_name,
        input_payload=run.input_payload,
        output_payload=run.output_payload,
        output_text=run.output_text,
        status=run.status,
    )
    return suggestion, audit_log


@pytest.mark.django_db(transaction=True)
def test_unsupported_provider_profiles_are_normalized_to_local(restore_latest_migrations):
    old_target = ('ai_agents', '0001_initial')
    new_target = ('ai_agents', '0002_normalize_agent_profile_providers')
    executor = MigrationExecutor(connection)
    executor.migrate([old_target])
    old_apps = executor.loader.project_state([old_target]).apps
    AgentProfile = old_apps.get_model('ai_agents', 'AIAgentProfile')
    profile = AgentProfile.objects.create(
        code='AGT-LEGACY-PROVIDER',
        name='Agente com provedor legado',
        agent_type='summary',
        source_module='documents',
        provider='retired-provider',
        model_name='retired-model',
        system_prompt='Resuma o documento.',
        allowed_source_modules=['documents'],
    )
    openai_profile = AgentProfile.objects.create(
        code='AGT-OPENAI-PROVIDER',
        name='Agente OpenAI',
        agent_type='summary',
        source_module='documents',
        provider='openai',
        model_name='configured-openai-model',
        system_prompt='Resuma o documento.',
        allowed_source_modules=['documents'],
    )
    local_profile = AgentProfile.objects.create(
        code='AGT-LOCAL-PROVIDER',
        name='Agente local',
        agent_type='summary',
        source_module='documents',
        provider='local',
        model_name='local',
        system_prompt='Resuma o documento.',
        allowed_source_modules=['documents'],
    )

    executor = MigrationExecutor(connection)
    executor.migrate([new_target])
    migrated_apps = executor.loader.project_state([new_target]).apps
    MigratedAgentProfile = migrated_apps.get_model('ai_agents', 'AIAgentProfile')

    migrated = MigratedAgentProfile.objects.get(pk=profile.pk)
    preserved_openai = MigratedAgentProfile.objects.get(pk=openai_profile.pk)
    preserved_local = MigratedAgentProfile.objects.get(pk=local_profile.pk)

    assert migrated.provider == 'local'
    assert migrated.model_name == 'local'
    assert (preserved_openai.provider, preserved_openai.model_name) == (
        'openai',
        'configured-openai-model',
    )
    assert (preserved_local.provider, preserved_local.model_name) == ('local', 'local')


@pytest.mark.django_db(transaction=True)
def test_existing_local_agent_records_are_purged_without_touching_openai(
    restore_latest_migrations,
):
    old_target = ('ai_agents', '0002_normalize_agent_profile_providers')
    new_target = ('ai_agents', '0003_purge_existing_local_agent_records')
    executor = MigrationExecutor(connection)
    executor.migrate([old_target])
    old_apps = executor.loader.project_state([old_target]).apps

    AgentProfile = old_apps.get_model('ai_agents', 'AIAgentProfile')
    AgentRun = old_apps.get_model('ai_agents', 'AIAgentRun')
    Suggestion = old_apps.get_model('ai_agents', 'AIInsightSuggestion')
    AuditLog = old_apps.get_model('ai_agents', 'AIPromptAuditLog')

    local_profile = _create_profile(
        AgentProfile,
        code='AGT-LOCAL-PURGE',
        provider='local',
    )
    openai_profile = _create_profile(
        AgentProfile,
        code='AGT-OPENAI-KEEP',
        provider='openai',
    )
    local_run = _create_run(AgentRun, local_profile, 'AIRUN-LOCAL-PURGE')
    openai_run = _create_run(AgentRun, openai_profile, 'AIRUN-OPENAI-KEEP')
    local_suggestion, local_audit = _create_dependents(
        Suggestion,
        AuditLog,
        local_profile,
        local_run,
    )
    openai_suggestion, openai_audit = _create_dependents(
        Suggestion,
        AuditLog,
        openai_profile,
        openai_run,
    )

    executor = MigrationExecutor(connection)
    executor.migrate([new_target])
    migrated_apps = executor.loader.project_state([new_target]).apps
    MigratedAgentProfile = migrated_apps.get_model('ai_agents', 'AIAgentProfile')
    MigratedAgentRun = migrated_apps.get_model('ai_agents', 'AIAgentRun')
    MigratedSuggestion = migrated_apps.get_model('ai_agents', 'AIInsightSuggestion')
    MigratedAuditLog = migrated_apps.get_model('ai_agents', 'AIPromptAuditLog')

    assert not MigratedAgentProfile.objects.filter(pk=local_profile.pk).exists()
    assert not MigratedAgentRun.objects.filter(pk=local_run.pk).exists()
    assert not MigratedSuggestion.objects.filter(pk=local_suggestion.pk).exists()
    assert not MigratedAuditLog.objects.filter(pk=local_audit.pk).exists()
    assert MigratedAgentProfile.objects.filter(pk=openai_profile.pk).exists()
    assert MigratedAgentRun.objects.filter(pk=openai_run.pk).exists()
    assert MigratedSuggestion.objects.filter(pk=openai_suggestion.pk).exists()
    assert MigratedAuditLog.objects.filter(pk=openai_audit.pk).exists()
