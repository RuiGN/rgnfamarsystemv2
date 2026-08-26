from datetime import date, datetime
from unittest.mock import Mock

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from integrations.models import LabelPrinterSettings
from inventory.label_service import (
    LabelDataError,
    LabelPrinterConfigurationError,
    LabelPrinterConnectionError,
    print_lot_label,
    render_lot_label_tspl,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def make_lot():
    from inventory.models import StockLot
    from masters.models import Product, UnitOfMeasure

    unit = UnitOfMeasure.objects.create(code='UN', name='Unidade', symbol='un')
    product = Product.objects.create(
        code='PROD-001',
        description='Solução Ácida',
        item_type=Product.ItemType.FINISHED_PRODUCT,
        unit=unit,
    )
    return StockLot.objects.create(
        product=product,
        lot_number='LOTE-001',
        sublot_number='SUB-IGNORADO',
        manufacturing_date=date(2026, 8, 1),
        expiry_date=date(2027, 8, 1),
    )


def test_renderer_contains_only_approved_label_data(django_user_model):
    user = django_user_model.objects.create_user(
        username='operador',
        email='operador@example.com',
        first_name='Maria',
        last_name='Silva',
    )
    printed_at = timezone.make_aware(datetime(2026, 8, 26, 14, 30))

    payload = render_lot_label_tspl(
        make_lot(), user, width_mm=40, height_mm=30, printed_at=printed_at
    )

    assert 'PRODUTO: PROD-001 - Solucao Acida' in payload
    assert 'LOTE: LOTE-001' in payload
    assert 'VALIDADE: 01/08/2027' in payload
    assert 'ASS: Maria Silva 26/08/2026 14:30' in payload
    assert 'BARCODE' not in payload
    assert 'FAB:' not in payload
    assert 'SUB-IGNORADO' not in payload


def test_renderer_falls_back_to_username(django_user_model):
    user = django_user_model.objects.create_user(
        username='operador-sem-nome', email='operador-sem-nome@example.com'
    )

    payload = render_lot_label_tspl(make_lot(), user, width_mm=40, height_mm=30)

    assert 'ASS: operador-sem-nome ' in payload


def test_renderer_rejects_missing_expiry(django_user_model):
    user = django_user_model.objects.create_user(
        username='operador', email='operador-expiry@example.com'
    )
    lot = make_lot()
    lot.expiry_date = None

    with pytest.raises(LabelDataError, match='validade'):
        render_lot_label_tspl(lot, user, width_mm=40, height_mm=30)


def test_print_lot_label_uses_active_database_configuration(monkeypatch, django_user_model):
    user = django_user_model.objects.create_user(
        username='operador', email='operador-print@example.com'
    )
    LabelPrinterSettings.objects.create(
        name='Argox principal',
        host='10.20.30.40',
        port=9100,
        width_mm=40,
        height_mm=30,
        is_active=True,
    )
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    create_connection = Mock(return_value=connection)
    monkeypatch.setattr('inventory.label_service.socket.create_connection', create_connection)

    result = print_lot_label(make_lot(), user)

    create_connection.assert_called_once_with(('10.20.30.40', 9100), timeout=5)
    sent_payload = connection.sendall.call_args.args[0].decode('ascii')
    assert 'ASS: operador ' in sent_payload
    assert result['printer_host'] == '10.20.30.40'


def test_print_lot_label_converts_socket_errors(monkeypatch, django_user_model):
    user = django_user_model.objects.create_user(
        username='operador', email='operador-timeout@example.com'
    )
    LabelPrinterSettings.objects.create(name='Argox', host='10.20.30.40', is_active=True)
    monkeypatch.setattr(
        'inventory.label_service.socket.create_connection',
        Mock(side_effect=TimeoutError('network detail must stay internal')),
    )

    with pytest.raises(LabelPrinterConnectionError, match='Não foi possível conectar') as caught:
        print_lot_label(make_lot(), user)

    assert 'network detail' not in str(caught.value)


def test_print_endpoint_requires_stock_lot_permission(api_client, django_user_model):
    user = django_user_model.objects.create_user(
        username='sem-permissao', email='sem-permissao@example.com'
    )
    api_client.force_authenticate(user)

    response = api_client.post(reverse('inventory:lot-print-label', args=(make_lot().pk,)))

    assert response.status_code == 403


def test_print_endpoint_requires_authentication(api_client):
    response = api_client.post(reverse('inventory:lot-print-label', args=(make_lot().pk,)))

    assert response.status_code == 403


def test_print_endpoint_enforces_csrf_for_session_authentication(django_user_model):
    user = django_user_model.objects.create_user(
        username='operador-csrf', email='operador-csrf@example.com'
    )
    user.user_permissions.add(Permission.objects.get(codename='view_stocklot'))
    csrf_client = APIClient(enforce_csrf_checks=True)
    csrf_client.force_login(user)

    response = csrf_client.post(reverse('inventory:lot-print-label', args=(make_lot().pk,)))

    assert response.status_code == 403


def test_print_endpoint_returns_success(monkeypatch, api_client, django_user_model):
    user = django_user_model.objects.create_user(
        username='operador', email='operador-endpoint@example.com'
    )
    user.user_permissions.add(Permission.objects.get(codename='view_stocklot'))
    api_client.force_authenticate(user)
    lot = make_lot()
    send = Mock(return_value={'printer_name': 'Argox principal', 'lot_number': lot.lot_number})
    monkeypatch.setattr('inventory.views.print_lot_label', send)

    response = api_client.post(reverse('inventory:lot-print-label', args=(lot.pk,)))

    assert response.status_code == 200
    assert response.data['detail'] == 'Etiqueta enviada à impressora.'
    send.assert_called_once_with(lot, user)


@pytest.mark.parametrize(
    ('error_type', 'expected_status'),
    (
        (LabelDataError, 400),
        (LabelPrinterConfigurationError, 503),
        (LabelPrinterConnectionError, 503),
    ),
)
def test_print_endpoint_normalizes_domain_errors(
    monkeypatch, api_client, django_user_model, error_type, expected_status
):
    user = django_user_model.objects.create_user(
        username=f'operador-{error_type.__name__}',
        email=f'operador-{error_type.__name__.lower()}@example.com',
    )
    user.user_permissions.add(Permission.objects.get(codename='view_stocklot'))
    api_client.force_authenticate(user)
    lot = make_lot()
    monkeypatch.setattr(
        'inventory.views.print_lot_label', Mock(side_effect=error_type('mensagem segura'))
    )

    response = api_client.post(reverse('inventory:lot-print-label', args=(lot.pk,)))

    assert response.status_code == expected_status
    assert response.data == {'detail': 'mensagem segura'}
