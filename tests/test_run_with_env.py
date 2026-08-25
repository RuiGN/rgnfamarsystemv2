import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RUN_WITH_ENV = ROOT / 'scripts' / 'run_with_env.py'


def run_wrapper(env_file, command, *, environment=None):
    env = os.environ.copy()
    env.update(environment or {})
    return subprocess.run(
        [sys.executable, RUN_WITH_ENV, '--env-file', env_file, '--', *command],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_wrapper_loads_dotenv_values_with_spaces_without_shell_evaluation(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('DISPLAY_NAME=RGN Farma Local\n', encoding='utf-8')

    result = run_wrapper(
        env_file,
        [sys.executable, '-c', "import os; print(os.environ['DISPLAY_NAME'])"],
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'RGN Farma Local'


def test_wrapper_preserves_exported_environment_precedence(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('DB_HOST=from-file\n', encoding='utf-8')

    result = run_wrapper(
        env_file,
        [sys.executable, '-c', "import os; print(os.environ['DB_HOST'])"],
        environment={'DB_HOST': 'from-process'},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'from-process'


def test_wrapper_propagates_command_exit_code(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('SAFE_VALUE=present\n', encoding='utf-8')

    result = run_wrapper(env_file, [sys.executable, '-c', 'raise SystemExit(23)'])

    assert result.returncode == 23
