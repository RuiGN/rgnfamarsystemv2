from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from base.roles import OperationalRole


User = get_user_model()


def create_user(email):
    return User.objects.create_user(username=email, email=email, password='S3curePass!123')


class WorkflowModelTests(TestCase):
    def test_rf27_notification_center_email_internal_and_async_job_progress(self):
        from workflow.models import AsyncJobStatus, WorkflowHistory, WorkflowNotification

        user = create_user('workflow.user@example.com')
        notification = WorkflowNotification.objects.create(
            category=WorkflowNotification.Category.APPROVAL,
            channel=WorkflowNotification.Channel.INTERNAL,
            recipient=user,
            title='Aprovação pendente',
            message='Existe uma aprovação aguardando decisão.',
            source_module=WorkflowNotification.SourceModule.QUALITY,
            source_model='QualityReview',
            source_record_id='123',
            criticality=WorkflowNotification.Criticality.HIGH,
            due_at=timezone.now() + timedelta(days=1),
        )
        email_notification = WorkflowNotification.objects.create(
            category=WorkflowNotification.Category.ALERT,
            channel=WorkflowNotification.Channel.EMAIL,
            recipient=user,
            title='Alerta transacional',
            message='Email transacional configurado para envio.',
            source_module=WorkflowNotification.SourceModule.FISCAL,
            source_model='FiscalDocument',
            source_record_id='456',
            criticality=WorkflowNotification.Criticality.MEDIUM,
        )
        notification.send()
        notification.mark_read(user=user)
        email_notification.send()
        job = AsyncJobStatus.objects.create(
            task_name='reports.tasks.generate_report_execution',
            title='Geração de relatório',
            loading_message='Gerando relatório em segundo plano.',
            source_module=WorkflowNotification.SourceModule.QUALITY,
            source_model='ReportExecution',
            source_record_id='REP-001',
            requested_by=user,
        )
        job.start(task_id='celery-rf27-001')
        job.update_progress(45, message='Processando dados de qualidade.')
        job.complete(
            result_reference='reports/planta-recife/rep-001.csv', message='Relatório concluído.'
        )
        job.refresh_from_db()

        assert notification.status == WorkflowNotification.Status.READ
        assert notification.read_at is not None
        assert email_notification.status == WorkflowNotification.Status.SENT
        assert email_notification.sent_at is not None
        assert job.status == AsyncJobStatus.Status.COMPLETED
        assert job.progress_percent == 100
        assert job.result_reference.endswith('.csv')
        assert WorkflowNotification.objects.filter(
            recipient=user,
            category=WorkflowNotification.Category.TASK_COMPLETED,
            source_record_id=str(job.id),
        ).exists()
        assert WorkflowHistory.objects.filter(
            async_job=job, action=WorkflowHistory.Action.COMPLETED
        ).exists()

    def test_rf27_approval_queue_delegation_comments_attachments_and_history(self):
        from workflow.models import (
            ApprovalQueue,
            ApprovalTask,
            WorkflowAttachment,
            WorkflowComment,
            WorkflowDelegation,
            WorkflowHistory,
            WorkflowNotification,
        )

        requester = create_user('workflow.requester@example.com')
        qa_approver = create_user('workflow.qa@example.com')
        substitute = create_user('workflow.substitute@example.com')
        finance_user = create_user('workflow.finance@example.com')
        other_user = create_user('workflow.other@example.com')
        quality_group, _ = Group.objects.get_or_create(name=OperationalRole.QUALITY)
        finance_group, _ = Group.objects.get_or_create(name=OperationalRole.FINANCE)
        qa_approver.groups.add(quality_group)
        finance_user.groups.add(finance_group)
        queue = ApprovalQueue.objects.create(
            code='APV-QUAL-001',
            name='Aprovação de qualidade crítica',
            module=WorkflowNotification.SourceModule.QUALITY,
            area='Garantia da Qualidade',
            profile_role=OperationalRole.QUALITY,
            criticality=WorkflowNotification.Criticality.HIGH,
            approval_limit=Decimal('10000.00'),
        )
        task = ApprovalTask.objects.create(
            queue=queue,
            title='Aprovar desvio crítico',
            description='Decisão de QA para desvio crítico.',
            source_module=WorkflowNotification.SourceModule.QUALITY,
            source_model='QualityEvent',
            source_record_id='DEV-001',
            area='Garantia da Qualidade',
            criticality=WorkflowNotification.Criticality.HIGH,
            amount=Decimal('5000.00'),
            requested_by=requester,
            assigned_to=qa_approver,
            due_at=timezone.now() + timedelta(days=2),
        )
        delegation = WorkflowDelegation.objects.create(
            from_user=qa_approver,
            to_user=substitute,
            module=WorkflowNotification.SourceModule.QUALITY,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(days=3),
            reason='Substituição temporária em férias.',
        )
        task.add_comment(author=requester, comment='Priorizar análise regulatória.')
        task.attach_file(
            file_name='evidencia-desvio.pdf',
            file_reference='workflow/evidencias/dev-001.pdf',
            content_hash='sha256:dev-001',
            uploaded_by=requester,
        )

        with pytest.raises(ValidationError) as denied:
            task.approve(user=finance_user, comments='Tentativa indevida.')
        task.approve(user=substitute, comments='Aprovado via delegação temporária.')
        task.refresh_from_db()
        other_queue = ApprovalQueue.objects.create(
            code='APV-OUTRO-001',
            name='Fila alternativa',
            module=WorkflowNotification.SourceModule.QUALITY,
            area='QA',
            profile_role=OperationalRole.QUALITY,
        )
        invalid_task = ApprovalTask(
            queue=other_queue,
            title='Inválida',
            source_module=WorkflowNotification.SourceModule.QUALITY,
            source_model='QualityEvent',
            source_record_id='DEV-999',
            requested_by=requester,
            assigned_to=other_user,
        )

        assert (
            queue.matches(
                qa_approver,
                WorkflowNotification.SourceModule.QUALITY,
                'Garantia da Qualidade',
                WorkflowNotification.Criticality.HIGH,
                Decimal('5000.00'),
            )
            is True
        )
        assert (
            queue.matches(
                finance_user,
                WorkflowNotification.SourceModule.QUALITY,
                'Garantia da Qualidade',
                WorkflowNotification.Criticality.HIGH,
                Decimal('5000.00'),
            )
            is False
        )
        assert 'permission' in denied.value.message_dict
        assert delegation.applies_to(task) is True
        assert task.status == ApprovalTask.Status.APPROVED
        assert task.decided_by == substitute
        assert task.decided_at is not None
        assert WorkflowComment.objects.filter(task=task, author=requester).exists()
        assert WorkflowAttachment.objects.filter(task=task, content_hash='sha256:dev-001').exists()
        assert set(WorkflowHistory.objects.filter(task=task).values_list('action', flat=True)) >= {
            WorkflowHistory.Action.CREATED,
            WorkflowHistory.Action.COMMENTED,
            WorkflowHistory.Action.ATTACHED,
            WorkflowHistory.Action.APPROVED,
        }
        with pytest.raises(ValidationError):
            invalid_task.full_clean()


@pytest.mark.legacy_api_permissions
class WorkflowApiTests(TestCase):
    def test_rf27_api_uses_global_scope_and_executes_approval_delegation_notifications_and_async_job(
        self,
    ):
        from workflow.models import (
            ApprovalQueue,
            ApprovalTask,
            AsyncJobStatus,
            WorkflowHistory,
            WorkflowNotification,
        )

        requester = create_user('workflow.api.requester@example.com')
        approver = create_user('workflow.api.approver@example.com')
        substitute = create_user('workflow.api.substitute@example.com')
        other_user = create_user('workflow.api.other@example.com')
        quality_group, _ = Group.objects.get_or_create(name=OperationalRole.QUALITY)
        approver.groups.add(quality_group)
        ApprovalQueue.objects.create(
            code='APV-OUTRO-API',
            name='Fila alternativa',
            module=WorkflowNotification.SourceModule.QUALITY,
            area='QA',
            profile_role=OperationalRole.QUALITY,
            created_by=other_user,
        )
        client = APIClient()
        client.force_authenticate(requester)

        queue_response = client.post(
            '/api/workflow/approval-queues/',
            {
                'code': 'APV-QA-API',
                'name': 'Fila QA API',
                'module': WorkflowNotification.SourceModule.QUALITY,
                'area': 'Garantia da Qualidade',
                'profile_role': OperationalRole.QUALITY,
                'criticality': WorkflowNotification.Criticality.HIGH,
                'approval_limit': '10000.00',
            },
            format='json',
        )
        queue_id = queue_response.json()['id']
        task_response = client.post(
            '/api/workflow/approval-tasks/',
            {
                'queue': queue_id,
                'title': 'Aprovar revisão QA',
                'description': 'Aprovação via API.',
                'source_module': WorkflowNotification.SourceModule.QUALITY,
                'source_model': 'QAReview',
                'source_record_id': 'QA-001',
                'area': 'Garantia da Qualidade',
                'criticality': WorkflowNotification.Criticality.HIGH,
                'amount': '5000.00',
                'assigned_to': approver.id,
                'due_at': (timezone.now() + timedelta(days=1)).isoformat(),
            },
            format='json',
        )
        task_id = task_response.json()['id']
        comment_response = client.post(
            '/api/workflow/comments/',
            {'task': task_id, 'comment': 'Comentário de contexto para aprovação.'},
            format='json',
        )
        attachment_response = client.post(
            '/api/workflow/attachments/',
            {
                'task': task_id,
                'file_name': 'contexto.pdf',
                'file_reference': 'workflow/contexto.pdf',
                'content_hash': 'sha256:contexto',
            },
            format='json',
        )
        delegation_response = client.post(
            '/api/workflow/delegations/',
            {
                'from_user': approver.id,
                'to_user': substitute.id,
                'module': WorkflowNotification.SourceModule.QUALITY,
                'starts_at': (timezone.now() - timedelta(hours=1)).isoformat(),
                'ends_at': (timezone.now() + timedelta(days=2)).isoformat(),
                'reason': 'Substituição temporária.',
            },
            format='json',
        )
        client.force_authenticate(substitute)
        approve_response = client.post(
            f'/api/workflow/approval-tasks/{task_id}/approve/',
            {'comments': 'Aprovado por substituição.'},
            format='json',
        )
        client.force_authenticate(requester)
        job_response = client.post(
            '/api/workflow/async-jobs/',
            {
                'task_name': 'reports.tasks.generate_report_execution',
                'title': 'Geração assíncrona',
                'loading_message': 'Processando sem bloquear navegação.',
                'source_module': WorkflowNotification.SourceModule.QUALITY,
                'source_model': 'ReportExecution',
                'source_record_id': 'REP-API-001',
            },
            format='json',
        )
        job_id = job_response.json()['id']
        start_response = client.post(
            f'/api/workflow/async-jobs/{job_id}/start/',
            {'task_id': 'celery-api-rf27'},
            format='json',
        )
        progress_response = client.post(
            f'/api/workflow/async-jobs/{job_id}/update_progress/',
            {'progress_percent': 50, 'message': 'Metade concluída.'},
            format='json',
        )
        complete_response = client.post(
            f'/api/workflow/async-jobs/{job_id}/complete/',
            {'result_reference': 'reports/rep-api-001.csv', 'message': 'Finalizado.'},
            format='json',
        )
        notifications_response = client.get('/api/workflow/notifications/')
        queues_response = client.get('/api/workflow/approval-queues/')
        history_response = client.get('/api/workflow/history/')

        assert queue_response.status_code == 201
        assert task_response.status_code == 201
        assert task_response.json()['requested_by'] == requester.id
        assert comment_response.status_code == 201
        assert attachment_response.status_code == 201
        assert delegation_response.status_code == 201
        assert approve_response.status_code == 200
        assert approve_response.json()['status'] == ApprovalTask.Status.APPROVED
        assert job_response.status_code == 201
        assert start_response.status_code == 200
        assert progress_response.json()['progress_percent'] == 50
        assert complete_response.json()['status'] == AsyncJobStatus.Status.COMPLETED
        assert complete_response.json()['progress_percent'] == 100
        assert 'Fila alternativa' in {item['name'] for item in queues_response.json()['results']}
        assert notifications_response.status_code == 200
        assert any(
            item['category'] == WorkflowNotification.Category.TASK_COMPLETED
            for item in notifications_response.json()['results']
        )
        assert history_response.status_code == 200
        assert WorkflowHistory.objects.filter(action=WorkflowHistory.Action.APPROVED).exists()
