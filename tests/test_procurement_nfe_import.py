from datetime import date, timedelta
from decimal import Decimal
import hashlib

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


NFE_KEY = '2' * 44
NFE_NAMESPACE = 'http://www.portalfiscal.inf.br/nfe'


def nfe_parser_contract():
    try:
        from procurement.nfe_xml_import import (
            MAX_NFE_XML_SIZE,
            NfeImportError,
            parse_nfe_xml,
        )
    except ModuleNotFoundError:
        pytest.fail('O parser de NF-e ainda não foi implementado.')
    return MAX_NFE_XML_SIZE, NfeImportError, parse_nfe_xml


def authorized_nfe_xml(
    *,
    key=NFE_KEY,
    inf_key=None,
    model='55',
    status='100',
    quantity='2.5000',
    unit_price='10.0000',
    item_total='25.00',
    product_total='25.00',
    include_item=True,
):
    inf_key = key if inf_key is None else inf_key
    item = ''
    if include_item:
        item = f'''
        <det nItem="1">
          <prod>
            <cProd>PROD-NFE-001</cProd>
            <xProd>Glicerina vegetal</xProd>
            <qCom>{quantity}</qCom>
            <uCom>KG</uCom>
            <vUnCom>{unit_price}</vUnCom>
            <vProd>{item_total}</vProd>
            <rastro>
              <nLote>LOTE-GLI-001</nLote>
              <qLote>{quantity}</qLote>
              <dFab>2026-08-01</dFab>
              <dVal>2027-08-01</dVal>
            </rastro>
          </prod>
          <imposto><vTotTrib>1.25</vTotTrib></imposto>
        </det>'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
    <nfeProc xmlns="{NFE_NAMESPACE}" versao="4.00">
      <NFe>
        <infNFe Id="NFe{inf_key}" versao="4.00">
          <ide>
            <mod>{model}</mod>
            <serie>1</serie>
            <nNF>12345</nNF>
            <dhEmi>2026-09-01T10:15:00-03:00</dhEmi>
          </ide>
          <emit>
            <CNPJ>11222333000181</CNPJ>
            <xNome>Fornecedor Cosmético Ltda</xNome>
          </emit>
          <dest><CNPJ>99888777000166</CNPJ></dest>
          {item}
          <total><ICMSTot><vProd>{product_total}</vProd></ICMSTot></total>
        </infNFe>
      </NFe>
      <protNFe>
        <infProt>
          <chNFe>{key}</chNFe>
          <cStat>{status}</cStat>
        </infProt>
      </protNFe>
    </nfeProc>'''.encode()


def test_parse_authorized_model_55_nfe_with_namespaces_and_lot_data():
    _max_size, _error, parse_nfe_xml = nfe_parser_contract()
    xml = authorized_nfe_xml()

    parsed = parse_nfe_xml(xml)

    assert parsed.access_key == NFE_KEY
    assert parsed.number == '12345'
    assert parsed.series == '1'
    assert parsed.issue_date == date(2026, 9, 1)
    assert parsed.model == '55'
    assert parsed.authorization_status == '100'
    assert parsed.supplier_document == '11222333000181'
    assert parsed.supplier_name == 'Fornecedor Cosmético Ltda'
    assert parsed.destination_document == '99888777000166'
    assert parsed.product_total == Decimal('25.00')
    assert parsed.xml_sha256 == hashlib.sha256(xml).hexdigest()
    assert parsed.raw_xml == xml
    assert len(parsed.items) == 1
    item = parsed.items[0]
    assert item.product_code == 'PROD-NFE-001'
    assert item.description == 'Glicerina vegetal'
    assert item.quantity == Decimal('2.5000')
    assert item.unit_code == 'KG'
    assert item.unit_price == Decimal('10.0000')
    assert item.product_total == Decimal('25.00')
    assert item.tax_amount == Decimal('1.25')
    assert item.lot_number == 'LOTE-GLI-001'
    assert item.manufacturing_date == date(2026, 8, 1)
    assert item.expiry_date == date(2027, 8, 1)


@pytest.mark.parametrize(
    ('overrides', 'expected_fragment'),
    (
        ({'model': '65'}, 'modelo 55'),
        ({'status': '110'}, 'autorizada'),
        ({'key': '123'}, '44 dígitos'),
        ({'inf_key': '3' * 44}, 'diverge'),
        ({'include_item': False, 'product_total': '0.00'}, 'item'),
    ),
)
def test_parse_rejects_invalid_nfe_identity_or_authorization(overrides, expected_fragment):
    _max_size, error_class, parse_nfe_xml = nfe_parser_contract()

    with pytest.raises(error_class) as error:
        parse_nfe_xml(authorized_nfe_xml(**overrides))

    assert expected_fragment.casefold() in str(error.value).casefold()


@pytest.mark.parametrize(
    'overrides',
    (
        {'quantity': '-1.0000', 'item_total': '-10.00', 'product_total': '-10.00'},
        {'quantity': 'NaN'},
        {'unit_price': 'Infinity'},
        {'item_total': 'NaN', 'product_total': 'NaN'},
    ),
)
def test_parse_rejects_negative_or_non_finite_numbers(overrides):
    _max_size, error_class, parse_nfe_xml = nfe_parser_contract()

    with pytest.raises(error_class):
        parse_nfe_xml(authorized_nfe_xml(**overrides))


def test_parse_rejects_malformed_and_mismatched_totals():
    _max_size, error_class, parse_nfe_xml = nfe_parser_contract()

    with pytest.raises(error_class):
        parse_nfe_xml(b'<nfeProc>')
    with pytest.raises(error_class) as mismatch:
        parse_nfe_xml(authorized_nfe_xml(product_total='24.99'))

    assert 'total' in str(mismatch.value).casefold()


def test_malicious_doctype_and_entity_are_rejected_before_xml_parsing():
    _max_size, error_class, parse_nfe_xml = nfe_parser_contract()
    malicious = (
        b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        + authorized_nfe_xml()
    )

    with pytest.raises(error_class) as error:
        parse_nfe_xml(malicious)

    assert 'doctype' in str(error.value).casefold() or 'entity' in str(error.value).casefold()


def test_size_limit_accepts_exactly_ten_mib_and_rejects_one_extra_byte():
    max_size, error_class, parse_nfe_xml = nfe_parser_contract()
    xml = authorized_nfe_xml()
    closing_tag = b'</nfeProc>'
    closing_index = xml.rfind(closing_tag)
    comment_overhead = len(b'<!---->')
    padding_size = max_size - len(xml) - comment_overhead
    exact_xml = (
        xml[:closing_index]
        + b'<!--'
        + (b'x' * padding_size)
        + b'-->'
        + xml[closing_index:]
    )

    assert len(exact_xml) == max_size
    assert parse_nfe_xml(exact_xml).access_key == NFE_KEY

    with pytest.raises(error_class) as error:
        parse_nfe_xml(exact_xml + b' ')

    assert '10 MiB' in str(error.value)


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
