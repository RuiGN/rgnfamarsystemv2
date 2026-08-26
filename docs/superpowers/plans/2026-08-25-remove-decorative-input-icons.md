# Remove Decorative Input Icons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every decorative icon prepended to system form fields while preserving functional icons on buttons, menus, states, and interactive controls.

**Architecture:** Remove the icon metadata contract from the central Django form configurator and the avatar widget, then simplify each shared form template to render fields directly. Lock the behavior with metadata, rendered-response, and static-template contract tests so future forms cannot reintroduce decorative input icons.

**Tech Stack:** Python 3.14, Django 6, pytest-django, Django templates, Bootstrap 5, Feather Icons

## Global Constraints

- Remove only icons used as visual adornments before form fields.
- Preserve icons that represent actions, states, menus, alerts, or interactive controls.
- Preserve masks, placeholders, Bootstrap classes, input types, validation markup, and accessibility attributes.
- Do not add migrations, dependencies, API changes, or business-rule changes.
- Execute all test commands from the repository root.

---

## File Map

- `base/ui/forms.py`: central widget metadata; remove `_field_icon()` and icon publication.
- `accounts/forms.py`: avatar upload widget; remove its decorative `data-icon` attribute.
- `templates/app/resource_form.html`: main resource fields; render fields without icon groups.
- `templates/app/resource_action_form.html`: action fields; render fields without icon groups.
- `templates/app/resource_execution_board.html`: execution fields; render fields without icon groups.
- `templates/app/includes/inline_stacked.html`: stacked inline fields; remove both icon-group branches.
- `templates/app/includes/inline_tabular.html`: tabular inline fields; remove both icon-group branches.
- `templates/app/includes/inline_qc_grid.html`: QC grid fields; remove both icon-group branches.
- `templates/registration/login.html`: remove decorative wrappers around username and password.
- `templates/accounts/avatar.html`: remove the decorative wrapper around avatar upload.
- `tests/test_app_ui.py`: verify central metadata and rendered resource/login forms.
- `tests/test_action_forms.py`: verify action widget metadata has no icon contract.
- `tests/test_accounts_avatar.py`: verify avatar markup has no decorative icon contract.
- `tests/test_template_language.py`: enforce the repository-wide template contract and preserve representative functional icons.
- `docs/architecture/templates.md`: document the form icon rule for future UI work.

---

### Task 1: Remove Decorative Icon Metadata

**Files:**
- Modify: `tests/test_app_ui.py:1595-1641`
- Modify: `tests/test_action_forms.py:126-154`
- Modify: `tests/test_accounts_avatar.py:65-99`
- Modify: `base/ui/forms.py:288-333, 382-390`
- Modify: `accounts/forms.py:8-18`

**Interfaces:**
- Consumes: `_apply_widget_metadata(name: str, field: forms.Field) -> None`.
- Produces: widgets with layout, mask, placeholder, type, and Bootstrap metadata but no `data-icon` attribute and no `field.rgn_icon` property.

- [ ] **Step 1: Replace icon-positive metadata assertions with a failing no-icon contract**

In `tests/test_app_ui.py`, rename
`test_widget_metadata_adds_specific_placeholders_and_icons` to
`test_widget_metadata_adds_specific_placeholders_without_decorative_icons`.
Keep the existing field construction, `_apply_widget_metadata()` calls, and
placeholder assertions. Replace every `data-icon` assertion with:

```python
        fields = (
            document_field,
            email_field,
            date_field,
            money_field,
            phone_field,
            url_field,
            quantity_field,
            percent_field,
            file_field,
        )
        for field in fields:
            assert 'data-icon' not in field.widget.attrs
            assert not hasattr(field, 'rgn_icon')
```

In `tests/test_action_forms.py`, retain the mask, type, and placeholder
assertions in `test_action_fields_receive_project_widget_metadata`, then add:

```python
        for field in form_class.base_fields.values():
            assert 'data-icon' not in field.widget.attrs
            assert not hasattr(field, 'rgn_icon')
```

Remove that test's six positive `data-icon` assertions.

In `tests/test_accounts_avatar.py`, add to
`test_avatar_form_requires_login_and_renders_current_avatar`:

```python
        assert 'data-icon=' not in content
```

- [ ] **Step 2: Run the metadata tests and verify RED**

Run:

```bash
.venv/bin/pytest \
  tests/test_app_ui.py::AppUiFormEnhancementTests::test_widget_metadata_adds_specific_placeholders_without_decorative_icons \
  tests/test_action_forms.py::ActionFormTests::test_action_fields_receive_project_widget_metadata \
  tests/test_accounts_avatar.py::UserAvatarTests::test_avatar_form_requires_login_and_renders_current_avatar \
  -q
```

Expected: FAIL because widgets still contain `data-icon`, fields still contain
`rgn_icon`, and the avatar output still contains icon metadata.

- [ ] **Step 3: Remove icon metadata from production form configuration**

Delete `_field_icon()` entirely from `base/ui/forms.py`. In
`_apply_widget_metadata()`, remove only this block:

```python
    icon = _field_icon(name, field)
    field.rgn_icon = icon
    if icon:
        attrs['data-icon'] = icon
```

Keep the surrounding layout, class, placeholder, type, mask, address, and
accessibility configuration unchanged.

In `accounts/forms.py`, change the avatar widget attributes to:

```python
                attrs={
                    'class': 'form-control',
                    'accept': 'image/*',
                    'capture': 'user',
                }
```

- [ ] **Step 4: Run the metadata tests and verify GREEN**

Run the command from Step 2 again.

Expected: `3 passed` with no failures.

- [ ] **Step 5: Commit the metadata contract removal**

```bash
git add base/ui/forms.py accounts/forms.py tests/test_app_ui.py tests/test_action_forms.py tests/test_accounts_avatar.py
git commit -m "refactor: remove decorative field icon metadata"
```

---

### Task 2: Remove Decorative Icon Markup From All Form Templates

**Files:**
- Modify: `tests/test_template_language.py`
- Modify: `tests/test_app_ui.py:75-84, 1633-1641`
- Modify: `tests/test_accounts_avatar.py:65-99`
- Modify: `templates/app/resource_form.html:33-43`
- Modify: `templates/app/resource_action_form.html:54-65`
- Modify: `templates/app/resource_execution_board.html:45-55`
- Modify: `templates/app/includes/inline_stacked.html:39-49, 74-84`
- Modify: `templates/app/includes/inline_tabular.html:54-63, 87-96`
- Modify: `templates/app/includes/inline_qc_grid.html:47-55, 80-88`
- Modify: `templates/registration/login.html:41-59`
- Modify: `templates/accounts/avatar.html:38-44`

**Interfaces:**
- Consumes: Django `BoundField` values exposed as `field` or `form.avatar`.
- Produces: direct widget markup without `.resource-input-group`, `.resource-input-icon`, `data-field-icon`, or `field.field.rgn_icon` references.

- [ ] **Step 1: Add the failing repository-wide template contract**

Append to `tests/test_template_language.py`:

```python
def test_templates_do_not_render_decorative_input_icons():
    forbidden = (
        'field.field.rgn_icon',
        'resource-input-icon',
        'resource-input-group',
        'data-field-icon',
    )

    for template in sorted((ROOT / 'templates').rglob('*.html')):
        source = template.read_text()
        for marker in forbidden:
            assert marker not in source, f'{marker!r} encontrado em {template}'


def test_representative_functional_icons_remain_available():
    form_actions = (ROOT / 'templates/includes/form_actions.html').read_text()
    base = (ROOT / 'templates/base.html').read_text()
    chat = (ROOT / 'templates/app/resource_chat.html').read_text()

    assert 'feather-save' in form_actions
    assert 'feather-x' in form_actions
    assert 'feather-search' in base
    assert 'btn-close' in base
    assert 'feather-paperclip' in chat
    assert 'feather-send' in chat
```

Rename `test_resource_form_renders_icon_input_groups` in
`tests/test_app_ui.py` to
`test_resource_form_renders_fields_without_decorative_icons` and replace its
markup assertions with:

```python
        assert 'name="document"' in content
        assert 'resource-input-group' not in content
        assert 'resource-input-icon' not in content
        assert 'data-field-icon=' not in content
        assert 'feather-file-text' not in content
```

Add to `test_login_template_uses_design_system_auth_shell`:

```python
        assert 'resource-input-group' not in content
        assert 'data-field-icon=' not in content
```

Add to `test_avatar_form_requires_login_and_renders_current_avatar` in
`tests/test_accounts_avatar.py`:

```python
        assert 'resource-input-group' not in content
        assert 'data-field-icon=' not in content
```

- [ ] **Step 2: Run the template contract tests and verify RED**

Run:

```bash
.venv/bin/pytest \
  tests/test_template_language.py::test_templates_do_not_render_decorative_input_icons \
  tests/test_app_ui.py::AppUiFormEnhancementTests::test_resource_form_renders_fields_without_decorative_icons \
  tests/test_app_ui.py::AppUiFoundationTests::test_login_template_uses_design_system_auth_shell \
  -q
```

Expected: FAIL listing the shared templates that still render decorative icon
groups.

- [ ] **Step 3: Simplify the resource, action, and execution templates**

In `templates/app/resource_form.html` and
`templates/app/resource_execution_board.html`, replace each complete
`{% if field.field.rgn_icon %} ... {% else %} ... {% endif %}` block with:

```django
                    {{ field }}
```

In `templates/app/resource_action_form.html`, replace its complete icon branch
with:

```django
                        {{ field }}
```

- [ ] **Step 4: Simplify all inline form templates**

In both field-rendering locations of each file below, replace the complete
`rgn_icon` conditional with the correctly indented direct field rendering:

```django
{{ field }}
```

Files and occurrence counts:

- `templates/app/includes/inline_stacked.html`: 2 occurrences;
- `templates/app/includes/inline_tabular.html`: 2 occurrences;
- `templates/app/includes/inline_qc_grid.html`: 2 occurrences.

Do not change checkbox/delete-field branches, labels, help text, error markup,
table cells, or inline formset controls.

- [ ] **Step 5: Remove empty decorative wrappers from login and avatar**

In `templates/registration/login.html`, replace the username wrapper with:

```django
                                <input id="id_username" type="text" name="username" class="form-control{% if form.username.errors %} is-invalid{% endif %}" value="{{ form.username.value|default_if_none:'' }}" placeholder="Digite seu usuário" required autofocus autocomplete="username"{% if form.username.errors %} aria-invalid="true" aria-describedby="id_username_errors"{% endif %}>
```

Replace the password wrapper with:

```django
                                <input id="id_password" type="password" name="password" class="form-control{% if form.password.errors %} is-invalid{% endif %}" placeholder="Digite sua senha" required autocomplete="current-password"{% if form.password.errors %} aria-invalid="true" aria-describedby="id_password_errors"{% endif %}>
```

In `templates/accounts/avatar.html`, replace its wrapper with:

```django
                        {{ form.avatar }}
```

- [ ] **Step 6: Run the template and UI tests and verify GREEN**

Run:

```bash
.venv/bin/pytest \
  tests/test_template_language.py \
  tests/test_app_ui.py \
  tests/test_accounts_avatar.py \
  -q
```

Expected: all selected tests pass. The functional-icon contract test must also
pass, proving representative button and control icons remain.

- [ ] **Step 7: Commit the template simplification**

```bash
git add templates tests/test_template_language.py tests/test_app_ui.py tests/test_accounts_avatar.py
git commit -m "refactor: remove decorative icons from form fields"
```

---

### Task 3: Document and Verify the Completed UI Contract

**Files:**
- Modify: `docs/architecture/templates.md`

**Interfaces:**
- Consumes: the final metadata and template contract from Tasks 1 and 2.
- Produces: a documented rule for future form implementations and fresh verification evidence.

- [ ] **Step 1: Document the design-system rule**

Append this paragraph to the `APIs e UI` section of
`docs/architecture/templates.md`:

```markdown
Campos de formulário são renderizados sem ícones decorativos prefixados. Ícones
permanecem permitidos em botões, menus, alertas, indicadores e controles
interativos quando comunicam uma ação ou um estado. A configuração central de
widgets não publica `data-icon` nem metadados equivalentes de apresentação.
```

- [ ] **Step 2: Run focused regression tests**

Run:

```bash
.venv/bin/pytest \
  tests/test_app_ui.py \
  tests/test_action_forms.py \
  tests/test_accounts_avatar.py \
  tests/test_template_language.py \
  tests/test_formula_inline_components_ui.py \
  -q
```

Expected: all selected tests pass with zero failures.

- [ ] **Step 3: Run Django and source-contract verification**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check
rg -n 'rgn_icon|data-icon|resource-input-icon|data-field-icon|resource-input-group' \
  base accounts templates \
  --glob '*.py' --glob '*.html'
git diff --check
```

Expected: Django reports `System check identified no issues`; `rg` returns no
matches; `git diff --check` returns no output.

- [ ] **Step 4: Confirm no migrations were introduced**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py makemigrations --check --dry-run
```

Expected: `No changes detected`.

- [ ] **Step 5: Commit documentation and final verification state**

```bash
git add docs/architecture/templates.md
git commit -m "docs: define icon-free form field contract"
```
