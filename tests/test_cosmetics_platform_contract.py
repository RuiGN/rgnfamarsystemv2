from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_runtime_contract_uses_python_314_and_django_6():
    assert read('Dockerfile').startswith('FROM python:3.14-slim')
    assert 'target-version = "py314"' in read('pyproject.toml')
    assert 'python_version = "3.14"' in read('pyproject.toml')
    assert 'Django==6.0.8' in read('requirements.txt')

    for workflow in ('.github/workflows/quality.yml', '.github/workflows/release.yml'):
        assert '3.14' in read(workflow)
        assert '3.13' not in read(workflow)


def test_default_runtime_and_test_profile_require_postgresql():
    assert "'core.settings'" in read('manage.py')
    assert 'core.settings.sqlite' not in read('manage.py')

    test_settings = read('core/settings/test.py')
    assert "default='sqlite:" not in test_settings
    assert 'sqlite://' not in test_settings
    assert "('postgresql://', 'postgres://')" in test_settings
    assert not (ROOT / 'core/settings/sqlite.py').exists()


def test_every_supported_compose_profile_contains_postgresql():
    for path in (
        'docker-compose.local.yml',
        'docker-compose.test.yml',
        'docker-compose.vps.yml',
    ):
        services = yaml.safe_load(read(path))['services']
        postgres_services = [
            service
            for service in services.values()
            if service.get('image', '').startswith('postgres:')
        ]
        assert len(postgres_services) == 1, f'{path} must provide one PostgreSQL service'


def test_vps_application_connects_to_the_private_postgresql_container():
    compose = yaml.safe_load(read('docker-compose.vps.yml'))
    app_environment = compose['services']['app']['environment']

    assert app_environment['DATABASE_URL'].endswith('@db:5432/${POSTGRES_DB}')
    assert app_environment['DB_DEPLOYMENT'] == 'container'
    assert app_environment['DB_HOST'] == 'db'

    environment_template = read('.env.example')
    assert 'DB_DEPLOYMENT=container' in environment_template
    assert 'DB_HOST=db' in environment_template
    assert '@db:5432/rgnfarmasystem' in environment_template


def test_primary_product_docs_describe_the_cosmetics_single_instance_contract():
    for path in ('README.md', 'PRD.md', 'AGENTS.md'):
        source = read(path).casefold()
        assert 'cosmétic' in source
        assert 'single-instance' in source or 'instância única' in source
        assert 'erp farmacêutico' not in source

    readme = read('README.md')
    assert 'Python 3.14' in readme
    assert 'Django 6' in readme
    assert 'PostgreSQL' in readme
    assert 'Docker' in readme


def test_repository_has_no_legacy_customer_scope_references():
    forbidden_marker = 'ten' + 'ant'
    result = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    violations = []

    for relative_name in result.stdout.splitlines():
        path = ROOT / relative_name
        if not path.is_file():
            continue
        if forbidden_marker in relative_name.casefold():
            violations.append(relative_name)
        try:
            source = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if forbidden_marker in source.casefold():
            violations.append(relative_name)

    assert sorted(set(violations)) == []


def test_quality_gate_only_targets_existing_runtime_packages():
    source = read('scripts/ci/quality-gate.sh')
    for removed_package in ('control_plane', 'pharmacovigilance', 'regulatory'):
        assert f'  {removed_package}\n' not in source


def test_ai_runtime_contract_uses_only_active_integrations():
    services = read('ai_agents/services.py')
    assert 'langchain_openai' in services

    requirements = read('requirements.txt').casefold().splitlines()
    ai_client_requirements = {
        requirement
        for requirement in requirements
        if any(marker in requirement for marker in ('openai', 'genai'))
    }

    assert ai_client_requirements == {'langchain-openai==1.6.0', 'openai==3.3.1'}


def test_ai_configuration_and_demo_use_only_active_contracts():
    settings_source = read('core/settings/base.py')
    demo_source = read('governance/demo_seeders.py')

    assert "OPENAI_API_KEY = env('OPENAI_API_KEY'" in settings_source
    assert "OPENAI_MODEL = env('OPENAI_MODEL'" in settings_source
    assert 'def _seed_ai_agents(self):' in demo_source
    assert "'ai_agents.profiles'" not in demo_source
    assert "'ai_agents.runs'" not in demo_source
    assert "'ai_agents.suggestions'" not in demo_source


def test_legacy_inventory_does_not_claim_active_knowledge_module_was_removed():
    source = read('LEGACY_MODULES.md')
    assert '`knowledge` foram completamente removidos' not in source
    assert 'módulo `knowledge` permanece ativo' in source


def test_nginx_never_serves_protected_media_as_static_content():
    source = read('deploy/nginx/rgnfarmasystem.conf')
    protected_location = source.index('location ^~ /media/protected/')
    public_media_location = source.index('location /media/')

    assert 'return 404;' in source[protected_location:public_media_location]
    assert protected_location < public_media_location
