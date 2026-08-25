"""Decifra um arquivo de backup cifrado com AES-256-GCM.

Usado por ``scripts/restore.sh`` para restaurar artefatos baixados do Google
Drive sem precisar instalar dependencias externas no host.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from integrations.services.backup_encryption import (
    BackupEncryptionError,
    decrypt_file,
)


KIND_CHOICES = ('postgres', 'media')
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Decifra um arquivo de backup cifrado pelo servico de upload.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, help='Caminho do arquivo .enc')
        parser.add_argument(
            '--destination',
            default='',
            help='Caminho de saida. Default: <source> sem .enc (com sufixo .dec.gz).',
        )
        parser.add_argument('--kind', required=True, choices=KIND_CHOICES)
        parser.add_argument(
            '--expected-sha256',
            default='',
            help='Hash esperado para validacao (opcional).',
        )

    def handle(self, *args, **options):
        source = Path(options['source'])
        if not source.exists():
            raise CommandError(f'Arquivo de origem invalido: {source}')

        destination = options['destination']
        if not destination:
            stripped = str(source)
            if stripped.endswith('.enc'):
                stripped = stripped[: -len('.enc')]
            destination = f'{stripped}.dec.gz'
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            digest = decrypt_file(
                source,
                destination_path,
                kind=options['kind'],
                expected_sha256=options['expected_sha256'],
            )
        except BackupEncryptionError as error:
            raise CommandError(f'Falha na decifragem: {error}')

        if os.environ.get('BACKUP_KEEP_ENCRYPTED_ON_RESTORE', 'true') != 'true':
            try:
                source.unlink()
            except OSError:
                logger.warning(
                    'Falha ao remover backup criptografado restaurado: %s',
                    source,
                    exc_info=True,
                )

        self.stdout.write(self.style.SUCCESS(f'OK {destination_path} sha256={digest}'))
