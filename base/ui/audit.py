import json
from typing import Any

from compliance.models import RecordStatusHistory
from documents.models import ControlledDocument

from base.ui.presentation import AuditEntry, resolve_status


MAX_AUDIT_ENTRIES = 25


def _normalized_limit(limit: int) -> int:
    try:
        requested = int(limit)
    except (TypeError, ValueError):
        requested = MAX_AUDIT_ENTRIES
    return max(0, min(requested, MAX_AUDIT_ENTRIES))


def _actor_label(actor: Any) -> str:
    if actor is None:
        return ''
    full_name = actor.get_full_name().strip()
    if full_name:
        return full_name
    email = str(getattr(actor, 'email', '') or '').strip()
    if email:
        return email
    username = str(actor.get_username() or '').strip()
    if username:
        return username
    return f'Usuário #{actor.pk}' if actor.pk is not None else ''


def _readable_snapshot(snapshot: Any) -> str:
    text = str(snapshot or '').strip()
    if not text:
        return ''
    try:
        structured = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return text
    return json.dumps(structured, ensure_ascii=False, sort_keys=True)


def _document_audit_entries(
    document: ControlledDocument, limit: int
) -> tuple[AuditEntry, ...]:
    rows = (
        document.audit_trail.select_related('actor')
        .order_by('-created_at', '-pk')[:limit]
    )
    return tuple(
        AuditEntry(
            occurred_at=row.created_at,
            actor_label=_actor_label(row.actor),
            action_label=row.get_action_display(),
            details=_readable_snapshot(row.snapshot),
            reason=str(row.reason or ''),
            status=resolve_status(row.get_action_display()),
        )
        for row in rows
    )


def _generic_audit_entries(obj: Any, limit: int) -> tuple[AuditEntry, ...]:
    rows = (
        RecordStatusHistory.objects.filter(
            source_module=obj._meta.app_label,
            target_model=obj.__class__.__name__,
            target_record_id=str(obj.pk),
        )
        .select_related('actor')
        .order_by('-occurred_at', '-pk')[:limit]
    )
    return tuple(
        AuditEntry(
            occurred_at=row.occurred_at,
            actor_label=_actor_label(row.actor),
            action_label=str(row.action),
            details=f'{row.previous_status} → {row.new_status}',
            reason=str(row.reason or ''),
            status=resolve_status(row.action),
        )
        for row in rows
    )


def get_audit_entries(obj: Any, limit: int = MAX_AUDIT_ENTRIES) -> tuple[AuditEntry, ...]:
    """Retorna eventos persistidos, recentes e isolados para ``obj``."""

    normalized_limit = _normalized_limit(limit)
    if not normalized_limit or getattr(obj, 'pk', None) is None:
        return ()
    if isinstance(obj, ControlledDocument):
        return _document_audit_entries(obj, normalized_limit)
    return _generic_audit_entries(obj, normalized_limit)
