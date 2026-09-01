from django.core.exceptions import ImproperlyConfigured

from base.ui.actions.copy import ACTION_LABELS
from base.ui.actions.discovery import discover_post_actions
from base.ui.actions.inventory import fields_for
from base.ui.actions.states import state_rule_for
from base.ui.actions.types import ActionConfig, ActionConfirmation, FieldKind, SubmissionFormat
from base.ui.registry import get_resource


CRITICAL_ACTIONS = frozenset(
    {
        'approve',
        'approve_for_implementation',
        'approve_repeat',
        'approve_resampling',
        'approve_retest',
        'archive',
        'block',
        'cancel',
        'close',
        'conclude',
        'delete_secure',
        'issue',
        'obsolete',
        'publish',
        'reject',
        'release',
        'release_quality',
        'reopen',
        'reverse',
        'revoke',
        'submit',
        'submit_for_review',
        'unblock',
    }
)


def action_config(
    module_slug,
    resource_slug,
    action_name,
    *,
    fields=(),
    allowed_states=(),
    confirmation=None,
    **overrides,
):
    try:
        default_label = ACTION_LABELS[action_name]
    except KeyError as exc:
        raise ImproperlyConfigured(
            f'Ação sem vocabulário pt-BR aprovado: {action_name!r}.'
        ) from exc

    resource = get_resource(module_slug, resource_slug)
    if resource is None:
        raise ImproperlyConfigured(
            f'Ação aponta para recurso inexistente: {(module_slug, resource_slug)!r}.'
        )
    endpoints = tuple(
        endpoint
        for endpoint in discover_post_actions()
        if endpoint.model is resource.model and endpoint.action_name == action_name
    )
    if len(endpoints) != 1:
        raise ImproperlyConfigured(
            f'Ação deve corresponder a um endpoint DRF: '
            f'{(module_slug, resource_slug, action_name)!r}; encontrados={len(endpoints)}.'
        )
    endpoint = endpoints[0]
    state_rule = state_rule_for(
        (module_slug, resource_slug, action_name),
        endpoint.model,
        detail=endpoint.detail,
    )
    if state_rule is not None and not allowed_states:
        allowed_states = state_rule.allowed_states
        overrides.setdefault('state_field', state_rule.field_name)
    if not fields:
        fields = fields_for(module_slug, resource_slug, action_name, endpoint.model)
    label = overrides.pop('label', default_label)
    if confirmation is None and action_name in CRITICAL_ACTIONS:
        confirmation = ActionConfirmation(
            title=f'Confirmar {label.casefold()}',
            message=f'Confirme a ação {label.casefold()} para este registro.',
            acknowledge_label='Confirmo que revisei os dados e desejo continuar.',
        )

    icon = 'feather-play'
    if action_name in ('delete', 'delete_secure'):
        icon = 'feather-trash-2'
    elif action_name in (
        'cancel',
        'reject',
        'fail',
        'block',
        'suspend',
        'revoke',
        'obsolete',
        'mark_lost',
        'test_failure',
        'expire',
    ):
        icon = 'feather-x'
    elif action_name in (
        'approve',
        'accept',
        'acknowledge',
        'complete',
        'complete_execution',
        'conclude',
        'verify',
        'mark_won',
        'test_success',
        'mark_read',
        'mark_received',
        'mark_sent',
        'apply',
        'post_entry',
        'post_stock',
        'answer',
        'collect',
        'receive',
        'record_response',
        'record_return',
    ) or action_name.startswith('approve_'):
        icon = 'feather-check'
    elif action_name in (
        'start',
        'run',
        'execute',
        'trigger_now',
        'advance',
        'use',
    ) or action_name.startswith('start_'):
        icon = 'feather-play-circle'
    elif action_name == 'pause':
        icon = 'feather-pause-circle'
    elif action_name == 'resume':
        icon = 'feather-play-circle'
    elif action_name == 'archive':
        icon = 'feather-archive'
    elif action_name in ('release', 'release_quality', 'unblock', 'authorize'):
        icon = 'feather-unlock'
    elif (
        'review' in action_name
        or 'evaluate' in action_name
        or action_name in ('inspect', 'check_status', 'record_view')
    ):
        icon = 'feather-search'
    elif action_name in (
        'send',
        'send_email',
        'issue',
        'publish',
        'record_regulatory_communication',
    ):
        icon = 'feather-arrow-right'
    elif 'create' in action_name or 'generate' in action_name or action_name.startswith('from_'):
        icon = 'feather-file-plus'
    elif action_name in ('download', 'export'):
        icon = 'feather-download'
    elif action_name == 'import_xml':
        icon = 'feather-upload'
    elif 'calculate' in action_name or action_name in (
        'reconcile',
        'reverse',
        'replace',
        'rotate_secret',
    ):
        icon = 'feather-activity'
    elif (
        'date' in action_name
        or 'period' in action_name
        or action_name == 'mark_overdue'
        or action_name == 'validate_period'
    ):
        icon = 'feather-calendar'

    defaults = {
        'module_slug': module_slug,
        'resource_slug': resource_slug,
        'app_label': endpoint.app_label,
        'model': endpoint.model,
        'action_name': action_name,
        'route_name': endpoint.route_name,
        'detail': endpoint.detail,
        'label': label,
        'icon': overrides.pop('icon', icon),
        'description': f'Execute esta ação em {resource.label.casefold()}.',
        'success_message': f'{label} concluído com sucesso.',
        'permissions': endpoint.permissions,
        'fields': tuple(fields),
        'allowed_states': tuple(allowed_states),
        'confirmation': confirmation,
        'submission_format': (
            SubmissionFormat.MULTIPART
            if any(field.kind == FieldKind.FILE for field in fields)
            else SubmissionFormat.JSON
        ),
    }
    defaults.update(overrides)
    return ActionConfig(**defaults)
