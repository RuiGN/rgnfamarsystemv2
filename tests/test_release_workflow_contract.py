from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_release_workflow_has_tag_trigger_minimal_permissions_and_no_push():
    workflow = yaml.safe_load((ROOT / '.github/workflows/release.yml').read_text())

    assert 'push' in workflow[True]
    assert workflow[True]['push']['tags'] == ['v*.*.*']
    assert workflow['permissions']['contents'] == 'read'
    assert 'gates' in workflow['jobs']
    assert 'build' in workflow['jobs']
    build = workflow['jobs']['build']['steps']
    assert not any('docker push' in str(step.get('run', '')) for step in build)


def test_release_workflow_configures_secure_test_runtime():
    workflow = yaml.safe_load((ROOT / '.github/workflows/release.yml').read_text())

    gate_environment = workflow['jobs']['gates']['env']
    required_environment = {
        'SECRET_KEY': 'ci-only-non-production-secret-key-with-adequate-length',
        'DEBUG': 'False',
        'ALLOWED_HOSTS': 'localhost,127.0.0.1',
        'CSRF_TRUSTED_ORIGINS': 'https://app.example.invalid',
        'CUSTOMER_APP_BASE_URL': 'https://app.example.invalid',
        'DATA_ENCRYPTION_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
    }

    assert required_environment.items() <= gate_environment.items()
