"""Testes para o cliente do Google Drive baseado em Service Account."""

import base64
import json
import os
import tempfile
from unittest import mock

import pytest
from django.test import SimpleTestCase, override_settings

from integrations.services.google_drive import (
    GoogleDriveAuthError,
    GoogleDriveError,
    GoogleDriveFile,
    GoogleDriveUploadError,
    GoogleDriveUploader,
    build_uploader_from_mapping,
)


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


def _credentials_blob():
    return base64.b64encode(json.dumps(SERVICE_ACCOUNT_JSON).encode('utf-8')).decode('ascii')


class FakeFilesApi:
    def __init__(self, *, create_response=None, list_response=None):
        self.create_response = create_response or {
            'id': 'drive-file-id',
            'name': 'postgres.sql.gz',
            'mimeType': 'application/gzip',
            'size': '1024',
            'webViewLink': 'https://drive.google.com/file/d/drive-file-id',
            'md5Checksum': 'deadbeef',
        }
        self.list_response = list_response or {'files': []}
        self.delete_calls = []
        self.create_calls = []

    def create(self, *, body, media_body, fields):
        self.create_calls.append({'body': body, 'media_body': media_body, 'fields': fields})
        return _FakeExecute(self.create_response)

    def list(self, **kwargs):
        return _FakeExecute(self.list_response)

    def delete(self, *, fileId):
        self.delete_calls.append(fileId)
        return _FakeExecute(None)

    def get(self, **kwargs):  # pragma: no cover - usado apenas em ping
        return _FakeExecute({'user': {'displayName': 'Backup'}})


class _FakeExecute:
    def __init__(self, payload):
        self._payload = payload or {}

    def execute(self):
        return self._payload


def _fake_service(api):
    service = mock.MagicMock()
    service.files.return_value = api
    return service


class GoogleDriveUploaderTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'postgres.sql.gz')
        with open(self.path, 'wb') as handle:
            handle.write(b'fake-dump-bytes')

    def test_constructor_requires_folder_id(self):
        with pytest.raises(GoogleDriveError):
            GoogleDriveUploader(folder_id='')

    def test_constructor_requires_credentials(self):
        with pytest.raises(GoogleDriveAuthError):
            GoogleDriveUploader(folder_id='folder')

    def test_from_settings_loads_secret_path(self):
        secret_path = os.path.join(self.tmp.name, 'sa.json')
        with open(secret_path, 'w') as handle:
            json.dump(SERVICE_ACCOUNT_JSON, handle)
        with override_settings(BACKUP_GDRIVE_FOLDER_ID='folder-id'):
            with mock.patch.dict(os.environ, {'BACKUP_GDRIVE_CREDENTIALS_PATH': secret_path}):
                with mock.patch(
                    'integrations.services.google_drive._resolve_credentials',
                    return_value=mock.MagicMock(),
                ):
                    uploader = GoogleDriveUploader.from_settings()
        assert uploader.folder_id == 'folder-id'

    def test_from_settings_falls_back_to_docker_secret(self):
        secret_path_shadow = '/run/secrets/GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON'

        original_exists = os.path.exists

        def fake_exists(path):
            if path == secret_path_shadow:
                return True
            return original_exists(path)

        with override_settings(BACKUP_GDRIVE_FOLDER_ID='folder-id'):
            with mock.patch(
                'integrations.services.google_drive.os.path.exists', side_effect=fake_exists
            ):
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop('BACKUP_GDRIVE_CREDENTIALS_PATH', None)
                    os.environ.pop('BACKUP_GDRIVE_CREDENTIALS_BASE64', None)
                    with mock.patch(
                        'integrations.services.google_drive._resolve_credentials',
                        return_value=mock.MagicMock(),
                    ) as resolve_mock:
                        uploader = GoogleDriveUploader.from_settings()
        assert uploader.folder_id == 'folder-id'
        resolve_mock.assert_called_once()
        kwargs = resolve_mock.call_args.kwargs
        assert kwargs['credentials_path'] == secret_path_shadow

    def test_upload_file_invokes_files_create(self):
        api = FakeFilesApi()
        uploader = GoogleDriveUploader(
            folder_id='folder-id',
            credentials_base64=_credentials_blob(),
            service=_fake_service(api),
        )
        result = uploader.upload_file(
            self.path, target_name='postgres.sql.gz', description='diario'
        )
        assert isinstance(result, GoogleDriveFile)
        assert result.file_id == 'drive-file-id'
        assert result.name == 'postgres.sql.gz'
        assert api.create_calls
        body = api.create_calls[0]['body']
        assert body['parents'] == ['folder-id']
        assert body['name'] == 'postgres.sql.gz'
        assert body['description'] == 'diario'

    def test_upload_file_raises_on_invalid_path(self):
        api = FakeFilesApi()
        uploader = GoogleDriveUploader(
            folder_id='folder-id',
            credentials_base64=_credentials_blob(),
            service=_fake_service(api),
        )
        with pytest.raises(GoogleDriveUploadError):
            uploader.upload_file(os.path.join(self.tmp.name, 'missing.sql.gz'))

    def test_find_file_by_name_returns_none_when_empty(self):
        api = FakeFilesApi(list_response={'files': []})
        uploader = GoogleDriveUploader(
            folder_id='folder-id',
            credentials_base64=_credentials_blob(),
            service=_fake_service(api),
        )
        assert uploader.find_file_by_name('postgres.sql.gz') is None

    def test_find_file_by_name_escapes_quotes(self):
        api = FakeFilesApi(
            list_response={
                'files': [
                    {
                        'id': 'fid',
                        'name': "weird'name.sql.gz",
                        'mimeType': 'application/gzip',
                        'size': '12',
                        'webViewLink': 'https://drive',
                    }
                ]
            }
        )
        uploader = GoogleDriveUploader(
            folder_id='folder-id',
            credentials_base64=_credentials_blob(),
            service=_fake_service(api),
        )
        file = uploader.find_file_by_name("weird'name.sql.gz")
        assert file is not None
        assert file.file_id == 'fid'

    def test_ping_returns_user_payload(self):
        api = FakeFilesApi()
        uploader = GoogleDriveUploader(
            folder_id='folder-id',
            credentials_base64=_credentials_blob(),
            service=_fake_service(api),
        )
        payload = uploader.ping()
        assert payload['user']['displayName'] == 'Backup'

    def test_build_uploader_from_mapping(self):
        api = FakeFilesApi()
        test_file = os.path.join(self.tmp.name, 'bundle.bin')
        with open(test_file, 'wb') as handle:
            handle.write(b'x')
        with mock.patch(
            'integrations.services.google_drive._resolve_credentials',
            return_value=mock.MagicMock(),
        ):
            uploader = build_uploader_from_mapping(
                {
                    'folder_id': 'folder',
                    'credentials_base64': _credentials_blob(),
                }
            )
        uploader._service = _fake_service(api)
        result = uploader.upload_file(test_file, target_name='x')
        assert result.file_id == 'drive-file-id'
