import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


User = get_user_model()


@pytest.mark.django_db
class TestSingleInstanceApi:
    def test_me_endpoint_returns_authenticated_user_profile(self):
        user = User.objects.create_user(
            username='Current API User',
            email='qa@example.com',
            password='S3curePass!123',
            first_name='QA',
        )
        client = APIClient()
        client.force_authenticate(user)

        response = client.get('/api/accounts/me/')

        assert response.status_code == 200
        assert response.json()['email'] == 'qa@example.com'


class UsernameLoginViewTests(TestCase):
    def setUp(self):
        User.objects.create_user(
            username='Quality Reviewer',
            email='qa@example.com',
            password='S3curePass!123',
        )

    def test_login_view_accepts_username_and_rejects_email(self):
        accepted = self.client.post(
            '/accounts/login/',
            {
                'username': 'Quality Reviewer',
                'password': 'S3curePass!123',
            },
        )

        assert accepted.status_code == 302
        assert accepted['Location'] == '/app/'

        self.client.logout()

        rejected = self.client.post(
            '/accounts/login/',
            {
                'username': 'qa@example.com',
                'password': 'S3curePass!123',
            },
        )

        assert rejected.status_code == 200

    def test_login_page_labels_and_autocompletes_username(self):
        response = self.client.get('/accounts/login/')
        content = response.content.decode()

        assert response.status_code == 200
        assert 'Nome do usuário' in content
        assert 'autocomplete="username"' in content
