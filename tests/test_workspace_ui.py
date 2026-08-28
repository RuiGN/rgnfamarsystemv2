from dataclasses import FrozenInstanceError

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase

from base.ui.workspaces import WORKSPACES, get_workspace
from workflow.models import WorkflowNotification


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
