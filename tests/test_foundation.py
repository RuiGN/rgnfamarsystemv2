import importlib

import pytest
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase


class FoundationSettingsTests(TestCase):
    def test_project_settings_use_required_foundation_defaults(self):
        assert settings.LANGUAGE_CODE == 'pt-br'
        assert settings.TIME_ZONE == 'America/Recife'
        assert settings.AUTH_USER_MODEL == 'accounts.User'
        assert 'rest_framework' in settings.INSTALLED_APPS
        assert 'base' in settings.INSTALLED_APPS
        assert 'tenants' in settings.INSTALLED_APPS
        assert 'accounts' in settings.INSTALLED_APPS
        assert 'control_plane' in settings.INSTALLED_APPS


class HealthCheckTests(TestCase):
    def test_health_check_returns_lightweight_ok_response(self):
        response = Client().get('/health/')

        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}


class ApplicationShellTests(TestCase):
    def test_home_redirects_anonymous_users_to_login(self):
        response = Client().get('/')

        assert response.status_code == 302
        assert response['Location'] == '/accounts/login/'


class UserModelTests(TestCase):
    def test_user_authenticates_with_normalized_full_name_as_username_field(self):
        User = get_user_model()

        assert User.USERNAME_FIELD == 'username'

        user = User.objects.create_user(
            username='  Quality   Reviewer  ',
            email='quality@example.com',
            password='S3curePass!123',
            first_name='Quality',
            last_name='Reviewer',
        )

        assert user.email == 'quality@example.com'
        assert user.username == 'Quality Reviewer'
        assert user.check_password('S3curePass!123')
        assert authenticate(username='Quality Reviewer', password='S3curePass!123') == user

    def test_user_rejects_case_insensitive_duplicate_username(self):
        User = get_user_model()
        User.objects.create_user(username='João Silva', email='joao1@example.com')

        with pytest.raises(IntegrityError), transaction.atomic():
            User.objects.create_user(username='joão silva', email='joao2@example.com')

    def test_user_requires_non_empty_username_and_email(self):
        User = get_user_model()

        with pytest.raises(ValueError, match='nome do usuário'):
            User.objects.create_user(username='   ', email='quality@example.com')
        with pytest.raises(ValueError, match='email'):
            User.objects.create_user(username='Quality Reviewer', email='')

    def test_superuser_requires_staff_and_superuser_flags(self):
        User = get_user_model()

        superuser = User.objects.create_superuser(
            username='System Administrator',
            email='admin@example.com',
            password='S3curePass!123',
        )

        assert superuser.is_staff is True
        assert superuser.is_superuser is True


@pytest.mark.django_db
class TestSingleInstanceFoundation:
    def test_user_model_uses_username_identity_without_scope_field(self):
        users_models = importlib.import_module('accounts.models')
        User = users_models.User

        user = User.objects.create_user(
            username='Single Instance User',
            email='single@example.com',
            password='S3curePass!123',
        )

        assert str(user) == 'Single Instance User'
        assert user.email == 'single@example.com'
        assert not hasattr(user, 'tenant')
