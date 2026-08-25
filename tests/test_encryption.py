import base64
import tempfile

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from files.models import ProtectedFile
from tests.test_files import create_fiscal_document, create_user


def encryption_test_key():
    return base64.urlsafe_b64encode(b'1' * 32).decode()


class AES256GCMCipherTests(TestCase):
    @override_settings(
        DATA_ENCRYPTION_KEYS=f'test:{encryption_test_key()}', DATA_ENCRYPTION_KEY_ID='test'
    )
    def test_encrypts_without_plaintext_and_decrypts_with_same_context(self):
        from core.crypto import AES256GCMCipher

        cipher = AES256GCMCipher()
        encrypted = cipher.encrypt_text('segredo regulatorio', associated_data='record:1:field')

        assert encrypted.startswith('aes256gcm:v1:test:')
        assert 'segredo regulatorio' not in encrypted
        assert (
            cipher.decrypt_text(encrypted, associated_data='record:1:field')
            == 'segredo regulatorio'
        )

    @override_settings(
        DATA_ENCRYPTION_KEYS=f'test:{encryption_test_key()}', DATA_ENCRYPTION_KEY_ID='test'
    )
    def test_rejects_decryption_with_different_context(self):
        from core.crypto import AES256GCMCipher, DecryptionError

        cipher = AES256GCMCipher()
        encrypted = cipher.encrypt_text('segredo regulatorio', associated_data='record:1')

        with pytest.raises(DecryptionError):
            cipher.decrypt_text(encrypted, associated_data='record:2')

    @override_settings(DATA_ENCRYPTION_KEYS='bad:not-a-32-byte-key', DATA_ENCRYPTION_KEY_ID='bad')
    def test_requires_32_byte_key_for_aes_256(self):
        from core.crypto import AES256GCMCipher, EncryptionKeyConfigurationError

        with pytest.raises(EncryptionKeyConfigurationError):
            AES256GCMCipher()


class ProtectedFileEncryptionTests(TestCase):
    def test_reserved_storage_reference_must_use_canonical_protected_path(self):
        owner = create_user('aes.reserved-path@example.com')
        protected_file = ProtectedFile.objects.create(
            source_module=ProtectedFile.SourceModule.OPERATIONAL,
            source_model='EncryptionTest',
            source_record_id='reserved-path',
            file_type=ProtectedFile.FileType.REPORT,
            origin=ProtectedFile.Origin.SYSTEM,
            criticality=ProtectedFile.Criticality.HIGH,
            confidentiality=ProtectedFile.Confidentiality.RESTRICTED,
            title='Reserva criptografada',
            file_name='reserva.xml',
            file_reference='pending',
            mime_type='application/xml',
            file_size=0,
            content_hash='sha256:pending',
            responsible=owner,
            uploaded_by=owner,
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(
                MEDIA_ROOT=media_root,
                DATA_ENCRYPTION_KEYS=f'test:{encryption_test_key()}',
                DATA_ENCRYPTION_KEY_ID='test',
            ):
                with pytest.raises(ValidationError) as invalid_reference:
                    protected_file.store_encrypted_content(
                        b'segredo',
                        user=owner,
                        reserved_reference='arbitrary/reserva.enc',
                    )

        assert invalid_reference.value.message_dict == {
            'file_reference': ['A referência reservada não é canônica.'],
        }

    def test_protected_file_content_is_stored_encrypted_and_read_with_permission(self):
        owner = create_user('aes.owner@example.com')
        intruder = create_user('aes.intruder@example.com')
        fiscal_document = create_fiscal_document(suffix='777')
        content = b'<xml><valor>segredo fiscal</valor></xml>'
        protected_file = ProtectedFile.objects.create(
            source_module=ProtectedFile.SourceModule.FISCAL,
            source_model='FiscalDocument',
            source_record_id=str(fiscal_document.id),
            fiscal_document=fiscal_document,
            file_type=ProtectedFile.FileType.FISCAL_DOCUMENT,
            origin=ProtectedFile.Origin.UPLOAD,
            criticality=ProtectedFile.Criticality.HIGH,
            confidentiality=ProtectedFile.Confidentiality.RESTRICTED,
            title='XML fiscal criptografado',
            file_name='placeholder.xml',
            file_reference='pending',
            mime_type='application/xml',
            file_size=0,
            content_hash='sha256:pending',
            responsible=owner,
            uploaded_by=owner,
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(
                MEDIA_ROOT=media_root,
                DATA_ENCRYPTION_KEYS=f'test:{encryption_test_key()}',
                DATA_ENCRYPTION_KEY_ID='test',
            ):
                protected_file.store_encrypted_content(
                    content,
                    file_name='nf-criptografada.xml',
                    mime_type='application/xml',
                    user=owner,
                )
                protected_file.refresh_from_db()

                encrypted_path = f'{media_root}/{protected_file.file_reference}'
                with open(encrypted_path, 'rb') as encrypted_file:
                    encrypted_payload = encrypted_file.read()

                assert protected_file.is_encrypted is True
                assert (
                    protected_file.encryption_algorithm
                    == ProtectedFile.EncryptionAlgorithm.AES_256_GCM
                )
                assert protected_file.encryption_key_id == 'test'
                assert protected_file.encrypted_at is not None
                assert protected_file.file_size == len(content)
                assert protected_file.encrypted_size == len(encrypted_payload)
                assert protected_file.content_hash.startswith('sha256:')
                assert b'segredo fiscal' not in encrypted_payload
                assert protected_file.read_encrypted_content(owner) == content

                with pytest.raises(ValidationError):
                    protected_file.read_encrypted_content(intruder)
