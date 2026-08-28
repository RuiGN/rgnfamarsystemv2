from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomeNavigationTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('home'))

        self.assertRedirects(
            response,
            reverse('accounts:login'),
            fetch_redirect_response=False,
        )

    def test_authenticated_user_is_redirected_to_app_index(self):
        user = get_user_model().objects.create_user(
            username='home-user@example.com',
            email='home-user@example.com',
            password='HomeSecure!123',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('home'))

        self.assertRedirects(
            response,
            reverse('app:index'),
            fetch_redirect_response=False,
        )

    def test_static_dashboard_home_template_has_been_removed(self):
        self.assertFalse(Path('templates/dashboard/home.html').exists())
