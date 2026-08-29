# Master Formula Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a permission-aware **Reaproveitar** row action that opens an unsaved new master formula prefilled from an existing formula, including all components, while generating a fresh code on save.

**Architecture:** A small formulation-domain service builds safe parent and component initial data. The generic resource configuration exposes an optional reuse route and permission contract, while a dedicated `MasterFormulaReuseView` reuses `ResourceCreateView` hooks for GET prefill and atomic POST persistence. Version conflicts are serialized on the selected product and translated from the existing unique constraint into a field error.

**Tech Stack:** Python 3.14, Django 6.0, Django ModelForms and inline formsets, PostgreSQL/SQLite, Bootstrap 5 templates, pytest-django.

## Global Constraints

- The GET flow must not persist a formula, component, audit event, or sequence number.
- Copy product, batch data, yield, validity dates, notes, and every component field approved by the specification.
- Never copy primary keys, approval actors/timestamps, audit timestamps, or the source code.
- Suggest `max(version for selected source product) + 1`; keep `version` editable.
- Always display and persist the reused formula as `draft`.
- Keep `code` empty and disabled until the existing automatic identifier allocates it during save.
- Assign `copied_from` on the server; never render or trust it from POST data.
- Require `view_masterformula`, `add_masterformula`, `view_formulacomponent`, and `add_formulacomponent` for the action.
- Formula and copied components must save in the existing atomic transaction or roll back together.
- Preserve the existing dirty worktree. Before every commit, inspect `git diff --cached` and stage only the task's hunks; do not include the prior sidebar or “Copiada de” edits accidentally.
- No model or schema change is expected; `makemigrations --check --dry-run` must report no changes.

## File Map

- Create `formulations/reuse.py`: safe initial-value builders, reuse form factory, and unique-conflict classifier.
- Create `formulations/ui_views.py`: dedicated permission-aware GET/POST reuse view.
- Modify `base/ui/registry.py`: optional reuse route/permission configuration and Formula resource declaration.
- Modify `base/ui/views.py`: generic initial-data and pre-save/error hooks used by the dedicated view.
- Modify `base/ui/urls.py`: named master-formula reuse route before generic detail/edit routes.
- Modify `templates/app/resource_list.html`: generic row button driven by `ResourceConfig`.
- Modify `tests/test_formula_inline_components_ui.py`: service, UI, permissions, persistence, rollback, and conflict coverage.
- Modify `TEMPLATES.md`: document optional row reuse actions and server-owned fields.
- Modify `docs/pdf/manual_usuario.md`: document the operator workflow.

---

### Task 1: Build safe reuse data and form contracts

**Files:**
- Create: `formulations/reuse.py`
- Test: `tests/test_formula_inline_components_ui.py`

**Interfaces:**
- Consumes: `build_resource_form(resource)`, `MasterFormula`, and `FormulaComponent`.
- Produces: `master_formula_reuse_initial(source) -> dict[str, object]`, `component_reuse_initial(source) -> list[dict[str, object]]`, `build_master_formula_reuse_form(resource) -> type[forms.ModelForm]`, and `is_formula_version_conflict(error) -> bool`.

- [ ] **Step 1: Add failing tests for copied values, next version, hidden traceability, and disabled status**

Add these imports and tests to `tests/test_formula_inline_components_ui.py`:

```python
from django.db import IntegrityError

from formulations.reuse import (
    build_master_formula_reuse_form,
    component_reuse_initial,
    is_formula_version_conflict,
    master_formula_reuse_initial,
)


def test_master_formula_reuse_builders_copy_only_approved_values(self):
    source, component = self._formula_with_component('FRM-REUSE-SOURCE', quantity='2.5000')
    source.status = MasterFormula.Status.APPROVED
    source.expected_yield_percent = Decimal('98.7500')
    source.notes = 'Origem validada.'
    source.save()
    MasterFormula.objects.create(
        product=self.product,
        code='FRM-REUSE-V3',
        version=3,
        batch_size=Decimal('100.0000'),
        batch_unit=self.unit,
    )

    parent_initial = master_formula_reuse_initial(source)
    children_initial = component_reuse_initial(source)

    assert parent_initial == {
        'product': self.product.pk,
        'version': 4,
        'status': MasterFormula.Status.DRAFT,
        'batch_size': source.batch_size,
        'batch_unit': self.unit.pk,
        'expected_yield_percent': Decimal('98.7500'),
        'effective_from': source.effective_from,
        'effective_to': source.effective_to,
        'notes': 'Origem validada.',
    }
    assert children_initial == [
        {
            'line_number': component.line_number,
            'material': component.material_id,
            'role': component.role,
            'quantity': component.quantity,
            'unit': component.unit_id,
            'expected_loss_percent': component.expected_loss_percent,
            'conversion_factor': component.conversion_factor,
            'is_active': component.is_active,
        }
    ]
    assert 'code' not in parent_initial
    assert 'copied_from' not in parent_initial


def test_master_formula_reuse_form_hides_source_and_locks_status(self):
    form_class = build_master_formula_reuse_form(get_resource('formulations', 'formulas'))
    form = form_class(request=type('Request', (), {'user': self.user})())

    assert 'copied_from' not in form.fields
    assert form.fields['code'].disabled is True
    assert form.fields['status'].disabled is True
    assert form.fields['status'].initial == MasterFormula.Status.DRAFT


def test_formula_version_conflict_classifier_is_constraint_specific(self):
    conflict = IntegrityError(
        'UNIQUE constraint failed: '
        'formulations_masterformula.product_id, formulations_masterformula.version'
    )
    unrelated = IntegrityError('UNIQUE constraint failed: formulations_masterformula.code')

    assert is_formula_version_conflict(conflict) is True
    assert is_formula_version_conflict(unrelated) is False
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/test_formula_inline_components_ui.py \
  -k 'reuse_builders or reuse_form_hides or version_conflict_classifier'
```

Expected: collection/import failure because `formulations.reuse` does not exist.

- [ ] **Step 3: Implement the formulation reuse service**

Create `formulations/reuse.py`:

```python
from django import forms
from django.db import IntegrityError
from django.db.models import Max

from base.ui.forms import build_resource_form
from formulations.models import MasterFormula


VERSION_CONFLICT_MESSAGE = (
    'Esta versão já foi utilizada para o produto selecionado. '
    'Atualize a versão e tente novamente.'
)

COMPONENT_REUSE_FIELDS = (
    'line_number',
    'role',
    'quantity',
    'expected_loss_percent',
    'conversion_factor',
    'is_active',
)


def next_formula_version(product_id: int) -> int:
    maximum = MasterFormula.objects.filter(product_id=product_id).aggregate(
        maximum=Max('version')
    )['maximum']
    return (maximum or 0) + 1


def master_formula_reuse_initial(source: MasterFormula) -> dict[str, object]:
    return {
        'product': source.product_id,
        'version': next_formula_version(source.product_id),
        'status': MasterFormula.Status.DRAFT,
        'batch_size': source.batch_size,
        'batch_unit': source.batch_unit_id,
        'expected_yield_percent': source.expected_yield_percent,
        'effective_from': source.effective_from,
        'effective_to': source.effective_to,
        'notes': source.notes,
    }


def component_reuse_initial(source: MasterFormula) -> list[dict[str, object]]:
    initial = []
    for component in source.components.order_by('line_number', 'pk'):
        row = {field: getattr(component, field) for field in COMPONENT_REUSE_FIELDS}
        row['material'] = component.material_id
        row['unit'] = component.unit_id
        initial.append(row)
    return initial


def build_master_formula_reuse_form(resource) -> type[forms.ModelForm]:
    parent_form = build_resource_form(resource)

    class MasterFormulaReuseForm(parent_form):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields.pop('copied_from', None)
            self.fields['status'].disabled = True
            self.fields['status'].initial = MasterFormula.Status.DRAFT

    return MasterFormulaReuseForm


def is_formula_version_conflict(error: IntegrityError) -> bool:
    cause = error.__cause__
    constraint_name = getattr(getattr(cause, 'diag', None), 'constraint_name', '')
    if constraint_name == 'unique_formula_product_version':
        return True
    message = str(error)
    return (
        'formulations_masterformula.product_id' in message
        and 'formulations_masterformula.version' in message
    )
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the Step 2 command again.

Expected: `3 passed` and no warnings produced by these tests.

- [ ] **Step 5: Commit only Task 1 hunks**

```bash
git add formulations/reuse.py
git add -p tests/test_formula_inline_components_ui.py
git diff --cached --check
git diff --cached --name-only
git commit -m "feat: define master formula reuse data"
```

Expected staged paths: only `formulations/reuse.py` and the Task 1 test hunks.

---

### Task 2: Expose a permission-aware Reaproveitar GET flow

**Files:**
- Create: `formulations/ui_views.py`
- Modify: `base/ui/registry.py`
- Modify: `base/ui/views.py`
- Modify: `base/ui/urls.py`
- Modify: `templates/app/resource_list.html`
- Test: `tests/test_formula_inline_components_ui.py`

**Interfaces:**
- Consumes: all four Task 1 helpers.
- Produces: `ResourceConfig.can_reuse(user) -> bool`, the URL name `app:master_formula_reuse`, generic create-view initial hooks, and `MasterFormulaReuseView`.

- [ ] **Step 1: Add failing list, permission, and GET-prefill tests**

Add to `FormulaInlineComponentsUiTests`:

```python
def test_formula_list_offers_reuse_to_fully_authorized_user(self):
    source = self._formula_with_component('FRM-LIST-REUSE', quantity='1.0000')[0]

    response = self.client.get(
        reverse(
            'app:resource_list',
            kwargs={'module_slug': 'formulations', 'resource_slug': 'formulas'},
        )
    )

    assert response.status_code == 200
    assert 'Reaproveitar' in response.content.decode()
    assert reverse('app:master_formula_reuse', kwargs={'pk': source.pk}) in response.content.decode()


def test_formula_reuse_button_and_url_require_parent_and_component_permissions(self):
    source = self._formula_with_component('FRM-REUSE-PERMS', quantity='1.0000')[0]
    user = get_user_model().objects.create_user(
        email='reuse-permissions@example.com',
        password='S3curePass!123',
        username='Permissões de reaproveitamento',
    )
    permissions = Permission.objects.filter(
        content_type__app_label='formulations',
        codename__in=('view_masterformula', 'add_masterformula'),
    )
    user.user_permissions.set(permissions)
    self.client.force_login(user)

    list_response = self.client.get(
        reverse(
            'app:resource_list',
            kwargs={'module_slug': 'formulations', 'resource_slug': 'formulas'},
        )
    )
    direct_response = self.client.get(
        reverse('app:master_formula_reuse', kwargs={'pk': source.pk})
    )

    assert list_response.status_code == 200
    assert 'Reaproveitar' not in list_response.content.decode()
    assert direct_response.status_code == 403


def test_formula_reuse_get_prefills_parent_and_all_components_without_persisting(self):
    from base.models import IdentifierSequence
    from governance.models import GovernanceAuditLog

    source, first = self._formula_with_component('FRM-REUSE-GET', quantity='2.0000')
    second = FormulaComponent.objects.create(
        formula=source,
        line_number=20,
        material=self.materials[1],
        role=FormulaComponent.Role.EXCIPIENT,
        quantity=Decimal('3.0000'),
        unit=self.unit,
    )
    MasterFormula.objects.create(
        product=self.product,
        code='FRM-REUSE-GET-V4',
        version=4,
        batch_size=Decimal('100.0000'),
        batch_unit=self.unit,
    )
    formula_count = MasterFormula.objects.count()
    component_count = FormulaComponent.objects.count()
    audit_count = GovernanceAuditLog.objects.count()
    sequence_count = IdentifierSequence.objects.count()

    response = self.client.get(reverse('app:master_formula_reuse', kwargs={'pk': source.pk}))

    assert response.status_code == 200
    form = response.context['form']
    formset = response.context['inline_formsets'][0]['formset']
    assert form.initial['product'] == self.product.pk
    assert form.initial['version'] == 5
    assert form.initial['status'] == MasterFormula.Status.DRAFT
    assert 'copied_from' not in form.fields
    copied_rows = [row.initial for row in formset.forms if row.initial.get('line_number')]
    assert [row['line_number'] for row in copied_rows] == [10, 20]
    assert [row['material'] for row in copied_rows] == [first.material_id, second.material_id]
    assert all(not row.instance.pk for row in formset.forms)
    assert MasterFormula.objects.count() == formula_count
    assert FormulaComponent.objects.count() == component_count
    assert GovernanceAuditLog.objects.count() == audit_count
    assert IdentifierSequence.objects.count() == sequence_count


def test_formula_reuse_missing_source_returns_404(self):
    response = self.client.get(reverse('app:master_formula_reuse', kwargs={'pk': 999999}))

    assert response.status_code == 404
```

- [ ] **Step 2: Run the GET-flow tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_formula_inline_components_ui.py \
  -k 'list_offers_reuse or reuse_button_and_url or reuse_get_prefills or reuse_missing_source'
```

Expected: failures because the route, configuration, button, and view do not exist.

- [ ] **Step 3: Add declarative reuse configuration**

Extend `ResourceConfig` in `base/ui/registry.py`:

```python
reuse_route_name: str = ''
reuse_permissions: tuple[str, ...] = field(default_factory=tuple)

def can_reuse(self, user):
    return bool(
        self.reuse_route_name
        and self.can_view(user)
        and self.can_add(user)
        and user.has_perms(self.reuse_permissions)
    )
```

Add to the Fórmulas mestras `ResourceConfig`:

```python
reuse_route_name='app:master_formula_reuse',
reuse_permissions=(
    'formulations.view_formulacomponent',
    'formulations.add_formulacomponent',
),
```

Expose the result in `ResourceContextMixin.get_context_data()`:

```python
context['can_reuse'] = resource.can_reuse(self.request.user)
```

- [ ] **Step 4: Add generic unbound initial-data hooks to the create view**

Change `_build_inline_formset` in `base/ui/views.py` to accept `initial=None` and pass it to the formset constructor:

```python
def _build_inline_formset(
    request,
    resource,
    inline,
    *,
    data=None,
    instance=None,
    allow_add=True,
    initial=None,
):
    formset_class = inlineformset_factory(
        resource.model,
        inline.child_model,
        fk_name=inline.parent_field,
        form=_build_inline_form_class(inline),
        fields=inline.fields,
        extra=inline.extra if allow_add and inline.can_add(request.user) else 0,
        can_delete=inline.can_delete(request.user),
        max_num=None if allow_add else 0,
        validate_max=not allow_add,
    )
    return formset_class(
        data=data,
        instance=instance,
        prefix=inline.key,
        form_kwargs={'request': request},
        initial=initial,
    )
```

Add these hooks to `ResourceCreateView`:

```python
def get_form_initial(self):
    return {}

def get_inline_initial(self):
    return {}
```

Replace `ResourceCreateView.get_inline_formsets` so initial data is passed only
to unbound formsets:

```python
def get_inline_formsets(self, *, data=None, instance=None, initial_by_key=None):
    resource = self.get_resource()
    inline_formsets = []
    initial_by_key = initial_by_key or {}
    for inline in resource.inlines:
        can_view = inline.can_view(self.request.user)
        allow_add = not (
            resource.app_label == 'production'
            and resource.slug == 'orders'
            and (instance is None or instance.pk is None)
        )
        submitted = bool(data and any(key.startswith(f'{inline.key}-') for key in data))
        formset = None
        if can_view:
            formset = _build_inline_formset(
                self.request,
                resource,
                inline,
                data=data,
                instance=instance,
                allow_add=allow_add,
                initial=initial_by_key.get(inline.key) if data is None else None,
            )
        inline_formsets.append(
            {
                'config': inline,
                'key': inline.key,
                'title': inline.title,
                'description': inline.description,
                'add_label': inline.add_label,
                'available': can_view,
                'submitted': submitted,
                'can_add': can_view and allow_add and inline.can_add(self.request.user),
                'can_change': can_view and inline.can_change(self.request.user),
                'can_delete': can_view and inline.can_delete(self.request.user),
                'inline_style': getattr(inline, 'inline_style', 'stacked'),
                'formset': formset,
            }
        )
    return inline_formsets
```

Instantiate the unbound form and formsets in `get_context_data` with the hooks:

```python
form = kwargs.get('form') or self.get_form_class()(
    request=self.request,
    initial=self.get_form_initial(),
)
if inline_formsets is None:
    inline_formsets = self.get_inline_formsets(
        instance=getattr(form, 'instance', None),
        initial_by_key=self.get_inline_initial(),
    )
```

- [ ] **Step 5: Implement the dedicated GET/POST view shell and route**

Create `formulations/ui_views.py`:

```python
from django.core.exceptions import PermissionDenied
from django.http import Http404

from base.ui.views import ResourceCreateView
from formulations.models import MasterFormula
from formulations.reuse import (
    build_master_formula_reuse_form,
    component_reuse_initial,
    master_formula_reuse_initial,
)


class MasterFormulaReuseView(ResourceCreateView):
    source = None

    def dispatch(self, request, *args, **kwargs):
        resource = self.get_resource()
        if resource.model is not MasterFormula:
            raise Http404('Reaproveitamento disponível somente para fórmulas mestras.')
        if not resource.can_reuse(request.user):
            raise PermissionDenied('Usuário sem permissão para reaproveitar esta fórmula.')
        self.get_source()
        return super().dispatch(request, *args, **kwargs)

    def get_source(self):
        if self.source is None:
            try:
                self.source = (
                    self.get_queryset()
                    .select_related('product', 'batch_unit')
                    .prefetch_related('components')
                    .get(pk=self.kwargs['pk'])
                )
            except MasterFormula.DoesNotExist as exc:
                raise Http404('Fórmula de origem não encontrada.') from exc
        return self.source

    def get_form_class(self):
        return build_master_formula_reuse_form(self.get_resource())

    def get_form_initial(self):
        return master_formula_reuse_initial(self.get_source())

    def get_inline_initial(self):
        return {'components': component_reuse_initial(self.get_source())}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reuse_source'] = self.get_source()
        return context
```

Import the view in `base/ui/urls.py` and add this path before the generic detail route:

```python
from formulations.ui_views import MasterFormulaReuseView

path(
    'formulations/formulas/<int:pk>/reuse/',
    MasterFormulaReuseView.as_view(),
    {'module_slug': 'formulations', 'resource_slug': 'formulas'},
    name='master_formula_reuse',
),
```

- [ ] **Step 6: Render the action without hard-coding the resource in the template**

In `templates/app/resource_list.html`, immediately before **Detalhe**:

```django
{% if can_reuse %}
    <a href="{% url resource.reuse_route_name row.object.pk %}"
       class="btn btn-sm btn-light-brand d-inline-flex align-items-center gap-2"
       aria-label="Reaproveitar {{ row.object }}">
        <i class="feather-copy" aria-hidden="true"></i>Reaproveitar
    </a>
{% endif %}
```

- [ ] **Step 7: Run the GET-flow tests and existing create/edit tests**

```bash
.venv/bin/pytest -q tests/test_formula_inline_components_ui.py \
  -k 'reuse or formula_form_creates or formula_edit'
```

Expected: all selected tests pass; ordinary creation and editing remain unchanged.

- [ ] **Step 8: Commit only Task 2 hunks**

```bash
git add formulations/ui_views.py base/ui/urls.py templates/app/resource_list.html
git add -p base/ui/registry.py base/ui/views.py tests/test_formula_inline_components_ui.py
git diff --cached --check
git diff --cached --name-only
git commit -m "feat: open reusable master formula drafts"
```

Expected staged paths: only Task 2 files/hunks; prior unrelated working-tree edits remain unstaged.

---

### Task 3: Persist reused formulas atomically and handle version races

**Files:**
- Modify: `base/ui/views.py`
- Modify: `formulations/ui_views.py`
- Test: `tests/test_formula_inline_components_ui.py`

**Interfaces:**
- Consumes: `is_formula_version_conflict`, `VERSION_CONFLICT_MESSAGE`, and the Task 2 view.
- Produces: generic `prepare_object_for_save(obj, action=...)` and `handle_integrity_error(form, error) -> bool` hooks; the reuse view overrides both.

- [ ] **Step 1: Add failing successful-POST, tamper-resistance, rollback, and conflict tests**

Add to `FormulaInlineComponentsUiTests`:

```python
def test_formula_reuse_post_generates_code_traceability_and_new_components(self):
    from governance.models import GovernanceAuditLog

    source, first = self._formula_with_component('FRM-REUSE-POST', quantity='2.0000')
    second = FormulaComponent.objects.create(
        formula=source,
        line_number=20,
        material=self.materials[1],
        role=FormulaComponent.Role.EXCIPIENT,
        quantity=Decimal('3.0000'),
        unit=self.unit,
    )
    payload = {
        **self._formula_payload('TAMPERED-CODE'),
        'version': '2',
        'status': MasterFormula.Status.APPROVED,
        'copied_from': '',
        'components-TOTAL_FORMS': '2',
        'components-INITIAL_FORMS': '0',
        'components-MIN_NUM_FORMS': '0',
        'components-MAX_NUM_FORMS': '1000',
        **self._component_payload(0, 10, first.material, first.role),
        **self._component_payload(1, 20, second.material, second.role),
    }

    response = self.client.post(
        reverse('app:master_formula_reuse', kwargs={'pk': source.pk}), payload
    )

    assert response.status_code == 302, self._response_form_errors(response)
    reused = MasterFormula.objects.exclude(pk=source.pk).get(version=2)
    assert reused.code.startswith('MF-')
    assert reused.code != 'TAMPERED-CODE'
    assert reused.status == MasterFormula.Status.DRAFT
    assert reused.copied_from == source
    assert reused.components.count() == 2
    assert not set(reused.components.values_list('pk', flat=True)) & {first.pk, second.pk}
    audit = GovernanceAuditLog.objects.get(
        action='ui.resource.created',
        target_model='MasterFormula',
        target_record_id=str(reused.pk),
    )
    assert audit.safe_context['inline_resources']['components'] == 2
    source.refresh_from_db()
    assert source.code == 'FRM-REUSE-POST'
    assert source.components.count() == 2


def test_formula_reuse_child_failure_rolls_back_parent(self):
    source = self._formula_with_component('FRM-REUSE-ROLLBACK', quantity='2.0000')[0]
    payload = {
        **self._formula_payload('IGNORED'),
        'version': '2',
        'components-TOTAL_FORMS': '1',
        'components-INITIAL_FORMS': '0',
        'components-MIN_NUM_FORMS': '0',
        'components-MAX_NUM_FORMS': '1000',
        **self._component_payload(0, 10, self.materials[0], FormulaComponent.Role.ACTIVE),
    }

    with patch.object(FormulaComponent, 'save', side_effect=RuntimeError('storage failure')):
        with self.assertRaisesMessage(RuntimeError, 'storage failure'):
            self.client.post(
                reverse('app:master_formula_reuse', kwargs={'pk': source.pk}), payload
            )

    assert MasterFormula.objects.count() == 1
    assert FormulaComponent.objects.count() == 1


def test_formula_reuse_version_integrity_conflict_returns_form_error(self):
    source = self._formula_with_component('FRM-REUSE-CONFLICT', quantity='2.0000')[0]
    payload = {
        **self._formula_payload('IGNORED'),
        'version': '2',
        'components-TOTAL_FORMS': '0',
        'components-INITIAL_FORMS': '0',
        'components-MIN_NUM_FORMS': '0',
        'components-MAX_NUM_FORMS': '1000',
    }
    conflict = IntegrityError(
        'UNIQUE constraint failed: '
        'formulations_masterformula.product_id, formulations_masterformula.version'
    )

    with patch.object(MasterFormula, 'save', side_effect=conflict):
        response = self.client.post(
            reverse('app:master_formula_reuse', kwargs={'pk': source.pk}), payload
        )

    assert response.status_code == 200
    assert 'Esta versão já foi utilizada' in response.content.decode()
    assert MasterFormula.objects.count() == 1
```

- [ ] **Step 2: Run the POST tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_formula_inline_components_ui.py \
  -k 'reuse_post_generates or reuse_child_failure or reuse_version_integrity'
```

Expected: the success test creates no traceability/forced draft yet, and the conflict escapes instead of becoming a form error.

- [ ] **Step 3: Add safe generic persistence hooks**

Import `IntegrityError` in `base/ui/views.py` and add to `ResourceCreateView`:

```python
def prepare_object_for_save(self, obj, *, action):
    return obj

def handle_integrity_error(self, form, error):
    del form, error
    return False
```

Inside `save_object_and_inline_formsets`, immediately after `form.save(commit=False)`:

```python
obj = self.prepare_object_for_save(obj, action=action)
```

Extend the create POST exception handling without swallowing unrelated integrity errors:

```python
try:
    obj = self.save_object_and_inline_formsets(form, inline_formsets, action='created')
except (_InlineRevalidationError, _OrderRevalidationError) as exc:
    _add_validation_error_to_form(exc.form, exc.error)
    self.annotate_inline_formsets(inline_formsets)
    return self.render_to_response(
        self.get_context_data(form=form, inline_formsets=inline_formsets)
    )
except IntegrityError as exc:
    if not self.handle_integrity_error(form, exc):
        raise
    _annotate_form_accessibility(form)
    self.annotate_inline_formsets(inline_formsets)
    return self.render_to_response(
        self.get_context_data(form=form, inline_formsets=inline_formsets)
    )
```

- [ ] **Step 4: Make the reuse view own traceability, status, code, and conflict behavior**

Extend `formulations/ui_views.py`:

```python
from masters.models import Product
from formulations.reuse import (
    VERSION_CONFLICT_MESSAGE,
    is_formula_version_conflict,
)

def prepare_object_for_save(self, obj, *, action):
    del action
    Product.objects.select_for_update().only('pk').get(pk=obj.product_id)
    obj.code = ''
    obj.status = MasterFormula.Status.DRAFT
    obj.copied_from = self.get_source()
    obj.approved_by = None
    obj.approved_at = None
    return obj

def handle_integrity_error(self, form, error):
    if not is_formula_version_conflict(error):
        return False
    form.add_error('version', VERSION_CONFLICT_MESSAGE)
    return True
```

The product lock is acquired inside the existing `transaction.atomic()` in `save_object_and_inline_formsets`. The unique constraint remains the final authority and the handler converts only `unique_formula_product_version` into a recoverable response.

- [ ] **Step 5: Run POST tests, all formula UI tests, and verify GREEN**

```bash
.venv/bin/pytest -q tests/test_formula_inline_components_ui.py
```

Expected: every test in the file passes, including existing create/edit/rollback contracts.

- [ ] **Step 6: Commit only Task 3 hunks**

```bash
git add formulations/ui_views.py
git add -p base/ui/views.py tests/test_formula_inline_components_ui.py
git diff --cached --check
git diff --cached --name-only
git commit -m "feat: persist reused master formulas atomically"
```

Expected staged content: only the persistence hooks, view overrides, and Task 3 tests.

---

### Task 4: Document, verify, and exercise the operator flow

**Files:**
- Modify: `TEMPLATES.md`
- Modify: `docs/pdf/manual_usuario.md`
- Verify: all files modified by Tasks 1–3

**Interfaces:**
- Consumes: completed list action, reuse route, GET prefill, and POST persistence.
- Produces: operator documentation and fresh verification evidence.

- [ ] **Step 1: Document the generic row-action contract**

Add to `TEMPLATES.md` after “Como adicionar novos recursos ao CRUD HTML genérico”:

```markdown
Recursos com reaproveitamento declaram `reuse_route_name` e
`reuse_permissions` no `ResourceConfig`. O template apenas renderiza a rota
autorizada; a view repete as permissões, controla campos de rastreabilidade e
não persiste dados no GET.
```

- [ ] **Step 2: Document the Formulações operator workflow**

Add under `### Formulações` in `docs/pdf/manual_usuario.md`:

```markdown
Para criar uma nova versão com base em uma fórmula existente, use
**Reaproveitar** na coluna **Ações**. O sistema abre um novo registro em
Rascunho, sugere a próxima versão e copia todos os componentes. Revise os dados
antes de salvar; o código é gerado na gravação e a fórmula de origem permanece
inalterada.
```

- [ ] **Step 3: Run focused and adjacent automated verification**

```bash
.venv/bin/pytest -q \
  tests/test_formula_inline_components_ui.py \
  tests/test_app_ui.py
```

Expected: all tests pass with zero failures.

- [ ] **Step 4: Run Django, syntax, migration, and diff checks**

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python -m compileall -q formulations base/ui tests/test_formula_inline_components_ui.py
.venv/bin/ruff check formulations/reuse.py formulations/ui_views.py base/ui/registry.py base/ui/views.py tests/test_formula_inline_components_ui.py
git diff --check
```

Expected: Django reports no issues, migrations report `No changes detected`, compilation and Ruff exit 0, and `git diff --check` prints nothing.

- [ ] **Step 5: Run the full project suite**

```bash
./scripts/test.sh -q
```

Expected: the complete suite exits 0. Report the exact passed/skipped counts from the fresh output; do not reuse an older count.

- [ ] **Step 6: Restart the local no-reload server and verify ownership**

Resolve the current PID and cwd before replacement:

```bash
server_pid=$(pgrep -f '^.venv/bin/python manage.py runserver 127.0.0.1:8002 --noreload$' | head -n 1)
readlink -f "/proc/${server_pid}/cwd"
kill "${server_pid}"
tmux new-session -d -s rgnfarmasystem -c \
  /mnt/2c8d19a3-3bbb-4f90-b09f-9e17c780ce6a/Projects/rgnfarmasystem-main \
  '.venv/bin/python manage.py runserver 127.0.0.1:8002 --noreload'
curl -fsS http://127.0.0.1:8002/health/
```

Expected cwd: this repository. Expected health body: `{"status": "ok"}`. If the tmux session still exists after killing the process, create the replacement only after confirming it exited; never kill an unresolved PID.

- [ ] **Step 7: Verify the real list and prefilled form in a browser**

Using an authenticated local session, verify:

1. `/app/formulations/formulas/` shows **Reaproveitar** beside **Detalhe**;
2. the link opens `/app/formulations/formulas/<pk>/reuse/`;
3. the heading remains **Novo registro - Fórmulas mestras**;
4. code is empty/disabled, status is Rascunho/disabled, and version is the next available;
5. `copied_from` is absent;
6. every source component is present with no source ID;
7. browser runtime errors are empty;
8. navigating back without saving does not change formula/component counts.

Capture the evaluated DOM facts as JSON and fail the verification command if any assertion is false.

- [ ] **Step 8: Commit documentation only if it can be isolated safely**

```bash
git add docs/pdf/manual_usuario.md
git add -p TEMPLATES.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: explain master formula reuse"
```

Expected staged content: only Task 4 documentation hunks. If pre-existing `TEMPLATES.md` edits cannot be isolated reliably, leave that file unstaged and report the intended documentation commit instead of including unrelated work.

- [ ] **Step 9: Final working-tree and requirement audit**

```bash
git status --short --branch
git diff --stat
git diff --cached --stat
```

Confirm every specification criterion has a passing test or browser assertion, the source formula remains unchanged, no migration exists, no unrelated file was staged, and no required work remains.
