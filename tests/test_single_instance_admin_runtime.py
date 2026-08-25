from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import Resolver404, resolve, reverse


User = get_user_model()


class SingleInstanceAdminRuntimeTests(TestCase):
    def test_platform_route_is_gone(self):
        assert self.client.get('/platform/').status_code == 404
        with self.assertRaises(Resolver404):
            resolve('/platform/')

    def test_admin_uses_standard_staff_boundary(self):
        staff = User.objects.create_user(
            'Staff',
            'staff@example.com',
            'Secret123!',
            is_staff=True,
        )
        ordinary = User.objects.create_user(
            'Ordinary',
            'user@example.com',
            'Secret123!',
        )
        inactive_staff = User.objects.create_user(
            'Inactive Staff',
            'inactive-staff@example.com',
            'Secret123!',
            is_staff=True,
            is_active=False,
        )

        self.client.force_login(staff)
        assert self.client.get('/admin/').status_code == 200

        self.client.force_login(ordinary)
        response = self.client.get('/admin/')
        assert response.status_code == 302
        assert response['Location'].startswith('/admin/login/?next=')

        self.client.force_login(inactive_staff)
        response = self.client.get('/admin/')
        assert response.status_code == 302
        assert response['Location'].startswith('/admin/login/?next=')

    def test_settings_have_no_control_plane_runtime(self):
        serialized = repr((settings.INSTALLED_APPS, settings.MIDDLEWARE, vars(settings)))

        assert 'django_otp' not in serialized
        assert 'ControlPlaneHostMiddleware' not in serialized
        assert not any(name.startswith('CONTROL_PLANE_') for name in dir(settings))

    def test_user_model_has_no_platform_operator_field(self):
        assert 'is_platform_operator' not in {field.name for field in User._meta.get_fields()}

    def test_valid_login_preserves_local_admin_next(self):
        User.objects.create_user(
            'Admin Visitor',
            'admin-visitor@example.com',
            'Secret123!',
            is_staff=True,
        )

        response = self.client.post(
            '/accounts/login/',
            {
                'username': 'Admin Visitor',
                'password': 'Secret123!',
                'next': '/admin/',
            },
        )

        assert response.status_code == 302
        assert response['Location'] == '/admin/'

    def test_valid_login_rejects_external_next(self):
        User.objects.create_user(
            'External Redirect',
            'external-redirect@example.com',
            'Secret123!',
        )

        response = self.client.post(
            '/accounts/login/',
            {
                'username': 'External Redirect',
                'password': 'Secret123!',
                'next': 'https://evil.example/',
            },
        )

        assert response.status_code == 302
        assert response['Location'] == '/app/'

    def test_staff_login_without_next_uses_customer_app(self):
        User.objects.create_user(
            'Staff Login',
            'staff-login@example.com',
            'Secret123!',
            is_staff=True,
        )

        response = self.client.post(
            '/accounts/login/',
            {
                'username': 'Staff Login',
                'password': 'Secret123!',
            },
        )

        assert response.status_code == 302
        assert response['Location'] == '/app/'

    def test_admin_login_redirects_to_shared_login_with_safe_next(self):
        response = self.client.get('/admin/login/', {'next': '/admin/auth/user/'})

        assert response.status_code == 302
        assert response['Location'] == ('/accounts/login/?next=/admin/auth/user/')

        external_next = self.client.get(
            '/admin/login/',
            {'next': 'https://evil.example/admin/'},
        )

        assert external_next.status_code == 302
        assert external_next['Location'] == '/accounts/login/?next=/admin/'


@override_settings(
    LOGIN_MAX_ATTEMPTS=3,
    LOGIN_WINDOW_SECONDS=600,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class LoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='Rate Limited User',
            email='rate-limited@example.com',
            password='Secret123!',
        )

    def tearDown(self):
        cache.clear()

    def test_repeated_invalid_passwords_are_rate_limited(self):
        for _ in range(3):
            response = self.client.post(
                reverse('accounts:login'),
                {'username': self.user.username, 'password': 'wrong-password'},
                REMOTE_ADDR='203.0.113.10',
            )
            assert response.status_code == 200

        blocked = self.client.post(
            reverse('accounts:login'),
            {'username': self.user.username, 'password': 'wrong-password'},
            REMOTE_ADDR='203.0.113.10',
        )

        assert blocked.status_code == 429
        assert blocked['Retry-After'] == '600'
        assert 'Muitas tentativas' in blocked.content.decode()

    def test_admin_login_cannot_bypass_shared_rate_limit(self):
        for _ in range(3):
            response = self.client.post(
                reverse('accounts:login'),
                {'username': self.user.username, 'password': 'wrong-password'},
                REMOTE_ADDR='203.0.113.12',
            )
            assert response.status_code == 200

        admin_response = self.client.post(
            '/admin/login/?next=/admin/',
            {'username': self.user.username, 'password': 'Secret123!'},
            REMOTE_ADDR='203.0.113.12',
        )

        assert admin_response.status_code == 302
        assert admin_response['Location'] == '/accounts/login/?next=/admin/'
        assert '_auth_user_id' not in self.client.session

        shared_response = self.client.post(
            admin_response['Location'],
            {'username': self.user.username, 'password': 'Secret123!'},
            REMOTE_ADDR='203.0.113.12',
        )
        assert shared_response.status_code == 429

    @patch('accounts.views.cache.get', side_effect=ConnectionError('cache unavailable'))
    def test_cache_outage_fails_closed_with_service_unavailable(self, _mocked_get):
        response = self.client.post(
            reverse('accounts:login'),
            {'username': self.user.username, 'password': 'Secret123!'},
            REMOTE_ADDR='203.0.113.11',
        )

        assert response.status_code == 503
        assert response['Retry-After'] == '60'
        assert 'temporariamente indisponível' in response.content.decode()
