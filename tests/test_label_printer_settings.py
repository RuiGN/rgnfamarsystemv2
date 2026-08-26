import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from integrations.models import LabelPrinterSettings


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def printer_data(**overrides):
    data = {
        'name': 'Argox principal',
        'host': '10.20.30.40',
        'port': 9100,
        'protocol': 'tspl2',
        'width_mm': 40,
        'height_mm': 30,
        'is_active': True,
        'notes': '',
    }
    data.update(overrides)
    return data


def test_active_printer_requires_valid_network_and_dimensions():
    printer = LabelPrinterSettings(**printer_data(host='', port=0, width_mm=0))

    with pytest.raises(ValidationError) as caught:
        printer.full_clean()

    assert {'host', 'port', 'width_mm'} <= set(caught.value.message_dict)


def test_only_one_printer_can_be_active():
    LabelPrinterSettings.objects.create(**printer_data())

    with pytest.raises(ValidationError):
        LabelPrinterSettings.objects.create(**printer_data(name='Argox reserva'))


def test_inactive_backup_printer_is_allowed():
    LabelPrinterSettings.objects.create(**printer_data())
    backup = LabelPrinterSettings.objects.create(
        **printer_data(name='Argox reserva', host='', is_active=False)
    )

    assert backup.is_active is False


def test_printer_settings_api_and_ui_registry(api_client, django_user_model):
    user = django_user_model.objects.create_superuser(
        username='master-printer', email='master-printer@example.com', password='master'
    )
    api_client.force_authenticate(user)

    response = api_client.post(reverse('integrations:label-printer-list'), printer_data())

    assert response.status_code == 201
    assert response.data['host'] == '10.20.30.40'
    from base.ui.registry import get_resource

    assert get_resource('integrations', 'label-printers').model is LabelPrinterSettings
