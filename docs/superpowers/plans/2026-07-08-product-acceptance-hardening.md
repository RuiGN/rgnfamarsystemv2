# Product Acceptance Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Sprint 35, a final product acceptance gate for the RGN Farma System after Sprints 1-34.

**Architecture:** Add a lightweight evaluator in `core/product_acceptance.py`, following the existing readiness pattern from `core/operational_readiness.py` and `core/backup_restore_readiness.py`. Expose it through a Django management command in `base/management/commands/check_product_acceptance.py`, then document and record Sprint 35 in PRD/MKDocs.

**Tech Stack:** Python, Django, Django management commands, pytest, MKDocs, Markdown.

## Global Constraints

- Do not create a new Django app.
- Do not create or alter persistent models.
- Do not generate migrations.
- Code identifiers remain in English.
- User-facing output remains in Brazilian Portuguese.
- The evaluator must work without database access.
- Do not require external services, production secrets, or real restore operations.
- Follow the existing readiness report style: dataclasses, stable check codes, text and JSON command output.
- Update documentation, PRD, menus/permissions review evidence, and verification commands before closing the sprint.

---

### Task 1: Product Acceptance Evaluator

**Files:**
- Create: `core/product_acceptance.py`
- Create: `tests/test_product_acceptance.py`

**Interfaces:**
- Consumes: Django `settings.BASE_DIR`, route modules `core.urls` and `core.api_v1_urls`, management command registry, project documentation files.
- Produces: `ProductAcceptanceCheckStatus`, `ProductAcceptanceCheck`, `ProductAcceptanceReport`, `evaluate_product_acceptance(project_root=None)`.

- [ ] **Step 1: Write the failing test**

Add this test skeleton to `tests/test_product_acceptance.py`:

```python
import json
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase


class ProductAcceptanceTests(SimpleTestCase):
    def test_product_acceptance_report_covers_routes_commands_docs_and_prd(self):
        from core.product_acceptance import ProductAcceptanceCheckStatus, evaluate_product_acceptance

        report = evaluate_product_acceptance(project_root=settings.BASE_DIR)
        checks = {check.code: check for check in report.checks}

        expected_codes = {
            'routes.core_entrypoints',
            'routes.api_v1_modules',
            'ui.admin_menus',
            'commands.operational_gates',
            'docs.product_acceptance',
            'prd.sprint_35_recorded',
            'security.no_real_secrets',
        }

        assert report.passed is True
        assert expected_codes.issubset(checks)
        assert all(check.status == ProductAcceptanceCheckStatus.PASS for check in checks.values())
        assert '/api/v1/' in checks['routes.api_v1_modules'].evidence
        assert 'check_product_acceptance' in checks['docs.product_acceptance'].evidence

    def test_product_acceptance_report_serializes_to_json(self):
        from core.product_acceptance import evaluate_product_acceptance

        payload = json.loads(evaluate_product_acceptance(project_root=settings.BASE_DIR).to_json())

        assert payload['passed'] is True
        assert 'checks' in payload
        assert 'routes.core_entrypoints' in {item['code'] for item in payload['checks']}

    def test_product_acceptance_can_report_documentation_failure(self):
        from core.product_acceptance import evaluate_product_acceptance

        temporary_root = Path(settings.BASE_DIR) / 'tests' / 'fixtures' / 'missing-product-acceptance-docs'

        report = evaluate_product_acceptance(project_root=temporary_root)
        checks = {check.code: check for check in report.checks}

        assert report.passed is False
        assert checks['docs.product_acceptance'].status.value == 'fail'
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_product_acceptance.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.product_acceptance'`.

- [ ] **Step 3: Write the minimal evaluator**

Create `core/product_acceptance.py` with dataclasses, `ProductAcceptanceCheckStatus`, `ProductAcceptanceCheck`, `ProductAcceptanceReport`, `_read`, `_check`, and the check functions:

```python
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from django.conf import settings
from django.core.management import get_commands
from django.urls import NoReverseMatch, reverse


class ProductAcceptanceCheckStatus(str, Enum):
    PASS = 'pass'
    FAIL = 'fail'
    WARNING = 'warning'


@dataclass(frozen=True)
class ProductAcceptanceCheck:
    code: str
    title: str
    status: ProductAcceptanceCheckStatus
    evidence: str

    def to_dict(self):
        return {
            'code': self.code,
            'title': self.title,
            'status': self.status.value,
            'evidence': self.evidence,
        }


@dataclass(frozen=True)
class ProductAcceptanceReport:
    checks: tuple[ProductAcceptanceCheck, ...]

    @property
    def passed(self):
        return all(check.status == ProductAcceptanceCheckStatus.PASS for check in self.checks)

    def to_dict(self):
        return {
            'passed': self.passed,
            'checks': [check.to_dict() for check in self.checks],
        }

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def evaluate_product_acceptance(project_root=None):
    root = Path(project_root or settings.BASE_DIR)
    core_urls = _read(root / 'core' / 'urls.py')
    api_v1_urls = _read(root / 'core' / 'api_v1_urls.py')
    base_template = _read(root / 'templates' / 'base.html')
    readme = _read(root / 'README.md')
    mkdocs = _read(root / 'mkdocs.yml')
    docs_index = _read(root / 'docs' / 'index.md')
    deployment_docs = _read(root / 'docs' / 'deployment.md')
    compliance_docs = _read(root / 'docs' / 'architecture' / 'compliance.md')
    operational_docs = _read(root / 'docs' / 'architecture' / 'operational-readiness.md')
    backup_restore_docs = _read(root / 'docs' / 'architecture' / 'backup-restore.md')
    product_acceptance_docs = _read(root / 'docs' / 'architecture' / 'product-acceptance.md')
    prd = _read(root / 'PRD.md')

    checks = [
        _core_routes_check(core_urls),
        _api_v1_modules_check(api_v1_urls),
        _admin_menus_check(base_template),
        _commands_check(),
        _docs_check(
            readme,
            mkdocs,
            docs_index,
            deployment_docs,
            compliance_docs,
            operational_docs,
            backup_restore_docs,
            product_acceptance_docs,
        ),
        _prd_check(prd),
        _security_check('\n'.join([readme, deployment_docs, operational_docs, backup_restore_docs, product_acceptance_docs])),
    ]
    return ProductAcceptanceReport(tuple(checks))


def _read(path):
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''


def _check(code, title, passed, pass_evidence, fail_evidence):
    return ProductAcceptanceCheck(
        code=code,
        title=title,
        status=ProductAcceptanceCheckStatus.PASS if passed else ProductAcceptanceCheckStatus.FAIL,
        evidence=pass_evidence if passed else fail_evidence,
    )
```

Then add the helper checks:

```python
def _core_routes_check(core_urls):
    route_names = ('health', 'home', 'schema', 'swagger-ui', 'admin:index')
    unresolved = []
    for route_name in route_names:
        try:
            reverse(route_name)
        except NoReverseMatch:
            unresolved.append(route_name)

    required_source = ("path('health/'", "path('', home", "path('api/v1/'", "path('api/schema/'", "path('api/docs/'", "path('admin/'")
    missing_source = [item for item in required_source if item not in core_urls]
    passed = not unresolved and not missing_source
    return _check(
        'routes.core_entrypoints',
        'Rotas principais carregaveis',
        passed,
        'Rotas /health/, /, /api/v1/, /api/schema/, /api/docs/ e admin estao registradas.',
        'Rotas principais ausentes ou nao resolviveis: ' + ', '.join(unresolved + missing_source),
    )


def _api_v1_modules_check(api_v1_urls):
    required_modules = (
        'accounts', 'tenants', 'masters', 'formulations', 'production',
        'planning', 'procurement', 'inventory', 'costing', 'finance', 'fiscal',
        'crm', 'quality', 'qa', 'documents', 'deviations', 'capa', 'changes',
        'audits', 'risks', 'regulatory', 'pharmacovigilance', 'recalls',
        'maintenance', 'training', 'files', 'reports', 'workflow',
        'integrations', 'ai_agents', 'governance', 'compliance',
    )
    missing = [module for module in required_modules if module not in api_v1_urls]
    return _check(
        'routes.api_v1_modules',
        'Modulos publicados em API v1',
        not missing and "path('', include('tenants.urls'" in api_v1_urls,
        'Namespace /api/v1/ inclui os modulos principais e tenants.',
        'Modulos ausentes em /api/v1/: ' + ', '.join(missing),
    )


def _admin_menus_check(base_template):
    required_admin_links = (
        'admin:production_productionorder_changelist',
        'admin:inventory_stocklot_changelist',
        'admin:quality_qualitysample_changelist',
        'admin:documents_controlleddocument_changelist',
        'admin:deviations_qualityevent_changelist',
        'admin:capa_caparecord_changelist',
        'admin:governance_tenantmodulesetting_changelist',
        'admin:compliance_transversalrequirementpolicy_changelist',
    )
    missing = [link for link in required_admin_links if link not in base_template]
    return _check(
        'ui.admin_menus',
        'Menus administrativos criticos',
        not missing,
        'Menus administrativos criticos existem para operacao, qualidade, governanca e compliance.',
        'Menus administrativos criticos ausentes: ' + ', '.join(missing),
    )


def _commands_check():
    commands = get_commands()
    required_commands = (
        'check_operational_readiness',
        'check_backup_restore_readiness',
        'check_transversal_compliance',
        'check_product_acceptance',
    )
    missing = [command for command in required_commands if command not in commands]
    return _check(
        'commands.operational_gates',
        'Comandos operacionais de aceite',
        not missing,
        'Comandos operacionais de prontidao, backup, compliance e aceite estao registrados.',
        'Comandos operacionais ausentes: ' + ', '.join(missing),
    )


def _docs_check(readme, mkdocs, docs_index, deployment_docs, compliance_docs, operational_docs, backup_restore_docs, product_acceptance_docs):
    requirements = {
        'README.md:check_product_acceptance': 'check_product_acceptance' in readme,
        'mkdocs.yml:product_acceptance': 'architecture/product-acceptance.md' in mkdocs,
        'docs/index.md:aceite': 'Aceite técnico' in docs_index or 'aceite técnico' in docs_index,
        'docs/deployment.md:check_product_acceptance': 'check_product_acceptance' in deployment_docs,
        'compliance.md:check_transversal_compliance': 'check_transversal_compliance' in compliance_docs,
        'operational-readiness.md:check_operational_readiness': 'check_operational_readiness' in operational_docs,
        'backup-restore.md:check_backup_restore_readiness': 'check_backup_restore_readiness' in backup_restore_docs,
        'product-acceptance.md:canonical': 'check_product_acceptance' in product_acceptance_docs and 'Critério de Aceitação' in product_acceptance_docs,
    }
    missing = [name for name, present in requirements.items() if not present]
    return _check(
        'docs.product_acceptance',
        'Documentacao navegavel de aceite',
        not missing,
        'README, MKDocs, deploy e arquitetura documentam check_product_acceptance e os gates relacionados.',
        'Documentacao de aceite incompleta: ' + ', '.join(missing),
    )


def _prd_check(prd):
    passed = (
        '<sprint number="35"' in prd
        and 'Aceite técnico, hardening e checklist de lançamento' in prd
        and 'status="executed"' in prd
        and 'check_product_acceptance' in prd
    )
    return _check(
        'prd.sprint_35_recorded',
        'PRD registra Sprint 35 executada',
        passed,
        'PRD.md registra a Sprint 35 executada com checklist de aceite tecnico.',
        'PRD.md ainda nao registra a Sprint 35 executada com check_product_acceptance.',
    )


def _security_check(source):
    secret_patterns = (
        r'sk-[A-Za-z0-9]{20,}',
        r'AKIA[0-9A-Z]{16}',
        r'ghp_[A-Za-z0-9]{30,}',
        r'-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----',
    )
    leaked = [pattern for pattern in secret_patterns if re.search(pattern, source)]
    return _check(
        'security.no_real_secrets',
        'Sem segredos reais em docs de aceite',
        not leaked,
        'Documentacao de aceite e operacao usa variaveis simbolicas, sem tokens reais detectados.',
        'Possivel segredo real detectado por padrao: ' + ', '.join(leaked),
    )
```

- [ ] **Step 4: Run test to verify current failures are meaningful**

Run:

```bash
.venv/bin/pytest tests/test_product_acceptance.py -q
```

Expected: failures now point to missing command/docs/PRD, not missing module.

### Task 2: Management Command

**Files:**
- Create: `base/management/commands/check_product_acceptance.py`
- Modify: `tests/test_product_acceptance.py`

**Interfaces:**
- Consumes: `core.product_acceptance.evaluate_product_acceptance()`.
- Produces: Django command `check_product_acceptance` supporting `--format text|json` and `--fail-on-error`.

- [ ] **Step 1: Add command tests**

Append these tests to `tests/test_product_acceptance.py`:

```python
    def test_product_acceptance_command_outputs_json_report(self):
        stdout = StringIO()

        call_command('check_product_acceptance', format='json', stdout=stdout)

        payload = json.loads(stdout.getvalue())
        assert payload['passed'] is True
        assert {item['status'] for item in payload['checks']} == {'pass'}
        assert 'commands.operational_gates' in {item['code'] for item in payload['checks']}

    def test_product_acceptance_command_can_fail_on_errors(self):
        stdout = StringIO()

        call_command('check_product_acceptance', fail_on_error=True, stdout=stdout)

        assert 'product_acceptance: aprovado=True' in stdout.getvalue()
```

- [ ] **Step 2: Run command tests to verify red**

Run:

```bash
.venv/bin/pytest tests/test_product_acceptance.py::ProductAcceptanceTests::test_product_acceptance_command_outputs_json_report -q
```

Expected: FAIL with unknown command `check_product_acceptance`.

- [ ] **Step 3: Create the management command**

Create `base/management/commands/check_product_acceptance.py`:

```python
from django.core.management.base import BaseCommand, CommandError

from core.product_acceptance import evaluate_product_acceptance


class Command(BaseCommand):
    help = 'Avalia o aceite tecnico final do produto RGN Farma System.'

    def add_arguments(self, parser):
        parser.add_argument('--format', choices=('text', 'json'), default='text')
        parser.add_argument('--fail-on-error', action='store_true', dest='fail_on_error')

    def handle(self, *args, **options):
        report = evaluate_product_acceptance()

        if options['format'] == 'json':
            self.stdout.write(report.to_json())
        else:
            self.stdout.write(f'product_acceptance: aprovado={report.passed}')
            for check in report.checks:
                self.stdout.write(f'- {check.code}: {check.status.value} - {check.evidence}')

        if options['fail_on_error'] and not report.passed:
            raise CommandError('Aceite tecnico do produto possui falhas.')
```

- [ ] **Step 4: Run command tests**

Run:

```bash
.venv/bin/pytest tests/test_product_acceptance.py -q
```

Expected: tests may still fail only on docs/PRD acceptance until Task 3 is complete.

### Task 3: Documentation And PRD Closure

**Files:**
- Create: `docs/architecture/product-acceptance.md`
- Modify: `README.md`
- Modify: `docs/index.md`
- Modify: `docs/deployment.md`
- Modify: `mkdocs.yml`
- Modify: `PRD.md`

**Interfaces:**
- Consumes: command `check_product_acceptance`.
- Produces: navigable MKDocs page and Sprint 35 execution record.

- [ ] **Step 1: Add architecture page**

Create `docs/architecture/product-acceptance.md`:

````markdown
# Aceite Técnico de Produto

Documento canônico: `docs/architecture/product-acceptance.md`.

## Escopo

Esta página define o gate de aceite técnico final do RGN Farma System após as
Sprints 1 a 34. O objetivo é gerar evidência objetiva de que rotas, APIs,
menus, comandos operacionais, documentação e PRD permanecem coerentes.

O gate não acessa banco de dados, não executa restore real e não depende de
serviços externos.

## Comando

```bash
.venv/bin/python manage.py check_product_acceptance
.venv/bin/python manage.py check_product_acceptance --format json
.venv/bin/python manage.py check_product_acceptance --fail-on-error
```

## Cobertura

- Rotas principais: `/health/`, `/`, `/api/v1/`, `/api/schema/`, `/api/docs/`
  e Django admin.
- Publicação dos módulos principais no namespace `/api/v1/*`.
- Menus administrativos críticos para operação, qualidade, governança e
  conformidade.
- Comandos operacionais: `check_operational_readiness`,
  `check_backup_restore_readiness`, `check_transversal_compliance` e
  `check_product_acceptance`.
- Documentação navegável no MKDocs para deploy, compliance, prontidão
  operacional, backup/restauração e aceite de produto.
- Registro da Sprint 35 no `PRD.md`.

## Sequência de Aceite

```mermaid
flowchart TD
    A[Executar testes da Sprint 35] --> B[Executar check_product_acceptance]
    B --> C{passed=true?}
    C -- Nao --> D[Corrigir rota, menu, doc ou PRD]
    D --> B
    C -- Sim --> E[Executar checks operacionais existentes]
    E --> F[Gerar evidencia de release]
```

## Critério de Aceitação

- `check_product_acceptance --format json` retorna `passed=true`.
- `check_product_acceptance --fail-on-error` termina com exit code 0.
- `pytest tests/test_product_acceptance.py` passa.
- `check_operational_readiness --fail-on-error` continua passando.
- `check_backup_restore_readiness --fail-on-error` continua passando.
- `mkdocs build --strict` inclui esta página.
````

- [ ] **Step 2: Update MKDocs navigation**

Add this item after `Backup e Restauração` in `mkdocs.yml`:

```yaml
      - Aceite Técnico de Produto: architecture/product-acceptance.md
```

- [ ] **Step 3: Update README operational commands**

Add a product acceptance section near the operational checks in `README.md`:

````markdown
Aceite técnico de produto:

```bash
.venv/bin/python manage.py check_product_acceptance
.venv/bin/python manage.py check_product_acceptance --format json
.venv/bin/python manage.py check_product_acceptance --fail-on-error
```
````

- [ ] **Step 4: Update docs index**

Add this bullet to `docs/index.md`:

```markdown
- Aceite técnico de produto para validar rotas, APIs v1, menus administrativos, comandos operacionais, documentação e PRD antes do release.
```

- [ ] **Step 5: Update deployment docs**

Add this command block to `docs/deployment.md` near the other readiness checks:

````markdown
Aceite técnico final:

```bash
.venv/bin/python manage.py check_product_acceptance --fail-on-error
```
````

- [ ] **Step 6: Update PRD Sprint 35**

Insert this sprint after Sprint 34 in `PRD.md`:

```xml
      <sprint number="35" title="Aceite técnico, hardening e checklist de lançamento" status="executed">
        <task status="done">[x] Criar testes automatizados para aceite técnico de produto, rotas, APIs v1, menus, comandos operacionais, documentação e PRD.</task>
        <task status="done">[x] Criar core.product_acceptance com relatório estruturado de aceite final do produto.</task>
        <task status="done">[x] Criar comando Django check_product_acceptance com saída texto, JSON e opção --fail-on-error.</task>
        <task status="done">[x] Validar rotas /health/, /, /api/v1/, /api/schema/, /api/docs/ e Django admin.</task>
        <task status="done">[x] Validar publicação dos módulos principais no namespace /api/v1/*.</task>
        <task status="done">[x] Validar menus administrativos críticos para operação, qualidade, governança e conformidade.</task>
        <task status="done">[x] Validar presença dos comandos check_operational_readiness, check_backup_restore_readiness, check_transversal_compliance e check_product_acceptance.</task>
        <task status="done">[x] Atualizar README, MKDocs, docs/deployment.md e documentação técnica de Aceite de Produto.</task>
        <task status="done">[x] Executar testes específicos da sprint com sucesso.</task>
      </sprint>
```

- [ ] **Step 7: Run tests after docs/PRD**

Run:

```bash
.venv/bin/pytest tests/test_product_acceptance.py -q
```

Expected: PASS.

### Task 4: Full Verification And Sprint Commit

**Files:**
- Modify: files touched by Tasks 1-3 only.

**Interfaces:**
- Consumes: complete Sprint 35 implementation.
- Produces: committed branch ready for push.

- [ ] **Step 1: Run Django and migration checks**

Run:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py makemigrations --check --dry-run
```

Expected:

```text
System check identified no issues (0 silenced).
No changes detected
```

- [ ] **Step 2: Run Sprint 35 acceptance command**

Run:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_product_acceptance --fail-on-error
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_product_acceptance --format json
```

Expected: text output contains `product_acceptance: aprovado=True`; JSON output contains `"passed": true`.

- [ ] **Step 3: Run existing operational gates**

Run:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_operational_readiness --fail-on-error
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_backup_restore_readiness --fail-on-error
```

Expected: both commands exit 0.

- [ ] **Step 4: Run relevant tests**

Run:

```bash
.venv/bin/pytest tests/test_product_acceptance.py tests/test_operational_readiness.py tests/test_backup_restore_readiness.py -q
```

Expected: PASS.

- [ ] **Step 5: Build documentation**

Run:

```bash
mkdocs build --strict
```

Expected: exit 0. The Material for MkDocs deprecation warning about MkDocs 2.0 is informational if no strict build error occurs.

- [ ] **Step 6: Check git diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only Sprint 35 files modified before commit.

- [ ] **Step 7: Commit Sprint 35**

Run:

```bash
git add core/product_acceptance.py base/management/commands/check_product_acceptance.py tests/test_product_acceptance.py README.md docs/index.md docs/deployment.md docs/architecture/product-acceptance.md mkdocs.yml PRD.md
git diff --cached --check
git commit -m "feat: add product acceptance gate"
```

Expected: commit created on `sprint-35-product-acceptance-hardening`.

- [ ] **Step 8: Push Sprint 35 branch**

Run:

```bash
git push -u origin sprint-35-product-acceptance-hardening
```

Expected: remote branch created at `git@github.com:RuiGN/rgnfarmasystem.git`.
