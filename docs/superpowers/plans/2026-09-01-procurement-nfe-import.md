# Procurement NF-e Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import an authorized inbound NF-e model 55 into an approved purchase order as one auditable draft receipt without posting stock.

**Architecture:** Parse XML into immutable data objects, validate business rules under a purchase-order row lock, persist receipt metadata behind database idempotency, and encrypt the source XML through `ProtectedFile`. Expose the service through one DRF multipart collection action and the existing HTML action catalog.

**Tech Stack:** Django 6, Django REST Framework, PostgreSQL, defusedxml 0.7.1, AES-256-GCM protected storage, pytest-django.

## Global Constraints

- Accept only authorized NF-e model 55 linked to an approved purchase order.
- Maximum XML size is exactly 10 MiB.
- Do not create stock lots, post stock, release quality, query SEFAZ, or log XML content.
- Require a 44-digit access key and `cStat=100`.
- Preserve the original XML encrypted and store its clear-content SHA-256.
- Use `select_for_update()` and a PostgreSQL uniqueness constraint.
- Run tests only through `bash scripts/test.sh` or `.venv/bin/python -m <tool>`.

---

## File map

- Create `procurement/nfe_xml_import.py`: parser, validation and transactional import.
- Create `procurement/migrations/0003_purchase_receipt_nfe_import.py`: schema additions.
- Modify `procurement/models.py`: NF-e metadata and manufacturing date.
- Modify `procurement/serializers.py`: read-only NF-e metadata and nested imported items.
- Modify `procurement/views.py`: multipart `import_xml` action.
- Modify `base/ui/actions/modules/procurement.py`: expose action.
- Modify `base/ui/actions/inventory.py`: order/file fields and approved-order queryset.
- Modify `base/ui/actions/factory.py`: multipart inference and upload icon.
- Modify `requirements.txt`: pin `defusedxml==0.7.1`.
- Create `tests/test_procurement_nfe_import.py`: parser, domain, storage, API and UI tests.
- Modify `tests/test_action_catalog_completeness.py`: freeze the action contract.

### Task 1: Add the NF-e receipt schema

**Files:**
- Modify: `procurement/models.py`
- Create: `procurement/migrations/0003_purchase_receipt_nfe_import.py`
- Test: `tests/test_procurement_nfe_import.py`

**Interfaces:**
- Produces: `PurchaseReceipt.nfe_access_key`, `nfe_xml_sha256`, `nfe_xml_file`.
- Produces: `PurchaseReceiptItem.manufacturing_date`.

- [ ] **Step 1: Write failing model tests**

Assert two non-empty equal keys violate the database constraint, multiple blank keys are allowed, deleting a linked protected file is blocked, and manufacturing date persists as a date.

- [ ] **Step 2: Prove the tests fail**

Run: `bash scripts/test.sh tests/test_procurement_nfe_import.py -k 'schema' -q`

Expected: FAIL because the fields do not exist.

- [ ] **Step 3: Add model fields and constraint**

Add to `PurchaseReceipt`:

```python
nfe_access_key = models.CharField('chave de acesso NF-e', max_length=44, blank=True)
nfe_xml_sha256 = models.CharField('hash do XML NF-e', max_length=64, blank=True)
nfe_xml_file = models.OneToOneField(
    'files.ProtectedFile',
    on_delete=models.PROTECT,
    related_name='purchase_receipt_nfe',
    null=True,
    blank=True,
    verbose_name='XML NF-e protegido',
)
```

Append this constraint:

```python
models.UniqueConstraint(
    fields=['nfe_access_key'],
    condition=~Q(nfe_access_key=''),
    name='unique_purchase_receipt_nfe_access_key',
)
```

Add to `PurchaseReceiptItem`:

```python
manufacturing_date = models.DateField('fabricação', null=True, blank=True)
```

Add an index on `manufacturing_date` and validate that manufacturing does not exceed expiry when both are present.

- [ ] **Step 4: Generate and inspect the migration**

Run: `DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py makemigrations procurement --name purchase_receipt_nfe_import`

Expected: `0003_purchase_receipt_nfe_import.py` containing four fields, one conditional constraint and one index.

- [ ] **Step 5: Run schema tests and commit**

Run: `bash scripts/test.sh tests/test_procurement_nfe_import.py -k 'schema' -q`

Expected: PASS.

```bash
git add procurement/models.py procurement/migrations/0003_purchase_receipt_nfe_import.py tests/test_procurement_nfe_import.py
git commit -m "feat(procurement): add nfe receipt metadata"
```

### Task 2: Build the hardened parser

**Files:**
- Create: `procurement/nfe_xml_import.py`
- Modify: `requirements.txt`
- Test: `tests/test_procurement_nfe_import.py`

**Interfaces:**
- Produces: `NfeItemData`, `NfeData`, `NfeImportError`, `parse_nfe_xml(xml_content)`.

- [ ] **Step 1: Add parser fixtures and failing tests**

Use one authorized `nfeProc` fixture containing `mod=55`, `chNFe`, `cStat=100`, emitente, destinatário, `vProd`, one item and `rastro`. Test header/item extraction, namespaces, CNPJ normalization, model/status/key enforcement, itemless XML, malformed XML, DOCTYPE/XXE, negative numbers, non-finite decimals and the 10 MiB boundary.

- [ ] **Step 2: Prove the parser tests fail**

Run: `bash scripts/test.sh tests/test_procurement_nfe_import.py -k 'parse or malicious or size' -q`

Expected: FAIL because the module is absent.

- [ ] **Step 3: Implement immutable parser contracts**

Create frozen slot dataclasses with these fields:

```python
@dataclass(frozen=True, slots=True)
class NfeItemData:
    product_code: str
    description: str
    quantity: Decimal
    unit_code: str
    unit_price: Decimal
    product_total: Decimal
    tax_amount: Decimal
    lot_number: str
    manufacturing_date: date | None
    expiry_date: date | None


@dataclass(frozen=True, slots=True)
class NfeData:
    access_key: str
    number: str
    series: str
    issue_date: date
    model: str
    authorization_status: str
    supplier_document: str
    supplier_name: str
    destination_document: str
    product_total: Decimal
    items: tuple[NfeItemData, ...]
    xml_sha256: str
    raw_xml: bytes
```

Implement local-name traversal, strict decimal/date helpers and `defusedxml.ElementTree.fromstring`. Reject any raw input containing `<!DOCTYPE` or `<!ENTITY` case-insensitively before parsing, require model `55`, status `100`, exactly 44 key digits, at least one item and exact `sum(item.product_total) == product_total.quantize(Decimal('0.01'))` after cent rounding.

- [ ] **Step 4: Add the dependency and run parser tests**

Add `defusedxml==0.7.1` to `requirements.txt` in alphabetical position.

Run: `bash scripts/test.sh tests/test_procurement_nfe_import.py -k 'parse or malicious or size' -q`

Expected: PASS.

- [ ] **Step 5: Commit the parser**

```bash
git add procurement/nfe_xml_import.py requirements.txt tests/test_procurement_nfe_import.py
git commit -m "feat(procurement): parse authorized nfe xml"
```

### Task 3: Implement locked business validation and protected storage

**Files:**
- Modify: `procurement/nfe_xml_import.py`
- Test: `tests/test_procurement_nfe_import.py`

**Interfaces:**
- Produces: `import_nfe_into_purchase_order(xml_content, *, purchase_order, user, file_name='nfe.xml') -> PurchaseReceipt`.
- Consumes: `ProtectedFile.store_encrypted_content()` and active `InstitutionSettings`.

- [ ] **Step 1: Write failing import tests**

Cover approved-order success, non-approved order, destination mismatch, supplier mismatch, unknown product, unit mismatch, partial receipt balance, duplicate key, manufacturing/expiry persistence, no stock rows, encrypted round trip through `read_encrypted_content(user)`, audit record, and storage cleanup when a mocked save fails.

- [ ] **Step 2: Prove they fail**

Run: `bash scripts/test.sh tests/test_procurement_nfe_import.py -k 'import and not endpoint' -q`

Expected: FAIL because the service is absent.

- [ ] **Step 3: Implement the transactional service**

Normalize documents with digits only. Inside `transaction.atomic()`, refetch the order with `PurchaseOrder.objects.select_for_update().select_related('supplier').prefetch_related('items__product', 'items__unit').get(pk=purchase_order.pk)`. Require `PurchaseOrder.Status.APPROVED`, match the active `InstitutionSettings.document` to the destination, and match the supplier document.

For each order item compute consumed quantity with:

```python
consumed = PurchaseReceiptItem.objects.filter(
    order_item=order_item,
).exclude(
    receipt__status=PurchaseReceipt.Status.CANCELLED,
).aggregate(total=models.Sum('received_quantity'))['total'] or ZERO_QUANTITY
remaining = order_item.quantity - consumed
```

Reject the imported quantity when it exceeds `remaining`.

Create the draft receipt/items, then create a `ProtectedFile` with fiscal source/type, upload origin, internal confidentiality, `source_model='PurchaseReceipt'`, `source_record_id=str(receipt.pk)`, uploaded/responsible user, clear hash and a canonical reserved reference `protected/nfe-<key>/<token>.enc`. Call `store_encrypted_content(raw_xml, file_name=file_name, mime_type='application/xml', user=user, reserved_reference=reserved_reference)`, assign it to `receipt.nfe_xml_file`, and save that field.

Wrap the atomic block in an outer `try/except`. If any exception escapes after the reserved path is created, call `default_storage.delete(reserved_reference)` when it exists, then re-raise. Translate duplicate-key `IntegrityError` to `NfeImportError('A NF-e já foi importada no sistema.')` outside the broken transaction.

- [ ] **Step 4: Run import and encryption tests**

Run: `bash scripts/test.sh tests/test_procurement_nfe_import.py -k 'import or encrypted or cleanup' -q`

Expected: PASS.

- [ ] **Step 5: Commit the service**

```bash
git add procurement/nfe_xml_import.py tests/test_procurement_nfe_import.py
git commit -m "feat(procurement): import nfe into locked purchase receipt"
```

### Task 4: Expose the multipart API

**Files:**
- Modify: `procurement/serializers.py`
- Modify: `procurement/views.py`
- Test: `tests/test_procurement_nfe_import.py`

**Interfaces:**
- Produces: POST `/api/v1/procurement/receipts/import_xml/` with `xml` and `order_id`.

- [ ] **Step 1: Write failing endpoint tests**

Test 201 with nested imported items, 400 for missing fields/domain errors, 403 without `add_purchasereceipt`, multipart parsing, and read-only rejection of NF-e metadata in ordinary CRUD payloads.

- [ ] **Step 2: Prove they fail**

Run: `bash scripts/test.sh tests/test_procurement_nfe_import.py -k 'endpoint' -q`

Expected: FAIL with 404.

- [ ] **Step 3: Extend serializers and viewset**

Expose `nfe_access_key`, `nfe_xml_sha256`, `nfe_xml_file` as read-only receipt fields and `manufacturing_date` on items. Add a nested read-only `items = PurchaseReceiptItemSerializer(many=True, read_only=True)` to the receipt serializer.

Add this action to `PurchaseReceiptViewSet`:

```python
@action(detail=False, methods=['post'], parser_classes=(MultiPartParser, FormParser))
def import_xml(self, request):
    upload = request.FILES.get('xml')
    order_id = request.data.get('order_id')
    if upload is None or not order_id:
        return Response({'detail': 'Informe o pedido e o arquivo XML NF-e.'}, status=400)
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    try:
        receipt = import_nfe_into_purchase_order(
            upload.read(), purchase_order=order, user=request.user, file_name=upload.name
        )
    except NfeImportError as error:
        return Response(_validation_response_payload(error), status=400)
    return Response(self.get_serializer(receipt).data, status=201)
```

- [ ] **Step 4: Run endpoint tests and commit**

Run: `bash scripts/test.sh tests/test_procurement_nfe_import.py -k 'endpoint' -q`

Expected: PASS.

```bash
git add procurement/serializers.py procurement/views.py tests/test_procurement_nfe_import.py
git commit -m "feat(procurement): expose nfe multipart import"
```

### Task 5: Add the HTML action catalog entry

**Files:**
- Modify: `base/ui/actions/modules/procurement.py`
- Modify: `base/ui/actions/inventory.py`
- Modify: `base/ui/actions/factory.py`
- Modify: `tests/test_action_catalog_completeness.py`
- Test: `tests/test_procurement_nfe_import.py`

**Interfaces:**
- Produces: collection action `procurement/receipts/import_xml` with relation `order_id` and file `xml`.

- [ ] **Step 1: Write failing catalog and HTML tests**

Assert action route `v1_procurement:receipt-import-xml`, permission `procurement.add_purchasereceipt`, `detail is False`, multipart submission, upload icon, approved-order queryset and successful browser-form POST.

- [ ] **Step 2: Prove they fail**

Run: `bash scripts/test.sh tests/test_action_catalog_completeness.py tests/test_procurement_nfe_import.py -k 'catalog or html' -q`

Expected: FAIL because the action is undiscoverable.

- [ ] **Step 3: Register exact field contracts**

Add `('receipts', 'import_xml')` to the procurement action keys. Add `('procurement', 'receipts', 'import_xml'): 'order_id:r,xml:f'`, labels for both fields, and `'f': FieldKind.FILE`. Map `order_id` to `PurchaseOrder` and filter its queryset to `status=PurchaseOrder.Status.APPROVED`. In the factory, infer `SubmissionFormat.MULTIPART` when any field is `FieldKind.FILE` and map `import_xml` to `feather-upload`.

- [ ] **Step 4: Run catalog/HTML tests and commit**

Run: `bash scripts/test.sh tests/test_action_catalog_completeness.py tests/test_procurement_nfe_import.py -k 'catalog or html' -q`

Expected: PASS.

```bash
git add base/ui/actions/modules/procurement.py base/ui/actions/inventory.py base/ui/actions/factory.py tests/test_action_catalog_completeness.py tests/test_procurement_nfe_import.py
git commit -m "feat(ui): add purchase receipt nfe import action"
```

### Task 6: Run NF-e gates

- [ ] **Step 1: Run focused suites**

Run: `bash scripts/test.sh tests/test_procurement_nfe_import.py tests/test_procurement.py tests/test_action_catalog_completeness.py tests/test_encryption.py -q`

Expected: all tests pass.

- [ ] **Step 2: Run migration and Django checks**

Run: `DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py makemigrations --check --dry-run && DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py check`

Expected: no pending migrations and no system check issues.

- [ ] **Step 3: Verify source and forbidden terms**

Run: `git -C /mnt/2c8d19a3-3bbb-4f90-b09f-9e17c780ce6a/Projects/rgnfarmasystem status --short && git grep -n -i -E 'farmacovigil|TechnicalResponsible' -- procurement base/ui/actions tests ':!docs/superpowers/**'`

Expected: source repository clean; no forbidden-term matches in the implementation.
