from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from files.models import ProtectedFile
from masters.models import BusinessPartner, Product, UnitOfMeasure
from procurement.models import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
)


User = get_user_model()


class NfeImportSchemaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='nfe.schema@example.com',
            email='nfe.schema@example.com',
            password='S3curePass!123',
        )
        self.unit = UnitOfMeasure.objects.create(
            code='UN-NFE-SCHEMA',
            name='Unidade NF-e',
            symbol='UN',
        )
        self.product = Product.objects.create(
            code='PROD-NFE-SCHEMA',
            description='Produto para recebimento NF-e',
            item_type=Product.ItemType.RAW_MATERIAL,
            unit=self.unit,
            status=Product.Status.APPROVED,
            requires_approved_supplier=False,
        )
        self.supplier = BusinessPartner.objects.create(
            code='FOR-NFE-SCHEMA',
            legal_name='Fornecedor NF-e Schema Ltda',
            partner_type=BusinessPartner.PartnerType.SUPPLIER,
        )
        self.order = PurchaseOrder.objects.create(
            order_number='PC-NFE-SCHEMA',
            supplier=self.supplier,
            issue_date=timezone.localdate(),
            expected_delivery_date=timezone.localdate() + timedelta(days=5),
        )
        self.order_item = PurchaseOrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=Decimal('10.0000'),
            unit=self.unit,
            unit_price=Decimal('5.0000'),
        )

    def _receipt(self, **overrides):
        payload = {'order': self.order, **overrides}
        return PurchaseReceipt.objects.create(**payload)

    def _protected_file(self):
        return ProtectedFile.objects.create(
            source_module=ProtectedFile.SourceModule.FISCAL,
            source_model='PurchaseReceipt',
            source_record_id='pending',
            file_type=ProtectedFile.FileType.FISCAL_DOCUMENT,
            origin=ProtectedFile.Origin.UPLOAD,
            criticality=ProtectedFile.Criticality.HIGH,
            confidentiality=ProtectedFile.Confidentiality.INTERNAL,
            title='XML NF-e protegido',
            file_name='nfe.xml',
            file_reference='pending',
            mime_type='application/xml',
            file_size=0,
            content_hash='sha256:pending',
            responsible=self.user,
            uploaded_by=self.user,
        )

    def test_schema_purchase_receipt_exposes_nfe_metadata(self):
        field_names = {field.name for field in PurchaseReceipt._meta.fields}

        assert {'nfe_access_key', 'nfe_xml_sha256', 'nfe_xml_file'} <= field_names
        assert PurchaseReceipt._meta.get_field('nfe_access_key').max_length == 44
        assert PurchaseReceipt._meta.get_field('nfe_xml_sha256').max_length == 64

    def test_schema_nfe_access_key_is_conditionally_unique(self):
        assert any(field.name == 'nfe_access_key' for field in PurchaseReceipt._meta.fields)
        key = '1' * 44
        self._receipt(nfe_access_key=key)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                self._receipt(nfe_access_key=key)

        self._receipt(nfe_access_key='')
        self._receipt(nfe_access_key='')

    def test_schema_nfe_xml_file_is_protected_from_deletion(self):
        assert any(field.name == 'nfe_xml_file' for field in PurchaseReceipt._meta.fields)
        protected_file = self._protected_file()
        self._receipt(nfe_xml_file=protected_file)

        with pytest.raises(ProtectedError):
            protected_file.delete()

    def test_schema_manufacturing_date_persists_and_precedes_expiry(self):
        assert any(field.name == 'manufacturing_date' for field in PurchaseReceiptItem._meta.fields)
        receipt = self._receipt()
        item = PurchaseReceiptItem.objects.create(
            receipt=receipt,
            order_item=self.order_item,
            product=self.product,
            received_quantity=Decimal('2.0000'),
            unit=self.unit,
            manufacturing_date=date(2026, 8, 1),
            expiry_date=date(2027, 8, 1),
        )

        item.refresh_from_db()
        assert item.manufacturing_date == date(2026, 8, 1)

        item.manufacturing_date = date(2028, 1, 1)
        with pytest.raises(ValidationError) as error:
            item.full_clean()

        assert 'manufacturing_date' in error.value.message_dict
