from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, SimpleTestCase, TestCase
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


class GlobalSearchShellContractTests(SimpleTestCase):
    def test_base_template_exposes_accessible_progressive_search(self):
        template = Path('templates/base.html').read_text()

        self.assertIn('data-ui="global-search-input"', template)
        self.assertIn('data-search-url="{% url \'app:global_search\' %}"', template)
        self.assertIn('aria-controls="global-search-results"', template)
        self.assertIn('aria-live="polite"', template)
        self.assertIn("{% static 'js/global-search.js' %}", template)
        self.assertIn("{% static 'js/command-palette.js' %}", template)

    def test_global_search_script_uses_safe_cancelable_keyboard_navigation(self):
        script = Path('static/js/global-search.js').read_text()

        self.assertIn('AbortController', script)
        self.assertIn('SEARCH_DELAY_MS = 300', script)
        self.assertIn('textContent', script)
        self.assertNotIn('innerHTML', script)
        for key in ('ArrowDown', 'ArrowUp', 'Escape', 'Enter'):
            self.assertIn(key, script)

    def test_command_palette_indexes_only_rendered_authorized_links(self):
        script = Path('static/js/command-palette.js').read_text()
        sidebar = Path('templates/includes/sidebar.html').read_text()
        modal = Path('templates/includes/components/command_palette.html').read_text()

        self.assertIn('[data-command-label][data-command-url]', script)
        self.assertIn('event.ctrlKey', script)
        self.assertIn('event.metaKey', script)
        self.assertIn("event.key.toLowerCase() === 'k'", script)
        self.assertIn('textContent', script)
        self.assertNotIn('innerHTML', script)
        self.assertIn('data-command-label=', sidebar)
        self.assertIn('data-command-url=', sidebar)
        self.assertIn('id="command-palette-modal"', modal)
        self.assertIn('aria-live="polite"', modal)
        self.assertIn('Buscar um destino autorizado', modal)

    def test_search_and_palette_styles_preserve_focus_scroll_and_mobile_width(self):
        css = Path('static/css/app.css').read_text()

        self.assertIn('.global-search-result.is-active', css)
        self.assertIn('.command-palette__command:focus-visible', css)
        self.assertIn('.global-search-results', css)
        self.assertIn('max-height: 22rem', css)
        self.assertIn('width: min(42rem, calc(100vw - 2rem))', css)
        self.assertIn('.global-search-dropdown { width: calc(100vw - 1rem); }', css)
