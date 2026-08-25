from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'release_gate.sh'


def run(*args, **kwargs):
    return subprocess.run(['bash', str(SCRIPT), *args], capture_output=True, text=True, **kwargs)


def test_release_gate_accepts_semver_and_commit():
    result = run('v1.2.3', env={'PATH': '/usr/bin:/bin', 'GITHUB_SHA': 'a' * 40})

    assert result.returncode == 0
    assert 'v1.2.3' in result.stdout


def test_release_gate_rejects_invalid_tag():
    result = run('release-latest', env={'PATH': '/usr/bin:/bin', 'GITHUB_SHA': 'a' * 40})

    assert result.returncode != 0
    assert 'vMAJOR.MINOR.PATCH' in result.stderr
