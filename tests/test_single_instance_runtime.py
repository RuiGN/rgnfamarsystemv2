from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from masters.models import UnitOfMeasure


def grant_model_perm(user, model, action):
    permission = Permission.objects.get(
        content_type__app_label=model._meta.app_label,
        content_type__model=model._meta.model_name,
        codename=f'{action}_{model._meta.model_name}',
    )
    user.user_permissions.add(permission)
    for cache_name in ('_perm_cache', '_user_perm_cache', '_group_perm_cache'):
        if hasattr(user, cache_name):
            delattr(user, cache_name)


class SingleInstanceRuntimeTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username='qa.single@example.com',
            email='qa.single@example.com',
            password='S3curePass!123',
        )

    def test_app_index_does_not_require_scope_selection(self):
        grant_model_perm(self.user, UnitOfMeasure, 'view')
        self.client.force_login(self.user)

        response = self.client.get('/app/')

        assert response.status_code == 200
        content = response.content.decode()
        assert (
            reverse(
                'app:resource_list', kwargs={'module_slug': 'masters', 'resource_slug': 'units'}
            )
            in content
        )

    def test_resource_list_uses_global_queryset_without_active_scope(self):
        grant_model_perm(self.user, UnitOfMeasure, 'view')
        UnitOfMeasure.objects.create(
            code='KG',
            name='Quilograma',
            symbol='kg',
        )
        self.client.force_login(self.user)

        response = self.client.get('/app/masters/units/')

        assert response.status_code == 200
        assert 'Quilograma' in response.content.decode()

    def test_current_user_api_does_not_require_scope_header(self):
        client = APIClient()
        client.force_authenticate(self.user)

        response = client.get('/api/accounts/me/')

        assert response.status_code == 200
        assert response.json()['email'] == self.user.email

    def test_collection_generator_requires_add_permission(self):
        from risks.models import RiskAlert

        grant_model_perm(self.user, RiskAlert, 'change')
        client = APIClient()
        client.force_authenticate(self.user)

        denied = client.post('/api/risks/alerts/generate/', {})
        assert denied.status_code == 403

        grant_model_perm(self.user, RiskAlert, 'add')
        allowed = client.post('/api/risks/alerts/generate/', {})
        assert allowed.status_code == 200
        assert allowed.json() == {'generated': 0}

    def test_revision_action_requires_change_and_add_permissions(self):
        from django.utils import timezone

        from documents.models import ControlledDocument

        approver = self.User.objects.create_user(
            username='document.approver@example.com',
            email='document.approver@example.com',
            password='S3curePass!123',
        )
        document = ControlledDocument.objects.create(
            document_type=ControlledDocument.DocumentType.SOP,
            code='POP-PERM-001',
            title='Procedimento controlado',
            area='Qualidade',
            version='1.0',
            effective_from=timezone.localdate(),
            owner=self.user,
            content='Conteúdo controlado.',
            change_summary='Emissão inicial.',
        )
        document.submit_for_review(user=self.user)
        document.review(user=approver, comments='Revisado.')
        document.approve(user=approver, comments='Aprovado.')
        document.publish(user=approver)
        grant_model_perm(self.user, ControlledDocument, 'view')
        grant_model_perm(self.user, ControlledDocument, 'change')
        client = APIClient()
        client.force_authenticate(self.user)
        url = f'/api/documents/controlled-documents/{document.pk}/create_revision/'

        denied = client.post(url, {'change_summary': 'Alteração controlada.'})
        assert denied.status_code == 403

        grant_model_perm(self.user, ControlledDocument, 'add')
        allowed = client.post(url, {'change_summary': 'Alteração controlada.'})
        assert allowed.status_code == 201
