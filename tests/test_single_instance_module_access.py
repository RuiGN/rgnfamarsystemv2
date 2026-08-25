from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from base.ui.registry import get_module


def grant_module_view(user, module_slug):
    model = get_module(module_slug).resources[0].model
    permission = Permission.objects.get(
        content_type__app_label=model._meta.app_label,
        content_type__model=model._meta.model_name,
        codename=f'view_{model._meta.model_name}',
    )
    user.user_permissions.add(permission)


class SingleInstanceModuleAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='owner-modular@example.com',
            email='owner-modular@example.com',
            password='OwnerSecure!123',
        )
        for module_slug in ('production', 'quality', 'finance', 'auxiliary'):
            grant_module_view(self.user, module_slug)
        self.client.force_login(self.user)

    def test_module_contract_no_longer_controls_navigation(self):
        response = self.client.get(reverse('app:index'))

        assert response.status_code == 200
        content = response.content.decode()
        assert reverse('app:module', kwargs={'module_slug': 'production'}) in content
        assert reverse('app:module', kwargs={'module_slug': 'quality'}) in content
        assert reverse('app:module', kwargs={'module_slug': 'finance'}) in content
        assert reverse('app:module', kwargs={'module_slug': 'auxiliary'}) in content

    def test_module_html_routes_use_django_permissions(self):
        assert self.client.get('/app/quality/').status_code == 200
        assert self.client.get('/app/finance/').status_code == 200
        assert self.client.get('/app/auxiliary/').status_code == 200

    def test_api_no_longer_returns_module_contract_error(self):
        user_without_perms = get_user_model().objects.create_user(
            username='no-perms@example.com',
            email='no-perms@example.com',
            password='OwnerSecure!123',
        )
        self.client.logout()
        self.client.login(username=user_without_perms.username, password='OwnerSecure!123')

        response = self.client.get('/api/quality/samples/')

        assert response.status_code == 403
        assert response.json() == {'detail': 'Você não tem permissão para executar essa ação.'}

    def test_enabled_module_api_remains_available_by_permission(self):
        response = self.client.get('/api/production/orders/')

        assert response.status_code == 200
