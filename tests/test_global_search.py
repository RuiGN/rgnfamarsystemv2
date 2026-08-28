from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse

from base.ui.search import search_visible_resources
from workflow.models import WorkflowNotification


def grant_view_permission(user, model):
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label=model._meta.app_label,
            content_type__model=model._meta.model_name,
            codename=f'view_{model._meta.model_name}',
        )
    )


class GlobalSearchServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='busca-global@example.com',
            email='busca-global@example.com',
            password='BuscaGlobalSecure!123',
        )
        self.other_user = get_user_model().objects.create_user(
            username='busca-terceiro@example.com',
            email='busca-terceiro@example.com',
            password='BuscaGlobalSecure!123',
        )
        self.request = RequestFactory().get('/app/busca-global/')
        self.request.user = self.user

    def create_notification(self, recipient, title):
        return WorkflowNotification.objects.create(
            category=WorkflowNotification.Category.ALERT,
            recipient=recipient,
            title=title,
            message='Mensagem pesquisável e individual.',
            source_module=WorkflowNotification.SourceModule.QUALITY,
        )

    def test_returns_empty_result_for_query_shorter_than_three_characters(self):
        grant_view_permission(self.user, WorkflowNotification)
        self.create_notification(self.user, 'Alerta curto')

        self.assertEqual(search_visible_resources(self.request, 'ab'), ())

    def test_uses_resource_queryset_scope_to_exclude_another_users_record(self):
        grant_view_permission(self.user, WorkflowNotification)
        own_notification = self.create_notification(
            self.user,
            'Alerta pesquisável autorizado',
        )
        self.create_notification(
            self.other_user,
            'Alerta pesquisável sigiloso',
        )

        results = search_visible_resources(self.request, 'pesquisável')

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, own_notification.title)
        self.assertEqual(results[0].module_label, 'Fluxo de trabalho')
        self.assertEqual(results[0].resource_label, 'Notificações de workflow')
        self.assertEqual(
            results[0].url,
            reverse(
                'app:resource_detail',
                args=('workflow', 'notifications', own_notification.pk),
            ),
        )

    def test_limits_results_per_resource_and_globally(self):
        grant_view_permission(self.user, WorkflowNotification)
        for index in range(7):
            self.create_notification(self.user, f'Alerta de limite {index}')

        results = search_visible_resources(
            self.request,
            'limite',
            limit=4,
            per_resource_limit=3,
        )

        self.assertEqual(len(results), 3)

    def test_user_without_model_permission_receives_no_results(self):
        self.create_notification(self.user, 'Alerta sem permissão')

        self.assertEqual(search_visible_resources(self.request, 'permissão'), ())


class GlobalSearchEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='endpoint-busca@example.com',
            email='endpoint-busca@example.com',
            password='BuscaGlobalSecure!123',
        )

    def test_requires_authentication(self):
        response = self.client.get(reverse('app:global_search'), {'q': 'alerta'})

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_returns_scoped_json_without_ajax_header_requirement(self):
        grant_view_permission(self.user, WorkflowNotification)
        notification = WorkflowNotification.objects.create(
            category=WorkflowNotification.Category.ALERT,
            recipient=self.user,
            title='Alerta retornado pelo endpoint',
            message='Mensagem do endpoint.',
            source_module=WorkflowNotification.SourceModule.QUALITY,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('app:global_search'), {'q': 'endpoint'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['title'], notification.title)
        self.assertEqual(
            set(response.json()['results'][0]),
            {'title', 'module', 'type', 'url', 'icon'},
        )

    def test_short_query_returns_empty_json(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('app:global_search'), {'q': 'ab'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'results': []})
