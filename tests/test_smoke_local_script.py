from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_smoke_script_has_safe_shell_contract_and_documented_routes():
    script = ROOT / 'scripts' / 'smoke_local.sh'
    result = subprocess.run(['bash', '-n', str(script)], capture_output=True, text=True)

    assert result.returncode == 0
    source = script.read_text()
    assert 'set -euo pipefail' in source
    for route in ('/health/', '/', '/api/schema/', '/api/docs/'):
        assert route in source


def test_smoke_script_help_is_non_destructive():
    result = subprocess.run(
        ['bash', str(ROOT / 'scripts' / 'smoke_local.sh'), '--help'], capture_output=True, text=True
    )

    assert result.returncode == 0
    assert 'BASE_URL' in result.stdout
