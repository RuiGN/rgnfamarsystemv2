from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from documents.models import ControlledDocument, DocumentAuditTrail


class ImmutableAuditAdminTests(TestCase):
    def test_document_audit_trail_admin_is_immutable_even_for_superuser(self):
        user = get_user_model().objects.create_superuser(
            username='Audit Administrator',
            email='admin-audit@example.com',
            password='S3curePass!123',
        )
        request = RequestFactory().get('/admin/documents/documentaudittrail/')
        request.user = user
        model_admin = admin.site._registry[DocumentAuditTrail]

        assert model_admin.has_view_permission(request)
        assert not model_admin.has_add_permission(request)
        assert not model_admin.has_change_permission(request)
        assert not model_admin.has_delete_permission(request)

    def test_regulated_business_record_cannot_be_deleted_even_by_superuser(self):
        user = get_user_model().objects.create_superuser(
            username='Retention Administrator',
            email='admin-retention@example.com',
            password='S3curePass!123',
        )
        request = RequestFactory().get('/admin/documents/controlleddocument/')
        request.user = user
        model_admin = admin.site._registry[ControlledDocument]

        assert model_admin.has_view_permission(request)
        assert not model_admin.has_delete_permission(request)


class UserAdminIdentityTests(TestCase):
    def test_user_admin_requires_and_prioritizes_username(self):
        User = get_user_model()
        user = User.objects.create_superuser(
            username='User Administrator',
            email='user-admin@example.com',
            password='S3curePass!123',
        )
        request = RequestFactory().get('/admin/accounts/user/add/')
        request.user = user
        model_admin = admin.site._registry[User]
        form = model_admin.get_form(request)()

        assert model_admin.ordering == ('username',)
        assert 'username' in model_admin.list_display
        assert 'username' in model_admin.search_fields
        assert form.fields['username'].required is True
        assert form.fields['email'].required is True
