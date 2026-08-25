import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_settings_import(module, environment, expression="settings.DATABASES['default']['ENGINE']"):
    env = os.environ.copy()
    env.update(environment)
    env['DJANGO_SETTINGS_MODULE'] = module
    return subprocess.run(
        [
            sys.executable,
            '-c',
            (
                'import django; django.setup(); '
                'from django.conf import settings; '
                f'print({expression})'
            ),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_test_profile_uses_postgresql():
    result = run_settings_import(
        'core.settings.test',
        {
            'TEST_DATABASE_URL': 'postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test',
        },
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'django.db.backends.postgresql'


def test_development_environment_template_uses_native_local_services():
    source = (PROJECT_ROOT / '.env.development.example').read_text(encoding='utf-8')

    assert 'DATABASE_URL=postgresql://rgnfarmasystem:' in source
    assert '@127.0.0.1:5432/rgnfarmasystem' in source
    assert 'TEST_DATABASE_URL=postgresql://rgn_test:' in source
    assert '@127.0.0.1:5432/rgn_test' in source
    assert 'REDIS_URL=redis://127.0.0.1:6379/' in source
    assert '@127.0.0.1:5672//' in source
    assert 'host.docker.internal' not in source
    assert 'TENANT_' not in source


def test_development_environment_template_configures_native_local_backup():
    source = (PROJECT_ROOT / '.env.development.example').read_text(encoding='utf-8')

    assert 'DB_DEPLOYMENT=external' in source
    assert 'DB_HOST=127.0.0.1' in source
    assert 'DB_PORT=5432' in source
    assert 'POSTGRES_DB=rgnfarmasystem' in source
    assert 'POSTGRES_USER=rgnfarmasystem' in source
    assert 'POSTGRES_PASSWORD=rgnfarmasystem' in source
    assert 'BACKUP_DIR=backups' in source
    assert 'MEDIA_DIR=media' in source
    assert 'MEDIA_DEPLOYMENT=external' in source
    assert 'backups/' in (PROJECT_ROOT / '.gitignore').read_text(encoding='utf-8')


def test_local_venv_remaps_docker_media_root_to_project_path():
    result = run_settings_import(
        'core.settings.base',
        {'MEDIA_ROOT': '/app/media-settings-test'},
        'settings.MEDIA_ROOT',
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(PROJECT_ROOT / 'media-settings-test')


def test_debug_profile_uses_var_media_when_media_root_is_not_writable(tmp_path):
    locked_media_root = tmp_path / 'locked-media'
    locked_media_root.mkdir()
    locked_media_root.chmod(0o555)

    try:
        result = run_settings_import(
            'core.settings.base',
            {'DEBUG': 'True', 'MEDIA_ROOT': str(locked_media_root)},
            'settings.MEDIA_ROOT',
        )
    finally:
        locked_media_root.chmod(0o755)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(PROJECT_ROOT / 'var' / 'media')


def test_local_backup_documentation_uses_safe_dotenv_runner():
    source = (PROJECT_ROOT / 'docs/architecture/backup-restore.md').read_text(encoding='utf-8')

    assert 'scripts/run_with_env.py --env-file .env -- bash scripts/backup.sh' in source
    assert 'source .env' not in source


def test_runtime_settings_do_not_expose_legacy_invitation_scope():
    runtime_sources = [
        (PROJECT_ROOT / 'core/settings/base.py').read_text(encoding='utf-8'),
        (PROJECT_ROOT / '.env.example').read_text(encoding='utf-8'),
    ]

    assert all('TENANT_INVITATION_TTL_HOURS' not in source for source in runtime_sources)


def test_test_profile_requires_test_database_url():
    result = run_settings_import('core.settings.test', {'TEST_DATABASE_URL': ''})

    assert result.returncode != 0
    assert 'TEST_DATABASE_URL' in result.stderr


def test_production_profile_requires_secret_key():
    result = run_settings_import(
        'core.settings.production',
        {
            'SECRET_KEY': '',
            'DATABASE_URL': 'postgresql://rgn:rgn@127.0.0.1:5432/rgn',
        },
    )

    assert result.returncode != 0
    assert 'SECRET_KEY' in result.stderr


def test_production_profile_passes_deploy_check_with_hsts_environment():
    env = os.environ.copy()
    env.update(
        {
            'DJANGO_SETTINGS_MODULE': 'core.settings.production',
            'SECRET_KEY': 'ci-only-non-production-secret-key-with-adequate-length',
            'DEBUG': 'False',
            'ALLOWED_HOSTS': 'localhost,127.0.0.1',
            'DATABASE_URL': 'postgresql://rgn:rgn@127.0.0.1:5432/rgn',
            'CONTROL_PLANE_BASE_URL': 'https://control.example.invalid',
            'CUSTOMER_APP_BASE_URL': 'https://app.example.invalid',
            'DATA_ENCRYPTION_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
            'SECURE_HSTS_SECONDS': '31536000',
            'SECURE_HSTS_INCLUDE_SUBDOMAINS': 'True',
            'SECURE_HSTS_PRELOAD': 'True',
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            'manage.py',
            'check',
            '--deploy',
            '--fail-level',
            'WARNING',
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
