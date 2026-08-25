from typing import Any

from django import forms
from django.contrib.auth import get_user_model

from base.ui.actions.types import ActionField, FieldKind


FIELD_SPECS = {
    (
        'ai_agents',
        'profiles',
        'run',
    ): 'source_module:c,source_model:t,source_record_id:t,input_payload:j,run_immediately:b,dispatch:b',
    ('ai_agents', 'runs', 'enqueue'): 'dispatch:b',
    ('ai_agents', 'suggestions', 'apply'): 'comments:T',
    ('ai_agents', 'suggestions', 'approve'): 'comments:T',
    ('ai_agents', 'suggestions', 'reject'): 'comments:T',
    ('audits', 'plans', 'cancel'): 'reason:T',
    ('audits', 'plans', 'close'): 'summary:T',
    ('audits', 'checklist-items', 'answer'): 'status:c,answer:T',
    ('audits', 'actions', 'complete'): 'completion_notes:T,evidence_reference:t,content_hash:t',
    ('capa', 'records', 'cancel'): 'reason:T',
    ('capa', 'records', 'close'): 'summary:T',
    ('capa', 'actions', 'complete'): 'completion_notes:T',
    ('capa', 'effectiveness-checks', 'verify'): 'result:c,evidence_reference:t,effective:b',
    ('capa', 'approvals', 'approve'): 'comments:T',
    ('capa', 'approvals', 'reject'): 'comments:T',
    ('changes', 'controls', 'cancel'): 'reason:T',
    ('changes', 'controls', 'close'): 'summary:T',
    (
        'changes',
        'assessments',
        'complete',
    ): 'impact_level:c,impact_description:T,required_actions:T',
    ('changes', 'actions', 'complete'): 'completion_notes:T,evidence_reference:t,content_hash:t',
    ('changes', 'approvals', 'approve'): 'comments:T',
    ('changes', 'approvals', 'reject'): 'comments:T',
    ('changes', 'stock-assessments', 'complete'): 'decision:c,assessment_summary:T',
    ('compliance', 'checklist-items', 'evaluate_module'): 'module:c',
    ('costing', 'monthly-closings', 'reopen'): 'validation_notes:T',
    ('costing', 'monthly-closings', 'validate_period'): 'validation_notes:T',
    ('production', 'orders', 'calculate_cost'): 'period_start:D,period_end:D',
    ('crm', 'opportunities', 'advance'): 'stage:c',
    ('crm', 'opportunities', 'mark_lost'): 'reason:T',
    ('crm', 'proposals', 'reject'): 'reason:T',
    ('crm', 'orders', 'cancel'): 'reason:T',
    ('crm', 'complaints', 'cancel'): 'reason:T',
    ('crm', 'complaints', 'close'): 'resolution:T',
    ('deviations', 'events', 'cancel'): 'reason:T',
    ('deviations', 'events', 'close'): 'summary:T',
    ('deviations', 'investigations', 'conclude'): 'root_cause:T,impact_conclusion:T,conclusion:T',
    ('deviations', 'approvals', 'approve'): 'comments:T',
    ('deviations', 'approvals', 'reject'): 'comments:T',
    ('documents', 'controlled-documents', 'approve'): 'comments:T',
    ('documents', 'controlled-documents', 'archive'): 'reason:T',
    ('documents', 'controlled-documents', 'cancel'): 'reason:T',
    ('documents', 'controlled-documents', 'create_revision'): 'change_summary:T',
    ('documents', 'controlled-documents', 'obsolete'): 'reason:T',
    ('documents', 'controlled-documents', 'review'): 'comments:T',
    ('documents', 'distributions', 'confirm_read'): 'confirmation_text:T',
    ('files', 'protected-files', 'delete_secure'): 'reason:T',
    ('files', 'protected-files', 'generate_link'): 'purpose:T,expires_in_minutes:i',
    (
        'files',
        'protected-files',
        'replace',
    ): 'new_file_reference:t,new_file_name:t,content_hash:t,reason:T,file_size:i,mime_type:t',
    ('files', 'secure-links', 'revoke'): 'reason:T',
    ('finance', 'settlements', 'reverse'): 'reversal_reason:T',
    ('finance', 'cash-flow', 'from_settlement'): 'settlement:r',
    ('finance', 'cash-flow', 'from_title'): 'title:r',
    ('finance', 'period-closings', 'reopen'): 'validation_notes:T',
    ('finance', 'period-closings', 'validate_period'): 'validation_notes:T',
    ('fiscal', 'documents', 'cancel'): 'justification:T',
    ('fiscal', 'documents', 'create_financial_title'): 'category:r,due_date:D',
    ('fiscal', 'book-entries', 'from_document'): 'document:r',
    ('fiscal', 'obligations', 'submit'): 'protocol_number:t',
    ('integrations', 'connectors', 'suspend'): 'reason:T',
    ('integrations', 'connectors', 'test_failure'): 'error_message:T,details:j',
    ('integrations', 'connectors', 'test_success'): 'details:j',
    ('integrations', 'api-clients', 'rotate_secret'): 'secret:t',
    ('maintenance', 'assets', 'block'): 'reason:T',
    ('maintenance', 'plans', 'generate_order'): 'source_lot:r,due_date:D',
    ('maintenance', 'orders', 'cancel'): 'reason:T',
    ('maintenance', 'orders', 'complete'): 'summary:T,evidence_reference:t,content_hash:t',
    ('maintenance', 'downtimes', 'close'): 'ended_at:DT',
    ('maintenance', 'metric-reports', 'generate'): 'content_reference:t',
    ('pharmacovigilance', 'cases', 'cancel'): 'reason:T',
    ('pharmacovigilance', 'cases', 'close'): 'summary:T',
    (
        'pharmacovigilance',
        'actions',
        'complete',
    ): 'completion_notes:T,evidence_reference:t,content_hash:t',
    ('pharmacovigilance', 'reports', 'generate'): 'content_reference:t',
    ('procurement', 'requisitions', 'reject'): 'rejection_reason:T',
    ('procurement', 'receipts', 'release_quality'): 'quality_status:c',
    ('qa', 'reviews', 'reject'): 'reason:T',
    ('qa', 'checklist-items', 'complete'): 'evidence_reference:t,comments:T',
    ('qa', 'lot-releases', 'approve'): 'decision:c',
    ('qa', 'lot-releases', 'block'): 'reason:T',
    ('qa', 'lot-releases', 'reject'): 'reason:T',
    ('qa', 'lot-releases', 'unblock'): 'reason:T',
    ('qa', 'blocks', 'unblock'): 'reason:T',
    ('qa', 'training-records', 'complete'): 'evidence_reference:t',
    ('qa', 'training-records', 'revoke'): 'reason:T',
    ('qa', 'critical-activity-rules', 'authorize'): 'user:r',
    ('quality', 'samples', 'cancel'): 'reason:T',
    ('quality', 'samples', 'create_analysis'): 'method_reference:t',
    ('quality', 'samples', 'reject'): 'reason:T',
    ('quality', 'analyses', 'reject'): 'reason:T',
    ('quality', 'investigations', 'approve_repeat'): 'justification:T',
    ('quality', 'investigations', 'approve_resampling'): 'justification:T',
    ('quality', 'investigations', 'approve_retest'): 'justification:T',
    ('quality', 'investigations', 'conclude'): 'root_cause:T,conclusion:T',
    ('quality', 'documents', 'cancel'): 'reason:T',
    ('recalls', 'complaints', 'cancel'): 'reason:T',
    ('recalls', 'complaints', 'close'): 'summary:T',
    ('recalls', 'complaints', 'record_regulatory_communication'): 'reference:t',
    ('recalls', 'returns', 'cancel'): 'reason:T',
    ('recalls', 'returns', 'close'): 'summary:T',
    ('recalls', 'returns', 'inspect'): 'disposition:c,notes:T',
    ('recalls', 'returns', 'receive'): 'quantity:d',
    ('recalls', 'campaigns', 'cancel'): 'reason:T',
    ('recalls', 'campaigns', 'close'): 'summary:T',
    ('recalls', 'impacted-customers', 'record_response'): 'status:c,notes:T',
    ('recalls', 'impacted-customers', 'record_return'): 'quantity:d,notes:T',
    ('recalls', 'reports', 'generate'): 'content_reference:t',
    ('reports', 'definitions', 'run'): 'export_format:c,filters:j',
    ('regulatory', 'dossiers', 'cancel'): 'reason:T',
    ('regulatory', 'dossiers', 'close'): 'summary:T',
    ('regulatory', 'petitions', 'record_response'): 'response_summary:T',
    ('regulatory', 'petitions', 'submit'): 'protocol_number:t',
    (
        'regulatory',
        'requirements',
        'answer',
    ): 'response_summary:T,evidence_reference:t,content_hash:t',
    (
        'regulatory',
        'commitments',
        'complete',
    ): 'completion_summary:T,evidence_reference:t,content_hash:t',
    ('regulatory', 'reports', 'generate'): 'content_reference:t',
    ('risks', 'records', 'cancel'): 'reason:T',
    ('risks', 'records', 'close'): 'summary:T',
    ('risks', 'actions', 'complete'): 'completion_notes:T,evidence_reference:t,content_hash:t',
    ('risks', 'reviews', 'complete'): 'result:c,next_review_date:D',
    ('training', 'sessions', 'convocate'): 'user:r,due_date:D',
    ('training', 'enrollments', 'approve'): 'certificate_reference:t',
    ('training', 'enrollments', 'complete'): 'score:d,evidence_reference:t,content_hash:t',
    ('training', 'enrollments', 'fail'): 'reason:T',
    ('training', 'enrollments', 'revoke'): 'reason:T',
    ('training', 'critical-activity-rules', 'authorize'): 'user:r',
    ('training', 'indicator-reports', 'generate'): 'content_reference:t',
    ('workflow', 'tasks', 'approve'): 'comments:T',
    ('workflow', 'tasks', 'cancel'): 'comments:T',
    ('workflow', 'tasks', 'reject'): 'comments:T',
    ('workflow', 'async-jobs', 'complete'): 'result_reference:t,message:T',
    ('workflow', 'async-jobs', 'fail'): 'error_message:T,message:T',
    ('workflow', 'async-jobs', 'start'): 'task_id:t',
    ('workflow', 'async-jobs', 'update_progress'): 'progress_percent:i,message:T',
}


SENSITIVE_FIELD_LABEL = 'Segredo'


FIELD_LABELS = {
    'answer': 'Resposta',
    'assessment_summary': 'Resumo da avaliação',
    'cancel_reason': 'Justificativa do cancelamento',
    'category': 'Categoria',
    'certificate_reference': 'Referência do certificado',
    'change_summary': 'Resumo da alteração',
    'comments': 'Comentários',
    'completion_notes': 'Notas de conclusão',
    'completion_summary': 'Resumo da conclusão',
    'conclusion': 'Conclusão',
    'confirmation_text': 'Texto de confirmação',
    'content_hash': 'Hash do conteúdo',
    'content_reference': 'Referência do conteúdo',
    'details': 'Detalhes',
    'decision': 'Decisão',
    'dispatch': 'Despachar em segundo plano',
    'disposition': 'Destinação',
    'due_date': 'Data de vencimento',
    'effective': 'Eficaz',
    'ended_at': 'Encerrado em',
    'error_message': 'Mensagem de erro',
    'evidence_reference': 'Referência da evidência',
    'expires_in_minutes': 'Validade em minutos',
    'export_format': 'Formato de exportação',
    'file_size': 'Tamanho do arquivo',
    'filters': 'Filtros',
    'impact_conclusion': 'Conclusão de impacto',
    'impact_description': 'Descrição do impacto',
    'impact_level': 'Nível de impacto',
    'input_payload': 'Dados de entrada',
    'justification': 'Justificativa',
    'message': 'Mensagem',
    'method_reference': 'Referência do método',
    'mime_type': 'Tipo MIME',
    'module': 'Módulo',
    'new_file_name': 'Nome do novo arquivo',
    'new_file_reference': 'Referência do novo arquivo',
    'next_review_date': 'Data da próxima revisão',
    'notes': 'Observações',
    'progress_percent': 'Progresso percentual',
    'protocol_number': 'Número do protocolo',
    'purpose': 'Finalidade',
    'period_end': 'Fim do período',
    'period_start': 'Início do período',
    'quality_status': 'Situação da qualidade',
    'quantity': 'Quantidade',
    'reason': 'Justificativa',
    'reference': 'Referência',
    'rejection_reason': 'Justificativa da rejeição',
    'resolution': 'Resolução',
    'response_summary': 'Resumo da resposta',
    'result': 'Resultado',
    'result_reference': 'Referência do resultado',
    'reversal_reason': 'Justificativa do estorno',
    'root_cause': 'Causa raiz',
    'run_immediately': 'Executar imediatamente',
    'score': 'Pontuação',
    'secret': SENSITIVE_FIELD_LABEL,
    'settlement': 'Liquidação',
    'source_lot': 'Lote de origem',
    'source_model': 'Model de origem',
    'source_module': 'Módulo de origem',
    'source_record_id': 'Registro de origem',
    'stage': 'Etapa',
    'status': 'Situação',
    'summary': 'Resumo',
    'task_id': 'Identificador da tarefa',
    'title': 'Título financeiro',
    'user': 'Usuário',
    'validation_notes': 'Notas da validação',
}


KIND_MAP = {
    't': FieldKind.TEXT,
    'T': FieldKind.TEXTAREA,
    'i': FieldKind.INTEGER,
    'd': FieldKind.DECIMAL,
    'b': FieldKind.BOOLEAN,
    'D': FieldKind.DATE,
    'DT': FieldKind.DATETIME,
    'c': FieldKind.CHOICE,
    'r': FieldKind.RELATION,
    'j': FieldKind.JSON,
}


def fields_for(module_slug, resource_slug, action_name, model):
    specification = FIELD_SPECS.get((module_slug, resource_slug, action_name), '')
    if not specification:
        return ()
    fields = []
    for item in specification.split(','):
        name, code = item.split(':', 1)
        kind = KIND_MAP[code]
        options: dict[str, Any] = {
            'required': kind != FieldKind.BOOLEAN,
            'choices': (
                _choices_for(module_slug, resource_slug, action_name, model, name)
                if kind == FieldKind.CHOICE
                else ()
            ),
            'queryset_factory': _relation_factory(name) if kind == FieldKind.RELATION else None,
        }
        if name == 'expires_in_minutes':
            options.update(min_value=1, max_value=10080)
        elif name in {'score', 'progress_percent'}:
            options.update(min_value=0, max_value=100)
        if name == 'secret':
            options['widget_factory'] = lambda: forms.PasswordInput(render_value=False)
        fields.append(ActionField(name, FIELD_LABELS.get(name, name), kind, **options))
    return tuple(fields)


def _choices_for(module_slug, resource_slug, action_name, model, name):
    try:
        choices = model._meta.get_field(name).flatchoices
    except Exception:
        choices = CHOICE_OVERRIDES.get((module_slug, resource_slug, action_name, name), ())
    if not choices:
        choices = CHOICE_OVERRIDES.get((module_slug, resource_slug, action_name, name), ())
    return tuple((str(value), str(label)) for value, label in choices)


def _relation_factory(name):
    def factory(request):
        model = _relation_models()[name]
        permission = f'{model._meta.app_label}.view_{model._meta.model_name}'
        manager = model._default_manager
        return manager.all() if request.user.has_perm(permission) else manager.none()

    return factory


def _relation_models():
    from finance.models import FinancialCategory, FinancialSettlement, FinancialTitle
    from fiscal.models import FiscalDocument
    from inventory.models import StockLot

    return {
        'category': FinancialCategory,
        'document': FiscalDocument,
        'settlement': FinancialSettlement,
        'source_lot': StockLot,
        'title': FinancialTitle,
        'user': get_user_model(),
    }


def _operational_module_choices():
    from compliance.models import OperationalModule

    return OperationalModule.choices


def _recall_response_choices():
    from recalls.models import RecallImpactedCustomer

    return tuple(
        choice
        for choice in RecallImpactedCustomer.ResponseStatus.choices
        if choice[0] != RecallImpactedCustomer.ResponseStatus.PENDING
    )


def _report_format_choices():
    from reports.models import ReportExecution

    return ReportExecution.ExportFormat.choices


class _LazyChoices:
    def __init__(self, factory):
        self.factory = factory

    def __iter__(self):
        return iter(self.factory())


CHOICE_OVERRIDES = {
    ('capa', 'effectiveness-checks', 'verify', 'result'): (
        ('satisfactory', 'Satisfatório'),
        ('unsatisfactory', 'Insatisfatório'),
    ),
    ('compliance', 'checklist-items', 'evaluate_module', 'module'): _LazyChoices(
        _operational_module_choices
    ),
    ('qa', 'lot-releases', 'approve', 'decision'): (
        ('released', 'Liberado'),
        ('released_with_observation', 'Liberado com observação'),
    ),
    ('recalls', 'impacted-customers', 'record_response', 'status'): _LazyChoices(
        _recall_response_choices
    ),
    ('reports', 'definitions', 'run', 'export_format'): _LazyChoices(_report_format_choices),
    ('risks', 'reviews', 'complete', 'result'): (
        ('acceptable', 'Risco aceitável'),
        ('requires_treatment', 'Requer tratamento adicional'),
    ),
}
