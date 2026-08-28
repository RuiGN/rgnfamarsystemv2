from dataclasses import FrozenInstanceError

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from base.ui.views import WorkspaceView
from base.ui.workspaces import WORKSPACES, get_workspace
from production.models import ProductionOrder
from workflow.models import WorkflowNotification


def grant_view_permission(user, model):
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label=model._meta.app_label,
            content_type__model=model._meta.model_name,
            codename=f'view_{model._meta.model_name}',
        )
    )


class WorkspaceConfigurationTests(SimpleTestCase):
    def test_registry_contains_the_three_approved_workspaces(self):
        self.assertEqual(set(WORKSPACES), {'operations', 'quality', 'workflow'})
        self.assertEqual(get_workspace('operations').module_slug, 'production')
        self.assertEqual(get_workspace('quality').module_slug, 'quality')
        self.assertEqual(get_workspace('workflow').module_slug, 'workflow')

    def test_unknown_workspace_returns_none(self):
        self.assertIsNone(get_workspace('missing'))

    def test_workspace_configuration_is_immutable(self):
        workspace = get_workspace('operations')

        with self.assertRaises(FrozenInstanceError):
            workspace.title = 'Alterado'

    def test_workspace_navigation_metadata_and_urls_are_centralized(self):
        expectations = {
            'operations': (
                'app:operations_workspace',
                'Cockpit operacional',
                'feather-activity',
                10,
                '/app/workspaces/operations/',
            ),
            'quality': (
                'app:quality_workspace',
                'Cockpit de qualidade',
                'feather-check-square',
                20,
                '/app/workspaces/quality/',
            ),
            'workflow': (
                'app:workflow_workspace',
                'Central de workflow',
                'feather-git-pull-request',
                30,
                '/app/workspaces/workflow/',
            ),
        }

        for slug, expected in expectations.items():
            with self.subTest(slug=slug):
                workspace = get_workspace(slug)
                actual = (
                    workspace.route_name,
                    workspace.navigation_label,
                    workspace.icon,
                    workspace.order,
                    workspace.navigation_url,
                )
                self.assertEqual(actual, expected)

    def test_legacy_workspace_templates_are_removed_and_contract_is_documented(self):
        from pathlib import Path

        legacy_templates = (
            Path('templates/workspaces/operations.html'),
            Path('templates/workspaces/quality.html'),
            Path('templates/workspaces/workflow.html'),
        )
        documentation = Path('TEMPLATES.md').read_text()

        self.assertTrue(all(not path.exists() for path in legacy_templates))
        self.assertIn('workspaces/workspace.html', documentation)
        self.assertIn('/app/', documentation)
        self.assertIn('WorkspaceConfig', documentation)


class WorkspaceContentBuilderTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='workspace-builder@example.com',
            email='workspace-builder@example.com',
            password='WorkspaceSecure!123',
        )

    def request_for(self, user=None):
        request = RequestFactory().get('/app/workspaces/')
        request.user = user or self.admin
        return request

    def test_builders_preserve_metric_labels_and_primary_links(self):
        expectations = {
            'operations': (
                ('Ordens em execução', 'Lotes em estoque', 'Amostras pendentes'),
                '/app/production/orders/',
            ),
            'quality': (
                ('Amostras em análise', 'Análises pendentes', 'Investigações abertas'),
                '/app/quality/samples/',
            ),
            'workflow': (
                ('Aprovações pendentes', 'Notificações não lidas', 'Jobs em execução'),
                '/app/workflow/tasks/',
            ),
        }

        for slug, (labels, primary_url) in expectations.items():
            with self.subTest(slug=slug):
                content = get_workspace(slug).build_content(self.request_for())
                self.assertEqual(tuple(metric.label for metric in content.metrics), labels)
                self.assertEqual(content.metrics[0].url, primary_url)

    def test_workflow_notifications_are_scoped_to_request_user(self):
        other_user = get_user_model().objects.create_user(
            username='workspace-other@example.com',
            email='workspace-other@example.com',
            password='WorkspaceSecure!123',
        )
        for recipient in (self.admin, other_user, other_user):
            WorkflowNotification.objects.create(
                category=WorkflowNotification.Category.ALERT,
                recipient=recipient,
                title='Alerta de teste',
                message='Mensagem de teste',
                source_module=WorkflowNotification.SourceModule.QUALITY,
            )

        content = get_workspace('workflow').build_content(self.request_for())
        metric = next(
            item for item in content.metrics if item.label == 'Notificações não lidas'
        )

        self.assertEqual(metric.value, 1)


class WorkspaceAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='workspace@example.com',
            email='workspace@example.com',
            password='WorkspaceSecure!123',
        )
        self.admin = get_user_model().objects.create_superuser(
            username='workspace-admin@example.com',
            email='workspace-admin@example.com',
            password='WorkspaceSecure!123',
        )

    def test_existing_route_names_and_paths_are_preserved(self):
        self.assertEqual(reverse('app:operations_workspace'), '/app/workspaces/operations/')
        self.assertEqual(reverse('app:quality_workspace'), '/app/workspaces/quality/')
        self.assertEqual(reverse('app:workflow_workspace'), '/app/workspaces/workflow/')

    def test_workspace_requires_login(self):
        response = self.client.get(reverse('app:operations_workspace'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('accounts:login')))

    def test_all_workspaces_render_the_shared_template(self):
        self.client.force_login(self.admin)

        for route_name in (
            'app:operations_workspace',
            'app:quality_workspace',
            'app:workflow_workspace',
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'workspaces/workspace.html')
                self.assertContains(response, 'data-ui="workspace"')

    def test_user_without_module_permission_receives_403(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('app:operations_workspace'))

        self.assertEqual(response.status_code, 403)

    def test_unknown_direct_workspace_configuration_raises_404(self):
        request = RequestFactory().get('/app/workspaces/missing/')
        request.user = self.admin

        with self.assertRaises(Http404):
            WorkspaceView.as_view(workspace_slug='missing')(request)

    def test_metric_cards_are_filtered_by_model_permission(self):
        grant_view_permission(self.user, ProductionOrder)
        self.client.force_login(self.user)

        response = self.client.get(reverse('app:operations_workspace'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ordens em execução')
        self.assertNotContains(response, 'Lotes em estoque')
        self.assertNotContains(response, 'Amostras pendentes')
        self.assertNotContains(response, '>Planejamento<')
