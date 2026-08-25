"""Testes para a cifragem AES-256-GCM dos artefatos de backup."""

import base64
import os
import tempfile
from unittest import mock

import pytest
from django.test import SimpleTestCase, override_settings

from integrations.services.backup_encryption import (
    BackupEncryptionError,
    BackupEncryptionResult,
    compute_sha256,
    decrypt_file,
    encrypt_file,
    encrypt_directory_tar,
    read_sha256_sidecar,
    write_sha256_sidecar,
)


TEST_KEY = base64.urlsafe_b64encode(b'\x01' * 32).decode()


@override_settings(
    DATA_ENCRYPTION_KEYS=f'backup:{TEST_KEY}',
    DATA_ENCRYPTION_KEY_ID='backup',
)
class BackupEncryptionTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = os.path.join(self.tmp.name, 'payload.bin')
        with open(self.source, 'wb') as handle:
            handle.write(os.urandom(2048) + b'PLAIN-SEGMENT-RGN-FARMA' + os.urandom(1024))
        self.dest = os.path.join(self.tmp.name, 'payload.bin.enc')

    def test_encrypts_file_and_writes_sha256_sidecar(self):
        result = encrypt_file(self.source, self.dest, kind='postgres')

        assert isinstance(result, BackupEncryptionResult)
        assert str(result.encrypted_path) == self.dest
        assert result.size_bytes > 0
        assert result.key_id == 'backup'
        assert result.sha256 == compute_sha256(self.source)

        with open(self.dest, 'rb') as handle:
            payload = handle.read()
        assert b'PLAIN-SEGMENT-RGN-FARMA' not in payload
        assert payload.startswith(b'aes256gcm:v1:backup:')

        sidecar = read_sha256_sidecar(self.dest)
        assert sidecar == result.sha256

    def test_dash_destination_uses_a_private_random_temporary_file(self):
        result = encrypt_file(self.source, '-', kind='postgres')
        sidecar = result.encrypted_path.with_suffix(result.encrypted_path.suffix + '.sha256')
        self.addCleanup(result.encrypted_path.unlink, missing_ok=True)
        self.addCleanup(sidecar.unlink, missing_ok=True)

        assert result.encrypted_path.name.startswith('rgnfarma-backup-')
        assert result.encrypted_path.stat().st_mode & 0o777 == 0o600

    def test_decrypts_and_validates_sha256(self):
        encrypt_file(self.source, self.dest, kind='media')

        target = os.path.join(self.tmp.name, 'restored.bin')
        digest = decrypt_file(self.dest, target, kind='media')

        assert digest == compute_sha256(self.source)
        with open(target, 'rb') as handle:
            assert b'PLAIN-SEGMENT-RGN-FARMA' in handle.read()

    def test_rejects_tampered_ciphertext(self):
        encrypt_file(self.source, self.dest, kind='postgres')

        with open(self.dest, 'rb') as handle:
            blob = bytearray(handle.read())
        # Altera o final do payload para quebrar a tag GCM.
        blob[-5] ^= 0x55
        tampered = os.path.join(self.tmp.name, 'tampered.bin.enc')
        with open(tampered, 'wb') as handle:
            handle.write(bytes(blob))

        target = os.path.join(self.tmp.name, 'restored.bin')
        with pytest.raises(BackupEncryptionError):
            decrypt_file(tampered, target, kind='postgres')

    def test_rejects_associated_data_mismatch(self):
        encrypt_file(self.source, self.dest, kind='postgres')
        target = os.path.join(self.tmp.name, 'restored.bin')
        with pytest.raises(BackupEncryptionError):
            decrypt_file(self.dest, target, kind='media')

    def test_encrypt_directory_tar_produces_encrypted_archive(self):
        src_dir = os.path.join(self.tmp.name, 'src')
        os.makedirs(os.path.join(src_dir, 'nested'))
        with open(os.path.join(src_dir, 'a.txt'), 'w') as handle:
            handle.write('conteudo regulatorio')
        with open(os.path.join(src_dir, 'nested', 'b.txt'), 'w') as handle:
            handle.write('outro conteudo')

        tar_dest = os.path.join(self.tmp.name, 'bundle.tar.gz.enc')
        result = encrypt_directory_tar(
            src_dir, os.path.join(self.tmp.name, 'bundle.tar.gz'), tar_dest, kind='media'
        )

        assert str(result.encrypted_path) == tar_dest
        with open(tar_dest, 'rb') as handle:
            assert b'conteudo regulatorio' not in handle.read()

    def test_write_sha256_sidecar_overwrites_existing(self):
        write_sha256_sidecar(self.dest, 'abc123')
        write_sha256_sidecar(self.dest, 'def456')
        assert read_sha256_sidecar(self.dest) == 'def456'

    def test_raises_when_source_missing(self):
        with pytest.raises(BackupEncryptionError):
            encrypt_file(os.path.join(self.tmp.name, 'missing'), self.dest, kind='postgres')

    def test_propagates_cipher_errors(self):
        fake_cipher = mock.MagicMock()
        fake_cipher.active_key_id = 'backup'
        fake_cipher.encrypt_bytes.side_effect = BackupEncryptionError('boom')
        with pytest.raises(BackupEncryptionError):
            encrypt_file(self.source, self.dest, kind='postgres', cipher=fake_cipher)
