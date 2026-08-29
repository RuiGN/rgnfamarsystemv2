import pytest

from base.ui.actions.registry import action_registry
from base.ui.actions.states import RESTRICTED_ACTION_STATES


LIFECYCLE_FIELD_BY_MODEL = {
    'capa.capaapproval': 'decision',
    'changes.changeapproval': 'decision',
    'crm.opportunity': 'stage',
    'deviations.deviationapproval': 'decision',
    'qa.lotrelease': 'release_status',
    'quality.qualityresult': 'result_status',
    'recalls.recallimpactedcustomer': 'response_status',
}


def _lifecycle_field(config):
    explicit_name = LIFECYCLE_FIELD_BY_MODEL.get(config.model._meta.label_lower)
    if explicit_name:
        return config.model._meta.get_field(explicit_name)
    try:
        field = config.model._meta.get_field('status')
    except Exception:
        return None
    return field if field.choices else None


def test_every_detail_action_with_lifecycle_choices_declares_states():
    missing = []
    for config in action_registry.all():
        lifecycle_field = _lifecycle_field(config)
        if not config.detail or lifecycle_field is None:
            continue
        if not config.allowed_states:
            missing.append(config.key)
            continue
        configured_field = config.model._meta.get_field(config.state_field)
        assert configured_field.choices

    assert missing == []


def test_state_rule_inventory_has_no_orphans():
    configs = action_registry.all()
    registered_keys = {config.key for config in configs}

    assert set(RESTRICTED_ACTION_STATES) <= registered_keys
    assert sum(bool(config.allowed_states) for config in configs) == 215
    assert sum(config.detail and not config.allowed_states for config in configs) == 12
    assert all(not config.allowed_states for config in configs if not config.detail)


@pytest.mark.parametrize(
    ('key', 'state_field', 'allowed_states'),
    (
        (('audits', 'programs', 'activate'), 'status', ('draft',)),
        (('capa', 'records', 'start'), 'status', ('draft', 'open')),
        (
            ('changes', 'controls', 'approve_for_implementation'),
            'status',
            ('under_assessment',),
        ),
        (('costing', 'monthly-closings', 'close'), 'status', ('validated',)),
        (('costing', 'standard-costs', 'obsolete'), 'status', ('approved',)),
        (('crm', 'proposals', 'accept'), 'status', ('draft', 'sent')),
        (
            ('deviations', 'events', 'start_investigation'),
            'status',
            ('open', 'pending_approval'),
        ),
        (
            ('documents', 'controlled-documents', 'cancel'),
            'status',
            ('draft', 'in_review', 'reviewed', 'approved', 'cancelled'),
        ),
        (
            ('files', 'protected-files', 'generate_link'),
            'status',
            ('active', 'expired'),
        ),
        (('finance', 'titles', 'approve'), 'status', ('pending', 'overdue')),
        (
            ('fiscal', 'documents', 'cancel'),
            'emission_status',
            ('authorized',),
        ),
        (
            ('procurement', 'receipts', 'post_stock'),
            'quality_status',
            ('approved',),
        ),
        (
            ('production', 'orders', 'complete'),
            'status',
            ('in_progress',),
        ),
        (('qa', 'reviews', 'approve'), 'status', ('draft', 'in_review')),
        (
            ('quality', 'samples', 'reject'),
            'status',
            ('requested', 'collected', 'received', 'in_analysis', 'reviewed', 'rejected'),
        ),
        (
            ('recalls', 'complaints', 'close'),
            'status',
            ('investigation', 'pending_regulatory_communication'),
        ),
        (('reports', 'executions', 'run'), 'status', ('pending', 'running')),
        (('risks', 'records', 'start_monitoring'), 'status', ('in_treatment',)),
        (('training', 'enrollments', 'approve'), 'status', ('completed',)),
        (
            ('workflow', 'async-jobs', 'complete'),
            'status',
            ('pending', 'running'),
        ),
    ),
)
def test_restricted_action_states_reproduce_domain_preconditions(key, state_field, allowed_states):
    config = action_registry.get(*key)

    assert config.state_field == state_field
    assert tuple(str(state) for state in config.allowed_states) == allowed_states
