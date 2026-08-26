import pytest
from django.contrib import admin
from django.test import RequestFactory

from auxiliary.models import Currency
from base.automatic_fields import automatic_generated_fields
from base.ui.forms import build_resource_form
from base.ui.registry import get_resource
from masters.models import Product
from procurement.models import PurchaseOrder
from procurement.serializers import PurchaseOrderSerializer
from production.models import ProductionOrder


pytestmark = pytest.mark.django_db


def test_registry_distinguishes_automatic_and_manual_codes():
    assert automatic_generated_fields(Product) == ('code',)
    assert automatic_generated_fields(Currency) == ()
    assert automatic_generated_fields(PurchaseOrder) == ('order_number',)
    assert automatic_generated_fields(ProductionOrder) == ('batch_number',)


def test_create_form_disables_automatic_code():
    form = build_resource_form(get_resource('masters', 'products'))()
    field = form.fields['code']

    assert field.disabled is True
    assert field.required is False
    assert field.initial is None
    assert field.help_text == 'Gerado automaticamente pelo sistema ao salvar.'


def test_update_form_keeps_operational_identifier_immutable():
    form = build_resource_form(get_resource('procurement', 'orders'), update=True)()

    assert form.fields['order_number'].disabled is True
    assert form.fields['order_number'].help_text == 'Identificador imutável após o cadastro.'


def test_manual_number_remains_editable():
    form = build_resource_form(get_resource('masters', 'sites'))()

    assert form.fields['street_number'].disabled is False


def test_production_batch_is_visible_and_disabled():
    form = build_resource_form(get_resource('production', 'orders'))()

    assert form.fields['batch_number'].disabled is True
    assert form.fields['order_number'].disabled is False


def test_drf_serializer_marks_generated_identifier_readonly():
    serializer = PurchaseOrderSerializer()

    assert serializer.fields['order_number'].read_only is True


def test_disabled_identifier_ignores_forged_posted_value():
    form_class = build_resource_form(get_resource('procurement', 'orders'))
    form = form_class(data={'order_number': 'FORGED-999'})
    field = form.fields['order_number']

    assert field.disabled is True
    assert field.bound_data('FORGED-999', None) is None


def test_all_registered_automatic_fields_are_readonly_in_admin(django_user_model):
    request = RequestFactory().get('/admin/')
    request.user = django_user_model.objects.create_superuser(
        username='admin-auto-fields', email='admin-auto@example.com', password='master'
    )
    covered = 0
    for model, model_admin in admin.site._registry.items():
        expected = automatic_generated_fields(model)
        if not expected:
            continue
        covered += 1
        readonly = model_admin.get_readonly_fields(request)
        assert set(expected) <= set(readonly), model._meta.label

    assert covered >= 70


def test_manual_currency_code_remains_editable_in_admin(django_user_model):
    request = RequestFactory().get('/admin/')
    request.user = django_user_model.objects.create_superuser(
        username='admin-currency', email='currency@example.com', password='master'
    )
    model_admin = admin.site._registry[Currency]

    assert 'code' not in model_admin.get_readonly_fields(request)
