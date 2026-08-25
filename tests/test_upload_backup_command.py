"""Testes para o management command upload_backup e modelo BackupRun."""

import base64
import json
import os
import tempfile
from dataclasses import dataclass
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from auxiliary.models import BackupRun


SERVICE_ACCOUNT_JSON = {
    'type': 'service_account',
    'project_id': 'rgnfarma',
    'private_key_id': 'abc',
    'private_key': '-----BEGIN PRIVATE KEY-----\nMIIBVgIBADANBgkqhkiG9w0BAQEFAASCAUAwggE8AgEAAkEAuFvwGm9Q+a7VxMvA\n-----END PRIVATE KEY-----\n',
    'client_email': 'backup@rgnfarma.iam.gserviceaccount.com',
    'client_id': '123',
    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
    'token_uri': 'https://oauth2.googleapis.com/token',
    'auth_provider_x509_cert_url': 'https://www.googleapis.com/oauth2/v1/certs',
    'client_x509_cert_url': 'https://www.googleapis.com/robot/v1/metadata/x509/backup',
}


@dataclass
class FakeDriveFile:
    file_id: str
    name: str
    mime_type: str
    size_bytes: int
    web_view_link: str
    md5_checksum: str


TEST_KEY = base64.urlsafe_b64encode(b'\x02' * 32).decode()


def _credentials_blob():
    return base64.b64encode(json.dumps(SERVICE_ACCOUNT_JSON).encode('utf-8')).decode('ascii')


@override_settings(
    DATA_ENCRYPTION_KEYS=f'backup:{TEST_KEY}',
    DATA_ENCRYPTION_KEY_ID='backup',
    BACKUP_GDRIVE_FOLDER_ID='folder-id',
)
class UploadBackupCommandTests(TestCase):
    def setUp(self):
        BackupRun.objects.all().delete()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = os.path.join(self.tmp.name, 'postgres.sql.gz')
        with open(self.source, 'wb') as handle:
            handle.write(b'Pg-dump-mock-content')

    def _fake_uploader(self):
        uploader = mock.MagicMock()
        uploader.find_file_by_name.return_value = None
        uploader.upload_file.return_value = FakeDriveFile(
            file_id='drive-file-id',
            name='postgres.sql.gz.enc',
            mime_type='application/octet-stream',
            size_bytes=2048,
            web_view_link='https://drive',
            md5_checksum='cafef00d',
        )
        return uploader

    def test_uploads_and_creates_backup_run(self):
        stdout = StringIO()
        env = {
            'BACKUP_GDRIVE_CREDENTIALS_BASE64': _credentials_blob(),
        }
        uploader = self._fake_uploader()
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch(
                'integrations.management.commands.upload_backup.GoogleDriveUploader.from_settings',
                return_value=uploader,
            ):
                call_command(
                    'upload_backup',
                    '--source',
                    self.source,
                    '--kind',
                    'postgres',
                    '--target-name',
                    'postgres.sql.gz.enc',
                    '--json',
                    stdout=stdout,
                )
        payload = json.loads(stdout.getvalue())
        assert payload['status'] == 'success'
        assert payload['file_id'] == 'drive-file-id'

        run = BackupRun.objects.get(drive_file_id='drive-file-id')
        assert run.kind == BackupRun.Kind.POSTGRES
        assert run.status == BackupRun.Status.SUCCESS
        assert run.encrypted is True
        assert run.encryption_key_id == 'backup'
        assert run.sha256 and len(run.sha256) == 64

    def test_skip_if_exists_marks_skipped(self):
        stdout = StringIO()
        uploader = self._fake_uploader()
        uploader.find_file_by_name.return_value = FakeDriveFile(
            file_id='existing',
            name='postgres.sql.gz.enc',
            mime_type='application/octet-stream',
            size_bytes=2048,
            web_view_link='https://drive/existing',
            md5_checksum='abc',
        )
        with mock.patch.dict(
            os.environ, {'BACKUP_GDRIVE_CREDENTIALS_BASE64': _credentials_blob()}, clear=False
        ):
            with mock.patch(
                'integrations.management.commands.upload_backup.GoogleDriveUploader.from_settings',
                return_value=uploader,
            ):
                call_command(
                    'upload_backup',
                    '--source',
                    self.source,
                    '--kind',
                    'postgres',
                    '--skip-if-exists',
                    '--json',
                    stdout=stdout,
                )
        payload = json.loads(stdout.getvalue())
        assert payload['status'] == 'skipped'
        run = BackupRun.objects.get()
        assert run.status == BackupRun.Status.SKIPPED
        assert run.drive_file_id == 'existing'
        uploader.upload_file.assert_not_called()

    def test_upload_failure_marks_backup_run_failed(self):
        from integrations.services.google_drive import GoogleDriveUploadError

        uploader = self._fake_uploader()
        uploader.upload_file.side_effect = GoogleDriveUploadError('boom')
        with mock.patch.dict(
            os.environ, {'BACKUP_GDRIVE_CREDENTIALS_BASE64': _credentials_blob()}, clear=False
        ):
            with mock.patch(
                'integrations.management.commands.upload_backup.GoogleDriveUploader.from_settings',
                return_value=uploader,
            ):
                with pytest.raises(CommandError):
                    call_command(
                        'upload_backup',
                        '--source',
                        self.source,
                        '--kind',
                        'postgres',
                        '--json',
                        stdout=StringIO(),
                    )
        run = BackupRun.objects.get()
        assert run.status == BackupRun.Status.FAILED
        assert 'boom' in run.error_message

    def test_no_encrypt_keeps_plaintext_and_skips_sha_sidecar(self):
        stdout = StringIO()
        uploader = self._fake_uploader()
        uploader.upload_file.return_value = FakeDriveFile(
            file_id='plain-id',
            name='postgres.sql.gz',
            mime_type='application/gzip',
            size_bytes=os.path.getsize(self.source),
            web_view_link='https://drive/plain',
            md5_checksum='cafe',
        )
        with mock.patch.dict(
            os.environ, {'BACKUP_GDRIVE_CREDENTIALS_BASE64': _credentials_blob()}, clear=False
        ):
            with mock.patch(
                'integrations.management.commands.upload_backup.GoogleDriveUploader.from_settings',
                return_value=uploader,
            ):
                call_command(
                    'upload_backup',
                    '--source',
                    self.source,
                    '--kind',
                    'postgres',
                    '--no-encrypt',
                    '--target-name',
                    'postgres.sql.gz',
                    '--json',
                    stdout=stdout,
                )
        run = BackupRun.objects.get()
        assert run.encrypted is False
        assert run.encryption_key_id == ''
        assert run.sha256 and len(run.sha256) == 64

    def test_no_audit_skips_backup_run_persistence(self):
        stdout = StringIO()
        uploader = self._fake_uploader()
        with mock.patch.dict(
            os.environ, {'BACKUP_GDRIVE_CREDENTIALS_BASE64': _credentials_blob()}, clear=False
        ):
            with mock.patch(
                'integrations.management.commands.upload_backup.GoogleDriveUploader.from_settings',
                return_value=uploader,
            ):
                call_command(
                    'upload_backup',
                    '--source',
                    self.source,
                    '--kind',
                    'postgres',
                    '--no-audit',
                    '--json',
                    stdout=stdout,
                )
        assert BackupRun.objects.count() == 0
        payload = json.loads(stdout.getvalue())
        assert payload['status'] == 'success'

    def test_invalid_source_path_raises(self):
        with pytest.raises(CommandError):
            call_command(
                'upload_backup',
                '--source',
                '/no/such/file',
                '--kind',
                'postgres',
                stdout=StringIO(),
            )

    def test_invalid_kind_raises(self):
        with pytest.raises(CommandError):
            call_command(
                'upload_backup',
                '--source',
                self.source,
                '--kind',
                'invalid',
                stdout=StringIO(),
            )
