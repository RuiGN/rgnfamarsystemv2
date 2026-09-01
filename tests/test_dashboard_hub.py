import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from base.ui.presentation import ProgressMetric
from base.ui.views import DashboardHubView
from base.ui.registry import get_module
from finance.models import FinancialTitle
from inventory.models import StockLot
from production.models import ProductionOrder
from quality.models import LaboratoryInvestigation, QualityAnalysis, QualitySample


def grant_module_view(user, module_slug):
    model = get_module(module_slug).resources[0].model
    permission = Permission.objects.get(
        content_type__app_label=model._meta.app_label,
        content_type__model=model._meta.model_name,
        codename=f'view_{model._meta.model_name}',
    )
    user.user_permissions.add(permission)


class DashboardHubContractTests(SimpleTestCase):
    def test_all_dashboard_routes_are_named_and_have_module_mapping(self):
        expected = {'executive', 'operations', 'inventory', 'quality', 'finance'}
        self.assertEqual(set(DashboardHubView.dashboards), expected)
        for slug in expected:
            self.assertEqual(
                reverse('app:dashboard_hub', kwargs={'dashboard_slug': slug}),
                f'/app/dashboards/{slug}/',
            )

    def test_dashboard_configuration_uses_existing_modules(self):
        modules = {config['module'] for config in DashboardHubView.dashboards.values()}
        self.assertTrue({'production', 'inventory', 'quality', 'finance'}.issubset(modules))


class DashboardHubAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='dashboard@example.com',
            email='dashboard@example.com',
            password='DashboardSecure!123',
        )
        for module_slug in ('production', 'quality', 'finance'):
            grant_module_view(self.user, module_slug)
        self.client.force_login(self.user)

    def test_dashboard_renders_without_active_scope(self):
        response = self.client.get(reverse('app:dashboard_hub', args=['executive']))

        self.assertEqual(response.status_code, 200)

    def test_dashboard_renders_accessible_progress_metric_when_target_exists(self):
        data = {
            'kpis': [
                ProgressMetric(
                    'Em execução',
                    1,
                    'feather-activity',
                    'success',
                    'Produção',
                    reverse('app:resource_list', args=('production', 'orders')),
                    2,
                )
            ],
            'chart': {'labels': [], 'series': []},
            'table': [],
        }
        with patch.object(DashboardHubView, '_build_data', return_value=data):
            response = self.client.get(reverse('app:dashboard_hub', args=['operations']))

        self.assertContains(response, 'data-ui="progress-metric"')
        self.assertContains(response, 'role="progressbar"')
        self.assertContains(response, 'aria-valuenow="')
        self.assertContains(response, 'Ver detalhes')

    def test_all_dashboards_render_timestamp_and_complete_accessible_chart_summary(self):
        chart = {'labels': ['Em análise', 'Aprovado'], 'series': [3, 7]}
        data = {'kpis': [], 'chart': chart, 'table': []}
        grant_module_view(self.user, 'inventory')

        for slug, dashboard in DashboardHubView.dashboards.items():
            with (
                self.subTest(dashboard=slug),
                patch.object(DashboardHubView, '_build_data', return_value=data),
            ):
                response = self.client.get(reverse('app:dashboard_hub', args=[slug]))

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '<time datetime=', html=False)
            self.assertContains(response, 'Atualizado em')
            self.assertNotContains(response, 'Atualizado agora')
            timestamp = re.search(r'<time datetime="([^"]+)"', response.content.decode())
            self.assertIsNotNone(timestamp)
            self.assertIsNotNone(parse_datetime(timestamp.group(1)))
            self.assertContains(
                response,
                f'aria-label="Gráfico de distribuição dos indicadores do dashboard {dashboard["title"]}"',
                html=False,
            )
            self.assertContains(response, 'role="img"', html=False)
            self.assertContains(response, 'Resumo textual do gráfico')
            for label, value in zip(chart['labels'], chart['series'], strict=False):
                self.assertContains(response, label)
                self.assertContains(response, f'>{value}<', html=False)

    def test_dashboard_context_exposes_localized_timestamp_and_chart_rows_without_changing_chart(
        self,
    ):
        chart = {'labels': ['Pendente'], 'series': [4]}
        data = {'kpis': [], 'chart': chart, 'table': []}

        with patch.object(DashboardHubView, '_build_data', return_value=data):
            response = self.client.get(reverse('app:dashboard_hub', args=['operations']))

        self.assertEqual(response.context['dashboard_data']['chart'], chart)
        self.assertEqual(response.context['chart_rows'], (('Pendente', 4),))
        self.assertTrue(timezone.is_aware(response.context['generated_at']))

    def test_dashboard_filters_kpis_without_model_view_permission(self):
        forbidden_models = (StockLot, QualitySample, LaboratoryInvestigation)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('app:dashboard_hub', args=['executive']))

        self.assertContains(response, 'Ordens ativas')
        self.assertNotContains(response, 'Lotes em estoque')
        self.assertNotContains(response, 'Pendências de qualidade')
        self.assertNotContains(response, 'Investigações abertas')
        sql = '\n'.join(query['sql'].lower() for query in queries)
        for model in forbidden_models:
            with self.subTest(model=model.__name__):
                self.assertNotIn(model._meta.db_table.lower(), sql)

    def test_dashboard_builders_do_not_query_any_domain_model_without_exact_permission(self):
        user = get_user_model().objects.create_user(
            username='dashboard-sem-escopo@example.com',
            email='dashboard-sem-escopo@example.com',
            password='DashboardSecure!123',
        )
        models = (
            ProductionOrder,
            StockLot,
            QualitySample,
            QualityAnalysis,
            LaboratoryInvestigation,
            FinancialTitle,
        )
        view = DashboardHubView()

        with CaptureQueriesContext(connection) as queries:
            for slug in DashboardHubView.dashboards:
                data = view._build_data(slug, user)
                self.assertEqual(
                    data, {'kpis': [], 'chart': {'labels': [], 'series': []}, 'table': []}
                )

        sql = '\n'.join(query['sql'].lower() for query in queries)
        for model in models:
            with self.subTest(model=model.__name__):
                self.assertNotIn(model._meta.db_table.lower(), sql)

    def test_navigation_lists_dashboards_by_django_permissions(self):
        response = self.client.get(reverse('app:index'))

        self.assertContains(response, reverse('app:dashboard_hub', args=['executive']))
        self.assertContains(response, reverse('app:dashboard_hub', args=['operations']))
        self.assertContains(response, reverse('app:dashboard_hub', args=['quality']))
        self.assertContains(response, reverse('app:dashboard_hub', args=['finance']))

        dashboard_response = self.client.get(reverse('app:dashboard_hub', args=['executive']))
        self.assertContains(dashboard_response, reverse('app:dashboard_hub', args=['quality']))
