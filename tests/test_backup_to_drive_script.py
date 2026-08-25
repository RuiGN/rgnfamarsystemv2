"""Testes para o script orquestrador scripts/backup_to_drive.sh."""

from pathlib import Path
import os
import subprocess
import tempfile

from django.conf import settings
from django.test import SimpleTestCase


class BackupToDriveScriptTests(SimpleTestCase):
    def setUp(self):
        self.path = Path(settings.BASE_DIR) / 'scripts' / 'backup_to_drive.sh'
        self.source = self.path.read_text(encoding='utf-8')

    def test_is_defensive_bash(self):
        assert self.source.startswith('#!/usr/bin/env bash')
        assert 'set -euo pipefail' in self.source

    def test_uses_existing_backup_script(self):
        assert 'scripts/backup.sh' in self.source
        assert 'BACKUP_SCRIPT' in self.source

    def test_supports_run_once(self):
        assert 'RUN_ONCE' in self.source
        assert 'run_backup_cycle' in self.source

    def test_uses_lock_and_signal_trap(self):
        assert 'flock' in self.source
        assert 'EXIT INT TERM' in self.source

    def test_loads_service_account_credentials(self):
        assert 'GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON' in self.source
        assert 'BACKUP_GDRIVE_CREDENTIALS_PATH' in self.source
        assert 'BACKUP_GDRIVE_CREDENTIALS_BASE64' in self.source

    def test_computes_next_run_window(self):
        assert 'seconds_until_next_run' in self.source
        assert 'BACKUP_CRON_HOUR' in self.source
        assert 'BACKUP_CRON_MINUTE' in self.source

    def test_invokes_management_command(self):
        assert 'upload_backup' in self.source
        assert 'manage.py' in self.source

    def test_writes_healthcheck_markers(self):
        assert 'last_backup_ok' in self.source
        assert 'last_backup_run_at' in self.source

    def test_failed_upload_fails_cycle_without_health_or_success_log(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp_path = Path(temporary.name)
        backup_dir = tmp_path / 'backups'
        backup_dir.mkdir()
        log_dir = tmp_path / 'logs'
        bin_dir = tmp_path / 'bin'
        bin_dir.mkdir()
        fake_backup = tmp_path / 'backup.sh'
        fake_backup.write_text(
            '#!/bin/sh\nprintf dump > "$BACKUP_DIR/postgres-test.sql.gz"\n'
            'printf media > "$BACKUP_DIR/media-test.tar.gz"\n',
            encoding='utf-8',
        )
        fake_backup.chmod(0o755)
        fake_python = bin_dir / 'python'
        fake_python.write_text('#!/bin/sh\nexit 42\n', encoding='utf-8')
        fake_python.chmod(0o755)
        health = tmp_path / 'health'
        last_run = tmp_path / 'last-run'

        result = subprocess.run(
            [
                'bash',
                '-c',
                'source <(sed \'s|^BACKUP_SCRIPT=.*|BACKUP_SCRIPT="$FAKE_BACKUP"|\' "$1")',
                'bash',
                self.path,
            ],
            env={
                **os.environ,
                'BACKUP_DIR': str(backup_dir),
                'BACKUP_GDRIVE_ENABLED': 'true',
                'BACKUP_GDRIVE_FOLDER_ID': 'folder',
                'BACKUP_GDRIVE_REFRESH_TOKEN': 'token',
                'FAKE_BACKUP': str(fake_backup),
                'HEALTH_FILE': str(health),
                'LAST_RUN_FILE': str(last_run),
                'LOCK_FILE': str(tmp_path / 'lock'),
                'LOG_DIR': str(log_dir),
                'PYTHON_BIN': str(fake_python),
                'RUN_ONCE': 'true',
            },
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0
        assert not health.exists()
        assert not last_run.exists()
        log = (log_dir / 'backup-to-drive.log').read_text(encoding='utf-8')
        assert 'failed=1' in log
        assert 'Ciclo de backup concluido' not in log

    def test_missing_credentials_fails_configured_upload_cycle_without_markers(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp_path = Path(temporary.name)
        backup_dir = tmp_path / 'backups'
        backup_dir.mkdir()
        log_dir = tmp_path / 'logs'
        fake_backup = tmp_path / 'backup.sh'
        fake_backup.write_text(
            '#!/bin/sh\nprintf dump > "$BACKUP_DIR/postgres-test.sql.gz"\n'
            'printf media > "$BACKUP_DIR/media-test.tar.gz"\n',
            encoding='utf-8',
        )
        fake_backup.chmod(0o755)
        health = tmp_path / 'health'
        last_run = tmp_path / 'last-run'
        env = {
            **os.environ,
            'BACKUP_DIR': str(backup_dir),
            'BACKUP_GDRIVE_ENABLED': 'true',
            'BACKUP_GDRIVE_FOLDER_ID': 'configured-folder',
            'BACKUP_GDRIVE_REFRESH_TOKEN': '',
            'BACKUP_GDRIVE_CREDENTIALS_PATH': '',
            'BACKUP_GDRIVE_CREDENTIALS_BASE64': '',
            'FAKE_BACKUP': str(fake_backup),
            'HEALTH_FILE': str(health),
            'LAST_RUN_FILE': str(last_run),
            'LOCK_FILE': str(tmp_path / 'lock'),
            'LOG_DIR': str(log_dir),
            'RUN_ONCE': 'true',
        }

        result = subprocess.run(
            [
                'bash',
                '-c',
                'source <(sed \'s|^BACKUP_SCRIPT=.*|BACKUP_SCRIPT="$FAKE_BACKUP"|\' "$1")',
                'bash',
                self.path,
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0
        assert not health.exists()
        assert not last_run.exists()
        log = (log_dir / 'backup-to-drive.log').read_text(encoding='utf-8')
        assert 'credenciais' in log
        assert 'Ciclo de backup concluido' not in log

    def test_missing_folder_fails_enabled_upload_cycle_without_markers(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp_path = Path(temporary.name)
        backup_dir = tmp_path / 'backups'
        backup_dir.mkdir()
        log_dir = tmp_path / 'logs'
        fake_backup = tmp_path / 'backup.sh'
        fake_backup.write_text(
            '#!/bin/sh\nprintf dump > "$BACKUP_DIR/postgres-test.sql.gz"\n'
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
                'source <(sed \'s|^BACKUP_SCRIPT=.*|BACKUP_SCRIPT="$FAKE_BACKUP"|\' "$1")',
                'bash',
                self.path,
            ],
            env={
                **os.environ,
                'BACKUP_DIR': str(backup_dir),
                'BACKUP_GDRIVE_ENABLED': 'true',
                'BACKUP_GDRIVE_FOLDER_ID': '',
                'BACKUP_SKIP_UPLOAD_DURING_RESTORE': 'false',
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

        assert result.returncode != 0
        assert not health.exists()
        assert not last_run.exists()
        log = (log_dir / 'backup-to-drive.log').read_text(encoding='utf-8')
        assert 'BACKUP_GDRIVE_FOLDER_ID' in log
        assert 'Ciclo de backup concluido' not in log
