from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / 'docker-compose.test.yml'
SCRIPT_PATH = ROOT / 'scripts' / 'test.sh'
PYTEST_INI_PATH = ROOT / 'pytest.ini'


def test_test_compose_isolates_postgresql_on_loopback():
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding='utf-8'))
    service = compose['services']['postgres_test']

    assert compose['name'] == 'rgnfarmasystem-test'
    assert service['image'] == 'postgres:15-alpine'
    assert service['ports'] == ['127.0.0.1:${TEST_POSTGRES_PORT:-5433}:5432']
    assert service['environment'] == {
        'POSTGRES_DB': 'rgn_test',
        'POSTGRES_USER': 'rgn_test',
        'POSTGRES_PASSWORD': 'rgn_test',
    }
    assert service['volumes'] == ['postgres_test_data:/var/lib/postgresql/data']
    assert service['healthcheck']['test'] == [
        'CMD-SHELL',
        'pg_isready -U rgn_test -d rgn_test',
    ]
    assert 'postgres_test_data' in compose['volumes']


def test_test_script_starts_waits_and_runs_pytest_safely():
    source = SCRIPT_PATH.read_text(encoding='utf-8')

    assert 'set -Eeuo pipefail' in source
    assert 'COMPOSE_FILE="$ROOT_DIR/docker-compose.test.yml"' in source
    assert 'docker compose -f "$COMPOSE_FILE" up -d --wait postgres_test' in source
    assert 'postgresql://rgn_test:rgn_test@127.0.0.1:${TEST_POSTGRES_PORT}/rgn_test' in source
    assert 'export TEST_DATABASE_URL="$TEST_DATABASE_URL"' in source
    assert 'export DATABASE_URL="$TEST_DATABASE_URL"' in source
    assert 'export CSRF_TRUSTED_ORIGINS="http://localhost"' in source
    assert 'export COMPOSE_PROJECT_NAME="rgnfarmasystem-test"' in source
    assert 'exec "$PYTHON" -m pytest "$@"' in source
    assert 'source .env' not in source
    assert SCRIPT_PATH.stat().st_mode & 0o111


def test_pytest_uses_isolated_postgresql_settings_profile():
    source = PYTEST_INI_PATH.read_text(encoding='utf-8')

    assert 'DJANGO_SETTINGS_MODULE = core.settings.test' in source
    assert 'core.test_settings' not in source
    assert '--reuse-db' not in source


def test_quality_gate_recreates_the_test_database_after_an_interrupted_run():
    source = (ROOT / 'scripts' / 'ci' / 'quality-gate.sh').read_text(encoding='utf-8')

    assert 'python -m pytest --create-db ' in source


def test_readme_documents_isolated_test_workflow():
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')

    assert '## Testes automatizados' in readme
    assert 'bash scripts/test.sh' in readme
    assert 'bash scripts/test.sh tests/test_foundation.py -q' in readme
    assert 'docker compose -f docker-compose.test.yml down -v' in readme
    assert 'TEST_POSTGRES_PORT=55433 bash scripts/test.sh' in readme


def test_local_runserver_documents_http_security_overrides():
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    deployment = (ROOT / 'docs/deployment.md').read_text(encoding='utf-8')
    env_example = (ROOT / '.env.example').read_text(encoding='utf-8')

    for source in (readme, deployment, env_example):
        assert 'SECURE_SSL_REDIRECT=False' in source
        assert 'SESSION_COOKIE_SECURE=False' in source
        assert 'CSRF_COOKIE_SECURE=False' in source
