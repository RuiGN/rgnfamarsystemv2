# Single-instance Reference Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every residual marker of the retired customer-scope architecture while preserving the current single-instance runtime and internal organizational concepts.

**Architecture:** Keep the already-converted Django runtime unchanged and clean the remaining repository surface in two layers. A repository contract test prevents forbidden legacy terminology in file names and text; obsolete historical plans are removed while active tests and documentation are rewritten around positive single-instance behavior.

**Tech Stack:** Python 3.14, Django 6, pytest, PostgreSQL, Markdown, YAML

## Global Constraints

- Preserve all pre-existing worktree changes.
- Do not alter internal organizational roles, units, departments, or responsibility assignments.
- Do not rewrite migration history when the migration graph is already free of the retired marker.
- Keep authorization based on Django users, groups, and model permissions.
- Finish with repository text scan, Django checks, migration drift check, and relevant pytest suites.

---

### Task 1: Add a repository-level regression contract

**Files:**
- Modify: `tests/test_cosmetics_platform_contract.py`
- Test: `tests/test_cosmetics_platform_contract.py`

**Interfaces:**
- Consumes: the Git index and untracked non-ignored project files
- Produces: `test_repository_has_no_legacy_customer_scope_references()`

- [ ] **Step 1: Write the failing test**

```python
def test_repository_has_no_legacy_customer_scope_references():
    forbidden_marker = 'ten' + 'ant'
    result = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    violations = []
    for relative_name in result.stdout.splitlines():
        path = ROOT / relative_name
        if not path.is_file():
            continue
        if forbidden_marker in relative_name.casefold():
            violations.append(relative_name)
        try:
            source = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if forbidden_marker in source.casefold():
            violations.append(relative_name)
    assert sorted(set(violations)) == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_cosmetics_platform_contract.py::test_repository_has_no_legacy_customer_scope_references -q`

Expected: FAIL listing the remaining historical documents and negative tests.

### Task 2: Remove obsolete historical specifications

**Files:**
- Delete: `MODIFICACAGERAL.prd`
- Delete: superseded files under `docs/superpowers/plans/` and `docs/superpowers/specs/` that describe the retired customer-scoped architecture
- Modify: current architecture, validation, PDF, and legacy inventory documentation returned by the contract test

**Interfaces:**
- Consumes: current product contract in `PRD.md`, `README.md`, and `docs/architecture/single-instance.md`
- Produces: documentation that describes only the active single-instance architecture

- [ ] **Step 1: Remove superseded planning artifacts whose primary design is no longer valid**

Use patch-based file deletion so unrelated documentation remains untouched.

- [ ] **Step 2: Rewrite active documents in positive terms**

Describe one installation, one operational data space, and Django-native authorization without naming the retired architecture.

- [ ] **Step 3: Run the repository contract**

Run: `.venv/bin/pytest tests/test_cosmetics_platform_contract.py::test_repository_has_no_legacy_customer_scope_references -q`

Expected: FAIL only for residual tests, or PASS if documentation was the last source.

### Task 3: Refactor tests around positive single-instance behavior

**Files:**
- Modify: domain tests returned by the contract test
- Delete or rename: dedicated test modules whose only purpose is checking removed routes or schema names
- Modify: `tests/test_cosmetics_platform_contract.py`

**Interfaces:**
- Consumes: active API serializers, models, URL configuration, settings, and schema
- Produces: positive assertions for current fields, permissions, routes, and runtime contracts

- [ ] **Step 1: Remove redundant negative field assertions from domain tests**

Retain assertions for expected response fields and persisted model behavior; remove checks that name a retired field.

- [ ] **Step 2: Replace obsolete route tests with active single-instance access tests**

Keep authentication, permission, and root application behavior covered without requesting removed endpoints.

- [ ] **Step 3: Replace the package-list assertion**

Keep the quality gate test focused on packages that must exist and on executable commands, while the repository contract enforces terminology globally.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/test_cosmetics_platform_contract.py tests/test_app_ui.py tests/test_foundation.py tests/test_single_instance_runtime.py tests/test_single_instance_auth_access.py -q`

Expected: PASS with zero failures.

### Task 4: Verify the final single-instance contract

**Files:**
- Verify only

**Interfaces:**
- Consumes: the complete working tree after Tasks 1-3
- Produces: fresh evidence for source cleanliness, Django integrity, migrations, and regression safety

- [ ] **Step 1: Scan file names and contents**

Run: `rg -n -i --hidden --glob '!**/.git/**' --glob '!*.pyc' 'ten'"'"'ant|multi[ -]?ten'"'"'ant|multiten'"'"'ant' .`

Expected: no output.

- [ ] **Step 2: Run Django system checks**

Run: `.venv/bin/python manage.py check`

Expected: `System check identified no issues`.

- [ ] **Step 3: Check migration drift**

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`

Expected: `No changes detected`.

- [ ] **Step 4: Run focused and full tests**

Run: `.venv/bin/pytest tests/test_cosmetics_platform_contract.py tests/test_single_instance_runtime.py tests/test_app_ui.py -q`

Run: `.venv/bin/pytest -q`

Expected: all collected tests pass.

