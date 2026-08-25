import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from rest_framework.test import APIClient


PERMISSION_STRICT_TEST_FILES = {
    'test_app_ui.py',
    'test_master_data.py',
    'test_single_instance_runtime.py',
}


@pytest.fixture(autouse=True)
def grant_legacy_api_permissions(monkeypatch, request):
    if request.node.get_closest_marker('legacy_api_permissions') is None:
        return
    if request.node.get_closest_marker('permission_strict') is not None:
        return
    if request.node.path.name in PERMISSION_STRICT_TEST_FILES:
        raise AssertionError(
            'Testes de autorização estrita não podem solicitar permissões globais.'
        )

    original_force_authenticate = APIClient.force_authenticate
    original_force_login = Client.force_login

    def grant_all_permissions(user):
        user.user_permissions.add(*Permission.objects.all())
        for cache_name in ('_perm_cache', '_user_perm_cache', '_group_perm_cache'):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def force_authenticate_with_legacy_permissions(self, user=None, token=None):
        if user is not None:
            grant_all_permissions(user)
        return original_force_authenticate(self, user=user, token=token)

    def force_login_with_legacy_permissions(self, user, backend=None):
        grant_all_permissions(user)
        return original_force_login(self, user, backend=backend)

    monkeypatch.setattr(APIClient, 'force_authenticate', force_authenticate_with_legacy_permissions)
    monkeypatch.setattr(Client, 'force_login', force_login_with_legacy_permissions)
