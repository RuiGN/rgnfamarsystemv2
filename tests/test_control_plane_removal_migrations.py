import importlib
from types import SimpleNamespace

import pytest
from django.db import connection
from django.utils import timezone

from governance.models import GovernanceAuditLog


MIGRATION = importlib.import_module(
    'control_plane.migrations.0005_preserve_evidence_and_delete_runtime_models'
)


@pytest.mark.django_db
def test_divergent_legacy_log_aborts_before_source_models_are_removed():
    occurred_at = timezone.now()
    legacy_context = {
        'legacy_source': 'PlatformAuditEvent',
        'legacy_id': '42',
    }
    GovernanceAuditLog.objects.create(
        log_type='functional',
        severity='critical',
        module='quality',
        action='platform.adulterated',
        target_model='AdulteratedRecord',
        target_record_id='999',
        message='Conteúdo divergente.',
        safe_context=legacy_context,
        request_id='req-adulterated',
        occurred_at=occurred_at,
    )

    with pytest.raises(RuntimeError, match='Falha ao preservar evidências') as exc_info:
        MIGRATION._preserve_evidence_log(
            GovernanceAuditLog,
            'PlatformAuditEvent',
            '42',
            {
                'log_type': 'security',
                'severity': 'info',
                'module': 'governance',
                'action': 'platform.original',
                'target_model': 'OriginalRecord',
                'target_record_id': '42',
                'user_id': None,
                'message': 'Evidência original.',
                'safe_context': {
                    **legacy_context,
                    'action': 'platform.original',
                    'target_model': 'OriginalRecord',
                },
                'request_id': 'req-original',
                'occurred_at': occurred_at,
            },
            connection.alias,
        )

    message = str(exc_info.value)
    assert 'action' in message
    assert 'safe_context' in message


@pytest.mark.django_db
def test_control_plane_evidence_is_preserved_with_sanitized_context():
    event_occurred_at = timezone.now()
    event = SimpleNamespace(
        pk='evt-42',
        actor_id=None,
        action='platform.legacy',
        target_model='Record',
        target_record_id='42',
        message='Evidência histórica.',
        metadata={
            'ticket': 'SUP-42',
            'api_token': 'must-not-survive',
            'nested': {'password': 'must-not-survive', 'reference': 'QA-42'},
        },
        ip_address='192.0.2.10',
        user_agent='pytest',
        request_id='req-42',
        occurred_at=event_occurred_at,
    )

    event_context = MIGRATION._event_safe_context(event)
    MIGRATION._preserve_evidence_log(
        GovernanceAuditLog,
        'PlatformAuditEvent',
        event.pk,
        {
            'log_type': 'security',
            'severity': 'info',
            'module': 'governance',
            'action': event.action,
            'target_model': event.target_model,
            'target_record_id': event.target_record_id,
            'user_id': event.actor_id,
            'message': event.message,
            'safe_context': event_context,
            'request_id': event.request_id,
            'occurred_at': event.occurred_at,
        },
        connection.alias,
    )

    event_log = GovernanceAuditLog.objects.get(
        safe_context__legacy_source='PlatformAuditEvent',
        safe_context__legacy_id=event.pk,
    )
    assert event_log.log_type == 'security'
    assert event_log.severity == 'info'
    assert event_log.module == 'governance'
    assert event_log.action == 'platform.legacy'
    assert event_log.target_model == 'Record'
    assert event_log.target_record_id == '42'
    assert event_log.message == 'Evidência histórica.'
    assert event_log.request_id == 'req-42'
    assert event_log.occurred_at == event_occurred_at
    assert event_log.safe_context['metadata'] == {
        'ticket': 'SUP-42',
        'nested': {'reference': 'QA-42'},
    }

    timestamps = {
        'requested_at': timezone.now(),
        'approval_expires_at': timezone.now(),
        'approved_at': timezone.now(),
        'denied_at': timezone.now(),
        'activated_at': timezone.now(),
        'expires_at': timezone.now(),
        'last_activity_at': timezone.now(),
        'revoked_at': timezone.now(),
        'ended_at': timezone.now(),
        'created_at': timezone.now(),
        'updated_at': timezone.now(),
    }
    support = SimpleNamespace(
        pk='sup-42',
        operator_id=None,
        approved_by_id=None,
        denied_by_id=None,
        revoked_by_id=None,
        access_mode='read',
        status='ended',
        reason='Diagnóstico SUP-42.',
        duration_minutes=30,
        **timestamps,
    )

    support_context = MIGRATION._support_safe_context(support)
    MIGRATION._preserve_evidence_log(
        GovernanceAuditLog,
        'SupportSession',
        support.pk,
        {
            'log_type': 'security',
            'severity': 'info',
            'module': 'governance',
            'action': 'support_session.ended',
            'target_model': 'SupportSession',
            'target_record_id': support.pk,
            'user_id': support.operator_id,
            'message': support.reason,
            'safe_context': support_context,
            'request_id': '',
            'occurred_at': support.created_at,
        },
        connection.alias,
    )

    support_log = GovernanceAuditLog.objects.get(
        safe_context__legacy_source='SupportSession',
        safe_context__legacy_id=support.pk,
    )
    assert support_log.log_type == 'security'
    assert support_log.severity == 'info'
    assert support_log.module == 'governance'
    assert support_log.action == 'support_session.ended'
    assert support_log.target_model == 'SupportSession'
    assert support_log.target_record_id == support.pk
    assert support_log.message == 'Diagnóstico SUP-42.'
    assert support_log.occurred_at == support.created_at
    assert support_log.safe_context['duration_minutes'] == 30
    assert support_log.safe_context['created_at'] == str(support.created_at)
