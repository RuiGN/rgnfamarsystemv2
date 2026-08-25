from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from base.modules import OperationalModule


User = get_user_model()


def create_user(email):
    return User.objects.create_user(username=email, email=email, password='S3curePass!123')


class ComplianceModelTests(TestCase):
    def test_rf31_policies_status_history_and_critical_actions_are_global_and_safe(self):
        from compliance.models import (
            CriticalActionExecution,
            RecordStatusHistory,
            TransversalRequirementPolicy,
        )
        from governance.models import GovernanceAuditLog, GovernanceParameter

        owner = create_user('compliance.owner@example.com')
        other_user = create_user('compliance.other@example.com')
        tracked_parameter = GovernanceParameter.objects.create(
            scope=GovernanceParameter.Scope.MODULE,
            module=OperationalModule.GOVERNANCE,
            key='governance_enabled',
            value_type=GovernanceParameter.ValueType.BOOLEAN,
            value=False,
            default_value=False,
            updated_by=owner,
        )

        policy = TransversalRequirementPolicy.objects.create(
            code='RF31-GOVERNANCE',
            title='Criterios transversais RF-31',
            source_module=OperationalModule.GOVERNANCE,
            enforcement_level=TransversalRequirementPolicy.EnforcementLevel.BLOCKING,
            require_single_instance_scope=True,
            require_permission_check=True,
            require_audit_log=True,
            require_status_history=True,
            require_transaction=True,
            require_ptbr_messages=True,
            owner=owner,
        )
        invalid_policy = TransversalRequirementPolicy(
            code='RF31-CROSS',
            title='Politica invalida',
            source_module=OperationalModule.GOVERNANCE,
            enforcement_level=TransversalRequirementPolicy.EnforcementLevel.BLOCKING,
            owner=other_user,
        )
        status_history = RecordStatusHistory.record_transition(
            instance=tracked_parameter,
            previous_status='disabled',
            new_status='active',
            action='parameter.activate',
            actor=owner,
            reason='Ativacao revisada pela governanca.',
            metadata={'source': 'rf31'},
        )
        same_status_history = RecordStatusHistory(
            source_module=OperationalModule.GOVERNANCE,
            target_model='GovernanceParameter',
            target_record_id=str(tracked_parameter.id),
            previous_status='active',
            new_status='active',
            action='no.change',
            actor=owner,
        )
        alternate_actor_history = RecordStatusHistory(
            source_module=OperationalModule.GOVERNANCE,
            target_model='GovernanceParameter',
            target_record_id=str(tracked_parameter.id),
            previous_status='disabled',
            new_status='active',
            action='parameter.activate',
            actor=other_user,
        )

        def create_parameter(execution):
            GovernanceParameter.objects.create(
                scope=GovernanceParameter.Scope.WORKFLOW,
                module=OperationalModule.GOVERNANCE,
                key='rf31_transaction_guard',
                value_type=GovernanceParameter.ValueType.BOOLEAN,
                value=True,
                default_value=True,
                description='Parametro criado por acao critica transacional.',
                updated_by=owner,
            )
            RecordStatusHistory.record_transition(
                instance=tracked_parameter,
                previous_status='active',
                new_status='suspended',
                action='parameter.suspend.demo',
                actor=owner,
                reason='Transicao registrada pela acao critica.',
                metadata={'execution': execution.transaction_id},
            )

        success_execution = CriticalActionExecution.run_action(
            action_code='rf31.demo.success',
            source_module=OperationalModule.GOVERNANCE,
            target=tracked_parameter,
            actor=owner,
            message='Acao critica transacional concluida.',
            safe_context={'token': 'hidden', 'visible': 'ok'},
            callback=create_parameter,
        )

        def failing_callback(execution):
            GovernanceParameter.objects.create(
                scope=GovernanceParameter.Scope.WORKFLOW,
                module=OperationalModule.GOVERNANCE,
                key='rf31_should_rollback',
                value_type=GovernanceParameter.ValueType.BOOLEAN,
                value=True,
                default_value=True,
                updated_by=owner,
            )
            raise ValidationError({'status': 'Falha proposital para validar rollback.'})

        with pytest.raises(ValidationError):
            CriticalActionExecution.run_action(
                action_code='rf31.demo.failure',
                source_module=OperationalModule.GOVERNANCE,
                target=tracked_parameter,
                actor=owner,
                message='Acao critica falhou.',
                callback=failing_callback,
            )
        failed_execution = CriticalActionExecution.objects.get(action_code='rf31.demo.failure')

        invalid_policy.full_clean()
        with pytest.raises(ValidationError) as same_status_error:
            same_status_history.full_clean()
        alternate_actor_history.full_clean()

        success_execution.refresh_from_db()
        assert policy.require_transaction is True
        assert status_history.actor == owner
        assert status_history.target_model == 'GovernanceParameter'
        assert success_execution.status == CriticalActionExecution.Status.SUCCEEDED
        assert success_execution.completed_at is not None
        assert success_execution.safe_context == {'visible': 'ok'}
        assert failed_execution.status == CriticalActionExecution.Status.FAILED
        assert 'Falha proposital' in failed_execution.error_message
        assert not GovernanceParameter.objects.filter(key='rf31_should_rollback').exists()
        assert GovernanceParameter.objects.filter(key='rf31_transaction_guard').exists()
        assert GovernanceAuditLog.objects.filter(action='critical_action.succeeded').exists()
        assert GovernanceAuditLog.objects.filter(action='critical_action.failed').exists()
        assert 'new_status' in same_status_error.value.message_dict


@pytest.mark.legacy_api_permissions
class ComplianceApiTests(TestCase):
    def test_rf31_api_uses_global_scope_and_evaluates_module_readiness(self):
        from compliance.models import ComplianceChecklistItem, TransversalRequirementPolicy

        user = create_user('compliance.api@example.com')
        other_user = create_user('compliance.other.api@example.com')
        TransversalRequirementPolicy.objects.create(
            code='RF31-OTHER',
            title='Politica secundaria',
            source_module=OperationalModule.GOVERNANCE,
            owner=other_user,
        )
        client = APIClient()
        client.force_authenticate(user)

        policy_response = client.post(
            '/api/compliance/policies/',
            {
                'code': 'RF31-GOV-API',
                'title': 'Politica RF-31 via API',
                'description': 'Exige single-instance, permissao, auditoria, status, transacao e mensagens.',
                'source_module': OperationalModule.GOVERNANCE,
                'enforcement_level': TransversalRequirementPolicy.EnforcementLevel.BLOCKING,
                'require_single_instance_scope': True,
                'require_permission_check': True,
                'require_audit_log': True,
                'require_status_history': True,
                'require_transaction': True,
                'require_ptbr_messages': True,
            },
            format='json',
        )
        evaluate_response = client.post(
            '/api/compliance/checklist-items/evaluate_module/',
            {'module': OperationalModule.GOVERNANCE},
            format='json',
        )
        policies_list = client.get('/api/compliance/policies/')
        checklist_list = client.get('/api/compliance/checklist-items/')
        history_list = client.get('/api/compliance/status-history/')
        critical_actions_list = client.get('/api/compliance/critical-actions/')

        assert policy_response.status_code == 201
        assert 'tenant' not in policy_response.json()
        assert policy_response.json()['owner'] == user.id
        assert evaluate_response.status_code == 200
        assert evaluate_response.json()['module'] == OperationalModule.GOVERNANCE
        assert evaluate_response.json()['passed'] is True
        assert {item['check_type'] for item in evaluate_response.json()['items']} >= {
            ComplianceChecklistItem.CheckType.SINGLE_INSTANCE_SCOPE,
            ComplianceChecklistItem.CheckType.PERMISSION,
            ComplianceChecklistItem.CheckType.AUDIT,
            ComplianceChecklistItem.CheckType.DOCS,
            ComplianceChecklistItem.CheckType.MENU,
            ComplianceChecklistItem.CheckType.TESTS,
        }
        assert 'Politica secundaria' in {item['title'] for item in policies_list.json()['results']}
        assert checklist_list.status_code == 200
        assert history_list.status_code == 200
        assert critical_actions_list.status_code == 200
        assert (
            ComplianceChecklistItem.objects.filter(
                status=ComplianceChecklistItem.Status.PASS
            ).count()
            >= 6
        )


class ComplianceCommandTests(TestCase):
    def test_rf31_command_checks_transversal_compliance_for_module(self):
        from compliance.models import ComplianceChecklistItem

        stdout = StringIO()

        call_command(
            'check_transversal_compliance',
            module=OperationalModule.GOVERNANCE,
            stdout=stdout,
        )

        output = stdout.getvalue()
        assert 'governance' in output
        assert 'aprovado=True' in output
        assert (
            ComplianceChecklistItem.objects.filter(
                source_module=OperationalModule.GOVERNANCE,
                status=ComplianceChecklistItem.Status.PASS,
            ).count()
            >= 6
        )
