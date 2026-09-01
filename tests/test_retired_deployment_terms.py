from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_retired_orchestrator_directory_is_absent():
    retired_proxy_directory = ROOT / 'deploy' / ('trae' + 'fik')

    assert not retired_proxy_directory.exists()


def test_versioned_files_do_not_reference_retired_orchestrators():
    retired_terms = (
        b'trae' + b'fik',
        b'sw' + b'arm',
        b'docker' + b'-stack',
        b'docker' + b' stack',
        b'docker' + b' service',
        b'docker' + b' node',
        b'docker' + b' secret',
        b'stack' + b'_name',
        b'--stack' + b'-name',
    )
    tracked = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.split(b'\0')

    violations = []
    for relative_path in tracked:
        if not relative_path:
            continue
        path = ROOT / relative_path.decode()
        if not path.is_file():
            continue
        lowered_path = relative_path.lower()
        content = path.read_bytes().lower()
        if any(term in lowered_path or term in content for term in retired_terms):
            violations.append(relative_path.decode())

    assert violations == []


def test_retired_offsite_connector_files_are_absent():
    retired_paths = (
        ROOT / 'scripts' / ('backup_to_' + 'drive.sh'),
        ROOT / 'integrations' / 'services' / ('google_' + 'drive.py'),
        ROOT / 'integrations' / 'services' / ('google_' + 'drive_oauth.py'),
        ROOT / 'integrations' / 'management' / 'commands' / ('google_' + 'drive_auth.py'),
        ROOT / 'integrations' / 'management' / 'commands' / ('upload_' + 'backup.py'),
        ROOT / 'tests' / ('test_google_' + 'drive_uploader.py'),
        ROOT / 'tests' / ('test_upload_' + 'backup_command.py'),
        ROOT / 'tests' / ('test_backup_to_' + 'drive_script.py'),
    )

    assert [str(path.relative_to(ROOT)) for path in retired_paths if path.exists()] == []


def test_active_runtime_does_not_reference_retired_offsite_connector():
    inspected_paths = (
        '.env.example',
        'README.md',
        'core/backup_restore_readiness.py',
        'docker-compose.vps.yml',
        'docs/DEPLOY_VPS.md',
        'docs/architecture/backup-restore.md',
        'docs/architecture/operational-readiness.md',
        'docs/deployment.md',
        'docs/security/secrets-inventory.example.md',
        'requirements.txt',
        'scripts/deploy-vps.sh',
        'scripts/restore.sh',
    )
    retired_terms = (
        'BACKUP_' + 'GDRIVE',
        'Google ' + 'Drive',
        'google_' + 'drive',
        'backup_' + 'uploader',
        'backup_to_' + 'drive',
        'google-api-' + 'python-client',
    )
    violations = []
    for relative_path in inspected_paths:
        source = (ROOT / relative_path).read_text(encoding='utf-8').lower()
        if any(term.lower() in source for term in retired_terms):
            violations.append(relative_path)

    assert violations == []
