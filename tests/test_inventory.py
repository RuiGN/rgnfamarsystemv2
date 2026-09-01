from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from masters.models import BusinessPartner, Product, Site, StorageLocation, UnitOfMeasure, Warehouse


User = get_user_model()


def grant_model_perms(user, *models):
    for model in models:
        content_type = ContentType.objects.get_for_model(model)
        permissions = Permission.objects.filter(
            content_type=content_type,
            codename__in=[
                f'view_{model._meta.model_name}',
                f'add_{model._meta.model_name}',
                f'change_{model._meta.model_name}',
                f'delete_{model._meta.model_name}',
            ],
        )
        user.user_permissions.add(*permissions)
    if hasattr(user, '_perm_cache'):
        del user._perm_cache
    if hasattr(user, '_user_perm_cache'):
        del user._user_perm_cache


def create_stock_item(suffix='001', item_type=Product.ItemType.RAW_MATERIAL):
    unit = UnitOfMeasure.objects.create(
        code=f'KG-{suffix}',
        name='Quilograma',
        symbol='kg',
    )
    product = Product.objects.create(
        code=f'MP-{suffix}',
        description='Insumo rastreável',
        item_type=item_type,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    return unit, product


def create_stock_address(suffix='001'):
    site = Site.objects.create(
        code=f'PL-{suffix}',
        name=f'Planta {suffix}',
        site_type=Site.SiteType.PLANT,
    )
    warehouse = Warehouse.objects.create(
        site=site,
        code=f'ALM-{suffix}',
        name=f'Almoxarifado {suffix}',
        warehouse_type=Warehouse.WarehouseType.RAW_MATERIAL,
    )
    location = StorageLocation.objects.create(
        warehouse=warehouse,
        code=f'RUA-{suffix}',
        name=f'Rua {suffix}',
    )
    return warehouse, location


def create_purchase_receipt_item(suffix='001', accepted_quantity=Decimal('48.0000')):
    from procurement.models import (
        PurchaseOrder,
        PurchaseOrderItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
    )

    unit, product = create_stock_item(suffix=suffix)
    supplier = BusinessPartner.objects.create(
        code=f'FOR-{suffix}',
        legal_name=f'Fornecedor {suffix}',
        partner_type=BusinessPartner.PartnerType.SUPPLIER,
        qualification_status=BusinessPartner.QualificationStatus.QUALIFIED,
        qualification_valid_until=timezone.localdate() + timedelta(days=30),
    )
    order = PurchaseOrder.objects.create(
        order_number=f'PC-{suffix}',
        supplier=supplier,
        issue_date=timezone.localdate(),
        expected_delivery_date=timezone.localdate() + timedelta(days=5),
    )
    order_item = PurchaseOrderItem.objects.create(
        order=order,
        product=product,
        quantity=Decimal('50.0000'),
        unit=unit,
        unit_price=Decimal('10.0000'),
    )
    receipt = PurchaseReceipt.objects.create(
        receipt_number=f'REC-{suffix}',
        order=order,
        fiscal_document_number=f'NF-{suffix}',
        quality_status=PurchaseReceipt.QualityStatus.APPROVED,
    )
    receipt_item = PurchaseReceiptItem.objects.create(
        receipt=receipt,
        order_item=order_item,
        product=product,
        received_quantity=Decimal('50.0000'),
        accepted_quantity=accepted_quantity,
        rejected_quantity=Decimal('2.0000'),
        unit=unit,
        lot_number=f'LOTE-{suffix}',
        expiry_date=timezone.localdate() + timedelta(days=365),
    )
    return unit, product, supplier, receipt_item


class InventoryModelTests(TestCase):
    def test_purchase_receipt_creates_lot_balance_and_receipt_movement(self):
        from inventory.models import StockBalance, StockLot, StockMovement, StockQualityStatus

        _unit, product, supplier, receipt_item = create_purchase_receipt_item()
        warehouse, location = create_stock_address()

        movement = StockMovement.receive_purchase_receipt_item(
            receipt_item=receipt_item,
            warehouse=warehouse,
            location=location,
            quality_status=StockQualityStatus.APPROVED,
        )
        lot = StockLot.objects.get(product=product, lot_number='LOTE-001')
        balance = StockBalance.objects.get(product=product, lot=lot, location=location)

        assert movement.movement_type == StockMovement.MovementType.RECEIPT
        assert movement.source_purchase_receipt_item == receipt_item
        assert lot.supplier == supplier
        assert lot.expiry_date == receipt_item.expiry_date
        assert balance.quantity == Decimal('48.0000')
        assert balance.quality_status == StockQualityStatus.APPROVED

    def test_purchase_receipt_cannot_reintroduce_quarantine_balance_after_lot_release(self):
        from inventory.models import StockBalance, StockLot, StockMovement, StockQualityStatus

        _unit, product, _supplier, receipt_item = create_purchase_receipt_item(suffix='REL')
        warehouse, location = create_stock_address(suffix='REL')
        StockLot.objects.create(
            product=product,
            lot_number=receipt_item.lot_number,
            quality_status=StockQualityStatus.APPROVED,
        )

        with pytest.raises(ValidationError) as error:
            StockMovement.receive_purchase_receipt_item(
                receipt_item=receipt_item,
                warehouse=warehouse,
                location=location,
                quality_status=StockQualityStatus.QUARANTINE,
            )

        assert 'quality_status' in error.value.message_dict
        assert not StockBalance.objects.filter(product=product).exists()
        assert not StockMovement.objects.filter(product=product).exists()

    def test_balance_available_quantity_excludes_reserved_and_issue_blocks_overdraft(self):
        from inventory.models import StockBalance, StockLot, StockMovement, StockQualityStatus

        unit, product = create_stock_item()
        warehouse, location = create_stock_address()
        lot = StockLot.objects.create(
            product=product,
            lot_number='LOTE-001',
            expiry_date=timezone.localdate() + timedelta(days=365),
        )
        balance = StockBalance.objects.create(
            product=product,
            lot=lot,
            warehouse=warehouse,
            location=location,
            quality_status=StockQualityStatus.APPROVED,
            quantity=Decimal('100.0000'),
            reserved_quantity=Decimal('20.0000'),
            unit=unit,
        )

        assert balance.available_quantity == Decimal('80.0000')

        with pytest.raises(ValidationError) as error:
            StockMovement.issue_stock(
                product=product,
                lot=lot,
                warehouse=warehouse,
                location=location,
                quantity=Decimal('90.0000'),
                unit=unit,
                reason='Consumo de produção',
            )
        assert 'quantity' in error.value.message_dict

        movement = StockMovement.issue_stock(
            product=product,
            lot=lot,
            warehouse=warehouse,
            location=location,
            quantity=Decimal('30.0000'),
            unit=unit,
            reason='Consumo de produção',
        )
        balance.refresh_from_db()

        assert movement.movement_type == StockMovement.MovementType.ISSUE
        assert balance.quantity == Decimal('70.0000')
        assert balance.available_quantity == Decimal('50.0000')

    def test_transfer_moves_stock_between_physical_addresses(self):
        from inventory.models import StockBalance, StockLot, StockMovement, StockQualityStatus

        unit, product = create_stock_item()
        from_warehouse, from_location = create_stock_address(suffix='001')
        to_warehouse, to_location = create_stock_address(suffix='002')
        lot = StockLot.objects.create(
            product=product,
            lot_number='LOTE-001',
            expiry_date=timezone.localdate() + timedelta(days=365),
        )
        StockBalance.objects.create(
            product=product,
            lot=lot,
            warehouse=from_warehouse,
            location=from_location,
            quality_status=StockQualityStatus.APPROVED,
            quantity=Decimal('50.0000'),
            unit=unit,
        )

        movement = StockMovement.transfer_stock(
            product=product,
            lot=lot,
            from_warehouse=from_warehouse,
            from_location=from_location,
            to_warehouse=to_warehouse,
            to_location=to_location,
            quantity=Decimal('20.0000'),
            unit=unit,
            quality_status=StockQualityStatus.APPROVED,
            reason='Reendereçamento físico',
        )

        assert movement.movement_type == StockMovement.MovementType.TRANSFER
        assert StockBalance.objects.get(location=from_location).quantity == Decimal('30.0000')
        assert StockBalance.objects.get(location=to_location).quantity == Decimal('20.0000')

    def test_adjustment_requires_justification_and_specific_permission(self):
        from inventory.models import StockBalance, StockLot, StockMovement, StockQualityStatus

        unit, product = create_stock_item()
        warehouse, location = create_stock_address()
        lot = StockLot.objects.create(
            product=product,
            lot_number='LOTE-001',
            expiry_date=timezone.localdate() + timedelta(days=365),
        )
        StockBalance.objects.create(
            product=product,
            lot=lot,
            warehouse=warehouse,
            location=location,
            quality_status=StockQualityStatus.APPROVED,
            quantity=Decimal('10.0000'),
            unit=unit,
        )
        operator = User.objects.create_user(
            username='operador@example.com', email='operador@example.com', password='S3curePass!123'
        )
        supervisor = User.objects.create_user(
            username='supervisor@example.com',
            email='supervisor@example.com',
            password='S3curePass!123',
            is_staff=True,
        )

        with pytest.raises(ValidationError) as no_reason:
            StockMovement.adjust_stock(
                product=product,
                lot=lot,
                warehouse=warehouse,
                location=location,
                quantity_delta=Decimal('5.0000'),
                unit=unit,
                reason='',
                user=supervisor,
            )
        assert 'adjustment_reason' in no_reason.value.message_dict

        with pytest.raises(ValidationError) as no_permission:
            StockMovement.adjust_stock(
                product=product,
                lot=lot,
                warehouse=warehouse,
                location=location,
                quantity_delta=Decimal('5.0000'),
                unit=unit,
                reason='Contagem divergente',
                user=operator,
            )
        assert 'created_by' in no_permission.value.message_dict

        StockMovement.adjust_stock(
            product=product,
            lot=lot,
            warehouse=warehouse,
            location=location,
            quantity_delta=Decimal('5.0000'),
            unit=unit,
            reason='Contagem divergente',
            user=supervisor,
        )

        assert StockBalance.objects.get(location=location).quantity == Decimal('15.0000')

    def test_expired_or_blocked_stock_cannot_be_issued(self):
        from inventory.models import StockBalance, StockLot, StockMovement, StockQualityStatus

        unit, product = create_stock_item()
        warehouse, location = create_stock_address()
        expired_lot = StockLot.objects.create(
            product=product,
            lot_number='LOTE-VENCIDO',
            expiry_date=timezone.localdate() - timedelta(days=1),
        )
        StockBalance.objects.create(
            product=product,
            lot=expired_lot,
            warehouse=warehouse,
            location=location,
            quality_status=StockQualityStatus.APPROVED,
            quantity=Decimal('10.0000'),
            unit=unit,
        )

        with pytest.raises(ValidationError) as expired_error:
            StockMovement.issue_stock(
                product=product,
                lot=expired_lot,
                warehouse=warehouse,
                location=location,
                quantity=Decimal('1.0000'),
                unit=unit,
                reason='Tentativa de consumo',
            )
        assert 'lot' in expired_error.value.message_dict

        assert expired_lot.is_expired is True

    def test_lot_genealogy_links_input_material_to_generated_batch(self):
        from inventory.models import StockLot, StockLotGenealogy

        unit, material = create_stock_item(suffix='MAT')
        _finished_unit, finished_product = create_stock_item(
            suffix='FIN',
            item_type=Product.ItemType.FINISHED_PRODUCT,
        )
        input_lot = StockLot.objects.create(product=material, lot_number='MP-LOTE-001')
        output_lot = StockLot.objects.create(product=finished_product, lot_number='PA-LOTE-001')

        relation = StockLotGenealogy.objects.create(
            input_lot=input_lot,
            output_lot=output_lot,
            quantity=Decimal('5.0000'),
            unit=unit,
            relation_type=StockLotGenealogy.RelationType.CONSUMED_IN_PRODUCTION,
        )

        assert relation in output_lot.input_genealogy_links.all()
        assert input_lot.output_lots().get() == output_lot
        assert output_lot.input_lots().get() == input_lot


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestInventoryApi:
    def test_inventory_api_uses_single_instance_global_scope(self):
        from inventory.models import StockBalance, StockLot, StockQualityStatus

        unit, product = create_stock_item()
        other_unit, other_product = create_stock_item(suffix='999')
        warehouse, location = create_stock_address()
        other_warehouse, other_location = create_stock_address(suffix='999')
        other_lot = StockLot.objects.create(product=other_product, lot_number='LOTE-GLOBAL-999')
        StockBalance.objects.create(
            product=other_product,
            lot=other_lot,
            warehouse=other_warehouse,
            location=other_location,
            quality_status=StockQualityStatus.APPROVED,
            quantity=Decimal('99.0000'),
            unit=other_unit,
        )
        user = User.objects.create_user(
            username='estoque@example.com', email='estoque@example.com', password='S3curePass!123'
        )
        grant_model_perms(user, StockLot, StockBalance)
        client = APIClient()
        client.force_authenticate(user)

        lot_response = client.post(
            '/api/inventory/lots/',
            {
                'product': product.id,
                'lot_number': 'LOTE-API',
                'expiry_date': str(timezone.localdate() + timedelta(days=365)),
            },
        )
        assert lot_response.status_code == 201, lot_response.json()

        lot = StockLot.objects.get(pk=lot_response.json()['id'])
        balance = StockBalance.objects.create(
            product=product,
            lot=lot,
            warehouse=warehouse,
            location=location,
            quality_status=StockQualityStatus.QUARANTINE,
            quantity=Decimal('25.0000'),
            reserved_quantity=Decimal('5.0000'),
            unit=unit,
        )
        balance_response = client.get(f'/api/inventory/balances/{balance.pk}/')
        assert balance_response.status_code == 200
        assert balance_response.json()['available_quantity'] == '20.0000'

        list_response = client.get('/api/inventory/balances/')
        assert list_response.status_code == 200
        assert {item['product'] for item in list_response.json()['results']} == {
            product.id,
            other_product.id,
        }

    def test_generic_inventory_api_rejects_controlled_lot_and_balance_fields(self):
        from inventory.models import StockBalance, StockLot, StockQualityStatus

        unit, product = create_stock_item(suffix='CTRL')
        warehouse, location = create_stock_address(suffix='CTRL')
        alternate_location = StorageLocation.objects.create(
            warehouse=warehouse,
            code='RUA-CTRL-2',
            name='Rua controlada 2',
        )
        lot = StockLot.objects.create(
            product=product,
            lot_number='LOTE-CTRL',
            quality_status=StockQualityStatus.QUARANTINE,
            notes='Observação original',
        )
        balance = StockBalance.objects.create(
            product=product,
            lot=lot,
            warehouse=warehouse,
            location=location,
            quality_status=StockQualityStatus.QUARANTINE,
            quantity=Decimal('25.0000'),
            reserved_quantity=Decimal('5.0000'),
            unit=unit,
        )
        user = User.objects.create_user(
            username='estoque-controle@example.com',
            email='estoque-controle@example.com',
            password='S3curePass!123',
        )
        grant_model_perms(user, StockLot, StockBalance)
        client = APIClient()
        client.force_authenticate(user)

        create_lot_response = client.post(
            '/api/inventory/lots/',
            {
                'product': product.pk,
                'lot_number': 'LOTE-BYPASS',
                'quality_status': StockQualityStatus.APPROVED,
            },
        )
        patch_lot_response = client.patch(
            f'/api/inventory/lots/{lot.pk}/',
            {
                'quality_status': StockQualityStatus.APPROVED,
                'notes': 'Tentativa de alteração conjunta',
            },
            format='json',
        )
        put_lot_response = client.put(
            f'/api/inventory/lots/{lot.pk}/',
            {
                'product': product.pk,
                'lot_number': lot.lot_number,
                'quality_status': StockQualityStatus.APPROVED,
            },
            format='json',
        )
        for field_name, value in (
            ('quality_status', StockQualityStatus.APPROVED),
            ('quantity', '999.0000'),
            ('reserved_quantity', '24.0000'),
        ):
            response = client.patch(
                f'/api/inventory/balances/{balance.pk}/',
                {field_name: value},
                format='json',
            )
            assert response.status_code == 400
            assert field_name in response.json()

        create_balance_response = client.post(
            '/api/inventory/balances/',
            {
                'product': product.pk,
                'lot': lot.pk,
                'warehouse': warehouse.pk,
                'location': alternate_location.pk,
                'quality_status': StockQualityStatus.QUARANTINE,
                'quantity': '1.0000',
                'reserved_quantity': '0.0000',
                'unit': unit.pk,
            },
            format='json',
        )

        assert create_lot_response.status_code == 400
        assert 'quality_status' in create_lot_response.json()
        assert patch_lot_response.status_code == 400
        assert 'quality_status' in patch_lot_response.json()
        assert put_lot_response.status_code == 400
        assert 'quality_status' in put_lot_response.json()
        assert create_balance_response.status_code == 400
        assert {
            'quality_status',
            'quantity',
            'reserved_quantity',
        }.issubset(create_balance_response.json())
        assert not StockLot.objects.filter(lot_number='LOTE-BYPASS').exists()
        lot.refresh_from_db()
        balance.refresh_from_db()
        assert lot.quality_status == StockQualityStatus.QUARANTINE
        assert lot.notes == 'Observação original'
        assert balance.quality_status == StockQualityStatus.QUARANTINE
        assert balance.quantity == Decimal('25.0000')
        assert balance.reserved_quantity == Decimal('5.0000')

        safe_lot_response = client.patch(
            f'/api/inventory/lots/{lot.pk}/',
            {'notes': 'Observação permitida'},
            format='json',
        )
        immutable_balance_response = client.patch(
            f'/api/inventory/balances/{balance.pk}/',
            {'location': alternate_location.pk},
            format='json',
        )
        assert safe_lot_response.status_code == 200, safe_lot_response.json()
        assert immutable_balance_response.status_code == 400
        assert 'location' in immutable_balance_response.json()
        lot.refresh_from_db()
        balance.refresh_from_db()
        assert lot.notes == 'Observação permitida'
        assert balance.location == location

    def test_stock_balance_identity_is_immutable_in_model_and_api(self):
        from inventory.models import StockBalance, StockLot, StockQualityStatus

        unit, product = create_stock_item(suffix='IDENTITY')
        warehouse, location = create_stock_address(suffix='IDENTITY')
        other_unit, other_product = create_stock_item(suffix='IDENTITY-OTHER')
        other_warehouse, other_location = create_stock_address(suffix='IDENTITY-OTHER')
        lot = StockLot.objects.create(
            product=product,
            lot_number='LOTE-IDENTITY',
            quality_status=StockQualityStatus.QUARANTINE,
        )
        other_lot = StockLot.objects.create(
            product=other_product,
            lot_number='LOTE-IDENTITY-OTHER',
            quality_status=StockQualityStatus.QUARANTINE,
        )
        balance = StockBalance.objects.create(
            product=product,
            lot=lot,
            warehouse=warehouse,
            location=location,
            quality_status=StockQualityStatus.QUARANTINE,
            quantity=Decimal('25.0000'),
            reserved_quantity=Decimal('5.0000'),
            unit=unit,
        )
        user = User.objects.create_user(
            username='balance-identity@example.com',
            email='balance-identity@example.com',
            password='S3curePass!123',
        )
        grant_model_perms(user, StockBalance)
        client = APIClient()
        client.force_authenticate(user)

        replacements = {
            'product': other_product,
            'lot': other_lot,
            'warehouse': other_warehouse,
            'location': other_location,
            'unit': other_unit,
        }
        for field_name, replacement in replacements.items():
            for method in (client.patch, client.put):
                response = method(
                    f'/api/inventory/balances/{balance.pk}/',
                    {field_name: replacement.pk},
                    format='json',
                )
                assert response.status_code == 400
                assert field_name in response.json()

            setattr(balance, field_name, replacement)
            with pytest.raises(ValidationError) as error:
                balance.save()
            assert field_name in error.value.message_dict
            balance.refresh_from_db()

        balance.refresh_from_db()
        assert balance.product == product
        assert balance.lot == lot
        assert balance.warehouse == warehouse
        assert balance.location == location
        assert balance.unit == unit
        assert balance.quantity == Decimal('25.0000')
        assert balance.reserved_quantity == Decimal('5.0000')

    def test_stock_balance_update_ui_and_admin_hide_persisted_identity(self):
        from django.contrib.admin.sites import AdminSite

        from inventory.admin import StockBalanceAdmin
        from inventory.models import StockBalance, StockLot, StockQualityStatus

        unit, product = create_stock_item(suffix='IDENTITY-UI')
        warehouse, location = create_stock_address(suffix='IDENTITY-UI')
        lot = StockLot.objects.create(
            product=product,
            lot_number='LOTE-IDENTITY-UI',
            quality_status=StockQualityStatus.QUARANTINE,
        )
        balance = StockBalance.objects.create(
            product=product,
            lot=lot,
            warehouse=warehouse,
            location=location,
            quality_status=StockQualityStatus.QUARANTINE,
            quantity=Decimal('10.0000'),
            unit=unit,
        )
        user = User.objects.create_user(
            username='balance-identity-ui@example.com',
            email='balance-identity-ui@example.com',
            password='S3curePass!123',
        )
        grant_model_perms(user, StockBalance)
        client = Client()
        client.force_login(user)

        response = client.get(
            reverse(
                'app:resource_edit',
                kwargs={
                    'module_slug': 'inventory',
                    'resource_slug': 'balances',
                    'pk': balance.pk,
                },
            )
        )
        assert response.status_code == 200
        for field_name in ('product', 'lot', 'warehouse', 'location', 'unit'):
            assert f'name="{field_name}"' not in response.content.decode()

        model_admin = StockBalanceAdmin(StockBalance, AdminSite())
        assert {
            'product',
            'lot',
            'warehouse',
            'location',
            'unit',
        }.issubset(model_admin.get_readonly_fields(request=None, obj=balance))

    def test_generic_inventory_ui_omits_controlled_inputs_for_maximum_permission_user(self):
        from inventory.models import StockBalance, StockLot

        user = User.objects.create_user(
            username='estoque-ui-controle@example.com',
            email='estoque-ui-controle@example.com',
            password='S3curePass!123',
        )
        grant_model_perms(user, StockLot, StockBalance)
        client = Client()
        client.force_login(user)

        lot_response = client.get(
            reverse(
                'app:resource_create',
                kwargs={'module_slug': 'inventory', 'resource_slug': 'lots'},
            )
        )
        balance_response = client.get(
            reverse(
                'app:resource_create',
                kwargs={'module_slug': 'inventory', 'resource_slug': 'balances'},
            )
        )

        assert lot_response.status_code == 200
        assert balance_response.status_code == 200
        assert 'name="quality_status"' not in lot_response.content.decode()
        balance_html = balance_response.content.decode()
        for controlled_field in ('quality_status', 'quantity', 'reserved_quantity'):
            assert f'name="{controlled_field}"' not in balance_html

    def test_inventory_admin_treats_domain_controlled_fields_as_read_only(self):
        from django.contrib.admin.sites import AdminSite

        from inventory.admin import StockBalanceAdmin, StockLotAdmin
        from inventory.models import StockBalance, StockLot

        site = AdminSite()
        lot_admin = StockLotAdmin(StockLot, site)
        balance_admin = StockBalanceAdmin(StockBalance, site)

        assert 'quality_status' in lot_admin.get_readonly_fields(request=None)
        assert {
            'quality_status',
            'quantity',
            'reserved_quantity',
        }.issubset(balance_admin.get_readonly_fields(request=None))

    @pytest.mark.permission_strict
    def test_inventory_api_requires_view_permission(self):
        user = User.objects.create_user(
            username='estoque@example.com', email='estoque@example.com', password='S3curePass!123'
        )
        client = APIClient()
        client.login(username=user.username, password='S3curePass!123')

        response = client.get('/api/inventory/lots/')

        assert response.status_code == 403
