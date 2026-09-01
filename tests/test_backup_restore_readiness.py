import json
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase


class BackupRestoreReadinessTests(SimpleTestCase):
    def test_backup_restore_report_covers_backup_restore_safety_and_docs(self):
        from core.backup_restore_readiness import (
            BackupRestoreCheckStatus,
            evaluate_backup_restore_readiness,
        )

        report = evaluate_backup_restore_readiness(project_root=settings.BASE_DIR)
        checks = {check.code: check for check in report.checks}

        expected_codes = {
            'backup.postgres_dump_gzip',
            'backup.media_archive',
            'backup.retention_rotation',
            'restore.script_exists',
            'restore.requires_explicit_artifact',
            'restore.requires_confirmation',
            'restore.supports_dry_run',
            'restore.pre_restore_backup',
            'restore.postgres_restore',
            'restore.media_restore',
            'backup.local_scheduler',
            'backup.local_compose_service',
            'backup.local_environment',
            'docs.backup_restore_plan',
            'security.no_real_secrets',
        }

        assert report.passed is True
        assert expected_codes.issubset(checks)
        assert all(check.status == BackupRestoreCheckStatus.PASS for check in checks.values())
        assert 'pre-restore' in checks['restore.pre_restore_backup'].evidence
        assert 'docs/architecture/backup-restore.md' in checks['docs.backup_restore_plan'].evidence

    def test_backup_restore_command_outputs_json_report(self):
        stdout = StringIO()

        call_command('check_backup_restore_readiness', format='json', stdout=stdout)

        payload = json.loads(stdout.getvalue())
        assert payload['passed'] is True
        assert {item['status'] for item in payload['checks']} == {'pass'}
        assert 'restore.requires_confirmation' in {item['code'] for item in payload['checks']}

    def test_backup_restore_command_can_fail_on_errors(self):
        stdout = StringIO()

        call_command('check_backup_restore_readiness', fail_on_error=True, stdout=stdout)

        assert 'backup_restore_readiness: aprovado=True' in stdout.getvalue()

    def test_restore_script_is_defensive_and_supports_database_and_media_restore(self):
        restore_script = Path(settings.BASE_DIR) / 'scripts' / 'restore.sh'
        source = restore_script.read_text(encoding='utf-8')

        assert source.startswith('#!/usr/bin/env bash')
        assert 'set -euo pipefail' in source
        assert '--postgres' in source
        assert '--media' in source
        assert '--dry-run' in source
        assert '--yes' in source
        assert 'scripts/backup.sh' in source
        assert 'pre-restore' in source
        assert 'DROP SCHEMA IF EXISTS public CASCADE' in source
        assert 'CREATE SCHEMA public' in source
        assert 'gunzip -c' in source
        assert 'psql -v ON_ERROR_STOP=1' in source
        assert 'docker cp' in source
        assert 'tar -xzf' in source
        assert 'rm -f /tmp/rgnfarmasystem-media-restore.tar.gz' in source
        assert 'MEDIA_DEPLOYMENT' in source
        assert 'restore_media.py' in source

    def test_local_scheduler_checks_cover_orchestrator_and_vps_compose(self):
        checks = {check.code: check for check in self._report().checks}
        assert 'backup.local_scheduler' in checks
        assert 'backup.local_compose_service' in checks
        assert 'backup.local_environment' in checks

    def _report(self):
        from core.backup_restore_readiness import evaluate_backup_restore_readiness

        return evaluate_backup_restore_readiness(project_root=settings.BASE_DIR)
