from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from base.roles import OperationalRole


User = get_user_model()


def create_user(email):
    return User.objects.create_user(username=email, email=email, password='S3curePass!123')


def grant_permissions(user, *permission_labels):
    permissions = []
    for permission_label in permission_labels:
        app_label, codename = permission_label.split('.', 1)
        permissions.append(
            Permission.objects.get(
                content_type__app_label=app_label,
                codename=codename,
            )
        )
    user.user_permissions.add(*permissions)


class ReportingModelTests(TestCase):
    def test_rf26_dashboard_profile_filters_export_and_modules_are_controlled(self):
        from reports.models import (
            DashboardWidget,
            DashboardWorkspace,
            ReportDefinition,
            ReportExecution,
        )

        owner = create_user('reports.owner@example.com')
        quality_user = create_user('reports.quality@example.com')
        finance_user = create_user('reports.finance@example.com')
        quality_group, _ = Group.objects.get_or_create(name=OperationalRole.QUALITY)
        finance_group, _ = Group.objects.get_or_create(name=OperationalRole.FINANCE)
        quality_user.groups.add(quality_group)
        finance_user.groups.add(finance_group)
        grant_permissions(quality_user, 'reports.add_reportexecution')
        dashboard = DashboardWorkspace.objects.create(
            code='DASH-QUALIDADE',
            title='Dashboard Qualidade',
            module=ReportDefinition.Module.QUALITY,
            profile_role=OperationalRole.QUALITY,
            owner=owner,
            layout={'columns': 12},
        )
        DashboardWidget.objects.create(
            dashboard=dashboard,
            title='OOS em aberto',
            widget_type=DashboardWidget.WidgetType.KPI,
            module=ReportDefinition.Module.QUALITY,
            position_row=1,
            position_column=1,
            width=4,
            height=2,
            configuration={'metric': 'open_oos'},
        )
        definition = ReportDefinition.objects.create(
            code='REL-QUAL-001',
            title='Indicadores de qualidade',
            module=ReportDefinition.Module.QUALITY,
            category=ReportDefinition.Category.INDICATOR,
            allowed_export_formats=[
                ReportExecution.ExportFormat.PDF,
                ReportExecution.ExportFormat.CSV,
            ],
            default_filters={'area': 'Controle de Qualidade'},
            required_filters=['period_start', 'period_end', 'status'],
            query_config={'source': 'quality.QualitySample', 'metrics': ['requested', 'approved']},
            owner=owner,
        )

        with pytest.raises(ValidationError) as unsupported_filter:
            definition.create_execution(
                filters={
                    'period_start': '2026-07-01',
                    'period_end': '2026-07-31',
                    'unsupported': 'x',
                },
                export_format=ReportExecution.ExportFormat.PDF,
                requested_by=owner,
            )
        with pytest.raises(ValidationError) as invalid_period:
            definition.create_execution(
                filters={
                    'period_start': '2026-08-01',
                    'period_end': '2026-07-31',
                    'status': 'approved',
                },
                export_format=ReportExecution.ExportFormat.PDF,
                requested_by=owner,
            )
        execution = definition.create_execution(
            filters={
                'period_start': '2026-07-01',
                'period_end': '2026-07-31',
                'status': 'approved',
                'product': 'PRD-001',
            },
            export_format=ReportExecution.ExportFormat.CSV,
            requested_by=quality_user,
        )
        execution.run(user=quality_user)
        execution.refresh_from_db()

        assert dashboard.available_to(quality_user) is True
        assert dashboard.available_to(finance_user) is False
        assert 'unsupported' in unsupported_filter.value.message_dict
        assert 'period_end' in invalid_period.value.message_dict
        assert execution.status == ReportExecution.Status.COMPLETED
        assert execution.result_reference.endswith('.enc')
        assert execution.result_file.file_name.endswith('.csv')
        assert execution.content_hash.startswith('sha256:')
        assert execution.filters['area'] == 'Controle de Qualidade'
        assert execution.filters['product'] == 'PRD-001'
        assert set(ReportDefinition.Module.values) >= {
            'production',
            'mrp',
            'inventory',
            'traceability',
            'costing',
            'finance',
            'fiscal',
            'quality',
            'audit',
            'capa',
            'deviations',
            'risks',
            'regulatory',
            'pharmacovigilance',
        }

    def test_rf26_report_schedule_uses_celery_task_metadata_and_notifies_completion(self):
        from reports.models import (
            ReportDefinition,
            ReportExecution,
            ReportNotification,
            ReportSchedule,
        )

        owner = create_user('reports.scheduler@example.com')
        recipient = create_user('reports.recipient@example.com')
        grant_permissions(owner, 'reports.add_reportexecution')
        definition = ReportDefinition.objects.create(
            code='REL-FISCAL-001',
            title='Apuração fiscal mensal',
            module=ReportDefinition.Module.FISCAL,
            category=ReportDefinition.Category.OPERATIONAL,
            allowed_export_formats=[
                ReportExecution.ExportFormat.PDF,
                ReportExecution.ExportFormat.XLSX,
                ReportExecution.ExportFormat.CSV,
            ],
            required_filters=['period_start', 'period_end'],
            owner=owner,
        )
        schedule = ReportSchedule.objects.create(
            definition=definition,
            name='Apuração fiscal recorrente',
            frequency=ReportSchedule.Frequency.MONTHLY,
            filters={'period_start': '2026-07-01', 'period_end': '2026-07-31', 'status': 'posted'},
            export_format=ReportExecution.ExportFormat.XLSX,
            next_run_at=timezone.now() + timedelta(minutes=5),
            owner=owner,
        )
        schedule.recipients.add(recipient)

        execution = schedule.trigger_now(user=owner, run_immediately=True)
        schedule.refresh_from_db()
        execution.refresh_from_db()

        assert execution.schedule == schedule
        assert execution.celery_task_name == 'reports.tasks.generate_report_execution'
        assert execution.export_format == ReportExecution.ExportFormat.XLSX
        assert execution.status == ReportExecution.Status.COMPLETED
        assert execution.completed_at is not None
        assert schedule.last_run_at is not None
        assert schedule.next_run_at.date() >= timezone.localdate() + timedelta(days=29)
        assert ReportNotification.objects.filter(
            execution=execution,
            recipient=recipient,
            status=ReportNotification.Status.SENT,
        ).exists()


@pytest.mark.legacy_api_permissions
class ReportingApiTests(TestCase):
    def test_rf26_api_runs_report_and_triggers_schedule_with_global_permissions(self):
        from reports.models import (
            DashboardWorkspace,
            ReportDefinition,
            ReportExecution,
            ReportNotification,
            ReportSchedule,
        )

        user = create_user('reports.api@example.com')
        other_user = create_user('reports.other@example.com')
        ReportDefinition.objects.create(
            code='REL-OUTRO-001',
            title='Relatório secundario',
            module=ReportDefinition.Module.FINANCE,
            category=ReportDefinition.Category.INDICATOR,
            allowed_export_formats=[ReportExecution.ExportFormat.PDF],
            owner=other_user,
        )
        client = APIClient()
        client.force_authenticate(user)

        dashboard_response = client.post(
            '/api/reports/dashboards/',
            {
                'code': 'DASH-EXEC',
                'title': 'Dashboard executivo',
                'module': ReportDefinition.Module.FINANCE,
                'profile_role': OperationalRole.FINANCE,
                'layout': {'columns': 12},
            },
            format='json',
        )
        invalid_definition_response = client.post(
            '/api/reports/definitions/',
            {
                'code': 'REL-INV-INVALIDO',
                'title': 'Relatório inválido',
                'module': ReportDefinition.Module.INVENTORY,
                'category': ReportDefinition.Category.OPERATIONAL,
                'allowed_export_formats': [ReportExecution.ExportFormat.PDF],
                'required_filters': ['foo'],
            },
            format='json',
        )
        definition_response = client.post(
            '/api/reports/definitions/',
            {
                'code': 'REL-EST-API-001',
                'title': 'Posição de estoque',
                'module': ReportDefinition.Module.INVENTORY,
                'category': ReportDefinition.Category.OPERATIONAL,
                'allowed_export_formats': [
                    ReportExecution.ExportFormat.PDF,
                    ReportExecution.ExportFormat.CSV,
                ],
                'default_filters': {'area': 'Almoxarifado'},
                'required_filters': ['period_start', 'period_end'],
                'query_config': {'source': 'inventory.StockBalance'},
            },
            format='json',
        )
        definition_id = definition_response.json()['id']
        run_response = client.post(
            f'/api/reports/definitions/{definition_id}/run/',
            {
                'filters': {
                    'period_start': '2026-07-01',
                    'period_end': '2026-07-31',
                    'product': 'PRD-001',
                    'lot': 'LOTE-001',
                    'responsible': str(user.id),
                },
                'export_format': ReportExecution.ExportFormat.CSV,
            },
            format='json',
        )
        schedule_response = client.post(
            '/api/reports/schedules/',
            {
                'definition': definition_id,
                'name': 'Estoque diário',
                'frequency': ReportSchedule.Frequency.DAILY,
                'filters': {
                    'period_start': '2026-07-01',
                    'period_end': '2026-07-31',
                    'status': 'available',
                },
                'export_format': ReportExecution.ExportFormat.PDF,
                'next_run_at': (timezone.now() + timedelta(minutes=10)).isoformat(),
                'recipients': [user.id],
            },
            format='json',
        )
        trigger_response = client.post(
            f'/api/reports/schedules/{schedule_response.json()["id"]}/trigger_now/',
        )
        definitions_list = client.get('/api/reports/definitions/')
        notifications_list = client.get('/api/reports/notifications/')

        assert dashboard_response.status_code == 201
        assert 'tenant' not in dashboard_response.json()
        assert DashboardWorkspace.objects.get(pk=dashboard_response.json()['id']).owner == user
        assert invalid_definition_response.status_code == 400
        assert definition_response.status_code == 201
        assert 'tenant' not in definition_response.json()
        assert run_response.status_code == 201
        assert run_response.json()['status'] == ReportExecution.Status.COMPLETED
        assert 'result_reference' not in run_response.json()
        assert run_response.json()['filters']['area'] == 'Almoxarifado'
        assert schedule_response.status_code == 201
        assert trigger_response.status_code == 201
        assert trigger_response.json()['status'] == ReportExecution.Status.COMPLETED
        assert 'Relatório secundario' in {
            item['title'] for item in definitions_list.json()['results']
        }
        assert notifications_list.status_code == 200
        assert ReportNotification.objects.filter(
            recipient=user, status=ReportNotification.Status.SENT
        ).exists()
