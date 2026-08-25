"""Envia um artefato de backup para o Google Drive.

Este comando e consumido por ``scripts/backup_to_drive.sh`` apos o dump
PostgreSQL/medias ser gerado por ``scripts/backup.sh``. O comando cifra o
arquivo (AES-256-GCM) antes do upload e registra a execucao em
``auxiliary.BackupRun`` para fins de auditoria BPF/ALCOA+.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from auxiliary.models import BackupRun
from integrations.services.backup_encryption import (
    BackupEncryptionError,
    compute_sha256,
    encrypt_file,
    read_sha256_sidecar,
)
from integrations.services.google_drive import (
    GoogleDriveError,
    GoogleDriveUploadError,
    GoogleDriveUploader,
)


KIND_CHOICES = ('postgres', 'media')
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Cifra e envia um arquivo de backup para o Google Drive.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, help='Caminho do arquivo a enviar.')
        parser.add_argument(
            '--kind',
            required=True,
            choices=KIND_CHOICES,
            help='Tipo de backup (postgres ou media).',
        )
        parser.add_argument(
            '--target-name',
            default='',
            help='Nome do arquivo no Drive. Default: nome do arquivo de origem.',
        )
        parser.add_argument(
            '--encrypted-target',
            default='',
            help='Caminho onde gravar a versao cifrada. Default: <source>.enc',
        )
        parser.add_argument(
            '--description',
            default='',
            help='Descricao do arquivo no Drive (opcional).',
        )
        parser.add_argument(
            '--skip-if-exists',
            action='store_true',
            help='Nao faz upload se ja existir arquivo com mesmo nome e tamanho.',
        )
        parser.add_argument(
            '--no-encrypt',
            action='store_true',
            help='Desabilita cifragem antes do upload. NAO recomendado para producao.',
        )
        parser.add_argument(
            '--no-audit',
            action='store_true',
            help='Nao grava registro em auxiliary.BackupRun.',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Emite o resultado em JSON no stdout.',
        )

    def handle(self, *args, **options):
        source_path = Path(options['source'])
        if not source_path.exists() or not source_path.is_file():
            raise CommandError(f'Arquivo de origem invalido: {source_path}')

        kind = options['kind']
        target_name = options['target_name'] or source_path.name
        encrypted_target = options['encrypted_target'] or f'{source_path}.enc'
        description = options['description']
        skip_if_exists = options['skip_if_exists']
        encrypt_enabled = not options['no_encrypt']
        record_audit = not options['no_audit']
        emit_json = options['json']

        run = self._start_audit(
            record_audit, kind, source_path, target_name, encrypted_target, encrypt_enabled
        )
        started = time.monotonic()

        upload_path = source_path
        sha256_hex = ''
        encryption_key_id = ''
        encrypted_path = ''

        if encrypt_enabled:
            try:
                result = encrypt_file(source_path, encrypted_target, kind=kind)
            except BackupEncryptionError as error:
                self._finish_audit(
                    run,
                    record_audit,
                    success=False,
                    error=str(error),
                    duration=time.monotonic() - started,
                )
                raise CommandError(f'Falha na cifragem: {error}')
            upload_path = result.encrypted_path
            encrypted_path = str(result.encrypted_path)
            sha256_hex = result.sha256
            encryption_key_id = result.key_id
        else:
            sha256_hex = compute_sha256(source_path)

        try:
            _sha_sidecar = read_sha256_sidecar(upload_path) if upload_path.suffix == '.enc' else ''
        except BackupEncryptionError:
            _sha_sidecar = ''

        try:
            uploader = GoogleDriveUploader.from_settings()
        except GoogleDriveError as error:
            self._finish_audit(
                run,
                record_audit,
                success=False,
                error=str(error),
                duration=time.monotonic() - started,
            )
            raise CommandError(str(error))

        drive_file = None
        if skip_if_exists:
            existing = uploader.find_file_by_name(
                target_name if not encrypt_enabled else upload_path.name
            )
            if existing:
                self._finish_audit(
                    run,
                    record_audit,
                    success=True,
                    error='ja_existia',
                    drive_file=existing,
                    duration=time.monotonic() - started,
                    encrypted_path=encrypted_path,
                    encryption_key_id=encryption_key_id,
                    sha256_hex=sha256_hex,
                    extra={'skipped': True},
                )
                self._emit(
                    emit_json,
                    {
                        'status': 'skipped',
                        'file_id': existing.file_id,
                        'web_view_link': existing.web_view_link,
                        'sha256': sha256_hex,
                        'encryption_key_id': encryption_key_id,
                        'size_bytes': existing.size_bytes,
                    },
                )
                return

        try:
            drive_file = uploader.upload_file(
                upload_path,
                target_name=target_name if not encrypt_enabled else upload_path.name,
                description=description,
            )
        except GoogleDriveUploadError as error:
            self._finish_audit(
                run,
                record_audit,
                success=False,
                error=str(error),
                duration=time.monotonic() - started,
                encrypted_path=encrypted_path,
                encryption_key_id=encryption_key_id,
                sha256_hex=sha256_hex,
            )
            raise CommandError(f'Falha no upload: {error}')
        except GoogleDriveError as error:
            self._finish_audit(
                run,
                record_audit,
                success=False,
                error=str(error),
                duration=time.monotonic() - started,
                encrypted_path=encrypted_path,
                encryption_key_id=encryption_key_id,
                sha256_hex=sha256_hex,
            )
            raise CommandError(str(error))

        if encrypted_path and Path(encrypted_path).exists() and Path(encrypted_path) != source_path:
            try:
                Path(encrypted_path).unlink()
            except OSError:
                logger.warning(
                    'Falha ao remover backup criptografado temporario: %s',
                    encrypted_path,
                    exc_info=True,
                )

        self._finish_audit(
            run,
            record_audit,
            success=True,
            error='',
            drive_file=drive_file,
            duration=time.monotonic() - started,
            encrypted_path=encrypted_path,
            encryption_key_id=encryption_key_id,
            sha256_hex=sha256_hex,
        )

        self._emit(
            emit_json,
            {
                'status': 'success',
                'file_id': drive_file.file_id,
                'web_view_link': drive_file.web_view_link,
                'sha256': sha256_hex,
                'encryption_key_id': encryption_key_id,
                'size_bytes': drive_file.size_bytes,
                'name': drive_file.name,
            },
        )

    def _start_audit(
        self, record_audit, kind, source_path, target_name, encrypted_target, encrypt_enabled
    ):
        if not record_audit:
            return None
        run_number = f'BK-{timezone.now().strftime("%Y%m%d%H%M%S")}-{uuid.uuid4().hex[:8].upper()}'
        return BackupRun.objects.create(
            run_number=run_number,
            kind=kind,
            source_path=str(source_path),
            encrypted_path=str(encrypted_target) if encrypt_enabled else '',
            encrypted=encrypt_enabled,
            size_bytes=source_path.stat().st_size,
            triggered_by=os.environ.get('BACKUP_TRIGGERED_BY', 'cron'),
            status=BackupRun.Status.RUNNING,
            drive_folder_id=getattr(settings, 'BACKUP_GDRIVE_FOLDER_ID', '')
            or os.environ.get('BACKUP_GDRIVE_FOLDER_ID', ''),
        )

    def _finish_audit(
        self,
        run,
        record_audit,
        *,
        success: bool,
        error: str,
        drive_file=None,
        duration: float = 0.0,
        encrypted_path: str = '',
        encryption_key_id: str = '',
        sha256_hex: str = '',
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not record_audit or run is None:
            return
        extra = extra or {}
        if extra.get('skipped') and drive_file is not None:
            run.mark_skipped(
                error or 'ja_existia',
                duration_seconds=int(duration),
            )
            run.drive_file_id = drive_file.file_id
            run.drive_file_name = drive_file.name
            run.drive_web_view_link = drive_file.web_view_link
            run.drive_mime_type = drive_file.mime_type
            run.drive_md5_checksum = drive_file.md5_checksum
        elif success and drive_file is not None:
            run.mark_success(
                drive_file=drive_file,
                encrypted_path=encrypted_path,
                encryption_key_id=encryption_key_id,
                duration_seconds=int(duration),
            )
        elif success:
            run.status = BackupRun.Status.SUCCESS
            run.encryption_key_id = encryption_key_id
            run.encrypted_path = encrypted_path
            run.duration_seconds = int(duration)
            run.finished_at = timezone.now()
        else:
            run.mark_failed(error or 'falha_desconhecida', duration_seconds=int(duration))
        if sha256_hex:
            run.sha256 = sha256_hex
        run.save()

    def _emit(self, emit_json: bool, payload: dict[str, Any]) -> None:
        if emit_json:
            self.stdout.write(json.dumps(payload, ensure_ascii=False))
        else:
            self.stdout.write(self.style.SUCCESS(json.dumps(payload, ensure_ascii=False)))
