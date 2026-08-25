import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from files.models import PROTECTED_STORAGE_REFERENCE_PATTERN, ProtectedFile
from governance.models import GovernanceAuditLog
from reports.contracts import ReportColumn, ReportContext, ReportDataset, ReportRow
from reports.models import (
    ReportDefinition,
    ReportExecution,
    clone_safe_json_object,
)
from reports.registry import get_executor
from reports.renderers import render_report


logger = logging.getLogger(__name__)

INTERNAL_FAILURE_MESSAGE = 'Falha interna ao processar o relatório.'
VALIDATION_FAILURE_MESSAGE = 'Falha de validação ao processar o relatório.'
RETRYABLE_FAILURE_MESSAGE = 'Falha temporária ao processar o relatório.'
RETRY_EXHAUSTED_FAILURE_MESSAGE = 'Falha temporária após esgotar as tentativas do relatório.'
REPORT_EXECUTION_LEASE_SECONDS = 300


class ReportExecutionError(ValidationError):
    def __init__(self, message: str = INTERNAL_FAILURE_MESSAGE):
        self.public_message = message
        super().__init__({'execution': message})

    def __reduce__(self):
        return type(self), (self.public_message,)


class ReportExecutionInProgress(ReportExecutionError):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)
        super().__init__('A execução do relatório já está em andamento.')

    def __reduce__(self):
        return type(self), (self.retry_after,)


class ReportExecutionRetryableError(ReportExecutionError):
    def __init__(self):
        super().__init__(RETRYABLE_FAILURE_MESSAGE)

    def __reduce__(self):
        return type(self), ()


@dataclass(frozen=True, slots=True)
class _ExecutionSnapshot:
    execution_id: int
    definition_id: int
    filters: dict[str, Any]
    export_format: str
    requested_by_id: int | None
    schedule_id: int | None
    execution_number: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class _ExecutionClaim:
    execution: ReportExecution
    definition: ReportDefinition
    actor: Any
    started_at: datetime | None
    snapshot: _ExecutionSnapshot | None
    should_execute: bool
    reclaimed: bool = False
    orphan_artifact_ids: tuple[int, ...] = ()


def _lease_seconds() -> int:
    configured = getattr(
        settings,
        'REPORT_EXECUTION_LEASE_SECONDS',
        REPORT_EXECUTION_LEASE_SECONDS,
    )
    if type(configured) is not int or configured <= 0:
        return REPORT_EXECUTION_LEASE_SECONDS
    return configured


def _capture_execution_snapshot(execution: ReportExecution) -> _ExecutionSnapshot:
    try:
        filters = clone_safe_json_object(execution.filters)
    except ValueError:
        raise ValidationError(
            {'filters': 'Filtros da execução devem ser um objeto JSON seguro.'}
        ) from None
    return _ExecutionSnapshot(
        execution_id=execution.pk,
        definition_id=execution.definition_id,
        filters=filters,
        export_format=execution.export_format,
        requested_by_id=execution.requested_by_id,
        schedule_id=execution.schedule_id,
        execution_number=execution.execution_number,
        requested_at=execution.requested_at,
    )


class _CountingRows:
    def __init__(self, rows: Iterable[ReportRow]):
        self._rows = rows
        self._consumed = False
        self.count = 0

    def __iter__(self) -> Iterator[ReportRow]:
        if self._consumed:
            raise ValidationError(
                {'rows': 'As linhas do relatório só podem ser percorridas uma vez.'}
            )
        self._consumed = True
        for row in self._rows:
            self.count += 1
            yield row


def _record_execution_audit(
    execution_id: int,
    *,
    action: str,
    message: str,
    actor: Any,
    severity: str = str(GovernanceAuditLog.Severity.INFO),
    safe_context: dict[str, Any] | None = None,
) -> None:
    try:
        GovernanceAuditLog.record(
            log_type=GovernanceAuditLog.LogType.FUNCTIONAL,
            severity=severity,
            module='reports',
            action=action,
            target_model='ReportExecution',
            target_record_id=execution_id,
            user=actor,
            message=message,
            safe_context=safe_context or {},
        )
    except Exception:
        logger.exception(
            'Falha ao registrar auditoria da execução de relatório. execution_id=%s action=%s',
            execution_id,
            action,
        )


def _canonical_actor(user: Any):
    if (
        user is None
        or not getattr(user, 'is_authenticated', False)
        or getattr(user, 'pk', None) is None
    ):
        raise PermissionDenied
    try:
        actor = get_user_model()._default_manager.get(pk=user.pk)
    except (get_user_model().DoesNotExist, TypeError, ValueError):
        raise PermissionDenied from None
    if not actor.is_active:
        raise PermissionDenied
    return actor


def run_report_definition(*, definition, user, filters, export_format):
    actor = _canonical_actor(user)
    definition_id = getattr(definition, 'pk', None)
    if not isinstance(definition, ReportDefinition) or definition_id is None:
        raise ValidationError({'definition': 'Informe um relatório persistido válido.'})
    with transaction.atomic():
        try:
            canonical_definition = ReportDefinition.objects.select_for_update().get(
                pk=definition_id
            )
        except ReportDefinition.DoesNotExist:
            raise ValidationError({'definition': 'O relatório não está disponível.'}) from None
        if not canonical_definition.is_active:
            raise ValidationError({'definition': 'O relatório está inativo.'})
        if not actor.has_perm('reports.add_reportexecution'):
            raise PermissionDenied
        if canonical_definition.required_permission and not actor.has_perm(
            canonical_definition.required_permission
        ):
            raise PermissionDenied
        execution = canonical_definition.create_execution(
            filters=filters,
            export_format=export_format,
            requested_by=actor,
        )
    return execute_report(execution, actor)


def _claim_execution(execution_id: int, user: Any):
    with transaction.atomic():
        execution = ReportExecution.objects.select_for_update().get(pk=execution_id)
        definition = ReportDefinition.objects.select_for_update().get(pk=execution.definition_id)
        actor = _canonical_actor(user)
        if execution.requested_by_id is None or actor.pk != execution.requested_by_id:
            raise PermissionDenied
        if not actor.has_perm('reports.add_reportexecution'):
            raise PermissionDenied
        if definition.required_permission and not actor.has_perm(definition.required_permission):
            raise PermissionDenied
        if execution.status == execution.Status.COMPLETED:
            if execution.result_file_id is None:
                raise ValidationError(
                    {'status': 'A execução não pode ser processada neste estado.'}
                )
            return _ExecutionClaim(
                execution=execution,
                definition=definition,
                actor=actor,
                started_at=execution.started_at,
                snapshot=None,
                should_execute=False,
            )
        now = timezone.now()
        reclaimed = False
        if execution.status == execution.Status.RUNNING:
            if execution.started_at is None:
                raise ValidationError(
                    {'status': 'A execução não pode ser processada neste estado.'}
                )
            lease_seconds = _lease_seconds()
            if execution.started_at > now - timedelta(seconds=lease_seconds):
                elapsed = (now - execution.started_at).total_seconds()
                raise ReportExecutionInProgress(ceil(lease_seconds - elapsed))
            reclaimed = True
        elif execution.status != execution.Status.PENDING:
            raise ValidationError({'status': 'A execução não pode ser processada neste estado.'})
        if not definition.is_active:
            raise ValidationError({'definition': 'O relatório está inativo.'})
        orphan_artifact_id_list = list(
            ProtectedFile.objects.select_for_update()
            .filter(
                source_model='reports.ReportExecution',
                source_record_id=str(execution.pk),
            )
            .exclude(status=ProtectedFile.Status.DELETED)
            .values_list('pk', flat=True)
        )
        reserved_artifact = None
        if execution.result_file_id is not None:
            reserved_artifact = ProtectedFile.objects.select_for_update().get(
                pk=execution.result_file_id
            )
            if (
                reserved_artifact.status != ProtectedFile.Status.DELETED
                and reserved_artifact.pk not in orphan_artifact_id_list
            ):
                orphan_artifact_id_list.append(reserved_artifact.pk)
        orphan_artifact_ids = tuple(orphan_artifact_id_list)
        snapshot = _capture_execution_snapshot(execution)
        claim_started_at = now
        execution.status = execution.Status.RUNNING
        execution.started_at = claim_started_at
        execution.completed_at = None
        execution.result_reference = ''
        execution.content_hash = ''
        execution.row_count = 0
        execution.error_message = ''
        execution.save(
            update_fields=[
                'status',
                'started_at',
                'completed_at',
                'result_reference',
                'content_hash',
                'row_count',
                'error_message',
                'updated_at',
            ]
        )
    if orphan_artifact_ids:
        try:
            for artifact_id in orphan_artifact_ids:
                _cleanup_artifact_strict(
                    ProtectedFile.objects.get(pk=artifact_id),
                    actor,
                    reason='Reserva anterior descartada após expiração do lease.',
                )
        except Exception:
            logger.exception(
                'Falha ao reconciliar reserva anterior. execution_id=%s',
                execution.pk,
            )
            _reset_claim_to_pending(
                execution.pk,
                claim_started_at,
                actor,
                reserved_artifact,
            )
            raise ReportExecutionRetryableError() from None
    if execution.result_file_id is not None:
        _detach_reconciled_artifact(
            execution.pk,
            claim_started_at,
            execution.result_file_id,
        )
    _record_execution_audit(
        execution.pk,
        action=(
            'report.execution.reclaimed'
            if reclaimed or orphan_artifact_ids
            else 'report.execution.claimed'
        ),
        message=(
            'Lease expirado; execução de relatório retomada.'
            if reclaimed or orphan_artifact_ids
            else 'Execução de relatório iniciada.'
        ),
        actor=actor,
        safe_context={
            'definition_id': definition.pk,
            'export_format': execution.export_format,
            'status': execution.Status.RUNNING,
        },
    )
    return _ExecutionClaim(
        execution=execution,
        definition=definition,
        actor=actor,
        started_at=claim_started_at,
        snapshot=snapshot,
        should_execute=True,
        reclaimed=reclaimed or bool(orphan_artifact_ids),
        orphan_artifact_ids=orphan_artifact_ids,
    )


def _legacy_user_dataset(
    snapshot: _ExecutionSnapshot,
    definition: ReportDefinition,
) -> ReportDataset:
    rows = [
        {'field': 'definition', 'value': definition.code},
        *({'field': key, 'value': value} for key, value in sorted(snapshot.filters.items())),
    ]
    return ReportDataset(
        title=definition.title,
        columns=(
            ReportColumn('field', 'Campo'),
            ReportColumn('value', 'Valor'),
        ),
        rows=rows,
    )


def _execute_definition(
    snapshot: _ExecutionSnapshot,
    definition: ReportDefinition,
    actor: Any,
) -> ReportDataset:
    if not definition.executor_key and not definition.is_system_managed:
        return _legacy_user_dataset(snapshot, definition)
    executor = get_executor(definition.executor_key)
    return executor(
        ReportContext(
            filters=clone_safe_json_object(snapshot.filters),
            user=actor,
        )
    )


def _reserve_protected_artifact(
    execution_id: int,
    claim_started_at,
    snapshot: _ExecutionSnapshot,
    definition: ReportDefinition,
    actor: Any,
    *,
    extension: str,
    mime_type: str,
) -> tuple[ProtectedFile, datetime]:
    if extension != snapshot.export_format:
        raise ValidationError({'export_format': 'Extensão renderizada incompatível.'})
    file_name = f'{snapshot.execution_number}.{snapshot.export_format}'
    with transaction.atomic():
        execution = ReportExecution.objects.select_for_update().get(pk=execution_id)
        if (
            execution.status != execution.Status.RUNNING
            or execution.started_at != claim_started_at
            or execution.result_file_id is not None
            or _capture_execution_snapshot(execution) != snapshot
        ):
            raise ValidationError({'status': 'A execução perdeu a posse do processamento.'})
        protected_file = ProtectedFile.objects.create(
            source_module=ProtectedFile.SourceModule.OPERATIONAL,
            source_model='reports.ReportExecution',
            source_record_id=str(snapshot.execution_id),
            file_type=ProtectedFile.FileType.REPORT,
            origin=ProtectedFile.Origin.SYSTEM,
            criticality=ProtectedFile.Criticality.MEDIUM,
            confidentiality=ProtectedFile.Confidentiality.INTERNAL,
            title=definition.title,
            file_name=file_name,
            file_reference=f'pending/reports/{execution_id}-{uuid4().hex}',
            mime_type=mime_type,
            file_size=0,
            content_hash='sha256:pending',
            responsible=actor,
            uploaded_by=actor,
        )
        protected_file.file_reference = protected_file._encrypted_storage_path()
        protected_file.save(update_fields=['file_reference', 'updated_at'])
        execution.result_file = protected_file
        renewed_started_at = timezone.now()
        execution.started_at = renewed_started_at
        execution.save(update_fields=['result_file', 'started_at', 'updated_at'])
    return protected_file, renewed_started_at


def _store_protected_artifact(
    execution_id: int,
    claim_started_at,
    snapshot: _ExecutionSnapshot,
    protected_file: ProtectedFile,
    content: bytes,
    actor: Any,
) -> ProtectedFile:
    with transaction.atomic():
        execution = ReportExecution.objects.select_for_update().get(pk=execution_id)
        reserved_file = ProtectedFile.objects.select_for_update().get(pk=protected_file.pk)
        if (
            execution.status != execution.Status.RUNNING
            or execution.started_at != claim_started_at
            or execution.result_file_id != reserved_file.pk
            or _capture_execution_snapshot(execution) != snapshot
            or reserved_file.status != ProtectedFile.Status.ACTIVE
            or reserved_file.file_reference != protected_file.file_reference
        ):
            raise ValidationError({'status': 'A execução perdeu a posse do processamento.'})
        reserved_file.store_encrypted_content(
            content,
            file_name=reserved_file.file_name,
            mime_type=reserved_file.mime_type,
            user=actor,
            reserved_reference=reserved_file.file_reference,
        )
        reserved_file.refresh_from_db()
    return reserved_file


def _complete_execution(
    execution_id: int,
    claim_started_at,
    snapshot: _ExecutionSnapshot,
    protected_file: ProtectedFile,
    row_count: int,
) -> ReportExecution:
    with transaction.atomic():
        execution = ReportExecution.objects.select_for_update().get(pk=execution_id)
        if (
            execution.status != execution.Status.RUNNING
            or execution.started_at != claim_started_at
            or execution.result_file_id != protected_file.pk
        ):
            raise ValidationError({'status': 'A execução perdeu a posse do processamento.'})
        if _capture_execution_snapshot(execution) != snapshot:
            raise ValidationError({'execution': 'Os dados de entrada da execução foram alterados.'})
        execution.result_reference = protected_file.file_reference
        execution.content_hash = protected_file.content_hash
        execution.row_count = row_count
        execution.status = execution.Status.COMPLETED
        execution.completed_at = timezone.now()
        execution.error_message = ''
        execution.save(
            update_fields=[
                'result_reference',
                'content_hash',
                'row_count',
                'status',
                'completed_at',
                'error_message',
                'updated_at',
            ]
        )
    return execution


def _delete_protected_artifact_blobs(protected_file: ProtectedFile) -> None:
    reference = protected_file.file_reference
    if (
        type(reference) is not str
        or PROTECTED_STORAGE_REFERENCE_PATTERN.fullmatch(reference) is None
    ):
        raise OSError('Referência de storage não canônica.')
    directory = reference.rpartition('/')[0]
    expected_directory = f'protected/{protected_file.file_number}'
    if directory != expected_directory:
        raise OSError('Diretório de storage não pertence ao arquivo protegido.')
    try:
        _subdirectories, file_names = default_storage.listdir(directory)
    except FileNotFoundError:
        file_names = ()
    references = {reference}
    for file_name in file_names:
        candidate = f'{directory}/{file_name}'
        if PROTECTED_STORAGE_REFERENCE_PATTERN.fullmatch(candidate) is not None:
            references.add(candidate)
    for candidate in sorted(references):
        default_storage.delete(candidate)


def _cleanup_artifact_strict(
    protected_file: ProtectedFile,
    actor: Any,
    *,
    reason: str,
) -> None:
    protected_file.refresh_from_db()
    if protected_file.status == protected_file.Status.DELETED:
        return
    reference = protected_file.file_reference
    is_encrypted_reference = (
        type(reference) is str
        and '\x00' not in reference
        and '\\' not in reference
        and PROTECTED_STORAGE_REFERENCE_PATTERN.fullmatch(reference) is not None
    )
    is_pending_reference = (
        type(reference) is str
        and reference.startswith('pending/reports/')
        and '/' not in reference.removeprefix('pending/reports/')
        and '\x00' not in reference
        and '\\' not in reference
    )
    if not is_encrypted_reference and not is_pending_reference:
        raise OSError('Referência de storage não canônica.')
    if is_encrypted_reference:
        _delete_protected_artifact_blobs(protected_file)
    protected_file.delete_secure(reason=reason, user=actor)


def _detach_reconciled_artifact(
    execution_id: int,
    claim_started_at,
    protected_file_id: int | None,
) -> bool:
    if protected_file_id is None:
        return True
    with transaction.atomic():
        execution = ReportExecution.objects.select_for_update().get(pk=execution_id)
        protected_file = ProtectedFile.objects.select_for_update().get(pk=protected_file_id)
        if (
            execution.started_at != claim_started_at
            or execution.result_file_id != protected_file.pk
            or protected_file.status != ProtectedFile.Status.DELETED
        ):
            return False
        execution.result_file = None
        execution.result_reference = ''
        execution.content_hash = ''
        execution.row_count = 0
        execution.save(
            update_fields=[
                'result_file',
                'result_reference',
                'content_hash',
                'row_count',
                'updated_at',
            ]
        )
    return True


def _cleanup_artifact(protected_file: ProtectedFile | None, actor: Any) -> bool:
    if protected_file is None:
        return True
    try:
        protected_file.refresh_from_db()
        reference = protected_file.file_reference
        if (
            type(reference) is str
            and '\x00' not in reference
            and '\\' not in reference
            and PROTECTED_STORAGE_REFERENCE_PATTERN.fullmatch(reference) is not None
        ):
            try:
                _delete_protected_artifact_blobs(protected_file)
            except Exception:
                logger.exception(
                    'Falha ao remover blob órfão de relatório. protected_file_id=%s',
                    protected_file.pk,
                )
                return False
        if protected_file.status != protected_file.Status.DELETED:
            protected_file.delete_secure(
                reason='Artefato descartado após falha da execução de relatório.',
                user=actor,
            )
        return True
    except Exception:
        logger.exception(
            'Falha ao marcar artefato órfão como excluído. protected_file_id=%s',
            protected_file.pk,
        )
        return False


def _cleanup_artifact_for_retry(
    protected_file: ProtectedFile | None,
    actor: Any,
) -> bool:
    if protected_file is None:
        return True
    try:
        _cleanup_artifact_strict(
            protected_file,
            actor,
            reason='Artefato descartado antes de nova tentativa do relatório.',
        )
        return True
    except Exception:
        logger.exception(
            'Cleanup transitório será reconciliado na próxima tentativa. protected_file_id=%s',
            protected_file.pk,
        )
        return False


def _safe_failure_message(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return VALIDATION_FAILURE_MESSAGE
    return INTERNAL_FAILURE_MESSAGE


def _mark_failed(
    execution_id: int,
    claim_started_at,
    actor: Any,
    error: Exception,
    protected_file: ProtectedFile | None = None,
) -> None:
    failed = False
    try:
        with transaction.atomic():
            execution = ReportExecution.objects.select_for_update().get(pk=execution_id)
            if (
                execution.status == execution.Status.RUNNING
                and execution.started_at == claim_started_at
                and execution.result_file_id
                == (protected_file.pk if protected_file is not None else None)
            ):
                execution.status = execution.Status.FAILED
                execution.completed_at = timezone.now()
                execution.result_reference = ''
                execution.content_hash = ''
                execution.row_count = 0
                execution.error_message = _safe_failure_message(error)
                execution.save(
                    update_fields=[
                        'status',
                        'completed_at',
                        'result_reference',
                        'content_hash',
                        'row_count',
                        'error_message',
                        'updated_at',
                    ]
                )
                failed = True
    except Exception:
        logger.exception(
            'Falha ao persistir estado FAILED da execução. execution_id=%s',
            execution_id,
        )
    if failed:
        _record_execution_audit(
            execution_id,
            action='report.execution.failed',
            message='Execução de relatório falhou.',
            actor=actor,
            severity=str(GovernanceAuditLog.Severity.ERROR),
            safe_context={'status': ReportExecution.Status.FAILED},
        )


def _release_for_retry(
    execution_id: int,
    claim_started_at,
    actor: Any,
    protected_file: ProtectedFile | None = None,
) -> None:
    released = False
    try:
        with transaction.atomic():
            execution = ReportExecution.objects.select_for_update().get(pk=execution_id)
            if (
                execution.status == execution.Status.RUNNING
                and execution.started_at == claim_started_at
                and execution.result_file_id
                == (protected_file.pk if protected_file is not None else None)
            ):
                execution.status = execution.Status.PENDING
                execution.started_at = None
                execution.completed_at = None
                execution.result_reference = ''
                execution.content_hash = ''
                execution.row_count = 0
                execution.error_message = RETRYABLE_FAILURE_MESSAGE
                execution.save(
                    update_fields=[
                        'status',
                        'started_at',
                        'completed_at',
                        'result_reference',
                        'content_hash',
                        'row_count',
                        'error_message',
                        'updated_at',
                    ]
                )
                released = True
    except Exception:
        logger.exception(
            'Falha ao liberar execução para nova tentativa. execution_id=%s',
            execution_id,
        )
    if released:
        _record_execution_audit(
            execution_id,
            action='report.execution.retry_scheduled',
            message='Execução liberada para nova tentativa após falha temporária.',
            actor=actor,
            severity=str(GovernanceAuditLog.Severity.WARNING),
            safe_context={'status': ReportExecution.Status.PENDING},
        )


def _reset_claim_to_pending(
    execution_id: int,
    claim_started_at,
    actor: Any,
    protected_file: ProtectedFile | None,
) -> None:
    _release_for_retry(
        execution_id,
        claim_started_at,
        actor,
        protected_file=protected_file,
    )


def mark_retry_exhausted(execution_id: int) -> bool:
    failed = False
    actor = None
    with transaction.atomic():
        execution = ReportExecution.objects.select_for_update().get(pk=execution_id)
        active_artifact_ids = set(
            ProtectedFile.objects.select_for_update()
            .filter(
                source_model='reports.ReportExecution',
                source_record_id=str(execution.pk),
            )
            .exclude(status=ProtectedFile.Status.DELETED)
            .values_list('pk', flat=True)
        )
        if execution.status == execution.Status.PENDING and active_artifact_ids.issubset(
            {execution.result_file_id}
        ):
            actor = execution.requested_by
            execution.status = execution.Status.FAILED
            execution.completed_at = timezone.now()
            execution.error_message = RETRY_EXHAUSTED_FAILURE_MESSAGE
            execution.result_reference = ''
            execution.content_hash = ''
            execution.row_count = 0
            execution.save(
                update_fields=[
                    'status',
                    'completed_at',
                    'error_message',
                    'result_reference',
                    'content_hash',
                    'row_count',
                    'updated_at',
                ]
            )
            failed = True
    if failed:
        _record_execution_audit(
            execution_id,
            action='report.execution.retry_exhausted',
            message='Tentativas da execução de relatório esgotadas.',
            actor=actor,
            severity=str(GovernanceAuditLog.Severity.ERROR),
            safe_context={'status': ReportExecution.Status.FAILED},
        )
    return failed


def _run_post_completion(execution: ReportExecution, actor: Any) -> None:
    if execution.schedule_id:
        try:
            execution.schedule.record_run()
        except Exception:
            logger.exception(
                'Falha ao atualizar agendamento após relatório concluído. execution_id=%s',
                execution.pk,
            )
    try:
        execution.notify_completion()
    except Exception:
        logger.exception(
            'Falha ao notificar conclusão do relatório. execution_id=%s',
            execution.pk,
        )
        _record_execution_audit(
            execution.pk,
            action='report.execution.notification_failed',
            message='Relatório concluído, mas a notificação falhou.',
            actor=actor,
            severity=str(GovernanceAuditLog.Severity.WARNING),
            safe_context={'status': execution.Status.COMPLETED},
        )


def execute_report(execution: ReportExecution, user: Any) -> ReportExecution:
    if not isinstance(execution, ReportExecution) or execution.pk is None:
        raise ValidationError({'execution': 'Informe uma execução persistida válida.'})
    claim = _claim_execution(execution.pk, user)
    if not claim.should_execute:
        return claim.execution
    claimed = claim.execution
    definition = claim.definition
    actor = claim.actor
    claim_started_at = claim.started_at
    snapshot = claim.snapshot
    protected_file = None
    try:
        dataset = _execute_definition(snapshot, definition, actor)
        counted_rows = _CountingRows(dataset.rows)
        rendered = render_report(
            ReportDataset(
                title=dataset.title,
                columns=dataset.columns,
                rows=counted_rows,
            ),
            snapshot.export_format,
        )
        protected_file, claim_started_at = _reserve_protected_artifact(
            claimed.pk,
            claim_started_at,
            snapshot,
            definition,
            actor,
            extension=rendered.extension,
            mime_type=rendered.mime_type,
        )
        protected_file = _store_protected_artifact(
            claimed.pk,
            claim_started_at,
            snapshot,
            protected_file,
            rendered.content,
            actor,
        )
        completed = _complete_execution(
            claimed.pk,
            claim_started_at,
            snapshot,
            protected_file,
            counted_rows.count,
        )
    except Exception as error:
        logger.exception(
            'Falha detalhada na execução de relatório. execution_id=%s',
            claimed.pk,
        )
        if isinstance(error, (ConnectionError, TimeoutError, OSError)):
            _release_for_retry(
                claimed.pk,
                claim_started_at,
                actor,
                protected_file,
            )
            if _cleanup_artifact_for_retry(protected_file, actor):
                _detach_reconciled_artifact(
                    claimed.pk,
                    None,
                    protected_file.pk if protected_file is not None else None,
                )
            raise ReportExecutionRetryableError() from None
        _mark_failed(
            claimed.pk,
            claim_started_at,
            actor,
            error,
            protected_file,
        )
        if _cleanup_artifact(protected_file, actor):
            _detach_reconciled_artifact(
                claimed.pk,
                claim_started_at,
                protected_file.pk if protected_file is not None else None,
            )
        raise ReportExecutionError(_safe_failure_message(error)) from None

    _record_execution_audit(
        completed.pk,
        action='report.execution.completed',
        message='Execução de relatório concluída.',
        actor=actor,
        safe_context={
            'status': completed.Status.COMPLETED,
            'row_count': completed.row_count,
            'protected_file_id': protected_file.pk,
        },
    )
    _run_post_completion(completed, actor)
    return completed
