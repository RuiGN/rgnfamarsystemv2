from django.db import migrations, transaction

from integrations.models import sanitize_safe_context


LEGACY_SOURCES = ('PlatformAuditEvent', 'SupportSession')
SUPPORT_TIMESTAMP_FIELDS = (
    'requested_at',
    'approval_expires_at',
    'approved_at',
    'denied_at',
    'activated_at',
    'expires_at',
    'last_activity_at',
    'revoked_at',
    'ended_at',
    'created_at',
    'updated_at',
)
EVIDENCE_LOG_FIELDS = (
    'log_type',
    'severity',
    'module',
    'action',
    'target_model',
    'target_record_id',
    'user_id',
    'message',
    'safe_context',
    'request_id',
    'occurred_at',
)


def _event_safe_context(event):
    return sanitize_safe_context(
        {
            'legacy_source': 'PlatformAuditEvent',
            'legacy_id': event.pk,
            'actor_id': event.actor_id,
            'action': event.action,
            'target_model': event.target_model,
            'target_record_id': event.target_record_id,
            'message': event.message,
            'metadata': event.metadata,
            'ip_address': event.ip_address,
            'user_agent': event.user_agent,
            'request_id': event.request_id,
            'occurred_at': event.occurred_at,
        }
    )


def _support_safe_context(support):
    context = {
        'legacy_source': 'SupportSession',
        'legacy_id': support.pk,
        'session_id': support.pk,
        'target_model': 'SupportSession',
        'target_record_id': support.pk,
        'operator_id': support.operator_id,
        'approved_by_id': support.approved_by_id,
        'denied_by_id': support.denied_by_id,
        'revoked_by_id': support.revoked_by_id,
        'access_mode': support.access_mode,
        'status': support.status,
        'reason': support.reason,
        'duration_minutes': support.duration_minutes,
    }
    context.update(
        {field_name: getattr(support, field_name) for field_name in SUPPORT_TIMESTAMP_FIELDS}
    )
    return sanitize_safe_context(context)


def _legacy_log_ids(Log, source, using):
    contexts = (
        Log.objects.using(using)
        .filter(safe_context__legacy_source=source)
        .values_list('safe_context', flat=True)
    )
    return [str(context.get('legacy_id')) for context in contexts]


def _validate_evidence_copy(source_ids, Log, source, using):
    logged_ids = _legacy_log_ids(Log, source, using)
    if len(logged_ids) != len(source_ids) or set(logged_ids) != source_ids:
        raise RuntimeError(
            f'Falha ao preservar evidências de {source}: '
            f'{len(source_ids)} registros de origem e {len(logged_ids)} logs válidos.'
        )


def _preserve_evidence_log(Log, source, legacy_id, values, using):
    try:
        log, _ = Log.objects.using(using).get_or_create(
            safe_context__legacy_source=source,
            safe_context__legacy_id=str(legacy_id),
            defaults=values,
        )
    except Log.MultipleObjectsReturned as exc:
        raise RuntimeError(
            f'Falha ao preservar evidências de {source} {legacy_id}: '
            'mais de um log usa a mesma identificação legada.'
        ) from exc

    divergent_fields = [
        field_name
        for field_name in EVIDENCE_LOG_FIELDS
        if getattr(log, field_name) != values[field_name]
    ]
    if divergent_fields:
        raise RuntimeError(
            f'Falha ao preservar evidências de {source} {legacy_id}: '
            f'conteúdo divergente nos campos {", ".join(divergent_fields)}.'
        )


def copy_legacy_evidence(apps, schema_editor):
    PlatformAuditEvent = apps.get_model('control_plane', 'PlatformAuditEvent')
    SupportSession = apps.get_model('control_plane', 'SupportSession')
    GovernanceAuditLog = apps.get_model('governance', 'GovernanceAuditLog')
    using = schema_editor.connection.alias

    with transaction.atomic(using=using):
        event_ids = {
            str(value)
            for value in PlatformAuditEvent.objects.using(using).values_list('pk', flat=True)
        }
        for event in PlatformAuditEvent.objects.using(using).iterator():
            safe_context = _event_safe_context(event)
            _preserve_evidence_log(
                GovernanceAuditLog,
                'PlatformAuditEvent',
                event.pk,
                {
                    'log_type': 'security',
                    'severity': 'info',
                    'module': 'governance',
                    'action': event.action,
                    'target_model': event.target_model,
                    'target_record_id': event.target_record_id[:120],
                    'user_id': event.actor_id,
                    'message': event.message,
                    'safe_context': safe_context,
                    'request_id': event.request_id[:120],
                    'occurred_at': event.occurred_at,
                },
                using,
            )
        _validate_evidence_copy(event_ids, GovernanceAuditLog, 'PlatformAuditEvent', using)

        support_ids = {
            str(value) for value in SupportSession.objects.using(using).values_list('pk', flat=True)
        }
        for support in SupportSession.objects.using(using).iterator():
            safe_context = _support_safe_context(support)
            _preserve_evidence_log(
                GovernanceAuditLog,
                'SupportSession',
                support.pk,
                {
                    'log_type': 'security',
                    'severity': 'info',
                    'module': 'governance',
                    'action': f'support_session.{support.status}',
                    'target_model': 'SupportSession',
                    'target_record_id': str(support.pk),
                    'user_id': support.operator_id,
                    'message': support.reason,
                    'safe_context': safe_context,
                    'request_id': '',
                    'occurred_at': support.created_at,
                },
                using,
            )
        _validate_evidence_copy(support_ids, GovernanceAuditLog, 'SupportSession', using)


def _restore_event(Event, log, context, using):
    legacy_id = context.get('legacy_id')
    if not legacy_id or Event.objects.using(using).filter(pk=legacy_id).exists():
        return

    Event.objects.using(using).create(
        event_id=legacy_id,
        actor_id=context.get('actor_id'),
        action=context.get('action', log.action),
        target_model=context.get('target_model', log.target_model),
        target_record_id=context.get('target_record_id', log.target_record_id),
        message=context.get('message', log.message),
        metadata=context.get('metadata') or {},
        ip_address=context.get('ip_address'),
        user_agent=context.get('user_agent') or '',
        request_id=context.get('request_id', log.request_id) or '',
    )
    Event.objects.using(using).filter(pk=legacy_id).update(
        occurred_at=context.get('occurred_at', log.occurred_at)
    )


def _restore_support(Session, log, context, using):
    legacy_id = context.get('legacy_id')
    if not legacy_id or Session.objects.using(using).filter(pk=legacy_id).exists():
        return

    Session.objects.using(using).create(
        session_id=context.get('session_id', legacy_id),
        operator_id=context.get('operator_id', log.user_id),
        approved_by_id=context.get('approved_by_id'),
        denied_by_id=context.get('denied_by_id'),
        revoked_by_id=context.get('revoked_by_id'),
        access_mode=context.get('access_mode'),
        status=context.get('status'),
        reason=context.get('reason', log.message),
        duration_minutes=context.get('duration_minutes'),
        approval_expires_at=context.get('approval_expires_at'),
        approved_at=context.get('approved_at'),
        denied_at=context.get('denied_at'),
        activated_at=context.get('activated_at'),
        expires_at=context.get('expires_at'),
        last_activity_at=context.get('last_activity_at'),
        revoked_at=context.get('revoked_at'),
        ended_at=context.get('ended_at'),
    )
    Session.objects.using(using).filter(pk=legacy_id).update(
        **{field_name: context.get(field_name) for field_name in SUPPORT_TIMESTAMP_FIELDS}
    )


def restore_legacy_evidence(apps, schema_editor):
    PlatformAuditEvent = apps.get_model('control_plane', 'PlatformAuditEvent')
    SupportSession = apps.get_model('control_plane', 'SupportSession')
    GovernanceAuditLog = apps.get_model('governance', 'GovernanceAuditLog')
    using = schema_editor.connection.alias

    with transaction.atomic(using=using):
        logs = GovernanceAuditLog.objects.using(using).filter(
            safe_context__legacy_source__in=LEGACY_SOURCES
        )
        for log in logs.iterator():
            context = log.safe_context or {}
            if context.get('legacy_source') == 'PlatformAuditEvent':
                _restore_event(PlatformAuditEvent, log, context, using)
            elif context.get('legacy_source') == 'SupportSession':
                _restore_support(SupportSession, log, context, using)


class Migration(migrations.Migration):
    dependencies = [
        ('control_plane', '0004_remove_platformauditevent_tenant_and_more'),
        ('governance', '0006_delete_tenantmodulesetting'),
    ]

    operations = [
        migrations.RunPython(copy_legacy_evidence, restore_legacy_evidence),
        migrations.DeleteModel(name='SupportSession'),
        migrations.DeleteModel(name='PlatformAuditEvent'),
    ]
