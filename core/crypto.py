import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


ENVELOPE_PREFIX = 'aes256gcm'
ENVELOPE_VERSION = 'v1'
KEY_BYTES = 32
NONCE_BYTES = 12


class EncryptionKeyConfigurationError(ImproperlyConfigured):
    pass


class DecryptionError(ValueError):
    pass


def generate_aes256_key():
    return base64.urlsafe_b64encode(os.urandom(KEY_BYTES)).decode('ascii')


def _decode_base64(value):
    try:
        normalized = str(value or '').strip()
        padding = '=' * (-len(normalized) % 4)
        return base64.urlsafe_b64decode(f'{normalized}{padding}')
    except (binascii.Error, ValueError) as error:
        raise EncryptionKeyConfigurationError(
            'Chave AES-256 inválida: use base64 URL-safe.'
        ) from error


def _encode_base64(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _parse_keyring():
    raw_keys = getattr(settings, 'DATA_ENCRYPTION_KEYS', '') or ''
    keyring = {}
    for item in str(raw_keys).split(','):
        if not item.strip():
            continue
        if ':' not in item:
            raise EncryptionKeyConfigurationError(
                'DATA_ENCRYPTION_KEYS deve usar o formato key_id:base64key.'
            )
        key_id, raw_key = item.split(':', 1)
        key_id = key_id.strip()
        if not key_id or ':' in key_id:
            raise EncryptionKeyConfigurationError(
                'Identificador de chave de criptografia inválido.'
            )
        key = _decode_base64(raw_key)
        if len(key) != KEY_BYTES:
            raise EncryptionKeyConfigurationError('AES-256 exige chave de 32 bytes.')
        keyring[key_id] = key

    legacy_key = getattr(settings, 'DATA_ENCRYPTION_KEY', '') or ''
    if legacy_key and not keyring:
        key_id = getattr(settings, 'DATA_ENCRYPTION_KEY_ID', 'primary') or 'primary'
        key = _decode_base64(legacy_key)
        if len(key) != KEY_BYTES:
            raise EncryptionKeyConfigurationError('AES-256 exige chave de 32 bytes.')
        keyring[str(key_id)] = key

    if not keyring:
        raise EncryptionKeyConfigurationError(
            'Configure DATA_ENCRYPTION_KEYS com uma chave AES-256.'
        )
    return keyring


class AES256GCMCipher:
    def __init__(self):
        self.keyring = _parse_keyring()
        self.active_key_id = str(
            getattr(settings, 'DATA_ENCRYPTION_KEY_ID', '') or next(iter(self.keyring))
        )
        if self.active_key_id not in self.keyring:
            raise EncryptionKeyConfigurationError(
                'DATA_ENCRYPTION_KEY_ID não existe em DATA_ENCRYPTION_KEYS.'
            )

    def encrypt_bytes(self, plaintext, *, associated_data=''):
        if plaintext is None:
            plaintext = b''
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')
        associated = str(associated_data or '').encode('utf-8')
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(self.keyring[self.active_key_id]).encrypt(
            nonce, bytes(plaintext), associated
        )
        return ':'.join(
            (
                ENVELOPE_PREFIX,
                ENVELOPE_VERSION,
                self.active_key_id,
                _encode_base64(nonce),
                _encode_base64(ciphertext),
            )
        )

    def decrypt_bytes(self, envelope, *, associated_data=''):
        if isinstance(envelope, bytes):
            envelope = envelope.decode('ascii')
        parts = str(envelope or '').split(':', 4)
        if len(parts) != 5 or parts[0] != ENVELOPE_PREFIX or parts[1] != ENVELOPE_VERSION:
            raise DecryptionError('Envelope de criptografia inválido.')
        _prefix, _version, key_id, raw_nonce, raw_ciphertext = parts
        key = self.keyring.get(key_id)
        if key is None:
            raise DecryptionError('Chave de criptografia não configurada para este dado.')
        associated = str(associated_data or '').encode('utf-8')
        try:
            return AESGCM(key).decrypt(
                _decode_base64(raw_nonce), _decode_base64(raw_ciphertext), associated
            )
        except (InvalidTag, EncryptionKeyConfigurationError) as error:
            raise DecryptionError('Falha ao descriptografar dado protegido.') from error

    def encrypt_text(self, plaintext, *, associated_data=''):
        return self.encrypt_bytes(
            (plaintext or '').encode('utf-8'), associated_data=associated_data
        )

    def decrypt_text(self, envelope, *, associated_data=''):
        return self.decrypt_bytes(envelope, associated_data=associated_data).decode('utf-8')
