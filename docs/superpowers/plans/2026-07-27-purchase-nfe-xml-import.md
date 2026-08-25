# Purchase NF-e XML Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe, auditable NF-e model 55 import workflow that validates an inbound purchase XML, previews mappings and divergences, and atomically creates draft fiscal and purchase receipt records only after human confirmation.

**Architecture:** Store the original XML in `ProtectedFile`, parse it with `defusedxml`, normalize it into immutable import/item records, resolve products and fiscal references through explicit mappings, and confirm through a transaction-locked application service. Upload/preview and confirmation are separate API/UI operations; neither posts stock, approves fiscal data, nor releases quality.

**Tech Stack:** Python 3.13, Django 5.2.16, Django REST Framework 3.17.1, PostgreSQL, defusedxml 0.7.1, Bootstrap 5, pytest-django.

## Global Constraints

- Support inbound NF-e model 55 only.
- Reject DTD/entity expansion, malformed XML, unsupported model, invalid 44-digit access key, duplicate hash/key, supplier/company mismatch, totals mismatch, and unresolved required references.
- The original XML must be encrypted and stored as a protected fiscal file.
- Confirmation must create `FiscalDocument` and `PurchaseReceipt` in draft in one transaction.
- Import must not post stock, approve fiscal data, create a financial settlement, or release quality.
- Preserve existing fiscal review, procurement receipt, QA, and stock posting workflows.
- Record user, timestamps, warnings, errors, hash, access key, generated records, and audit events.
- Do not modify or delete user-owned untracked files.

---

## File Structure

- `procurement/models.py`: supplier-product mapping, XML import header, and normalized item records.
- `procurement/xml_parser.py`: secure NF-e parsing into typed immutable payloads.
- `procurement/xml_import.py`: upload, validation, matching, and atomic confirmation services.
- `procurement/serializers.py`: upload, mapping update, preview, and confirmation contracts.
- `procurement/views.py`, `procurement/urls.py`: import CRUD and confirm action.
- `procurement/admin.py`: read-only operational inspection of imports.
- `procurement/migrations/0007_purchase_nfe_xml_import.py`: schema, constraints, and permissions.
- `base/ui/registry.py`: supplier mappings and XML import resource visibility.
- `base/ui/urls.py`, `base/ui/views.py`: upload/preview wizard.
- `templates/app/purchase_xml_upload.html`: protected XML upload.
- `templates/app/purchase_xml_preview.html`: item matching and divergence preview.
- `tests/fixtures/nfe_purchase_valid.xml`: synthetic valid NF-e fixture.
- `tests/test_purchase_xml_import.py`: parser, validation, transaction, API, UI, and security tests.
- `docs/architecture/procurement.md`, `docs/architecture/fiscal.md`, `docs/pdf/manual_usuario.md`: workflow documentation.

### Task 1: Import and mapping schema

**Files:**
- Modify: `procurement/models.py`
- Create: `procurement/migrations/0007_purchase_nfe_xml_import.py`
- Modify: `procurement/admin.py`
- Test: `tests/test_purchase_xml_import.py`

**Interfaces:**
- Produces: `SupplierProductMapping`, `PurchaseInvoiceXmlImport`, and `PurchaseInvoiceXmlImportItem`.
- Consumes: `BusinessPartner`, `Product`, `PurchaseOrder`, `PurchaseOrderItem`, fiscal references, `ProtectedFile`, and authenticated users.

- [ ] **Step 1: Write failing schema tests**

```python
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError


@pytest.mark.django_db
def test_supplier_product_mapping_is_unique_by_supplier_code(supplier, product):
    from procurement.models import SupplierProductMapping

    SupplierProductMapping.objects.create(
        supplier=supplier,
        product=product,
        supplier_code='FORN-001',
        gtin='7891234567890',
    )
    with pytest.raises(ValidationError):
        duplicate = SupplierProductMapping(
            supplier=supplier,
            product=product,
            supplier_code='FORN-001',
            gtin='',
        )
        duplicate.full_clean()


@pytest.mark.django_db
def test_xml_import_cannot_be_confirmed_without_resolved_items(xml_import):
    from procurement.models import PurchaseInvoiceXmlImport

    xml_import.status = PurchaseInvoiceXmlImport.Status.CONFIRMED
    with pytest.raises(ValidationError) as error:
        xml_import.full_clean()
    assert 'status' in error.value.message_dict
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py -k "mapping_is_unique or cannot_be_confirmed"
```

Expected: collection fails because the models do not exist.

- [ ] **Step 3: Add the three models**

Add these complete public fields and constraints:

```python
class SupplierProductMapping(SingleInstanceModel):
    supplier = models.ForeignKey(
        BusinessPartner, on_delete=models.PROTECT, related_name='product_mappings'
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='supplier_mappings'
    )
    supplier_code = models.CharField('código no fornecedor', max_length=80, blank=True)
    gtin = models.CharField('GTIN/EAN', max_length=14, blank=True)
    is_active = models.BooleanField('ativo', default=True)

    class Meta:
        ordering = ['supplier__legal_name', 'supplier_code', 'gtin']
        constraints = [
            models.UniqueConstraint(
                fields=['supplier', 'supplier_code'],
                condition=~models.Q(supplier_code=''),
                name='unique_supplier_product_code',
            ),
            models.UniqueConstraint(
                fields=['supplier', 'gtin'],
                condition=~models.Q(gtin=''),
                name='unique_supplier_product_gtin',
            ),
        ]

    def clean(self):
        if not self.supplier_code and not self.gtin:
            raise ValidationError({'supplier_code': 'Informe código do fornecedor ou GTIN.'})
        if self.supplier.partner_type not in {
            BusinessPartner.PartnerType.SUPPLIER,
            BusinessPartner.PartnerType.MANUFACTURER,
            BusinessPartner.PartnerType.DISTRIBUTOR,
        }:
            raise ValidationError({'supplier': 'O parceiro deve ser fornecedor.'})


class PurchaseInvoiceXmlImport(SingleInstanceModel):
    class Status(models.TextChoices):
        UPLOADED = 'uploaded', 'Enviado'
        PENDING_MAPPING = 'pending_mapping', 'Pendente de associação'
        READY = 'ready', 'Pronto para confirmar'
        CONFIRMED = 'confirmed', 'Confirmado'
        REJECTED = 'rejected', 'Rejeitado'

    protected_file = models.OneToOneField(
        'files.ProtectedFile', on_delete=models.PROTECT, related_name='purchase_xml_import'
    )
    content_hash = models.CharField('hash SHA-256', max_length=128, unique=True)
    access_key = models.CharField(
        'chave de acesso', max_length=44, unique=True, null=True, blank=True
    )
    status = models.CharField(
        'status', max_length=24, choices=Status.choices, default=Status.UPLOADED
    )
    supplier = models.ForeignKey(
        BusinessPartner, on_delete=models.PROTECT, related_name='purchase_xml_imports'
    )
    company = models.ForeignKey(
        'fiscal.FiscalCompany', on_delete=models.PROTECT, related_name='purchase_xml_imports'
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name='xml_imports'
    )
    fiscal_document = models.OneToOneField(
        'fiscal.FiscalDocument',
        on_delete=models.PROTECT,
        related_name='purchase_xml_import',
        null=True,
        blank=True,
    )
    purchase_receipt = models.OneToOneField(
        PurchaseReceipt,
        on_delete=models.PROTECT,
        related_name='purchase_xml_import',
        null=True,
        blank=True,
    )
    document_number = models.CharField('número', max_length=80, blank=True)
    series = models.CharField('série', max_length=20, blank=True)
    issue_date = models.DateField('emissão', null=True, blank=True)
    authorization_protocol = models.CharField(
        'protocolo de autorização', max_length=80, blank=True
    )
    authorization_at = models.DateTimeField('autorizada em', null=True, blank=True)
    total_products = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0.0000')
    )
    total_taxes = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0.0000')
    )
    total_amount = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0.0000')
    )
    parsed_summary = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    errors = models.JSONField(default=list, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_purchase_xml_imports',
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='confirmed_purchase_xml_imports',
        null=True,
        blank=True,
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['supplier', 'issue_date']),
            models.Index(fields=['purchase_order']),
        ]
        permissions = [
            ('import_purchaseinvoicexml', 'Pode importar XML de NF-e de compra'),
            ('confirm_purchaseinvoicexml', 'Pode confirmar XML de NF-e de compra'),
        ]

    def clean(self):
        errors = {}
        if self.purchase_order_id and self.purchase_order.supplier_id != self.supplier_id:
            errors['purchase_order'] = 'O pedido deve pertencer ao fornecedor do XML.'
        if self.status == self.Status.CONFIRMED:
            if not self.fiscal_document_id or not self.purchase_receipt_id:
                errors['status'] = 'Importação confirmada exige documento e recebimento.'
            if self.pk and self.items.exclude(match_status='matched').exists():
                errors['status'] = 'Todos os itens devem estar associados antes da confirmação.'
        if self.status in {self.Status.READY, self.Status.CONFIRMED} and not self.access_key:
            errors['access_key'] = 'Importação pronta exige chave de acesso válida.'
        if (
            self.status in {self.Status.READY, self.Status.CONFIRMED}
            and not self.authorization_protocol
        ):
            errors['authorization_protocol'] = 'Importação pronta exige protocolo de autorização.'
        if errors:
            raise ValidationError(errors)


class PurchaseInvoiceXmlImportItem(SingleInstanceModel):
    class MatchStatus(models.TextChoices):
        UNMATCHED = 'unmatched', 'Não associado'
        MATCHED = 'matched', 'Associado'
        DIVERGENT = 'divergent', 'Divergente'

    xml_import = models.ForeignKey(
        PurchaseInvoiceXmlImport, on_delete=models.CASCADE, related_name='items'
    )
    line_number = models.PositiveIntegerField('linha')
    supplier_code = models.CharField('código do fornecedor', max_length=80, blank=True)
    gtin = models.CharField('GTIN/EAN', max_length=14, blank=True)
    description = models.CharField('descrição', max_length=255)
    ncm_code = models.CharField('NCM', max_length=16)
    cfop_code = models.CharField('CFOP', max_length=8)
    unit_code = models.CharField('unidade', max_length=20)
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit_price = models.DecimalField(max_digits=14, decimal_places=4)
    total_amount = models.DecimalField(max_digits=14, decimal_places=4)
    tax_summary = models.JSONField(default=dict, blank=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    order_item = models.ForeignKey(
        PurchaseOrderItem, on_delete=models.PROTECT, null=True, blank=True
    )
    fiscal_unit = models.ForeignKey(
        'fiscal.FiscalUnit', on_delete=models.PROTECT, null=True, blank=True
    )
    ncm = models.ForeignKey(
        'fiscal.FiscalNCM', on_delete=models.PROTECT, null=True, blank=True
    )
    cfop = models.ForeignKey(
        'fiscal.FiscalOperationCode', on_delete=models.PROTECT, null=True, blank=True
    )
    tax_situation = models.ForeignKey(
        'fiscal.TaxSituation', on_delete=models.PROTECT, null=True, blank=True
    )
    match_status = models.CharField(
        max_length=16, choices=MatchStatus.choices, default=MatchStatus.UNMATCHED
    )
    validation_errors = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['xml_import', 'line_number']
        constraints = [
            models.UniqueConstraint(
                fields=['xml_import', 'line_number'], name='unique_purchase_xml_import_line'
            )
        ]

    def clean(self):
        errors = {}
        if self.quantity <= 0:
            errors['quantity'] = 'A quantidade deve ser maior que zero.'
        if self.unit_price < 0 or self.total_amount < 0:
            errors['unit_price'] = 'Valores não podem ser negativos.'
        if self.order_item_id and self.product_id != self.order_item.product_id:
            errors['product'] = 'O produto deve corresponder ao item do pedido.'
        if (
            self.order_item_id
            and self.xml_import_id
            and self.order_item.order_id != self.xml_import.purchase_order_id
        ):
            errors['order_item'] = 'O item deve pertencer ao pedido associado à importação.'
        if self.match_status == self.MatchStatus.MATCHED and not all(
            (
                self.product_id,
                self.order_item_id,
                self.fiscal_unit_id,
                self.ncm_id,
                self.cfop_id,
                self.tax_situation_id,
            )
        ):
            errors['match_status'] = 'A associação exige todas as referências obrigatórias.'
        if errors:
            raise ValidationError(errors)
```

- [ ] **Step 4: Generate and inspect migration**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py makemigrations procurement
```

Expected: one migration with the three models, partial unique constraints,
indexes, and custom permissions.

- [ ] **Step 5: Register read-only import admin and editable mapping admin**

`PurchaseInvoiceXmlImportAdmin` and its item inline must make hash, access key,
parsed summary, errors, generated records, users, and timestamps read-only.
`SupplierProductMappingAdmin` allows normal CRUD with supplier/product
autocomplete.

- [ ] **Step 6: Run model tests and commit**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py -k "mapping_is_unique or cannot_be_confirmed"
```

Expected: PASS.

```bash
git add procurement/models.py procurement/migrations/0007_*.py procurement/admin.py tests/test_purchase_xml_import.py
git commit -m "feat: add purchase invoice xml import records"
```

### Task 2: Secure NF-e parser

**Files:**
- Create: `procurement/xml_parser.py`
- Create: `tests/fixtures/nfe_purchase_valid.xml`
- Test: `tests/test_purchase_xml_import.py`

**Interfaces:**
- Produces: `NFePayload`, `NFeItemPayload`, and `parse_nfe_xml(content: bytes) -> NFePayload`.
- Consumes: at most 5 MiB of XML bytes.

- [ ] **Step 1: Add a synthetic valid fixture**

Create a namespaced `nfeProc` fixture containing:

- model `55`;
- a valid synthetic 44-digit key in `infNFe@Id`;
- emit CNPJ matching the supplier fixture;
- dest CNPJ matching the fiscal company fixture;
- number, series, issue timestamp;
- two `det` items with `cProd`, `cEAN`, `xProd`, `NCM`, `CFOP`, `uCom`,
  `qCom`, `vUnCom`, `vProd`, and ICMS data;
- `ICMSTot` with `vProd`, `vICMS`, `vIPI`, `vPIS`, `vCOFINS`, and `vNF`.
- `protNFe/infProt` with matching `chNFe`, `cStat=100`, protocol, and receipt timestamp.

All names and documents must be synthetic and explicitly marked for tests.

- [ ] **Step 2: Write parser and attack tests**

```python
def test_parser_reads_namespaced_model_55_fixture():
    from procurement.xml_parser import parse_nfe_xml

    payload = parse_nfe_xml(Path('tests/fixtures/nfe_purchase_valid.xml').read_bytes())
    assert payload.model == '55'
    assert len(payload.access_key) == 44
    assert payload.number == '123'
    assert payload.authorization_protocol
    assert len(payload.items) == 2
    assert payload.items[0].supplier_code == 'FORN-001'


@pytest.mark.parametrize(
    'content',
    [
        b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',
        b'<broken>',
        b'',
    ],
)
def test_parser_rejects_unsafe_or_malformed_xml(content):
    from procurement.xml_parser import NFeParseError, parse_nfe_xml

    with pytest.raises(NFeParseError):
        parse_nfe_xml(content)
```

- [ ] **Step 3: Verify failures**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py -k "parser_"
```

Expected: FAIL because the parser does not exist.

- [ ] **Step 4: Implement typed parser**

Create:

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree


MAX_XML_BYTES = 5 * 1024 * 1024


class NFeParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NFeItemPayload:
    line_number: int
    supplier_code: str
    gtin: str
    description: str
    ncm_code: str
    cfop_code: str
    unit_code: str
    quantity: Decimal
    unit_price: Decimal
    total_amount: Decimal
    tax_summary: dict[str, str]


@dataclass(frozen=True, slots=True)
class NFePayload:
    access_key: str
    model: str
    number: str
    series: str
    issued_at: datetime
    issuer_document: str
    recipient_document: str
    total_products: Decimal
    total_taxes: Decimal
    total_amount: Decimal
    authorization_protocol: str
    authorization_at: datetime
    items: tuple[NFeItemPayload, ...]


def _required_text(node, path):
    value = node.findtext(path)
    if value is None or not value.strip():
        raise NFeParseError(f'Campo obrigatório ausente: {path}')
    return value.strip()


def _decimal(node, path):
    try:
        return Decimal(_required_text(node, path)).quantize(Decimal('0.0001'))
    except InvalidOperation as exc:
        raise NFeParseError(f'Valor decimal inválido: {path}') from exc


def _tax_group(taxes, container):
    group = taxes.find(f'{{*}}{container}')
    if group is None:
        return {}
    detail = next((child for child in group if len(child)), group)
    return {
        child.tag.rsplit('}', 1)[-1]: (child.text or '').strip()
        for child in detail
        if child.text
    }


def _valid_access_key(value):
    if len(value) != 44 or not value.isdigit():
        return False
    weights = tuple(range(2, 10))
    total = sum(
        int(digit) * weights[index % len(weights)]
        for index, digit in enumerate(reversed(value[:43]))
    )
    candidate = 11 - (total % 11)
    expected = 0 if candidate >= 10 else candidate
    return expected == int(value[-1])


def parse_nfe_xml(content: bytes) -> NFePayload:
    if not content or len(content) > MAX_XML_BYTES:
        raise NFeParseError('XML vazio ou maior que 5 MiB.')
    try:
        root = ElementTree.fromstring(content)
    except Exception as exc:
        raise NFeParseError('XML inválido ou inseguro.') from exc
    info = root.find('.//{*}infNFe')
    if info is None:
        raise NFeParseError('Estrutura infNFe não encontrada.')
    access_key = str(info.attrib.get('Id', '')).removeprefix('NFe')
    if not _valid_access_key(access_key):
        raise NFeParseError('Chave de acesso inválida.')
    ide = info.find('{*}ide')
    issuer = info.find('{*}emit')
    recipient = info.find('{*}dest')
    totals = info.find('{*}total/{*}ICMSTot')
    protocol = root.find('.//{*}protNFe/{*}infProt')
    if None in (ide, issuer, recipient, totals, protocol):
        raise NFeParseError('Cabeçalho obrigatório da NF-e incompleto.')
    if _required_text(protocol, '{*}cStat') != '100':
        raise NFeParseError('A NF-e não está autorizada para uso.')
    if _required_text(protocol, '{*}chNFe') != access_key:
        raise NFeParseError('A chave do protocolo diverge da NF-e.')
    items = []
    for detail in info.findall('{*}det'):
        product = detail.find('{*}prod')
        taxes = detail.find('{*}imposto')
        items.append(NFeItemPayload(
            line_number=int(detail.attrib['nItem']),
            supplier_code=_required_text(product, '{*}cProd'),
            gtin=product.findtext('{*}cEAN', '').strip(),
            description=_required_text(product, '{*}xProd'),
            ncm_code=_required_text(product, '{*}NCM'),
            cfop_code=_required_text(product, '{*}CFOP'),
            unit_code=_required_text(product, '{*}uCom'),
            quantity=_decimal(product, '{*}qCom'),
            unit_price=_decimal(product, '{*}vUnCom'),
            total_amount=_decimal(product, '{*}vProd'),
            tax_summary={
                'icms': _tax_group(taxes, 'ICMS'),
                'ipi': _tax_group(taxes, 'IPI'),
                'pis': _tax_group(taxes, 'PIS'),
                'cofins': _tax_group(taxes, 'COFINS'),
            },
        ))
    issued_at = datetime.fromisoformat(_required_text(ide, '{*}dhEmi'))
    total_taxes = sum(
        (_decimal(totals, path) for path in ('{*}vICMS', '{*}vIPI', '{*}vPIS', '{*}vCOFINS')),
        Decimal('0.0000'),
    )
    return NFePayload(
        access_key=access_key,
        model=_required_text(ide, '{*}mod'),
        number=_required_text(ide, '{*}nNF'),
        series=_required_text(ide, '{*}serie'),
        issued_at=issued_at,
        issuer_document=_required_text(issuer, '{*}CNPJ'),
        recipient_document=_required_text(recipient, '{*}CNPJ'),
        total_products=_decimal(totals, '{*}vProd'),
        total_taxes=total_taxes,
        total_amount=_decimal(totals, '{*}vNF'),
        authorization_protocol=_required_text(protocol, '{*}nProt'),
        authorization_at=datetime.fromisoformat(_required_text(protocol, '{*}dhRecbto')),
        items=tuple(items),
    )
```

- [ ] **Step 5: Run parser tests and commit**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py -k "parser_"
```

Expected: PASS.

```bash
git add procurement/xml_parser.py tests/fixtures/nfe_purchase_valid.xml tests/test_purchase_xml_import.py
git commit -m "feat: parse inbound nfe xml safely"
```

### Task 3: Upload, validation, and matching service

**Files:**
- Create: `procurement/xml_import.py`
- Test: `tests/test_purchase_xml_import.py`

**Interfaces:**
- Consumes: `parse_nfe_xml()`, supplier/order/company, protected file storage, supplier mappings, and fiscal reference tables.
- Produces: `create_purchase_xml_import(*, content, file_name, purchase_order, company, user) -> PurchaseInvoiceXmlImport` and `refresh_purchase_xml_matches(xml_import)`.

- [ ] **Step 1: Write failing validation tests**

```python
@pytest.mark.django_db
def test_upload_encrypts_xml_and_marks_fully_mapped_import_ready(
    valid_nfe_bytes, purchase_order, fiscal_company, user, complete_xml_reference_data
):
    from procurement.models import PurchaseInvoiceXmlImport
    from procurement.xml_import import create_purchase_xml_import

    result = create_purchase_xml_import(
        content=valid_nfe_bytes,
        file_name='entrada.xml',
        purchase_order=purchase_order,
        company=fiscal_company,
        user=user,
    )
    assert result.status == PurchaseInvoiceXmlImport.Status.READY
    assert result.protected_file.is_encrypted
    assert result.items.filter(match_status='matched').count() == 2


@pytest.mark.django_db
def test_upload_rejects_supplier_company_and_total_mismatch(
    valid_nfe_bytes, unrelated_order, fiscal_company, user
):
    from procurement.models import PurchaseInvoiceXmlImport
    from procurement.xml_import import create_purchase_xml_import

    result = create_purchase_xml_import(
        content=valid_nfe_bytes,
        file_name='entrada.xml',
        purchase_order=unrelated_order,
        company=fiscal_company,
        user=user,
    )
    assert result.status == PurchaseInvoiceXmlImport.Status.REJECTED
    assert any(error['field'] == 'issuer_document' for error in result.errors)
    assert result.protected_file.is_encrypted
```

- [ ] **Step 2: Verify failures**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py -k "upload_"
```

Expected: FAIL because `procurement.xml_import` does not exist.

- [ ] **Step 3: Implement upload and protected storage**

Implement:

```python
def digits(value):
    return ''.join(character for character in str(value or '') if character.isdigit())


def create_purchase_xml_import(*, content, file_name, purchase_order, company, user):
    digest = f'sha256:{hashlib.sha256(content).hexdigest()}'
    duplicate_hash = PurchaseInvoiceXmlImport.objects.filter(content_hash=digest).first()
    if duplicate_hash:
        raise ValidationError({
            'xml_file': f'Arquivo já importado no registro {duplicate_hash.pk}.'
        })
    protected_file = ProtectedFile.objects.create(
        source_module=ProtectedFile.SourceModule.FISCAL,
        source_model='procurement.PurchaseInvoiceXmlImport',
        source_record_id='pending',
        file_type=ProtectedFile.FileType.FISCAL_DOCUMENT,
        origin=ProtectedFile.Origin.UPLOAD,
        criticality=ProtectedFile.Criticality.HIGH,
        confidentiality=ProtectedFile.Confidentiality.RESTRICTED,
        title='XML de NF-e de entrada',
        file_name=file_name,
        file_reference='pending',
        mime_type='application/xml',
        file_size=0,
        content_hash=digest,
        uploaded_by=user,
        responsible=user,
    )
    protected_file.store_encrypted_content(
        content, file_name=file_name, mime_type='application/xml', user=user
    )
    try:
        payload = parse_nfe_xml(content)
    except NFeParseError as exc:
        xml_import = PurchaseInvoiceXmlImport.objects.create(
            protected_file=protected_file,
            content_hash=digest,
            supplier=purchase_order.supplier,
            company=company,
            purchase_order=purchase_order,
            status=PurchaseInvoiceXmlImport.Status.REJECTED,
            errors=[{'field': 'xml_file', 'message': str(exc)}],
            uploaded_by=user,
        )
        protected_file.source_record_id = str(xml_import.pk)
        protected_file.save(update_fields=['source_record_id', 'updated_at'])
        return xml_import

    validation_errors = []
    checks = (
        ('model', payload.model == '55', 'Somente NF-e modelo 55 é suportada.'),
        (
            'issuer_document',
            digits(purchase_order.supplier.document) == digits(payload.issuer_document),
            'O emitente não corresponde ao fornecedor do pedido.',
        ),
        (
            'recipient_document',
            digits(company.document) == digits(payload.recipient_document),
            'O destinatário não corresponde à empresa fiscal.',
        ),
        (
            'issue_date',
            payload.issued_at.date() <= timezone.localdate(),
            'A data de emissão da NF-e não pode estar no futuro.',
        ),
        (
            'total_products',
            sum(
                (item.total_amount for item in payload.items),
                Decimal('0.0000'),
            ) == payload.total_products,
            'A soma dos itens diverge do total de produtos.',
        ),
    )
    for field, condition, message in checks:
        if not condition:
            validation_errors.append({'field': field, 'message': message})
    duplicate_key = PurchaseInvoiceXmlImport.objects.filter(
        access_key=payload.access_key
    ).first()
    if duplicate_key:
        validation_errors.append({
            'field': 'access_key',
            'message': f'Chave já importada no registro {duplicate_key.pk}.',
        })

    try:
        with transaction.atomic():
            xml_import = PurchaseInvoiceXmlImport.objects.create(
                protected_file=protected_file,
                content_hash=digest,
                access_key=None if duplicate_key else payload.access_key,
                supplier=purchase_order.supplier,
                company=company,
                purchase_order=purchase_order,
                document_number=payload.number,
                series=payload.series,
                issue_date=payload.issued_at.date(),
                authorization_protocol=payload.authorization_protocol,
                authorization_at=payload.authorization_at,
                total_products=payload.total_products,
                total_taxes=payload.total_taxes,
                total_amount=payload.total_amount,
                status=(
                    PurchaseInvoiceXmlImport.Status.REJECTED
                    if validation_errors
                    else PurchaseInvoiceXmlImport.Status.UPLOADED
                ),
                parsed_summary={
                    'model': payload.model,
                    'issuer_document': digits(payload.issuer_document),
                    'recipient_document': digits(payload.recipient_document),
                    'item_count': len(payload.items),
                    'duplicate_access_key': payload.access_key if duplicate_key else '',
                },
                errors=validation_errors,
                uploaded_by=user,
            )
            protected_file.source_record_id = str(xml_import.pk)
            protected_file.title = (
                f'NF-e de entrada {payload.number}/{payload.series}'
            )
            protected_file.save(
                update_fields=['source_record_id', 'title', 'updated_at']
            )
            for item in payload.items:
                PurchaseInvoiceXmlImportItem.objects.create(
                    xml_import=xml_import,
                    line_number=item.line_number,
                    supplier_code=item.supplier_code,
                    gtin=item.gtin,
                    description=item.description,
                    ncm_code=item.ncm_code,
                    cfop_code=item.cfop_code,
                    unit_code=item.unit_code,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_amount=item.total_amount,
                    tax_summary=item.tax_summary,
                )
    except Exception:
        protected_file.delete_secure(
            reason='Falha ao persistir a importação estruturada.',
            user=user,
        )
        raise
    if validation_errors:
        return xml_import
    return refresh_purchase_xml_matches(xml_import)
```

- [ ] **Step 4: Implement deterministic matching**

`refresh_purchase_xml_matches()` must resolve:

```python
mapping = SupplierProductMapping.objects.filter(
    supplier=xml_import.supplier,
    is_active=True,
).filter(
    models.Q(supplier_code=item.supplier_code)
    | (models.Q(gtin=item.gtin) if item.gtin else models.Q(pk__in=[]))
).select_related('product').first()

order_item = xml_import.purchase_order.items.filter(product=mapping.product).first()
fiscal_unit = FiscalUnit.objects.filter(code__iexact=item.unit_code, is_active=True).first()
ncm = FiscalNCM.objects.filter(code=item.ncm_code, is_active=True).first()
cfop = FiscalOperationCode.objects.filter(
    code=item.cfop_code,
    direction__in=(
        FiscalOperationCode.Direction.INBOUND,
        FiscalOperationCode.Direction.BOTH,
    ),
    is_active=True,
).first()
tax_situation = TaxSituation.objects.filter(
    code=(
        item.tax_summary.get('icms', {}).get('CST')
        or item.tax_summary.get('icms', {}).get('CSOSN')
    ),
    is_active=True,
).first()
```

Set the item to `MATCHED` only when all six required references exist and the
XML quantity does not exceed the remaining order quantity. Otherwise set
`UNMATCHED` or `DIVERGENT` with explicit Portuguese `validation_errors`. Set the
header to `READY` only when every item is matched; otherwise set
`PENDING_MAPPING`.

- [ ] **Step 5: Run validation/matching tests and commit**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py -k "upload_ or matching"
```

Expected: PASS.

```bash
git add procurement/xml_import.py tests/test_purchase_xml_import.py
git commit -m "feat: validate and match purchase nfe imports"
```

### Task 4: Atomic draft confirmation

**Files:**
- Modify: `procurement/xml_import.py`
- Test: `tests/test_purchase_xml_import.py`

**Interfaces:**
- Consumes: a `READY` import with all references resolved.
- Produces: `confirm_purchase_xml_import(xml_import, user) -> tuple[FiscalDocument, PurchaseReceipt]`.

- [ ] **Step 1: Write failing confirmation tests**

```python
@pytest.mark.django_db(transaction=True)
def test_confirmation_creates_linked_drafts_without_stock_or_quality_release(
    ready_xml_import, confirmer
):
    from inventory.models import StockMovement
    from procurement.xml_import import confirm_purchase_xml_import

    document, receipt = confirm_purchase_xml_import(ready_xml_import, confirmer)

    assert document.status == document.Status.DRAFT
    assert document.document_type == document.DocumentType.INBOUND
    assert receipt.status == receipt.Status.DRAFT
    assert receipt.quality_status == receipt.QualityStatus.PENDING
    assert receipt.stock_entry_status == receipt.StockEntryStatus.PENDING
    assert document.items.count() == ready_xml_import.items.count()
    assert document.taxes.exists()
    assert StockMovement.objects.filter(source_purchase_receipt_item__receipt=receipt).count() == 0


@pytest.mark.django_db(transaction=True)
def test_confirmation_is_idempotent_and_rolls_back_partial_creation(
    ready_xml_import, confirmer, monkeypatch
):
    from procurement.xml_import import confirm_purchase_xml_import

    document, receipt = confirm_purchase_xml_import(ready_xml_import, confirmer)
    repeated = confirm_purchase_xml_import(ready_xml_import, confirmer)
    assert repeated == (document, receipt)
```

- [ ] **Step 2: Verify failures**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py -k "confirmation_"
```

Expected: FAIL because confirmation does not exist.

- [ ] **Step 3: Implement transaction-locked confirmation**

Implement:

```python
@transaction.atomic
def confirm_purchase_xml_import(xml_import, user):
    xml_import = PurchaseInvoiceXmlImport.objects.select_for_update().select_related(
        'company', 'supplier', 'purchase_order', 'fiscal_document', 'purchase_receipt',
        'protected_file',
    ).get(pk=xml_import.pk)
    if xml_import.status == xml_import.Status.CONFIRMED:
        return xml_import.fiscal_document, xml_import.purchase_receipt
    refresh_purchase_xml_matches(xml_import)
    xml_import.refresh_from_db()
    if xml_import.status != xml_import.Status.READY:
        raise ValidationError({'status': 'Resolva todas as associações antes de confirmar.'})

    receipt = PurchaseReceipt.objects.create(
        order=xml_import.purchase_order,
        status=PurchaseReceipt.Status.DRAFT,
        fiscal_document_number=xml_import.document_number,
        fiscal_received_at=timezone.now(),
        quality_status=PurchaseReceipt.QualityStatus.PENDING,
        stock_entry_status=PurchaseReceipt.StockEntryStatus.PENDING,
        received_by=user,
        notes=f'Criado pela importação XML {xml_import.access_key}.',
    )
    document = FiscalDocument.objects.create(
        company=xml_import.company,
        partner=xml_import.supplier,
        document_type=FiscalDocument.DocumentType.INBOUND,
        operation_type=FiscalDocument.OperationType.PURCHASE,
        number=xml_import.document_number,
        series=xml_import.series,
        issue_date=xml_import.issue_date,
        operation_date=timezone.localdate(),
        status=FiscalDocument.Status.DRAFT,
        electronic_model=FiscalDocument.ElectronicModel.NFE_55,
        emission_status=FiscalDocument.EmissionStatus.AUTHORIZED,
        access_key=xml_import.access_key,
        authorization_protocol=xml_import.authorization_protocol,
        authorization_at=xml_import.authorization_at,
        purchase_order=xml_import.purchase_order,
        purchase_receipt=receipt,
        total_products=xml_import.total_products,
        total_taxes=xml_import.total_taxes,
        total_amount=xml_import.total_amount,
        notes=f'Importado do XML protegido {xml_import.protected_file.file_number}.',
    )
    for item in xml_import.items.select_related(
        'product', 'order_item', 'fiscal_unit', 'ncm', 'cfop', 'tax_situation'
    ):
        PurchaseReceiptItem.objects.create(
            receipt=receipt,
            order_item=item.order_item,
            product=item.product,
            received_quantity=item.quantity,
            accepted_quantity=Decimal('0.0000'),
            rejected_quantity=Decimal('0.0000'),
            unit=item.order_item.unit,
            notes=f'Linha {item.line_number} da NF-e; lote/validade pendentes.',
        )
        fiscal_item = FiscalDocumentItem.objects.create(
            document=document,
            line_number=item.line_number,
            product=item.product,
            fiscal_unit=item.fiscal_unit,
            ncm=item.ncm,
            cfop=item.cfop,
            tax_situation=item.tax_situation,
            quantity=item.quantity,
            unit_price=item.unit_price,
        )
        for tax_kind, fields in (
            (FiscalTax.TaxKind.ICMS, ('vBC', 'pICMS', 'vICMS')),
            (FiscalTax.TaxKind.IPI, ('vBC', 'pIPI', 'vIPI')),
            (FiscalTax.TaxKind.PIS, ('vBC', 'pPIS', 'vPIS')),
            (FiscalTax.TaxKind.COFINS, ('vBC', 'pCOFINS', 'vCOFINS')),
        ):
            summary = item.tax_summary.get(str(tax_kind), {})
            base_key, rate_key, amount_key = fields
            if all(summary.get(key) not in (None, '') for key in fields):
                FiscalTax.objects.create(
                    document=document,
                    item=fiscal_item,
                    tax_kind=tax_kind,
                    base_amount=Decimal(summary[base_key]),
                    rate_percent=Decimal(summary[rate_key]),
                    tax_amount=Decimal(summary[amount_key]),
                )
    xml_import.fiscal_document = document
    xml_import.purchase_receipt = receipt
    xml_import.status = xml_import.Status.CONFIRMED
    xml_import.confirmed_by = user
    xml_import.confirmed_at = timezone.now()
    xml_import.full_clean()
    xml_import.save(
        update_fields=[
            'fiscal_document', 'purchase_receipt', 'status',
            'confirmed_by', 'confirmed_at', 'updated_at',
        ]
    )
    xml_import.protected_file.fiscal_document = document
    xml_import.protected_file.save(update_fields=['fiscal_document', 'updated_at'])
    FiscalAuditTrail.record(
        user,
        'PurchaseInvoiceXmlImport',
        xml_import.pk,
        'confirmed',
        {'access_key': xml_import.access_key, 'document': document.pk, 'receipt': receipt.pk},
    )
    return document, receipt
```

Do not call `receipt.mark_received()`, `receipt.release_quality()`,
`receipt.post_stock()`, `document.submit_for_review()`,
`document.approve()`, or `document.post_entry()`.

- [ ] **Step 4: Add rollback fault test**

Patch `FiscalDocumentItem.objects.create` to raise on the second item and assert
that no fiscal document, receipt, or receipt item survives and the import remains
`READY`.

- [ ] **Step 5: Run confirmation tests and commit**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py -k "confirmation_"
```

Expected: PASS.

```bash
git add procurement/xml_import.py tests/test_purchase_xml_import.py
git commit -m "feat: confirm purchase xml into linked drafts"
```

### Task 5: REST upload, mapping, preview, and confirmation

**Files:**
- Modify: `procurement/serializers.py`
- Modify: `procurement/views.py`
- Modify: `procurement/urls.py`
- Test: `tests/test_purchase_xml_import.py`

**Interfaces:**
- Consumes: services from Tasks 3 and 4.
- Produces: `/api/procurement/xml-imports/`, item update endpoints, and `POST /api/procurement/xml-imports/<pk>/confirm/`.

- [ ] **Step 1: Write failing API tests**

```python
@pytest.mark.django_db
def test_xml_upload_requires_custom_permission(api_client, purchase_order, fiscal_company, user):
    api_client.force_authenticate(user)
    response = api_client.post(
        '/api/procurement/xml-imports/',
        {'xml_file': SimpleUploadedFile('entrada.xml', b'<xml/>'), 'purchase_order': purchase_order.pk, 'company': fiscal_company.pk},
        format='multipart',
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_confirm_endpoint_returns_linked_draft_ids(authorized_xml_client, ready_xml_import):
    response = authorized_xml_client.post(
        f'/api/procurement/xml-imports/{ready_xml_import.pk}/confirm/'
    )
    assert response.status_code == 200
    assert response.json()['fiscal_document']
    assert response.json()['purchase_receipt']
```

- [ ] **Step 2: Verify failures**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py -k "upload_requires or confirm_endpoint"
```

Expected: FAIL with 404.

- [ ] **Step 3: Add serializer contracts**

```python
class PurchaseInvoiceXmlUploadSerializer(serializers.Serializer):
    xml_file = serializers.FileField()
    purchase_order = serializers.PrimaryKeyRelatedField(queryset=PurchaseOrder.objects.all())
    company = serializers.PrimaryKeyRelatedField(queryset=FiscalCompany.objects.filter(is_active=True))

    def validate_xml_file(self, uploaded):
        if uploaded.size > MAX_XML_BYTES:
            raise serializers.ValidationError('O XML deve ter no máximo 5 MiB.')
        if not uploaded.name.lower().endswith('.xml'):
            raise serializers.ValidationError('Envie um arquivo com extensão .xml.')
        return uploaded


class PurchaseInvoiceXmlItemMatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseInvoiceXmlImportItem
        fields = ('product', 'order_item', 'fiscal_unit', 'ncm', 'cfop', 'tax_situation')

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.match_status = instance.MatchStatus.MATCHED
        instance.validation_errors = []
        instance.full_clean()
        instance.save()
        refresh_purchase_xml_matches(instance.xml_import)
        return instance
```

The import output serializer exposes parsed fields and nested items but marks
hash, access key, status, protected file, errors, users, generated records, and
timestamps read-only.

- [ ] **Step 4: Add permissioned viewsets**

`PurchaseInvoiceXmlImportViewSet.create()` must require
`procurement.import_purchaseinvoicexml`, read the upload once, and call
`create_purchase_xml_import()`. Its `confirm` action requires both
`procurement.confirm_purchaseinvoicexml` and the add permissions for
`FiscalDocument`, `FiscalDocumentItem`, `PurchaseReceipt`, and
`PurchaseReceiptItem`.

Register:

```python
router.register(
    'xml-imports',
    PurchaseInvoiceXmlImportViewSet,
    basename='xml-import',
)
router.register(
    'xml-import-items',
    PurchaseInvoiceXmlImportItemViewSet,
    basename='xml-import-item',
)
router.register(
    'supplier-product-mappings',
    SupplierProductMappingViewSet,
    basename='supplier-product-mapping',
)
```

- [ ] **Step 5: Run API tests and commit**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py -k "api or endpoint or upload_requires"
```

Expected: PASS.

```bash
git add procurement/serializers.py procurement/views.py procurement/urls.py tests/test_purchase_xml_import.py
git commit -m "feat: expose purchase xml import api"
```

### Task 6: Guided operational UI

**Files:**
- Modify: `base/ui/registry.py`
- Modify: `base/ui/urls.py`
- Modify: `base/ui/views.py`
- Create: `templates/app/purchase_xml_upload.html`
- Create: `templates/app/purchase_xml_preview.html`
- Test: `tests/test_purchase_xml_import.py`
- Test: `tests/test_app_ui.py`

**Interfaces:**
- Consumes: REST/service contracts from Task 5.
- Produces: `/app/procurement/xml-imports/new/` and `/app/procurement/xml-imports/<pk>/preview/`.

- [ ] **Step 1: Write failing wizard tests**

```python
@pytest.mark.django_db
def test_xml_upload_page_is_multipart_and_permission_protected(
    client, xml_import_operator
):
    client.force_login(xml_import_operator)
    response = client.get('/app/procurement/xml-imports/new/')
    assert response.status_code == 200
    assert b'enctype="multipart/form-data"' in response.content
    assert b'Nenhuma entrada de estoque' in response.content


@pytest.mark.django_db
def test_preview_disables_confirmation_when_items_are_unresolved(
    client, xml_import_operator, pending_xml_import
):
    client.force_login(xml_import_operator)
    response = client.get(
        f'/app/procurement/xml-imports/{pending_xml_import.pk}/preview/'
    )
    assert response.status_code == 200
    assert b'Confirmar importação' in response.content
    assert b'disabled' in response.content
```

- [ ] **Step 2: Verify failures**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py tests/test_app_ui.py -k "upload_page or preview_disables"
```

Expected: FAIL with 404.

- [ ] **Step 3: Implement upload and preview views**

The upload view uses a Django form with `xml_file`, `purchase_order`, and
`company`, calls the same upload service as the API, and redirects to preview.
The preview view:

- loads header, warnings, errors, and ordered items;
- renders current product/order/fiscal matches;
- posts one item mapping at a time through `PurchaseInvoiceXmlItemMatchSerializer`;
- shows quantity/value divergences;
- enables confirmation only for `READY`;
- calls `confirm_purchase_xml_import()` after a CSRF-protected explicit POST and
  redirects to the created purchase receipt.

Both views must require the matching custom permission and log unexpected
failures with the request ID.

- [ ] **Step 4: Register resources and create templates**

Add “Importações de NF-e” and “Produtos por fornecedor” under Compras.
The templates use existing page headers, status badges, field error patterns,
responsive tables, and these permanent warnings:

```html
<div class="alert alert-warning" role="alert">
  A confirmação cria apenas rascunhos fiscal e de recebimento.
  Nenhuma entrada de estoque, aprovação fiscal ou liberação de qualidade é executada.
</div>
```

- [ ] **Step 5: Run UI regression tests and commit**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py tests/test_app_ui.py tests/test_action_registry.py
```

Expected: PASS.

```bash
git add base/ui/registry.py base/ui/urls.py base/ui/views.py templates/app/purchase_xml_upload.html templates/app/purchase_xml_preview.html tests/test_purchase_xml_import.py tests/test_app_ui.py
git commit -m "feat: add guided purchase xml import ui"
```

### Task 7: Documentation and XML import verification

**Files:**
- Modify: `docs/architecture/procurement.md`
- Modify: `docs/architecture/fiscal.md`
- Modify: `docs/pdf/especificacao_funcional.md`
- Modify: `docs/pdf/manual_usuario.md`
- Modify: `mkdocs.yml`

**Interfaces:**
- Consumes: all XML import tasks.
- Produces: documented workflow, rollback guidance, and final verification.

- [ ] **Step 1: Document the workflow and segregation**

Document upload, validation, mapping, preview, confirmation, fiscal review,
physical receipt, QA release, and stock posting as separate steps. Include:

```text
Importar e confirmar um XML não comprova o recebimento físico, não aprova a
nota, não gera saldo e não libera o lote. XML rejeitado ou incompleto não cria
documento fiscal nem recebimento parcial.
```

Document duplicate resolution by access key/hash and how to correct mappings
without altering the encrypted source XML.

- [ ] **Step 2: Run Django and migration checks**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py makemigrations --check
```

Expected: exit 0 and `No changes detected`.

- [ ] **Step 3: Run procurement/fiscal/files/inventory tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_purchase_xml_import.py tests/test_procurement.py tests/test_fiscal.py tests/test_files.py tests/test_inventory.py
```

Expected: PASS.

- [ ] **Step 4: Run lint**

Run:

```bash
.venv/bin/ruff check procurement tests/test_purchase_xml_import.py
```

Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add docs/architecture/procurement.md docs/architecture/fiscal.md docs/pdf/especificacao_funcional.md docs/pdf/manual_usuario.md mkdocs.yml
git commit -m "docs: document purchase nfe xml import"
```
