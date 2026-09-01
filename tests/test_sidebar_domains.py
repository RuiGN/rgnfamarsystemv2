from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import Permission
from django.test import RequestFactory, SimpleTestCase, TestCase

from base.ui.context_processors import group_sidebar_modules, sidebar_menu
from production.models import ProductionOrder
from quality.models import QualitySample


def module(slug):
    return SimpleNamespace(slug=slug, label=slug.title(), resources=())


class SidebarDomainGroupingTests(SimpleTestCase):
    def test_groups_only_visible_modules_in_semantic_order(self):
        visible_modules = (
            module('quality'),
            module('production'),
            module('finance'),
        )

        domains = group_sidebar_modules(visible_modules)

        self.assertEqual(
            tuple((key, label) for key, label, _modules in domains),
            (
                ('operations', 'Operações'),
                ('quality', 'Qualidade'),
                ('finance', 'Financeiro e fiscal'),
            ),
        )
        self.assertEqual(
            tuple(module.slug for module in domains[0][2]),
            ('production',),
        )
        self.assertEqual(
            tuple(module.slug for module in domains[1][2]),
            ('quality',),
        )
        self.assertEqual(
            tuple(module.slug for module in domains[2][2]),
            ('finance',),
        )

    def test_places_unmapped_visible_modules_in_other_domain(self):
        domains = group_sidebar_modules((module('custom-module'),))

        key, label, modules = domains[-1]

        self.assertEqual((key, label), ('other', 'Outros'))
        self.assertEqual(tuple(item.slug for item in modules), ('custom-module',))

    def test_does_not_duplicate_module_declared_in_more_than_one_domain(self):
        domains = group_sidebar_modules((module('production'),))

        grouped_slugs = [item.slug for _key, _label, modules in domains for item in modules]

        self.assertEqual(grouped_slugs, ['production'])


class SidebarDomainContextTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/app/')

    @patch('base.ui.context_processors._institution_brand_context', return_value={})
    def test_anonymous_context_exposes_safe_empty_domains(self, _brand_context):
        self.request.user = AnonymousUser()

        context = sidebar_menu(self.request)

        self.assertEqual(context['sidebar_domains'], ())

    @patch('base.ui.context_processors._institution_brand_context', return_value={})
    @patch('base.ui.context_processors.get_visible_modules')
    def test_context_groups_the_same_authorized_module_objects(
        self,
        visible_modules,
        _brand_context,
    ):
        production = module('production')
        quality = module('quality')
        visible_modules.return_value = (production, quality)
        self.request.user = SimpleNamespace(
            is_authenticated=True,
            has_perm=lambda _permission: False,
        )

        context = sidebar_menu(self.request)

        grouped_modules = tuple(
            item for _key, _label, modules in context['sidebar_domains'] for item in modules
        )
        self.assertEqual(grouped_modules, (production, quality))
        visible_modules.assert_called_once_with(self.request.user)


class SidebarDomainRenderingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='sidebar-dominios@example.com',
            email='sidebar-dominios@example.com',
            password='SidebarSecure!123',
        )
        for model in (ProductionOrder, QualitySample):
            permission = Permission.objects.get(
                content_type__app_label=model._meta.app_label,
                content_type__model=model._meta.model_name,
                codename=f'view_{model._meta.model_name}',
            )
            self.user.user_permissions.add(permission)
        self.client.force_login(self.user)

    def test_sidebar_renders_only_domains_with_authorized_modules(self):
        response = self.client.get('/app/')

        self.assertContains(response, 'data-sidebar-domain="operations"')
        self.assertContains(response, '>Operações<', html=False)
        self.assertContains(response, 'data-sidebar-domain="quality"')
        self.assertContains(response, '>Qualidade<', html=False)
        self.assertNotContains(response, 'data-sidebar-domain="supply"')
        self.assertNotContains(response, 'data-sidebar-domain="finance"')

    def test_sidebar_template_uses_domain_modules_as_single_navigation_source(self):
        template = Path('templates/includes/sidebar.html').read_text()

        self.assertIn(
            '{% for domain_key, domain_label, domain_modules in sidebar_domains %}',
            template,
        )
        self.assertIn('{% for module in domain_modules %}', template)
        self.assertNotIn('{% for module in sidebar_modules %}', template)
