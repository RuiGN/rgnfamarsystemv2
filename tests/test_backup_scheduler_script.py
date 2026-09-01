from pathlib import Path
import os
import subprocess
import tempfile

from django.conf import settings
from django.test import SimpleTestCase


class BackupSchedulerScriptTests(SimpleTestCase):
    def setUp(self):
        self.path = Path(settings.BASE_DIR) / 'scripts' / 'backup_scheduler.sh'

    def test_scheduler_contract_is_local_only(self):
        source = self.path.read_text(encoding='utf-8')

        assert source.startswith('#!/usr/bin/env bash')
        assert 'set -euo pipefail' in source
        assert 'scripts/backup.sh' in source
        assert 'RUN_ONCE' in source
        assert 'flock' in source
        assert 'seconds_until_next_run' in source
        assert 'backup_scheduler_ready' in source
        assert 'last_backup_ok' in source
        assert 'manage.py' not in source

    def test_successful_local_cycle_writes_health_markers(self):
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            backup_dir = tmp_path / 'backups'
            log_dir = tmp_path / 'logs'
            fake_backup = tmp_path / 'backup.sh'
            fake_backup.write_text(
                '#!/bin/sh\n'
                'mkdir -p "$BACKUP_DIR"\n'
                'printf dump > "$BACKUP_DIR/postgres-test.sql.gz"\n'
                'printf media > "$BACKUP_DIR/media-test.tar.gz"\n',
                encoding='utf-8',
            )
            fake_backup.chmod(0o755)
            health = tmp_path / 'health'
            last_run = tmp_path / 'last-run'

            result = subprocess.run(
                [
                    'bash',
                    '-c',
                    'set -euo pipefail; test -f "$1"; '
                    'source <(sed \'s|^BACKUP_SCRIPT=.*|BACKUP_SCRIPT="$FAKE_BACKUP"|\' "$1")',
                    'bash',
                    self.path,
                ],
                env={
                    **os.environ,
                    'BACKUP_DIR': str(backup_dir),
                    'FAKE_BACKUP': str(fake_backup),
                    'HEALTH_FILE': str(health),
                    'LAST_RUN_FILE': str(last_run),
                    'LOCK_FILE': str(tmp_path / 'lock'),
                    'LOG_DIR': str(log_dir),
                    'RUN_ONCE': 'true',
                },
                capture_output=True,
                text=True,
                check=False,
            )

            assert result.returncode == 0, result.stderr
            assert health.exists()
            assert last_run.exists()

    def test_cycle_without_artifacts_fails_without_health_markers(self):
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            fake_backup = tmp_path / 'backup.sh'
            fake_backup.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
            fake_backup.chmod(0o755)
            health = tmp_path / 'health'
            last_run = tmp_path / 'last-run'

            result = subprocess.run(
                [
                    'bash',
                    '-c',
                    'set -euo pipefail; test -f "$1"; '
                    'source <(sed \'s|^BACKUP_SCRIPT=.*|BACKUP_SCRIPT="$FAKE_BACKUP"|\' "$1")',
                    'bash',
                    self.path,
                ],
                env={
                    **os.environ,
                    'BACKUP_DIR': str(tmp_path / 'backups'),
                    'FAKE_BACKUP': str(fake_backup),
                    'HEALTH_FILE': str(health),
                    'LAST_RUN_FILE': str(last_run),
                    'LOCK_FILE': str(tmp_path / 'lock'),
                    'LOG_DIR': str(tmp_path / 'logs'),
                    'RUN_ONCE': 'true',
                },
                capture_output=True,
                text=True,
                check=False,
            )

            assert result.returncode != 0
            assert 'artefato' in result.stderr.lower()
            assert not health.exists()
            assert not last_run.exists()
