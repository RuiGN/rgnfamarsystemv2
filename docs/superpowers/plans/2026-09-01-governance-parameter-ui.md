# Governance Parameter UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose governance parameters through type-aware, auditable HTML forms without changing their REST or persistence contract.

**Architecture:** Add optional form and actor hooks to the generic resource registry, then implement the type conversion inside a domain `ModelForm`. Keep `GovernanceParameter.full_clean()` authoritative and use progressive JavaScript only to improve control switching.

**Tech Stack:** Django 6, PostgreSQL, server-rendered templates, vanilla JavaScript, pytest-django.

## Global Constraints

- Preserve the existing `GovernanceParameter` model and REST fields.
- Do not restore `TechnicalResponsible` or `automatic_code_generation`.
- `updated_by` must come from the authenticated request and remain non-editable.
- JavaScript is progressive enhancement; server validation is mandatory.
- Run tests only through `bash scripts/test.sh` or `.venv/bin/python -m <tool>`.

---

## File map

- Create `governance/forms.py`: typed field construction and normalization.
- Modify `base/ui/registry.py`: optional form base and actor field contracts.
- Modify `base/ui/forms.py`: compose the registered form base with generic behavior.
- Modify `base/ui/views.py`: assign the authenticated actor before saving.
- Modify `static/js/app-form-enhancements.js`: live type switching.
- Modify `tests/test_app_ui.py`: HTML form and audit regressions.
- Modify `tests/test_governance.py`: domain coercion remains authoritative.

### Task 1: Add generic form-base and actor hooks

**Files:**
- Modify: `base/ui/registry.py`
- Modify: `base/ui/forms.py`
- Modify: `base/ui/views.py`
- Test: `tests/test_app_ui.py`

**Interfaces:**
- Produces: `ResourceConfig.form_base: type[forms.ModelForm] | None`
- Produces: `ResourceConfig.actor_field: str`
- Consumes: the existing `build_resource_form(resource, update=False)` API.

- [ ] **Step 1: Write failing registry and actor tests**

Add tests that construct the governance resource and assert `form_base` is registered, then POST an edited parameter and assert `updated_by == request.user`. Use `reverse('app:resource_update', kwargs={'module_slug': 'governance', 'resource_slug': 'parameters', 'pk': parameter.pk})` and grant `view_governanceparameter` plus `change_governanceparameter`.

- [ ] **Step 2: Prove the tests fail**

Run: `bash scripts/test.sh tests/test_app_ui.py -k 'governance_parameter and (form_base or updated_by)' -q`

Expected: FAIL because `ResourceConfig` has no `form_base`/`actor_field` and HTML saves do not assign `updated_by`.

- [ ] **Step 3: Extend `ResourceConfig`**

Import `forms` from Django and add these frozen dataclass fields after `update_form_fields`:

```python
form_base: type[forms.ModelForm] | None = None
actor_field: str = ''
```

In `build_resource_form()`, insert the base selection immediately before the
current nested class and change only its declaration line:

```python
form_base = resource.form_base or forms.ModelForm

class ResourceForm(form_base):
```

In `ResourceCreateView.prepare_object_for_save()` use:

```python
def prepare_object_for_save(self, obj, *, action):
    del action
    actor_field = self.get_resource().actor_field
    if actor_field:
        setattr(obj, actor_field, self.request.user)
    return obj
```

- [ ] **Step 4: Run the focused tests**

Run: `bash scripts/test.sh tests/test_app_ui.py -k 'governance_parameter and (form_base or updated_by)' -q`

Expected: PASS.

- [ ] **Step 5: Commit the generic hooks**

```bash
git add base/ui/registry.py base/ui/forms.py base/ui/views.py tests/test_app_ui.py
git commit -m "feat(ui): support domain forms and resource actors"
```

### Task 2: Implement the typed governance form

**Files:**
- Create: `governance/forms.py`
- Modify: `base/ui/registry.py`
- Test: `tests/test_app_ui.py`

**Interfaces:**
- Produces: `GovernanceParameterForm(forms.ModelForm)`.
- Consumes: `GovernanceParameter.ValueType`, `rules.choices`, and registered `form_base`.

- [ ] **Step 1: Write failing typed-control tests**

Cover boolean, integer, days, decimal, choice, string and JSON instances. Assert widget types, Python values after `is_valid()`, `False` persistence for an unchecked primary boolean, `{}` for an empty default, and rejection when `rules.choices` is missing or excludes the submitted value.

- [ ] **Step 2: Prove the tests fail**

Run: `bash scripts/test.sh tests/test_app_ui.py -k 'governance_parameter and typed' -q`

Expected: FAIL because both JSON-backed values render as generic textareas.

- [ ] **Step 3: Create `GovernanceParameterForm`**

Implement these exact helpers in `governance/forms.py`:

```python
import json
from decimal import Decimal

from django import forms

from governance.models import GovernanceParameter


BOOLEAN_DEFAULT_CHOICES = (
    ('', 'Não definido'),
    ('true', 'Ativado'),
    ('false', 'Desativado'),
)


def _boolean_default(value):
    if value in ('', None, {}):
        return {}
    return str(value).lower() == 'true'


class GovernanceParameterForm(forms.ModelForm):
    class Meta:
        model = GovernanceParameter
        fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        value_type = self._effective_value_type()
        rules = self._effective_rules()
        self.fields['value'] = self._typed_field(value_type, required=True, rules=rules)
        self.fields['default_value'] = self._typed_field(
            value_type, required=False, rules=rules, is_default=True
        )
        self.fields['value'].widget.attrs['data-governance-value'] = 'current'
        self.fields['default_value'].widget.attrs['data-governance-value'] = 'default'
        self.fields['value_type'].widget.attrs['data-governance-value-type'] = 'true'
        self.fields['rules'].widget.attrs['data-governance-rules'] = 'true'

    def _effective_value_type(self):
        if self.is_bound:
            return self.data.get(self.add_prefix('value_type'), '')
        return self.initial.get('value_type') or getattr(self.instance, 'value_type', '')

    def _effective_rules(self):
        if self.is_bound:
            raw = self.data.get(self.add_prefix('rules'), '{}')
            try:
                return json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, json.JSONDecodeError):
                return {}
        return self.initial.get('rules') or getattr(self.instance, 'rules', {}) or {}

    def _typed_field(self, value_type, *, required, rules, is_default=False):
        if value_type == GovernanceParameter.ValueType.BOOLEAN:
            if is_default:
                return forms.TypedChoiceField(
                    choices=BOOLEAN_DEFAULT_CHOICES,
                    coerce=_boolean_default,
                    empty_value={},
                    required=False,
                )
            return forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'role': 'switch'}))
        if value_type in {GovernanceParameter.ValueType.INTEGER, GovernanceParameter.ValueType.DAYS}:
            return forms.IntegerField(required=required)
        if value_type == GovernanceParameter.ValueType.DECIMAL:
            return forms.DecimalField(required=required)
        if value_type == GovernanceParameter.ValueType.CHOICE:
            choices = tuple((str(item), str(item)) for item in rules.get('choices', ()))
            return forms.ChoiceField(required=required, choices=choices)
        if value_type == GovernanceParameter.ValueType.JSON:
            return forms.JSONField(required=required, widget=forms.Textarea)
        return forms.CharField(required=required)

    def clean(self):
        cleaned = super().clean()
        if self._effective_value_type() == GovernanceParameter.ValueType.DECIMAL:
            for name in ('value', 'default_value'):
                value = cleaned.get(name)
                if isinstance(value, Decimal):
                    cleaned[name] = format(value, 'f')
        return cleaned
```

Ensure edit initial values map `{}` to the empty tri-state option and booleans to `true`/`false`.

- [ ] **Step 4: Register the domain form and explicit fields**

Import `GovernanceParameterForm` in `base/ui/registry.py`. Configure the parameter resource with list display `('scope', 'module', 'key', 'value', 'value_type', 'is_active')`, explicit fields `('scope', 'module', 'key', 'value_type', 'value', 'default_value', 'rules', 'description', 'is_active')`, `form_base=GovernanceParameterForm`, and `actor_field='updated_by'`.

- [ ] **Step 5: Run typed form and governance tests**

Run: `bash scripts/test.sh tests/test_app_ui.py tests/test_governance.py -k 'governance' -q`

Expected: PASS.

- [ ] **Step 6: Commit the typed form**

```bash
git add governance/forms.py base/ui/registry.py tests/test_app_ui.py
git commit -m "feat(governance): add typed parameter controls"
```

### Task 3: Add progressive control switching

**Files:**
- Modify: `static/js/app-form-enhancements.js`
- Test: `tests/test_app_ui.py`

**Interfaces:**
- Consumes: `data-governance-value-type`, `data-governance-rules`, and `data-governance-value`.
- Produces: browser-only control replacement without changing submitted field names.

- [ ] **Step 1: Add a failing JavaScript contract test**

Assert the script contains `initGovernanceParameterForm`, listens to both `change` and `input`, reads `rules.choices`, preserves `value` and `default_value` names, and never uses `innerHTML` with user-provided values.

- [ ] **Step 2: Prove it fails**

Run: `bash scripts/test.sh tests/test_app_ui.py -k 'governance_parameter and javascript' -q`

Expected: FAIL because the initializer is absent.

- [ ] **Step 3: Implement the initializer**

Add a function that finds the marked type/rules/current/default controls, creates elements with `document.createElement`, copies `name`, `id`, classes and ARIA attributes, and replaces only the input element. Map boolean current to checkbox, boolean default to a three-option select, numeric types to `type=number`, choice to options from parsed `rules.choices`, JSON to textarea and string to text. Cache the last value per type in a local `Map` and call the initializer on `DOMContentLoaded`.

- [ ] **Step 4: Run UI contracts**

Run: `bash scripts/test.sh tests/test_app_ui.py tests/test_responsive_layout_css.py -q`

Expected: PASS.

- [ ] **Step 5: Commit progressive enhancement**

```bash
git add static/js/app-form-enhancements.js tests/test_app_ui.py
git commit -m "feat(governance): switch parameter controls by type"
```

### Task 4: Run governance gates

**Files:**
- Verify only.

- [ ] **Step 1: Run focused suites**

Run: `bash scripts/test.sh tests/test_governance.py tests/test_app_ui.py tests/test_compliance.py -q`

Expected: all tests pass.

- [ ] **Step 2: Run Django checks**

Run: `DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py makemigrations --check --dry-run && DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py check`

Expected: “No changes detected” and no system check issues.

- [ ] **Step 3: Verify forbidden regressions**

Run: `git grep -n -i -E 'TechnicalResponsible|automatic_code_generation' -- governance base/ui static/js tests ':!docs/superpowers/**'`

Expected: no matches introduced by this plan.
