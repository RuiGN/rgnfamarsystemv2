from pathlib import Path
import shutil
import subprocess

import pytest


def test_sensitive_runtime_artifacts_are_not_tracked():
    if shutil.which('git') is None:
        pytest.skip('Git is not installed in this runtime image.')
    tracked = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
    forbidden = [
        path
        for path in tracked
        if path.startswith('.playwright-mcp/')
        or path.startswith('.env.backup')
        or (path.startswith('gen-lang-client-') and path.endswith('.json'))
    ]

    assert forbidden == []


def test_ignore_rules_cover_sensitive_artifacts():
    source = Path('.gitignore').read_text(encoding='utf-8')

    assert '.env.backup*' in source
    assert 'gen-lang-client-*.json' in source
    assert '.playwright-mcp/' in source
    assert 'validation/evidence/private/' in source


def test_docker_context_excludes_sensitive_artifacts():
    source = Path('.dockerignore').read_text(encoding='utf-8')

    assert '.env*' in source
    assert 'gen-lang-client-*.json' in source
    assert '.playwright-mcp/' in source
    assert 'validation/evidence/private/' in source


def test_local_sensitive_files_are_owner_only_when_present():
    candidates = [Path('.env'), Path('.env.local'), *Path('.').glob('.env.backup*')]
    candidates.extend(Path('.').glob('gen-lang-client-*.json'))
    candidates.extend(Path('.playwright-mcp').glob('client-secret-*.json'))

    insecure = [
        f'{path}:{oct(path.stat().st_mode & 0o777)}'
        for path in candidates
        if path.is_file() and path.stat().st_mode & 0o077
    ]

    assert insecure == []
