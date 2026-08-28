from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from unittest.mock import patch

from base.ui.presentation import ProgressMetric
from base.ui.views import DashboardHubView
from base.ui.registry import get_module


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
        self.assertTrue(
            {'production', 'inventory', 'quality', 'finance'}.issubset(modules)
        )


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

    def test_dashboard_filters_kpis_without_model_view_permission(self):
        response = self.client.get(reverse('app:dashboard_hub', args=['executive']))

        self.assertContains(response, 'Ordens ativas')
        self.assertNotContains(response, 'Lotes em estoque')

    def test_navigation_lists_dashboards_by_django_permissions(self):
        response = self.client.get(reverse('app:index'))

        self.assertContains(response, reverse('app:dashboard_hub', args=['executive']))
        self.assertContains(response, reverse('app:dashboard_hub', args=['operations']))
        self.assertContains(response, reverse('app:dashboard_hub', args=['quality']))
        self.assertContains(response, reverse('app:dashboard_hub', args=['finance']))

        dashboard_response = self.client.get(reverse('app:dashboard_hub', args=['executive']))
        self.assertContains(dashboard_response, reverse('app:dashboard_hub', args=['quality']))
