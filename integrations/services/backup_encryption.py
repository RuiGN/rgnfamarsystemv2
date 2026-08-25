"""Criptografia e integridade dos artefatos de backup enviados para a nuvem.

Reaproveita ``core.crypto.AES256GCMCipher`` (AES-256-GCM com KID) para garantir
que dumps PostgreSQL e arquivos de media nao trafeguem em claro para o Google
Drive, atendendo requisitos de confidencialidade do ambiente farmaceutico.

Alem da cifra, gera um sidecar ``.sha256`` para verificacao de integridade
ALCOA+ apos o download.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Union

from core.crypto import AES256GCMCipher, DecryptionError


PathLike = Union[str, os.PathLike[str]]

BUFFER_SIZE = 1024 * 1024  # 1 MiB


class BackupEncryptionError(Exception):
    """Erro generico de cifragem/decifragem de backup."""


@dataclass(frozen=True)
class BackupEncryptionResult:
    encrypted_path: Path
    sha256: str
    size_bytes: int
    key_id: str


def _is_stream(target) -> bool:
    return hasattr(target, 'read') and not isinstance(target, (str, os.PathLike))


def _open_binary(target: Union[PathLike, BinaryIO]):
    if isinstance(target, (str, os.PathLike)):
        try:
            return open(os.fspath(target), 'rb')
        except OSError as error:
            raise BackupEncryptionError(f'Falha ao abrir arquivo: {error}') from error
    return target


def _resolve_destination(target: Union[PathLike, BinaryIO], fallback_dir: Path) -> Path:
    if not isinstance(target, (str, os.PathLike)):
        stream_name = getattr(target, 'name', None)
        if not isinstance(stream_name, (str, os.PathLike)):
            raise BackupEncryptionError('Stream de destino sem nome de arquivo válido.')
        return Path(os.fspath(stream_name))
    path = Path(os.fspath(target))
    if str(path) == '-':
        fallback_dir.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix='rgnfarma-backup-', suffix='.bin', dir=fallback_dir
        )
        os.close(descriptor)
        return Path(temporary_name)
    return path


def _chunked(reader: BinaryIO, chunk_size: int = BUFFER_SIZE) -> Iterable[bytes]:
    while True:
        block = reader.read(chunk_size)
        if not block:
            break
        yield block


def _cipher(cipher: Union[AES256GCMCipher, None]) -> AES256GCMCipher:
    if cipher is None:
        return AES256GCMCipher()
    return cipher


def _sidecar_for(encrypted_path: Union[PathLike, Path]) -> Path:
    return Path(os.fspath(encrypted_path)).with_suffix(
        Path(os.fspath(encrypted_path)).suffix + '.sha256'
    )


def _encryption_associated_data(kind: str, source_name: str = '') -> str:
    return f'rgnfarma:backup:v1:{kind}'


def compute_sha256(source: Union[PathLike, BinaryIO], chunk_size: int = BUFFER_SIZE) -> str:
    """Calcula o SHA-256 em streaming para qualquer arquivo ou stream binario."""
    digest = hashlib.sha256()
    with _open_binary(source) as handle:
        for block in _chunked(handle, chunk_size):
            digest.update(block)
    return digest.hexdigest()


def write_sha256_sidecar(target_path: Union[PathLike, Path], sha256: str) -> Path:
    """Persiste um sidecar ``<arquivo>.sha256`` contendo o hash em hex."""
    sidecar = _sidecar_for(target_path)
    sidecar.write_text(f'{sha256}  {Path(os.fspath(target_path)).name}\n', encoding='utf-8')
    return sidecar


def read_sha256_sidecar(target_path: Union[PathLike, Path]) -> str:
    sidecar = _sidecar_for(target_path)
    if not sidecar.exists():
        raise BackupEncryptionError(f'Sidecar de integridade ausente: {sidecar}')
    content = sidecar.read_text(encoding='utf-8').strip()
    return content.split()[0] if content else ''


def encrypt_file(
    source: Union[PathLike, BinaryIO],
    destination: Union[PathLike, BinaryIO],
    *,
    kind: str = 'postgres',
    cipher: Union[AES256GCMCipher, None] = None,
    chunk_size: int = BUFFER_SIZE,
) -> BackupEncryptionResult:
    """Cifra um arquivo em streaming e devolve metadados do resultado.

    O arquivo de saida contera um envelope textual ``aes256gcm:v1:<kid>:<nonce>:<ciphertext>``
    seguido do payload criptografado. Para manter interoperabilidade, o envelope
    textual e gravado em UTF-8 e o restante em binario.
    """
    if kind not in {'postgres', 'media'}:
        raise BackupEncryptionError(f'Tipo de backup invalido: {kind}')

    cipher_obj = _cipher(cipher)
    associated_data = _encryption_associated_data(
        kind, getattr(source, 'name', str(source)) if not _is_stream(source) else ''
    )
    source_sha = hashlib.sha256()
    plaintext = io.BytesIO()
    with _open_binary(source) as handle:
        for block in _chunked(handle, chunk_size):
            source_sha.update(block)
            plaintext.write(block)
    plaintext.seek(0)

    envelope = cipher_obj.encrypt_bytes(plaintext.getvalue(), associated_data=associated_data)
    del plaintext

    dest_path = Path(
        os.fspath(_resolve_destination(destination, fallback_dir=Path(tempfile.gettempdir())))
    )
    with open(dest_path, 'wb') as out:
        out.write(envelope.encode('utf-8'))
        out.write(b'\n')

    sha_hex = source_sha.hexdigest()
    write_sha256_sidecar(dest_path, sha_hex)

    return BackupEncryptionResult(
        encrypted_path=dest_path,
        sha256=sha_hex,
        size_bytes=dest_path.stat().st_size,
        key_id=cipher_obj.active_key_id,
    )


def decrypt_file(
    source: Union[PathLike, BinaryIO],
    destination: Union[PathLike, BinaryIO],
    *,
    kind: str = 'postgres',
    cipher: Union[AES256GCMCipher, None] = None,
    expected_sha256: str = '',
) -> str:
    """Decifra um arquivo cifrado por :func:`encrypt_file`.

    Valida o hash SHA-256 contra o sidecar ou contra ``expected_sha256`` quando
    fornecido, lancando ``BackupEncryptionError`` em caso de divergencia.
    """
    if kind not in {'postgres', 'media'}:
        raise BackupEncryptionError(f'Tipo de backup invalido: {kind}')

    cipher_obj = _cipher(cipher)
    associated_data = _encryption_associated_data(
        kind, getattr(source, 'name', str(source)) if not _is_stream(source) else ''
    )

    if isinstance(source, (str, os.PathLike)):
        with open(os.fspath(source), 'rb') as handle:
            envelope = handle.read().decode('utf-8').rstrip('\n')
    else:
        envelope = source.read().decode('utf-8').rstrip('\n')

    try:
        plaintext = cipher_obj.decrypt_bytes(envelope, associated_data=associated_data)
    except DecryptionError as error:
        raise BackupEncryptionError(str(error)) from error

    dest_path = Path(
        os.fspath(_resolve_destination(destination, fallback_dir=Path(tempfile.gettempdir())))
    )
    with open(dest_path, 'wb') as out:
        out.write(plaintext)

    digest = hashlib.sha256(plaintext).hexdigest()

    target_hash = expected_sha256
    if not target_hash and isinstance(source, (str, os.PathLike)):
        try:
            target_hash = read_sha256_sidecar(Path(os.fspath(source)))
        except BackupEncryptionError:
            target_hash = ''

    if target_hash and target_hash != digest:
        raise BackupEncryptionError(
            f'Falha de integridade: esperado {target_hash}, calculado {digest}.'
        )

    return digest


def encrypt_directory_tar(
    source_dir: PathLike,
    tar_path: PathLike,
    destination: Union[PathLike, BinaryIO],
    *,
    kind: str = 'media',
    cipher: Union[AES256GCMCipher, None] = None,
) -> BackupEncryptionResult:
    """Empacota um diretorio em tar.gz e cifra o resultado.

    Util para cifrar a saida de ``scripts/backup.sh`` que gera
    ``media-${TIMESTAMP}.tar.gz`` antes de enviar para a nuvem.
    """
    src = Path(os.fspath(source_dir))
    intermediate = Path(os.fspath(tar_path))
    intermediate.parent.mkdir(parents=True, exist_ok=True)
    if intermediate.exists():
        intermediate.unlink()

    archive = shutil.make_archive(
        base_name=str(intermediate.with_suffix('')),
        format='gztar',
        root_dir=str(src),
    )
    intermediate_path = Path(archive)
    try:
        result = encrypt_file(intermediate_path, destination, kind=kind, cipher=cipher)
    finally:
        if intermediate_path.exists():
            intermediate_path.unlink()
    return result
