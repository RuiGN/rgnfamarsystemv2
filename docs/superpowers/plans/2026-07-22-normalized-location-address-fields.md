# Normalized Location Address Fields Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remover os campos textuais legados de cidade/UF dos recursos operacionais, manter somente os campos normalizados com labels finais `Cidade` e `UF`, e completar número/complemento de logradouro nos cadastros que já possuem logradouro.

**Architecture:** `auxiliary.StateProvince` e `auxiliary.City` continuam sendo a fonte da verdade. Os models deixam de espelhar `city/state` textuais e passam a validar diretamente `*_state_ref` e `*_city_ref`; serializers, registry, admin e templates genéricos herdam labels do model. Campos de número/complemento são adicionados somente onde já existe `street`/`*_street`.

**Tech Stack:** Python, Django ORM, Django REST Framework, PostgreSQL migrations, Bootstrap/Duralux templates genéricos.

## Global Constraints

- Não alterar `auxiliary.City.state`; esse campo é o relacionamento normalizado, não um campo legado de UF.
- Não alterar `governance.TechnicalResponsible.council_state`; esse campo representa UF do conselho profissional e já é uma FK normalizada.
- Não adicionar logradouro completo em registros que só armazenam cidade/UF de origem/notificador sem `street` existente.
- Labels finais em formulários/listas/API browsable: `*_state_ref` deve aparecer como `UF`; `*_city_ref` deve aparecer como `Cidade`.
- Campos legados textuais removidos não podem permanecer em serializers, registry, listagens, filtros, busca, admin ou testes.
- Migrations devem preservar dados: antes de remover colunas, falhar se houver registro com texto legado preenchido e FK normalizada vazia.
- Executar TDD: teste falhando antes de cada alteração de schema/contrato, depois migration/código mínimo, depois teste verde.

---

## Inventory

| App | Model | Remover | Manter com label final | Número/complemento |
| --- | --- | --- | --- | --- |
| `fiscal` | `FiscalCompany` | `city`, `state` | `city_ref` -> `Cidade`, `state_ref` -> `UF` | já possui `street_number`, `complement` |
| `fiscal` | `FiscalMunicipality` | `state` | `city_ref` -> `Cidade`, `state_ref` -> `UF` | não é endereço; não adicionar |
| `governance` | `InstitutionSettings` | `city`, `state` | `city_ref` -> `Cidade`, `state_ref` -> `UF` | já possui `street_number`, `complement` |
| `masters` | `BusinessPartner` | `city`, `state` | `city_ref` -> `Cidade`, `state_ref` -> `UF` | adicionar `street_number`, `complement` |
| `masters` | `Site` | `city`, `state` | `city_ref` -> `Cidade`, `state_ref` -> `UF` | adicionar `street_number`, `complement` |
| `audits` | `AuditPlan` | `venue_city`, `venue_state` | `venue_city_ref` -> `Cidade`, `venue_state_ref` -> `UF` | adicionar `venue_street_number`, `venue_complement` |
| `crm` | `SalesOrder` | `shipping_city`, `shipping_state` | `shipping_city_ref` -> `Cidade`, `shipping_state_ref` -> `UF` | adicionar `shipping_street_number`, `shipping_complement` |
| `crm` | `CustomerComplaint` | `city`, `state` | `city_ref` -> `Cidade`, `state_ref` -> `UF` | sem `street`; não adicionar |
| `pharmacovigilance` | `PharmacovigilanceCase` | `city`, `state` | `city_ref` -> `Cidade`, `state_ref` -> `UF` | sem `street`; não adicionar |
| `procurement` | `SupplierQualificationEvent` | `event_city`, `event_state` | `event_city_ref` -> `Cidade`, `event_state_ref` -> `UF` | adicionar `event_street_number`, `event_complement` |
| `procurement` | `PurchaseOrder` | `delivery_city`, `delivery_state` | `delivery_city_ref` -> `Cidade`, `delivery_state_ref` -> `UF` | adicionar `delivery_street_number`, `delivery_complement` |
| `recalls` | `MarketComplaint` | `city`, `state` | `city_ref` -> `Cidade`, `state_ref` -> `UF` | sem `street`; não adicionar |
| `training` | `TrainingSession` | `location_city`, `location_state` | `location_city_ref` -> `Cidade`, `location_state_ref` -> `UF` | adicionar `location_street_number`, `location_complement` |

## Files

- Modify: `base/normalized_locations.py`
- Modify: `fiscal/models.py`, `fiscal/serializers.py`, `fiscal/admin.py`
- Modify: `governance/models.py`, `governance/serializers.py`, `governance/admin.py`
- Modify: `masters/models.py`, `masters/serializers.py`, `masters/admin.py`
- Modify: `audits/models.py`, `audits/serializers.py`, `audits/admin.py`
- Modify: `crm/models.py`, `crm/serializers.py`, `crm/admin.py`
- Modify: `pharmacovigilance/models.py`, `pharmacovigilance/serializers.py`, `pharmacovigilance/admin.py`
- Modify: `procurement/models.py`, `procurement/serializers.py`, `procurement/admin.py`
- Modify: `recalls/models.py`, `recalls/serializers.py`, `recalls/admin.py`
- Modify: `training/models.py`, `training/serializers.py`, `training/admin.py`
- Modify: `base/ui/registry.py`
- Modify: `tests/test_normalized_locations.py`
- Modify: `tests/test_app_ui.py`
- Modify: `docs/architecture/auxiliary.md`
- Create: one migration per affected app using `python manage.py makemigrations <app>`

---

### Task 1: Freeze the Global Contract in Tests

**Files:**
- Modify: `tests/test_normalized_locations.py`

**Interfaces:**
- Consumes: current resource registry via `base.ui.registry.get_resource`.
- Produces: executable expectations for field removal, labels and address-number/complement additions.

- [ ] **Step 1: Add a failing inventory test**

Add this table-driven test to `tests/test_normalized_locations.py`:

```python
def test_location_models_keep_only_normalized_city_and_uf_with_final_labels():
    expectations = (
        ('fiscal', 'FiscalCompany', {'city', 'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        ('fiscal', 'FiscalMunicipality', {'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        ('governance', 'InstitutionSettings', {'city', 'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        ('masters', 'BusinessPartner', {'city', 'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        ('masters', 'Site', {'city', 'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        ('audits', 'AuditPlan', {'venue_city', 'venue_state'}, {'venue_city_ref': 'Cidade', 'venue_state_ref': 'UF'}),
        ('crm', 'SalesOrder', {'shipping_city', 'shipping_state'}, {'shipping_city_ref': 'Cidade', 'shipping_state_ref': 'UF'}),
        ('crm', 'CustomerComplaint', {'city', 'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        ('pharmacovigilance', 'PharmacovigilanceCase', {'city', 'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        ('procurement', 'SupplierQualificationEvent', {'event_city', 'event_state'}, {'event_city_ref': 'Cidade', 'event_state_ref': 'UF'}),
        ('procurement', 'PurchaseOrder', {'delivery_city', 'delivery_state'}, {'delivery_city_ref': 'Cidade', 'delivery_state_ref': 'UF'}),
        ('recalls', 'MarketComplaint', {'city', 'state'}, {'city_ref': 'Cidade', 'state_ref': 'UF'}),
        ('training', 'TrainingSession', {'location_city', 'location_state'}, {'location_city_ref': 'Cidade', 'location_state_ref': 'UF'}),
    )

    from django.apps import apps

    for app_label, model_name, removed_fields, normalized_labels in expectations:
        model = apps.get_model(app_label, model_name)
        model_fields = {field.name: field for field in model._meta.fields}
        assert removed_fields.isdisjoint(model_fields)
        for field_name, expected_label in normalized_labels.items():
            assert str(model_fields[field_name].verbose_name) == expected_label
```

- [ ] **Step 2: Add a failing address-completion test**

Add this test to the same file:

```python
def test_location_models_with_street_also_have_number_and_complement_fields():
    expectations = {
        'masters.BusinessPartner': {'street_number': 'número', 'complement': 'complemento'},
        'masters.Site': {'street_number': 'número', 'complement': 'complemento'},
        'audits.AuditPlan': {'venue_street_number': 'número', 'venue_complement': 'complemento'},
        'crm.SalesOrder': {'shipping_street_number': 'número', 'shipping_complement': 'complemento'},
        'procurement.SupplierQualificationEvent': {'event_street_number': 'número', 'event_complement': 'complemento'},
        'procurement.PurchaseOrder': {'delivery_street_number': 'número', 'delivery_complement': 'complemento'},
        'training.TrainingSession': {'location_street_number': 'número', 'location_complement': 'complemento'},
    }

    from django.apps import apps

    for model_path, expected_fields in expectations.items():
        app_label, model_name = model_path.split('.')
        model = apps.get_model(app_label, model_name)
        model_fields = {field.name: field for field in model._meta.fields}
        for field_name, expected_label in expected_fields.items():
            assert field_name in model_fields
            assert str(model_fields[field_name].verbose_name) == expected_label
            assert model_fields[field_name].blank is True
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_normalized_locations.py::test_location_models_keep_only_normalized_city_and_uf_with_final_labels tests/test_normalized_locations.py::test_location_models_with_street_also_have_number_and_complement_fields -q
```

Expected: both tests fail because legacy fields still exist, labels still include “normalizada”, and several number/complement fields are missing.

---

### Task 2: Replace Mirror Sync with Normalized Location Validation

**Files:**
- Modify: `base/normalized_locations.py`
- Modify: `tests/test_normalized_locations.py`

**Interfaces:**
- Produces: `validate_normalized_location(instance, *, city_ref_field='city_ref', state_ref_field='state_ref', require=False)`.
- Consumes: existing `normalized_state_code()` and `normalized_city_name()` remain for fiscal emission payloads.

- [ ] **Step 1: Add a failing helper test**

Add this test:

```python
def test_validate_normalized_location_checks_required_and_city_state_match():
    from base.normalized_locations import validate_normalized_location

    state, city = create_state_city()
    other_state = StateProvince.objects.create(code='SP', name='São Paulo', abbreviation='SP')

    class Holder:
        state_ref = other_state
        city_ref = city

    with pytest.raises(ValidationError) as error:
        validate_normalized_location(Holder(), require=True)

    assert 'city_ref' in error.value.message_dict

    class EmptyHolder:
        state_ref = None
        city_ref = None

    with pytest.raises(ValidationError) as missing_error:
        validate_normalized_location(EmptyHolder(), require=True)

    assert missing_error.value.message_dict == {
        'state_ref': ['Informe a UF.'],
        'city_ref': ['Informe a cidade.'],
    }
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
python -m pytest tests/test_normalized_locations.py::test_validate_normalized_location_checks_required_and_city_state_match -q
```

Expected: FAIL with `ImportError` for `validate_normalized_location`.

- [ ] **Step 3: Implement validation helper**

Add to `base/normalized_locations.py`:

```python
def validate_normalized_location(
    instance,
    *,
    city_ref_field='city_ref',
    state_ref_field='state_ref',
    require=False,
):
    city = getattr(instance, city_ref_field, None)
    state = getattr(instance, state_ref_field, None)
    errors = {}

    if require and not state:
        errors[state_ref_field] = 'Informe a UF.'
    if require and not city:
        errors[city_ref_field] = 'Informe a cidade.'

    if city and state and city.state_id and city.state_id != state.pk:
        errors[city_ref_field] = 'A cidade deve pertencer à UF informada.'

    if errors:
        raise ValidationError(errors)
```

- [ ] **Step 4: Run test and verify GREEN**

Run:

```bash
python -m pytest tests/test_normalized_locations.py::test_validate_normalized_location_checks_required_and_city_state_match -q
```

Expected: PASS.

---

### Task 3: Update Core Registration Apps

**Files:**
- Modify: `fiscal/models.py`, `governance/models.py`, `masters/models.py`
- Modify: `fiscal/serializers.py`, `governance/serializers.py`, `masters/serializers.py`
- Modify: `fiscal/admin.py`, `governance/admin.py`, `masters/admin.py`
- Modify: `base/ui/registry.py`
- Create: migrations for `fiscal`, `governance`, `masters`

**Interfaces:**
- Consumes: `validate_normalized_location()`.
- Produces: core resources with only normalized city/UF and completed address fields where applicable.

- [ ] **Step 1: Run core contract tests and verify RED**

Run:

```bash
python -m pytest tests/test_normalized_locations.py::PriorityNormalizedLocationTests tests/test_normalized_locations.py::test_location_models_keep_only_normalized_city_and_uf_with_final_labels tests/test_normalized_locations.py::test_location_models_with_street_also_have_number_and_complement_fields -q
```

Expected: FAIL on legacy fields and missing address fields in `masters`.

- [ ] **Step 2: Update core models**

Apply these model changes:

```python
# fiscal.models.FiscalCompany
# remove fields: city, state
state_ref = models.ForeignKey(..., verbose_name='UF')
city_ref = models.ForeignKey(..., verbose_name='Cidade')

def clean(self):
    super().clean()
    validate_normalized_location(self, require=True)

# fiscal.models.FiscalMunicipality
# remove field: state
state_ref = models.ForeignKey(..., verbose_name='UF')
city_ref = models.ForeignKey(..., verbose_name='Cidade')

def clean(self):
    super().clean()
    validate_normalized_location(self, require=True)
    if self.city_ref and not self.name:
        self.name = self.city_ref.name

# governance.models.InstitutionSettings
# remove fields: city, state
state_ref = models.ForeignKey(..., verbose_name='UF')
city_ref = models.ForeignKey(..., verbose_name='Cidade')

def clean(self):
    super().clean()
    validate_normalized_location(self, require=True)

# masters.models.BusinessPartner
# remove fields: city, state
street_number = models.CharField('número', max_length=20, blank=True)
complement = models.CharField('complemento', max_length=100, blank=True)
state_ref = models.ForeignKey(..., verbose_name='UF')
city_ref = models.ForeignKey(..., verbose_name='Cidade')

def clean(self):
    super().clean()
    validate_normalized_location(self)

# masters.models.Site
# remove fields: city, state
street_number = models.CharField('número', max_length=20, blank=True)
complement = models.CharField('complemento', max_length=100, blank=True)
state_ref = models.ForeignKey(..., verbose_name='UF')
city_ref = models.ForeignKey(..., verbose_name='Cidade')

def clean(self):
    super().clean()
    validate_normalized_location(self)
```

Import `validate_normalized_location` from `base.normalized_locations` and remove unused `sync_normalized_location` imports in these files.

- [ ] **Step 3: Update serializers**

Ensure field lists include the new address fields and do not reference removed fields:

```python
# masters.serializers.BusinessPartnerSerializer.Meta.fields
'zipcode', 'street', 'street_number', 'complement', 'neighborhood', 'state_ref', 'city_ref'

# masters.serializers.SiteSerializer.Meta.fields
'zipcode', 'street', 'street_number', 'complement', 'neighborhood', 'state_ref', 'city_ref'
```

Keep `FiscalCompanySerializer`, `FiscalMunicipalitySerializer` and `InstitutionSettingsSerializer` exposing `state_ref` and `city_ref`, and remove any `exclude = ('city', 'state')` workaround if the fields no longer exist.

- [ ] **Step 4: Update registry/admin**

In `base/ui/registry.py`, for `fiscal.companies`, `fiscal.municipalities`, `masters.partners`, `masters.sites`, and `governance.institution-settings`, ensure:

```python
list_display=(..., 'city_ref', 'state_ref', ...)
form_fields=(..., 'zipcode', 'street', 'street_number', 'complement', 'neighborhood', 'state_ref', 'city_ref', ...)
search_fields=(..., 'city_ref__name', 'state_ref__abbreviation', 'state_ref__name')
filterset_fields=(..., 'state_ref', 'city_ref', ...)
```

In the corresponding `admin.py` files, remove legacy `city/state` from `search_fields`, `list_display`, `list_filter`, `fieldsets`, and add `street_number/complement` to `masters.BusinessPartnerAdmin` and `masters.SiteAdmin` if admin fieldsets are explicit.

- [ ] **Step 5: Create and inspect migrations**

Run:

```bash
python manage.py makemigrations fiscal governance masters
python manage.py sqlmigrate fiscal <new_migration_number>
python manage.py sqlmigrate governance <new_migration_number>
python manage.py sqlmigrate masters <new_migration_number>
```

Expected: migrations contain `RemoveField` for legacy city/UF fields, `AlterField` for labels, and `AddField` for `masters` number/complement fields.

- [ ] **Step 6: Run core tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_normalized_locations.py::PriorityNormalizedLocationTests tests/test_normalized_locations.py::test_location_models_keep_only_normalized_city_and_uf_with_final_labels tests/test_normalized_locations.py::test_location_models_with_street_also_have_number_and_complement_fields -q
python manage.py check
```

Expected: all selected tests pass and system check has no issues.

---

### Task 4: Update Transactional Apps

**Files:**
- Modify: `audits/models.py`, `crm/models.py`, `pharmacovigilance/models.py`, `procurement/models.py`, `recalls/models.py`, `training/models.py`
- Modify: matching serializers/admin files
- Modify: `base/ui/registry.py`
- Create: migrations for `audits`, `crm`, `pharmacovigilance`, `procurement`, `recalls`, `training`

**Interfaces:**
- Consumes: `validate_normalized_location()`.
- Produces: transactional resources without textual city/UF mirrors and with number/complement fields where a street already exists.

- [ ] **Step 1: Run transactional tests and verify RED**

Run:

```bash
python -m pytest tests/test_normalized_locations.py::TransactionalNormalizedLocationTests tests/test_normalized_locations.py::test_location_models_keep_only_normalized_city_and_uf_with_final_labels tests/test_normalized_locations.py::test_location_models_with_street_also_have_number_and_complement_fields -q
```

Expected: FAIL until fields are removed/added and labels are updated.

- [ ] **Step 2: Update models with prefixed address fields**

Apply these patterns:

```python
# audits.models.AuditPlan
# remove venue_city, venue_state
venue_street_number = models.CharField('número', max_length=20, blank=True)
venue_complement = models.CharField('complemento', max_length=100, blank=True)
venue_state_ref = models.ForeignKey(..., verbose_name='UF')
venue_city_ref = models.ForeignKey(..., verbose_name='Cidade')
validate_normalized_location(self, city_ref_field='venue_city_ref', state_ref_field='venue_state_ref')

# crm.models.SalesOrder
# remove shipping_city, shipping_state
shipping_street_number = models.CharField('número', max_length=20, blank=True)
shipping_complement = models.CharField('complemento', max_length=100, blank=True)
shipping_state_ref = models.ForeignKey(..., verbose_name='UF')
shipping_city_ref = models.ForeignKey(..., verbose_name='Cidade')
validate_normalized_location(self, city_ref_field='shipping_city_ref', state_ref_field='shipping_state_ref')

# crm.models.CustomerComplaint
# remove city, state
state_ref = models.ForeignKey(..., verbose_name='UF')
city_ref = models.ForeignKey(..., verbose_name='Cidade')
validate_normalized_location(self)

# pharmacovigilance.models.PharmacovigilanceCase
# remove city, state
state_ref = models.ForeignKey(..., verbose_name='UF')
city_ref = models.ForeignKey(..., verbose_name='Cidade')
validate_normalized_location(self)

# procurement.models.SupplierQualificationEvent
# remove event_city, event_state
event_street_number = models.CharField('número', max_length=20, blank=True)
event_complement = models.CharField('complemento', max_length=100, blank=True)
event_state_ref = models.ForeignKey(..., verbose_name='UF')
event_city_ref = models.ForeignKey(..., verbose_name='Cidade')
validate_normalized_location(self, city_ref_field='event_city_ref', state_ref_field='event_state_ref')

# procurement.models.PurchaseOrder
# remove delivery_city, delivery_state
delivery_street_number = models.CharField('número', max_length=20, blank=True)
delivery_complement = models.CharField('complemento', max_length=100, blank=True)
delivery_state_ref = models.ForeignKey(..., verbose_name='UF')
delivery_city_ref = models.ForeignKey(..., verbose_name='Cidade')
validate_normalized_location(self, city_ref_field='delivery_city_ref', state_ref_field='delivery_state_ref')

# recalls.models.MarketComplaint
# remove city, state
state_ref = models.ForeignKey(..., verbose_name='UF')
city_ref = models.ForeignKey(..., verbose_name='Cidade')
validate_normalized_location(self)

# training.models.TrainingSession
# remove location_city, location_state
location_street_number = models.CharField('número', max_length=20, blank=True)
location_complement = models.CharField('complemento', max_length=100, blank=True)
location_state_ref = models.ForeignKey(..., verbose_name='UF')
location_city_ref = models.ForeignKey(..., verbose_name='Cidade')
validate_normalized_location(self, city_ref_field='location_city_ref', state_ref_field='location_state_ref')
```

- [ ] **Step 3: Update serializers**

Use explicit fields or update `exclude` so serializers do not reference removed fields. Add number/complement fields to:

```python
AuditPlanSerializer: 'venue_street_number', 'venue_complement'
SalesOrderSerializer: 'shipping_street_number', 'shipping_complement'
SupplierQualificationEventSerializer: 'event_street_number', 'event_complement'
PurchaseOrderSerializer: 'delivery_street_number', 'delivery_complement'
TrainingSessionSerializer: 'location_street_number', 'location_complement'
```

- [ ] **Step 4: Update registry/admin**

In `base/ui/registry.py`, for the resources in the inventory, remove all legacy city/UF fields from `list_display`, `form_fields`, `filterset_fields`, and `search_fields`. Add normalized fields and the new address fields in address order:

```python
'*_zipcode', '*_street', '*_street_number', '*_complement', '*_neighborhood', '*_state_ref', '*_city_ref'
```

Use the concrete prefix for each resource: `venue`, `shipping`, `event`, `delivery`, or `location`. For unprefixed complaint/case resources, keep only `state_ref` and `city_ref`.

- [ ] **Step 5: Create and inspect migrations**

Run:

```bash
python manage.py makemigrations audits crm pharmacovigilance procurement recalls training
python manage.py showmigrations audits crm pharmacovigilance procurement recalls training
```

Expected: each app has one new migration with label changes/removals; `audits`, `crm`, `procurement`, and `training` also add number/complement fields.

- [ ] **Step 6: Run transactional tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_normalized_locations.py::TransactionalNormalizedLocationTests tests/test_normalized_locations.py::test_location_models_keep_only_normalized_city_and_uf_with_final_labels tests/test_normalized_locations.py::test_location_models_with_street_also_have_number_and_complement_fields -q
python manage.py check
```

Expected: all selected tests pass and system check has no issues.

---

### Task 5: Remove Legacy Payload Assumptions and Update Fiscal Output Tests

**Files:**
- Modify: `fiscal/services.py`
- Modify: `tests/test_normalized_locations.py`
- Modify: `tests/test_fiscal.py`

**Interfaces:**
- Consumes: `normalized_city_name()` and `normalized_state_code()`.
- Produces: fiscal payloads derived only from FK normalized fields.

- [ ] **Step 1: Update tests that instantiate removed fields**

Replace object construction such as:

```python
BusinessPartner.objects.create(city='Texto legado incorreto', state='XX', state_ref=state, city_ref=city)
FiscalCompany.objects.create(city='Texto legado incorreto', state='XX', state_ref=state, city_ref=city)
```

with:

```python
BusinessPartner.objects.create(state_ref=state, city_ref=city)
FiscalCompany.objects.create(state_ref=state, city_ref=city)
```

Keep the assertion:

```python
assert payload['company']['city'] == 'Recife'
assert payload['company']['state'] == 'PE'
assert payload['partner']['city'] == 'Recife'
assert payload['partner']['state'] == 'PE'
```

- [ ] **Step 2: Run fiscal tests and verify RED if services still use removed fields**

Run:

```bash
python -m pytest tests/test_normalized_locations.py::PriorityNormalizedLocationTests::test_fiscal_issue_payload_uses_normalized_location_not_legacy_text tests/test_fiscal.py -q
```

Expected: pass if `fiscal/services.py` already uses `city_ref/state_ref`; fail with `FieldError` or attribute assumptions if any legacy access remains.

- [ ] **Step 3: Keep payload generation normalized-only**

In `fiscal/services.py`, keep party payload fields as:

```python
'city': normalized_city_name(getattr(party, 'city_ref', None)),
'state': normalized_state_code(getattr(party, 'state_ref', None)),
```

Do not read `party.city` or `party.state`.

- [ ] **Step 4: Run fiscal tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_normalized_locations.py::PriorityNormalizedLocationTests::test_fiscal_issue_payload_uses_normalized_location_not_legacy_text tests/test_fiscal.py -q
```

Expected: PASS.

---

### Task 6: Verify Templates Render the Final Labels

**Files:**
- Modify: `tests/test_app_ui.py`
- Modify: `base/ui/forms.py` only if widget metadata special-cases old field names.
- Modify: `templates/app/resource_form.html` only if generic rendering cannot display FK labels correctly.

**Interfaces:**
- Consumes: model `verbose_name` and registry form fields.
- Produces: UI forms showing `Cidade` and `UF`, not `Cidade normalizada`, `Município normalizado`, `Estado`, or legacy text fields.

- [ ] **Step 1: Add UI label tests**

Add a parametrized test using the existing authenticated app client helpers in `tests/test_app_ui.py`:

```python
@pytest.mark.parametrize(
    'module_slug,resource_slug,expected_labels,forbidden_labels',
    [
        ('fiscal', 'companies', {'Cidade', 'UF'}, {'município', 'UF normalizada', 'município normalizado'}),
        ('masters', 'partners', {'Cidade', 'UF', 'número', 'complemento'}, {'cidade normalizada', 'UF/estado normalizado'}),
        ('masters', 'sites', {'Cidade', 'UF', 'número', 'complemento'}, {'cidade normalizada', 'UF/estado normalizado'}),
        ('procurement', 'orders', {'Cidade', 'UF', 'número', 'complemento'}, {'cidade de entrega', 'UF de entrega'}),
        ('training', 'sessions', {'Cidade', 'UF', 'número', 'complemento'}, {'cidade do local', 'UF do local'}),
    ],
)
def test_location_forms_render_normalized_labels_only(authenticated_client, module_slug, resource_slug, expected_labels, forbidden_labels):
    response = authenticated_client.get(reverse('app:resource_create', args=[module_slug, resource_slug]))
    assert response.status_code == 200
    html = response.content.decode()
    for label in expected_labels:
        assert f'>{label}</label>' in html
    for label in forbidden_labels:
        assert label not in html
```

- [ ] **Step 2: Run UI test and verify RED**

Run:

```bash
python -m pytest tests/test_app_ui.py::test_location_forms_render_normalized_labels_only -q
```

Expected: FAIL until labels and registry form fields are corrected.

- [ ] **Step 3: Fix metadata only if needed**

If `base/ui/forms.py` maps field names such as `city_ref` to a verbose icon/help text containing “normalizada”, change visible text to `Cidade` and `UF`. Keep icons/select widgets unchanged.

- [ ] **Step 4: Run UI test and verify GREEN**

Run:

```bash
python -m pytest tests/test_app_ui.py::test_location_forms_render_normalized_labels_only -q
```

Expected: PASS.

---

### Task 7: Documentation and Full Verification

**Files:**
- Modify: `docs/architecture/auxiliary.md`
- Modify: app architecture docs only if they explicitly list legacy city/UF fields.

**Interfaces:**
- Produces: documentation reflecting normalized-only location policy.

- [ ] **Step 1: Update architecture documentation**

Change `docs/architecture/auxiliary.md` section “UF e município normalizados” to state:

```markdown
`StateProvince` e `City` são a fonte da verdade para UF e cidade nos cadastros e registros operacionais. A UI e APIs expõem os campos normalizados com os labels `UF` e `Cidade`; campos textuais legados de cidade/UF foram removidos dos recursos operacionais. Integrações fiscais derivam os textos exigidos em payloads externos a partir de `state_ref` e `city_ref`.
```

- [ ] **Step 2: Run targeted verification**

Run:

```bash
python -m pytest tests/test_normalized_locations.py tests/test_app_ui.py tests/test_fiscal.py tests/test_governance.py tests/test_crm.py tests/test_recalls.py -q
python manage.py check
python manage.py makemigrations --check --dry-run
```

Expected: tests pass, system check has no issues, and dry-run reports no missing migrations.

- [ ] **Step 3: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: full suite passes.

- [ ] **Step 4: Browser spot-check**

Run the project with source static files:

```bash
DEBUG=True python manage.py runserver 127.0.0.1:8123
```

Open and verify these forms:

```text
/app/fiscal/companies/new/
/app/masters/partners/new/
/app/masters/sites/new/
/app/procurement/orders/new/
/app/training/sessions/new/
```

Expected: each form shows `Cidade` and `UF`; forms with logradouro show `número` and `complemento`; no visible field says `Cidade normalizada`, `Município normalizado`, `Estado normalizado`, or the old contextual city/UF text.

---

## Execution Order

1. Task 1: freeze global expected contract.
2. Task 2: add validation helper so models can stop using mirror fields.
3. Task 3: core registration apps.
4. Task 4: transactional apps.
5. Task 5: fiscal payload/test cleanup.
6. Task 6: template/UI regression tests.
7. Task 7: docs and full verification.

## Acceptance Criteria

- No affected serializer exposes removed city/UF text fields.
- No affected `ResourceConfig` lists, filters, searches or forms use removed city/UF text fields.
- Affected forms show normalized FKs with labels `Cidade` and `UF`.
- Models with existing logradouro fields also have number and complement fields.
- Migrations are generated and `makemigrations --check --dry-run` is clean.
- `python manage.py check` passes.
- Full pytest suite passes.
