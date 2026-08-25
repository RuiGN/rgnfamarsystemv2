from dataclasses import dataclass

from django.db.models import Model


@dataclass(frozen=True, slots=True)
class ActionStateRule:
    field_name: str
    allowed_states: tuple[str, ...]


LIFECYCLE_FIELD_BY_MODEL = {
    'capa.capaapproval': 'decision',
    'changes.changeapproval': 'decision',
    'crm.opportunity': 'stage',
    'deviations.deviationapproval': 'decision',
    'qa.lotrelease': 'release_status',
    'quality.qualityresult': 'result_status',
    'recalls.recallimpactedcustomer': 'response_status',
}


# These restrictions mirror guards in domain methods and services. Actions not
# listed here receive every value from their lifecycle TextChoices, documenting
# that the backend currently has no state-of-origin restriction for that action.
RESTRICTED_ACTION_STATES = {
    ('production', 'orders', 'reserve_materials'): ('status', ('approved', 'released')),
    ('production', 'orders', 'issue_materials'): ('status', ('in_progress',)),
    ('production', 'orders', 'receive_outputs'): ('status', ('completed',)),
    ('production', 'orders', 'calculate_cost'): ('status', ('completed', 'closed')),
    ('audits', 'actions', 'start'): ('status', ('pending',)),
    (
        'audits',
        'plans',
        'cancel',
    ): ('status', ('draft', 'planned', 'in_progress', 'reporting', 'cancelled')),
    ('audits', 'plans', 'close'): ('status', ('reporting',)),
    ('audits', 'plans', 'complete_execution'): ('status', ('in_progress',)),
    ('audits', 'plans', 'start'): ('status', ('planned',)),
    ('audits', 'plans', 'submit'): ('status', ('draft',)),
    ('audits', 'programs', 'activate'): ('status', ('draft',)),
    ('audits', 'programs', 'close'): ('status', ('draft', 'active', 'closed')),
    ('capa', 'actions', 'start'): ('status', ('pending',)),
    (
        'capa',
        'records',
        'cancel',
    ): (
        'status',
        ('draft', 'open', 'in_progress', 'pending_effectiveness', 'pending_approval', 'cancelled'),
    ),
    ('capa', 'records', 'start'): ('status', ('draft', 'open')),
    ('capa', 'records', 'submit'): ('status', ('draft',)),
    ('changes', 'actions', 'start'): ('status', ('pending',)),
    (
        'changes',
        'controls',
        'approve_for_implementation',
    ): ('status', ('under_assessment',)),
    (
        'changes',
        'controls',
        'cancel',
    ): ('status', ('draft', 'under_assessment', 'approved', 'in_implementation', 'cancelled')),
    ('changes', 'controls', 'close'): ('status', ('in_implementation',)),
    ('changes', 'controls', 'start_implementation'): ('status', ('approved',)),
    ('changes', 'controls', 'submit'): ('status', ('draft',)),
    ('costing', 'monthly-closings', 'close'): ('status', ('validated',)),
    ('costing', 'monthly-closings', 'reopen'): ('status', ('closed',)),
    ('costing', 'monthly-closings', 'validate_period'): ('status', ('open', 'reopened')),
    ('costing', 'standard-costs', 'obsolete'): ('status', ('approved',)),
    ('crm', 'complaints', 'close'): ('status', ('open', 'under_investigation', 'closed')),
    ('crm', 'complaints', 'start_investigation'): ('status', ('open',)),
    ('crm', 'contracts', 'activate'): ('status', ('draft', 'suspended')),
    ('crm', 'contracts', 'cancel'): ('status', ('draft', 'active', 'suspended', 'expired')),
    ('crm', 'contracts', 'suspend'): ('status', ('active',)),
    ('crm', 'orders', 'cancel'): ('status', ('draft', 'approved', 'blocked', 'fulfilled')),
    ('crm', 'proposals', 'accept'): ('status', ('draft', 'sent')),
    ('crm', 'proposals', 'reject'): ('status', ('draft', 'sent')),
    ('crm', 'proposals', 'send'): ('status', ('draft',)),
    (
        'deviations',
        'events',
        'cancel',
    ): ('status', ('open', 'under_investigation', 'pending_approval', 'cancelled')),
    (
        'deviations',
        'events',
        'start_investigation',
    ): ('status', ('open', 'pending_approval')),
    ('documents', 'controlled-documents', 'approve'): ('status', ('in_review', 'reviewed')),
    ('documents', 'controlled-documents', 'archive'): ('status', ('obsolete', 'cancelled')),
    (
        'documents',
        'controlled-documents',
        'cancel',
    ): ('status', ('draft', 'in_review', 'reviewed', 'approved', 'cancelled')),
    ('documents', 'controlled-documents', 'create_revision'): ('status', ('published',)),
    ('documents', 'controlled-documents', 'obsolete'): ('status', ('published',)),
    ('documents', 'controlled-documents', 'publish'): ('status', ('approved',)),
    ('documents', 'controlled-documents', 'review'): ('status', ('in_review',)),
    ('documents', 'controlled-documents', 'submit_for_review'): ('status', ('draft',)),
    ('files', 'protected-files', 'delete_secure'): (
        'status',
        ('active', 'superseded', 'expired'),
    ),
    ('files', 'protected-files', 'expire'): ('status', ('active', 'superseded', 'expired')),
    ('files', 'protected-files', 'generate_link'): ('status', ('active', 'expired')),
    ('files', 'protected-files', 'record_view'): ('status', ('active', 'expired')),
    ('files', 'protected-files', 'replace'): ('status', ('active', 'superseded', 'expired')),
    ('finance', 'period-closings', 'close'): ('status', ('validated',)),
    ('finance', 'period-closings', 'reopen'): ('status', ('closed',)),
    ('finance', 'period-closings', 'validate_period'): ('status', ('open', 'reopened')),
    ('finance', 'settlements', 'reconcile'): ('status', ('active',)),
    ('finance', 'settlements', 'reverse'): ('status', ('active',)),
    ('finance', 'titles', 'approve'): ('status', ('pending', 'overdue')),
    (
        'finance',
        'titles',
        'cancel',
    ): ('status', ('pending', 'approved', 'overdue', 'cancelled', 'reversed')),
    ('finance', 'titles', 'mark_overdue'): ('status', ('pending', 'approved')),
    ('fiscal', 'assessments', 'close'): ('status', ('calculated',)),
    ('fiscal', 'documents', 'approve'): ('status', ('reviewed',)),
    ('fiscal', 'documents', 'cancel'): ('emission_status', ('authorized',)),
    (
        'fiscal',
        'documents',
        'issue',
    ): ('emission_status', ('not_sent', 'validating', 'sent', 'rejected', 'error')),
    ('fiscal', 'documents', 'post_entry'): ('status', ('approved',)),
    ('fiscal', 'documents', 'review'): ('status', ('under_review',)),
    ('fiscal', 'documents', 'send_email'): ('emission_status', ('authorized',)),
    ('fiscal', 'documents', 'submit_for_review'): ('status', ('draft',)),
    ('fiscal', 'obligations', 'submit'): ('status', ('open',)),
    (
        'maintenance',
        'assets',
        'block',
    ): (
        'status',
        (
            'draft',
            'available',
            'under_maintenance',
            'under_calibration',
            'cleaning',
            'sanitization',
            'blocked',
        ),
    ),
    (
        'maintenance',
        'assets',
        'release',
    ): (
        'status',
        (
            'draft',
            'available',
            'under_maintenance',
            'under_calibration',
            'cleaning',
            'sanitization',
            'blocked',
        ),
    ),
    ('maintenance', 'orders', 'cancel'): ('status', ('open', 'in_progress', 'cancelled')),
    ('maintenance', 'orders', 'complete'): ('status', ('in_progress',)),
    ('maintenance', 'orders', 'start'): ('status', ('open',)),
    ('procurement', 'orders', 'approve'): ('status', ('draft',)),
    (
        'procurement',
        'orders',
        'cancel',
    ): ('status', ('draft', 'approved', 'sent', 'partially_received', 'cancelled')),
    ('procurement', 'orders', 'send'): ('status', ('approved',)),
    ('procurement', 'receipts', 'post_stock'): ('quality_status', ('approved',)),
    ('procurement', 'requisitions', 'approve'): ('status', ('submitted',)),
    (
        'procurement',
        'requisitions',
        'cancel',
    ): ('status', ('draft', 'submitted', 'rejected', 'cancelled')),
    ('procurement', 'requisitions', 'reject'): ('status', ('submitted',)),
    ('procurement', 'requisitions', 'submit'): ('status', ('draft',)),
    ('procurement', 'rfqs', 'approve'): ('status', ('sent', 'quoted')),
    ('procurement', 'rfqs', 'send'): ('status', ('draft',)),
    ('qa', 'reviews', 'approve'): ('status', ('draft', 'in_review')),
    ('qa', 'reviews', 'reject'): ('status', ('draft', 'in_review', 'rejected', 'cancelled')),
    ('qa', 'reviews', 'submit'): ('status', ('draft',)),
    ('qa', 'lot-releases', 'approve'): ('release_status', ('under_review',)),
    ('qa', 'lot-releases', 'block'): ('release_status', ('under_review',)),
    (
        'qa',
        'lot-releases',
        'reject',
    ): ('release_status', ('under_review', 'blocked')),
    ('qa', 'lot-releases', 'unblock'): ('release_status', ('blocked',)),
    ('quality', 'analyses', 'approve'): ('status', ('reviewed',)),
    ('quality', 'analyses', 'complete'): ('status', ('in_progress',)),
    ('quality', 'analyses', 'review'): ('status', ('completed',)),
    ('quality', 'analyses', 'start'): ('status', ('pending',)),
    ('quality', 'documents', 'issue'): ('status', ('draft',)),
    ('quality', 'investigations', 'start'): ('status', ('open',)),
    ('quality', 'samples', 'approve'): ('status', ('reviewed',)),
    ('quality', 'samples', 'collect'): ('status', ('requested',)),
    ('quality', 'samples', 'receive'): ('status', ('collected',)),
    (
        'quality',
        'samples',
        'reject',
    ): ('status', ('requested', 'collected', 'received', 'in_analysis', 'reviewed', 'rejected')),
    ('quality', 'samples', 'review'): ('status', ('in_analysis',)),
    ('quality', 'samples', 'start_analysis'): ('status', ('received',)),
    ('recalls', 'campaigns', 'approve'): ('status', ('draft',)),
    (
        'recalls',
        'campaigns',
        'cancel',
    ): ('status', ('draft', 'approved', 'in_execution', 'monitoring', 'cancelled')),
    ('recalls', 'campaigns', 'close'): ('status', ('in_execution', 'monitoring')),
    ('recalls', 'campaigns', 'start'): ('status', ('approved',)),
    ('recalls', 'communications', 'acknowledge'): ('status', ('sent',)),
    ('recalls', 'communications', 'send'): ('status', ('draft',)),
    (
        'recalls',
        'complaints',
        'cancel',
    ): (
        'status',
        ('draft', 'triage', 'investigation', 'pending_regulatory_communication', 'cancelled'),
    ),
    (
        'recalls',
        'complaints',
        'close',
    ): ('status', ('investigation', 'pending_regulatory_communication')),
    (
        'recalls',
        'complaints',
        'record_regulatory_communication',
    ): ('status', ('investigation', 'pending_regulatory_communication')),
    ('recalls', 'complaints', 'start_investigation'): ('status', ('triage',)),
    ('recalls', 'complaints', 'start_triage'): ('status', ('draft',)),
    ('recalls', 'returns', 'authorize'): ('status', ('requested',)),
    (
        'recalls',
        'returns',
        'cancel',
    ): ('status', ('requested', 'authorized', 'received', 'inspected', 'cancelled')),
    ('recalls', 'returns', 'close'): ('status', ('inspected',)),
    ('recalls', 'returns', 'inspect'): ('status', ('received',)),
    ('recalls', 'returns', 'receive'): ('status', ('authorized',)),
    ('reports', 'executions', 'cancel'): ('status', ('pending', 'running', 'failed', 'cancelled')),
    ('reports', 'executions', 'run'): ('status', ('pending', 'running')),
    ('risks', 'actions', 'start'): ('status', ('pending',)),
    (
        'risks',
        'records',
        'cancel',
    ): ('status', ('draft', 'in_treatment', 'monitoring', 'cancelled')),
    ('risks', 'records', 'close'): ('status', ('monitoring',)),
    ('risks', 'records', 'start_monitoring'): ('status', ('in_treatment',)),
    ('risks', 'records', 'start_treatment'): ('status', ('draft',)),
    (
        'training',
        'sessions',
        'convocate',
    ): ('status', ('planned', 'open', 'completed')),
    ('training', 'enrollments', 'approve'): ('status', ('completed',)),
    ('training', 'enrollments', 'complete'): ('status', ('in_progress',)),
    ('training', 'enrollments', 'fail'): ('status', ('in_progress', 'completed')),
    ('training', 'enrollments', 'revoke'): ('status', ('completed', 'approved')),
    ('training', 'enrollments', 'start'): ('status', ('convoked',)),
    ('workflow', 'async-jobs', 'complete'): ('status', ('pending', 'running')),
    ('workflow', 'async-jobs', 'start'): ('status', ('pending',)),
    ('workflow', 'async-jobs', 'update_progress'): ('status', ('running',)),
    ('workflow', 'tasks', 'approve'): ('status', ('pending',)),
    ('workflow', 'tasks', 'cancel'): ('status', ('pending',)),
    ('workflow', 'tasks', 'reject'): ('status', ('pending',)),
}


def state_rule_for(
    key: tuple[str, str, str], model: type[Model], *, detail: bool
) -> ActionStateRule | None:
    if not detail:
        return None

    restricted = RESTRICTED_ACTION_STATES.get(key)
    if restricted is not None:
        field_name, allowed_states = restricted
        return ActionStateRule(field_name, allowed_states)

    field_name = LIFECYCLE_FIELD_BY_MODEL.get(model._meta.label_lower, 'status')
    try:
        field = model._meta.get_field(field_name)
    except Exception:
        return None
    if not field.choices:
        return None
    return ActionStateRule(
        field_name,
        tuple(str(value) for value, _label in field.flatchoices),
    )
