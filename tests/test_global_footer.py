from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


ROOT = Path(settings.BASE_DIR)
REMOVED_LABELS = ('Ajuda', 'Termos', 'Privacidade')


def extract_global_footer(response) -> str:
    html = response.content.decode()
    marker_index = html.index('data-ui="global-footer"')
    start = html.rfind('<footer', 0, marker_index)
    end = html.index('</footer>', marker_index) + len('</footer>')
    return html[start:end]


class GlobalFooterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='usuario-rodape',
            email='rodape@example.com',
            password='senha-local-segura',
        )

    def test_page_shells_use_the_shared_footer_partial(self):
        partial = (ROOT / 'templates/includes/footer.html').read_text()
        base = (ROOT / 'templates/base.html').read_text()
        login = (ROOT / 'templates/registration/login.html').read_text()

        assert 'data-ui="global-footer"' in partial
        assert 'Direitos autorais' in partial
        assert 'Versão 1.0' in partial
        assert "{% include 'includes/footer.html' %}" in base
        assert "{% include 'includes/footer.html' %}" in login
        for label in REMOVED_LABELS:
            assert label not in partial

    def test_login_renders_the_global_footer_without_removed_links(self):
        response = self.client.get(reverse('accounts:login'))

        assert response.status_code == 200
        footer = extract_global_footer(response)
        assert 'Direitos autorais' in footer
        assert 'Versão 1.0' in footer
        for label in REMOVED_LABELS:
            assert label not in footer

    def test_authenticated_app_renders_the_same_global_footer(self):
        self.client.force_login(self.user)

        response = self.client.get('/app/')

        assert response.status_code == 200
        footer = extract_global_footer(response)
        assert 'Direitos autorais' in footer
        assert 'Versão 1.0' in footer
        for label in REMOVED_LABELS:
            assert label not in footer
