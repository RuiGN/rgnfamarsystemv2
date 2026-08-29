import pytest
from django.contrib import admin
from django.test import RequestFactory

from auxiliary.models import Currency
from base.automatic_fields import automatic_generated_fields
from base.sequences import AutoCodeMixin
from base.ui.forms import build_resource_form
from base.ui.registry import get_resource
from crm.models import CustomerComplaint
from finance.models import ChartOfAccount
from finance.serializers import ChartOfAccountSerializer
from masters.models import Product
from procurement.models import PurchaseOrder
from procurement.serializers import PurchaseOrderSerializer
from production.models import ProductionOrder


pytestmark = pytest.mark.django_db


def test_registry_distinguishes_automatic_and_manual_codes():
    assert automatic_generated_fields(Product) == ('code',)
    assert automatic_generated_fields(ChartOfAccount) == ('code',)
    assert automatic_generated_fields(Currency) == ()
    assert automatic_generated_fields(PurchaseOrder) == ('order_number',)
    assert automatic_generated_fields(ProductionOrder) == ('batch_number',)
    assert automatic_generated_fields(CustomerComplaint) == ('complaint_number',)


def test_operational_identifiers_are_declared_on_their_models():
    from base.sequences import IdentifierSpec
    from training.models import TrainingEnrollment

    assert PurchaseOrder.AUTOMATIC_IDENTIFIERS == (
        IdentifierSpec(field_name='order_number', prefix='PC'),
    )
    assert TrainingEnrollment.AUTOMATIC_IDENTIFIERS == (
        IdentifierSpec(field_name='enrollment_number', prefix='TRN'),
        IdentifierSpec(
            field_name='certificate_number',
            prefix='CERT',
            trigger='approval',
        ),
    )


def test_every_model_with_an_active_auto_code_mixin_exposes_code_as_automatic():
    from django.apps import apps

    for model in apps.get_models():
        if issubclass(model, AutoCodeMixin) and model.CODE_PREFIX:
            assert 'code' in automatic_generated_fields(model), model._meta.label


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


@pytest.mark.parametrize(
    ('module_slug', 'resource_slug', 'field_name'),
    (
        ('finance', 'chart-accounts', 'code'),
        ('crm', 'complaints', 'complaint_number'),
    ),
)
def test_previously_omitted_generated_fields_are_disabled(module_slug, resource_slug, field_name):
    form = build_resource_form(get_resource(module_slug, resource_slug))()

    assert form.fields[field_name].disabled is True
    assert form.fields[field_name].required is False


def test_drf_serializer_marks_generated_identifier_readonly():
    serializer = PurchaseOrderSerializer()

    assert serializer.fields['order_number'].read_only is True


def test_chart_account_serializer_marks_generated_code_readonly():
    serializer = ChartOfAccountSerializer()

    assert serializer.fields['code'].read_only is True


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


@pytest.mark.parametrize(
    ('model', 'field_name'),
    (
        (ChartOfAccount, 'code'),
        (CustomerComplaint, 'complaint_number'),
    ),
)
def test_previously_omitted_generated_fields_are_readonly_in_admin(
    django_user_model, model, field_name
):
    request = RequestFactory().get('/admin/')
    request.user = django_user_model.objects.create_superuser(
        username=f'admin-{model._meta.model_name}',
        email=f'{model._meta.model_name}@example.com',
        password='master',
    )

    assert field_name in admin.site._registry[model].get_readonly_fields(request)
