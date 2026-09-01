# Release Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Sprint 36, a local/containerized release readiness gate for staging evidence after product acceptance.

**Architecture:** Add a lightweight evaluator in `core/release_readiness.py`, following the existing readiness pattern from `core/operational_readiness.py`, `core/backup_restore_readiness.py`, and `core/product_acceptance.py`. Expose it through `base/management/commands/check_release_readiness.py`, then document the release runbook and record Sprint 36 in `PRD.md`.

**Tech Stack:** Python, Django, Django management commands, pytest, DRF Spectacular, MKDocs, Markdown.

## Global Constraints

- Do not execute deploy real em VPS.
- Do not create or require the production orchestrator during tests.
- Do not access Cloudflare, GHCR, public domain, real certificates, production secrets, tokens, or credentials.
- Do not create a new Django app.
- Do not create or alter persistent models.
- Do not generate migrations.
- Do not create deep demo data for all modules; validate the existing `load_demo_scenario` command and documentation.
- Do not execute smoke HTTP against a remote server.
- Code identifiers remain in English.
- User-facing output remains in Brazilian Portuguese.
- The evaluator must work without database access.
- Follow the existing readiness report style: dataclasses, stable check codes, text and JSON command output.

---

### Task 1: Release Readiness Evaluator

**Files:**
- Create: `core/release_readiness.py`
- Create: `tests/test_release_readiness.py`

**Interfaces:**
- Consumes: Django `settings.BASE_DIR`, route module `core.urls`, management command registry, `core/settings.py`, `README.md`, `mkdocs.yml`, `docs/index.md`, `docs/deployment.md`, `docs/architecture/governance.md`, `docs/architecture/product-acceptance.md`, `docs/architecture/release-readiness.md`, and `PRD.md`.
- Produces: `ReleaseReadinessCheckStatus`, `ReleaseReadinessCheck`, `ReleaseReadinessReport`, `evaluate_release_readiness(project_root=None)`.

- [ ] **Step 1: Write the failing evaluator tests**

Create `tests/test_release_readiness.py`:

```python
import json
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase


class ReleaseReadinessTests(SimpleTestCase):
    def test_release_readiness_report_covers_gates_smoke_openapi_demo_docs_and_prd(self):
        from core.release_readiness import ReleaseReadinessCheckStatus, evaluate_release_readiness

        report = evaluate_release_readiness(project_root=settings.BASE_DIR)
        checks = {check.code: check for check in report.checks}

        expected_codes = {
            'release.required_gates',
            'release.smoke_routes',
            'release.openapi_schema',
            'release.demo_data',
            'release.evidence_runbook',
            'prd.sprint_36_recorded',
            'security.no_real_secrets',
        }

        assert report.passed is True
        assert expected_codes.issubset(checks)
        assert all(check.status == ReleaseReadinessCheckStatus.PASS for check in checks.values())
        assert 'check_release_readiness' in checks['release.required_gates'].evidence
        assert 'openapi-schema.yml' in checks['release.openapi_schema'].evidence

    def test_release_readiness_report_serializes_to_json(self):
        from core.release_readiness import evaluate_release_readiness

        payload = json.loads(evaluate_release_readiness(project_root=settings.BASE_DIR).to_json())

        assert payload['passed'] is True
        assert 'checks' in payload
        assert 'release.evidence_runbook' in {item['code'] for item in payload['checks']}

    def test_release_readiness_can_report_documentation_failure(self):
        from core.release_readiness import evaluate_release_readiness

        temporary_root = Path(settings.BASE_DIR) / 'tests' / 'fixtures' / 'missing-release-readiness-docs'

        report = evaluate_release_readiness(project_root=temporary_root)
        checks = {check.code: check for check in report.checks}

        assert report.passed is False
        assert checks['release.evidence_runbook'].status.value == 'fail'
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
.venv/bin/pytest tests/test_release_readiness.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.release_readiness'`.

- [ ] **Step 3: Create the evaluator**

Create `core/release_readiness.py`:

```python
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from django.conf import settings
from django.core.management import get_commands
from django.urls import NoReverseMatch, reverse


class ReleaseReadinessCheckStatus(str, Enum):
    PASS = 'pass'
    FAIL = 'fail'
    WARNING = 'warning'


@dataclass(frozen=True)
class ReleaseReadinessCheck:
    code: str
    title: str
    status: ReleaseReadinessCheckStatus
    evidence: str

    def to_dict(self):
        return {
            'code': self.code,
            'title': self.title,
            'status': self.status.value,
            'evidence': self.evidence,
        }


@dataclass(frozen=True)
class ReleaseReadinessReport:
    checks: tuple[ReleaseReadinessCheck, ...]

    @property
    def passed(self):
        return all(check.status == ReleaseReadinessCheckStatus.PASS for check in self.checks)

    def to_dict(self):
        return {
            'passed': self.passed,
            'checks': [check.to_dict() for check in self.checks],
        }

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def evaluate_release_readiness(project_root=None):
    root = Path(project_root or settings.BASE_DIR)
    core_urls = _read(root / 'core' / 'urls.py')
    settings_source = _read(root / 'core' / 'settings.py')
    readme = _read(root / 'README.md')
    mkdocs = _read(root / 'mkdocs.yml')
    docs_index = _read(root / 'docs' / 'index.md')
    deployment_docs = _read(root / 'docs' / 'deployment.md')
    governance_docs = _read(root / 'docs' / 'architecture' / 'governance.md')
    product_acceptance_docs = _read(root / 'docs' / 'architecture' / 'product-acceptance.md')
    release_docs = _read(root / 'docs' / 'architecture' / 'release-readiness.md')
    prd = _read(root / 'PRD.md')

    docs_source = '\n'.join(
        [
            readme,
            mkdocs,
            docs_index,
            deployment_docs,
            governance_docs,
            product_acceptance_docs,
            release_docs,
            prd,
        ]
    )

    checks = [
        _required_gates_check(readme, deployment_docs, product_acceptance_docs, release_docs),
        _smoke_routes_check(core_urls, deployment_docs, release_docs),
        _openapi_check(core_urls, settings_source, readme, deployment_docs, release_docs),
        _demo_data_check(readme, governance_docs, release_docs),
        _evidence_runbook_check(readme, deployment_docs, release_docs),
        _prd_check(prd),
        _security_check(docs_source),
    ]
    return ReleaseReadinessReport(tuple(checks))


def _read(path):
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''


def _check(code, title, passed, pass_evidence, fail_evidence):
    return ReleaseReadinessCheck(
        code=code,
        title=title,
        status=ReleaseReadinessCheckStatus.PASS if passed else ReleaseReadinessCheckStatus.FAIL,
        evidence=pass_evidence if passed else fail_evidence,
    )


def _required_gates_check(readme, deployment_docs, product_acceptance_docs, release_docs):
    commands = get_commands()
    required_commands = (
        'check_operational_readiness',
        'check_backup_restore_readiness',
        'check_product_acceptance',
        'check_release_readiness',
    )
    docs_source = '\n'.join([readme, deployment_docs, product_acceptance_docs, release_docs])
    missing_registered = [command for command in required_commands if command not in commands]
    missing_docs = [command for command in required_commands if command not in docs_source]
    passed = not missing_registered and not missing_docs
    return _check(
        'release.required_gates',
        'Gates obrigatorios de release',
        passed,
        'Gates check_operational_readiness, check_backup_restore_readiness, check_product_acceptance e check_release_readiness estao registrados e documentados.',
        'Gates ausentes no registry ou documentacao: ' + ', '.join(missing_registered + missing_docs),
    )


def _smoke_routes_check(core_urls, deployment_docs, release_docs):
    route_names = ('health', 'home', 'schema', 'swagger-ui')
    unresolved = []
    for route_name in route_names:
        try:
            reverse(route_name)
        except NoReverseMatch:
            unresolved.append(route_name)

    required_source = (
        "path('health/'",
        "path('', home",
        "path('api/v1/'",
        "path('api/schema/'",
        "'api/docs/'",
    )
    missing_source = [item for item in required_source if item not in core_urls]
    docs_source = '\n'.join([deployment_docs, release_docs])
    smoke_commands = (
        'curl -fsS http://127.0.0.1:8000/health/',
        'curl -fsS http://127.0.0.1:8000/',
        'curl -fsS http://127.0.0.1:8000/api/schema/',
        'curl -fsS http://127.0.0.1:8000/api/docs/',
        'curl -fsS http://127.0.0.1:8000/api/v1/',
    )
    missing_docs = [command for command in smoke_commands if command not in docs_source]
    passed = not unresolved and not missing_source and not missing_docs
    return _check(
        'release.smoke_routes',
        'Smoke local de rotas criticas',
        passed,
        'Runbook documenta smoke local para /health/, /, /api/schema/, /api/docs/ e /api/v1/; rotas Django carregam.',
        'Smoke local incompleto: ' + ', '.join(unresolved + missing_source + missing_docs),
    )


def _openapi_check(core_urls, settings_source, readme, deployment_docs, release_docs):
    docs_source = '\n'.join([readme, deployment_docs, release_docs])
    commands = get_commands()
    requirements = {
        'command:spectacular': 'spectacular' in commands,
        'settings:drf_spectacular': "'drf_spectacular'" in settings_source,
        'settings:DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema' in settings_source,
        'route:/api/schema/': "path('api/schema/'" in core_urls,
        'route:/api/docs/': "'api/docs/'" in core_urls,
        'docs:spectacular_file': 'spectacular --file openapi-schema.yml' in docs_source,
    }
    missing = [name for name, present in requirements.items() if not present]
    return _check(
        'release.openapi_schema',
        'OpenAPI pronto para release',
        not missing,
        'OpenAPI via drf-spectacular, /api/schema/, /api/docs/ e openapi-schema.yml estao disponiveis.',
        'OpenAPI incompleto para release: ' + ', '.join(missing),
    )


def _demo_data_check(readme, governance_docs, release_docs):
    commands = get_commands()
    docs_source = '\n'.join([readme, governance_docs, release_docs])
    requirements = {
        'command:load_demo_scenario': 'load_demo_scenario' in commands,
        'docs:scenario': '--scenario' in docs_source,
        'docs:scenario': '--scenario' in docs_source,
        'docs:base_master_data': 'base_master_data' in docs_source,
        'docs:quality_deviation': 'quality_deviation' in docs_source,
    }
    missing = [name for name, present in requirements.items() if not present]
    return _check(
        'release.demo_data',
        'Carga demo para staging local',
        not missing,
        'Comando load_demo_scenario esta registrado e documentado com scenario e exemplos de dados demo.',
        'Carga demo de staging incompleta: ' + ', '.join(missing),
    )


def _evidence_runbook_check(readme, deployment_docs, release_docs):
    docs_source = '\n'.join([readme, deployment_docs, release_docs])
    required_steps = (
        'manage.py check',
        'makemigrations --check --dry-run',
        'check_operational_readiness --fail-on-error',
        'check_backup_restore_readiness --fail-on-error',
        'check_product_acceptance --fail-on-error',
        'check_release_readiness --fail-on-error',
        'spectacular --file openapi-schema.yml',
        'curl -fsS http://127.0.0.1:8000/health/',
        'Evidencia de release',
    )
    missing = [step for step in required_steps if step not in docs_source]
    return _check(
        'release.evidence_runbook',
        'Runbook de evidencia de release',
        not missing,
        'Runbook documenta checks Django, migrations, gates, OpenAPI, smoke local e Evidencia de release.',
        'Runbook de release incompleto: ' + ', '.join(missing),
    )


def _prd_check(prd):
    passed = (
        '<sprint number="36"' in prd
        and _contains_any(
            prd,
            (
                'Prontidao de release e staging local',
                'Prontidão de release e staging local',
            ),
        )
        and 'status="executed"' in prd
        and 'check_release_readiness' in prd
    )
    return _check(
        'prd.sprint_36_recorded',
        'PRD registra Sprint 36 executada',
        passed,
        'PRD.md registra a Sprint 36 executada com checklist de prontidao de release.',
        'PRD.md ainda nao registra a Sprint 36 executada com check_release_readiness.',
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
        'Sem segredos reais em docs de release',
        not leaked,
        'Documentacao de release usa variaveis simbolicas, sem tokens reais detectados.',
        'Possivel segredo real detectado por padrao: ' + ', '.join(leaked),
    )


def _contains_any(source, candidates):
    return any(candidate in source for candidate in candidates)
```

- [ ] **Step 4: Run evaluator tests and confirm meaningful failures**

Run:

```bash
.venv/bin/pytest tests/test_release_readiness.py -q
```

Expected: FAIL because `check_release_readiness`, `docs/architecture/release-readiness.md`, runbook docs, and Sprint 36 PRD record do not exist yet. The failure must no longer be `ModuleNotFoundError`.

### Task 2: Management Command

**Files:**
- Create: `base/management/commands/check_release_readiness.py`
- Modify: `tests/test_release_readiness.py`

**Interfaces:**
- Consumes: `core.release_readiness.evaluate_release_readiness()`.
- Produces: Django command `check_release_readiness` supporting `--format text|json` and `--fail-on-error`.

- [ ] **Step 1: Add command tests**

Append these tests inside `ReleaseReadinessTests` in `tests/test_release_readiness.py`:

```python
    def test_release_readiness_command_outputs_json_report(self):
        stdout = StringIO()

        call_command('check_release_readiness', format='json', stdout=stdout)

        payload = json.loads(stdout.getvalue())
        assert payload['passed'] is True
        assert {item['status'] for item in payload['checks']} == {'pass'}
        assert 'release.required_gates' in {item['code'] for item in payload['checks']}

    def test_release_readiness_command_can_fail_on_errors(self):
        stdout = StringIO()

        call_command('check_release_readiness', fail_on_error=True, stdout=stdout)

        assert 'release_readiness: aprovado=True' in stdout.getvalue()
```

- [ ] **Step 2: Run command test to verify red**

Run:

```bash
.venv/bin/pytest tests/test_release_readiness.py::ReleaseReadinessTests::test_release_readiness_command_outputs_json_report -q
```

Expected: FAIL with unknown command `check_release_readiness`.

- [ ] **Step 3: Create the management command**

Create `base/management/commands/check_release_readiness.py`:

```python
from django.core.management.base import BaseCommand, CommandError

from core.release_readiness import evaluate_release_readiness


class Command(BaseCommand):
    help = 'Avalia a prontidao de release e staging local do RGN Farma System.'

    def add_arguments(self, parser):
        parser.add_argument('--format', choices=('text', 'json'), default='text')
        parser.add_argument('--fail-on-error', action='store_true', dest='fail_on_error')

    def handle(self, *args, **options):
        report = evaluate_release_readiness()

        if options['format'] == 'json':
            self.stdout.write(report.to_json())
        else:
            self.stdout.write(f'release_readiness: aprovado={report.passed}')
            for check in report.checks:
                self.stdout.write(f'- {check.code}: {check.status.value} - {check.evidence}')

        if options['fail_on_error'] and not report.passed:
            raise CommandError('Prontidao de release possui falhas.')
```

- [ ] **Step 4: Run command tests**

Run:

```bash
.venv/bin/pytest tests/test_release_readiness.py -q
```

Expected: tests still fail only on docs/PRD/runbook acceptance until Task 3 is complete.

### Task 3: Documentation And PRD Closure

**Files:**
- Create: `docs/architecture/release-readiness.md`
- Modify: `README.md`
- Modify: `docs/index.md`
- Modify: `docs/deployment.md`
- Modify: `mkdocs.yml`
- Modify: `PRD.md`

**Interfaces:**
- Consumes: command `check_release_readiness`.
- Produces: navigable MKDocs page, documented staging local runbook, and Sprint 36 execution record.

- [ ] **Step 1: Add architecture page**

Create `docs/architecture/release-readiness.md`:

````markdown
# Prontidão de Release e Staging Local

Documento canônico: `docs/architecture/release-readiness.md`.

## Escopo

Esta página define o gate de prontidão de release e staging local do RGN Farma
System após o aceite técnico de produto. O objetivo é consolidar evidências
antes de publicar uma versão interna, sem depender de VPS real, Cloudflare,
domínio público ou credenciais de produção.

O gate não acessa banco de dados, não executa deploy real e não inicia servidor
HTTP por conta própria.

## Comando

```bash
.venv/bin/python manage.py check_release_readiness
.venv/bin/python manage.py check_release_readiness --format json
.venv/bin/python manage.py check_release_readiness --fail-on-error
```

## Gates Obrigatórios

Antes de declarar o release pronto, execute:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py makemigrations --check --dry-run
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_operational_readiness --fail-on-error
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_backup_restore_readiness --fail-on-error
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_product_acceptance --fail-on-error
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_release_readiness --fail-on-error
```

## OpenAPI

Gere o schema versionável para revisão técnica:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py spectacular --file openapi-schema.yml
```

O arquivo `openapi-schema.yml` é evidência transitória de release. Ele deve ser
anexado ao pacote de evidência quando necessário e não precisa ser versionado.

## Smoke Local

Com o servidor local ou container de staging em execução, valide:

```bash
curl -fsS http://127.0.0.1:8000/health/
curl -fsS http://127.0.0.1:8000/
curl -fsS http://127.0.0.1:8000/api/schema/
curl -fsS http://127.0.0.1:8000/api/docs/
curl -fsS http://127.0.0.1:8000/api/v1/
```

Falha em qualquer comando deve bloquear o release interno até investigação.

## Dados Demo Para Staging

Para preparar uma demonstração local:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py load_demo_scenario --scenario base_master_data quality_deviation
```

O comando `load_demo_scenario` registra a execução e cria dados de governança
compatíveis com demonstração e revisão interna.

## Evidencia de release

Registre no pacote de release:

- Hash do commit.
- Resultado de `manage.py check`.
- Resultado de `makemigrations --check --dry-run`.
- Resultado dos comandos `check_operational_readiness`,
  `check_backup_restore_readiness`, `check_product_acceptance` e
  `check_release_readiness`.
- Arquivo `openapi-schema.yml` gerado para a versão.
- Evidência do smoke local de `/health/`, `/`, `/api/schema/`, `/api/docs/` e
  `/api/v1/`.
- Confirmação de que nenhum segredo real foi registrado em documentação,
  logs ou artefatos.

## Sequência

```mermaid
flowchart TD
    A[Executar checks Django] --> B[Executar gates operacionais]
    B --> C[Gerar OpenAPI]
    C --> D[Executar smoke local]
    D --> E{Falhas?}
    E -- Sim --> F[Corrigir e repetir gate]
    E -- Nao --> G[Registrar Evidencia de release]
```

## Critério de Aceitação

- `check_release_readiness --format json` retorna `passed=true`.
- `check_release_readiness --fail-on-error` termina com exit code 0.
- `check_product_acceptance --fail-on-error` continua passando.
- `spectacular --file openapi-schema.yml` gera schema OpenAPI.
- Smoke local cobre `/health/`, `/`, `/api/schema/`, `/api/docs/` e `/api/v1/`.
- `pytest tests/test_release_readiness.py` passa.
- `mkdocs build --strict` inclui esta página.
````

- [ ] **Step 2: Update MKDocs navigation**

Add this item after `Aceite Técnico de Produto` in `mkdocs.yml`:

```yaml
      - Prontidão de Release: architecture/release-readiness.md
```

- [ ] **Step 3: Update README operational commands**

Add this section after the product acceptance command block in `README.md`:

````markdown
Prontidão de release e staging local:

```bash
.venv/bin/python manage.py check_release_readiness
.venv/bin/python manage.py check_release_readiness --format json
.venv/bin/python manage.py check_release_readiness --fail-on-error
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py spectacular --file openapi-schema.yml
curl -fsS http://127.0.0.1:8000/health/
curl -fsS http://127.0.0.1:8000/
curl -fsS http://127.0.0.1:8000/api/schema/
curl -fsS http://127.0.0.1:8000/api/docs/
curl -fsS http://127.0.0.1:8000/api/v1/
```

Evidencia de release: registre commit, resultados de `manage.py check`,
`makemigrations --check --dry-run`, gates operacionais, schema OpenAPI e smoke
local antes de promover a versão.
````

- [ ] **Step 4: Update docs index**

Add this bullet to `docs/index.md` after the product acceptance bullet:

```markdown
- Prontidão de release e staging local para consolidar gates, OpenAPI, smoke local, dados demo e Evidencia de release antes de promover uma versão interna.
```

- [ ] **Step 5: Update deployment docs**

Add this section after `## Aceite Técnico Final` in `docs/deployment.md`:

````markdown
## Prontidão de Release e Staging Local

Antes de promover uma versão interna, execute o gate consolidado de release:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_release_readiness --fail-on-error
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py spectacular --file openapi-schema.yml
```

Com o servidor local ou container de staging em execução, execute o smoke local:

```bash
curl -fsS http://127.0.0.1:8000/health/
curl -fsS http://127.0.0.1:8000/
curl -fsS http://127.0.0.1:8000/api/schema/
curl -fsS http://127.0.0.1:8000/api/docs/
curl -fsS http://127.0.0.1:8000/api/v1/
```

Para preparar dados demo de staging local:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py load_demo_scenario --scenario base_master_data quality_deviation
```

Evidencia de release deve incluir commit, resultado dos gates
`check_operational_readiness --fail-on-error`,
`check_backup_restore_readiness --fail-on-error`,
`check_product_acceptance --fail-on-error`,
`check_release_readiness --fail-on-error`, OpenAPI gerado e smoke local.
````

- [ ] **Step 6: Update PRD Sprint 36**

Insert this sprint after Sprint 35 in `PRD.md`:

```xml
      <sprint number="36" title="Prontidão de release e staging local" status="executed">
        <task status="done">[x] Criar testes automatizados para prontidão de release, gates existentes, smoke local, OpenAPI, dados demo, documentação e PRD.</task>
        <task status="done">[x] Criar core.release_readiness com relatório estruturado de release local/containerizado.</task>
        <task status="done">[x] Criar comando Django check_release_readiness com saída texto, JSON e opção --fail-on-error.</task>
        <task status="done">[x] Validar presença dos gates check_operational_readiness, check_backup_restore_readiness, check_product_acceptance e check_release_readiness.</task>
        <task status="done">[x] Validar runbook de smoke local para /health/, /, /api/schema/, /api/docs/ e /api/v1/.</task>
        <task status="done">[x] Validar geração de OpenAPI via spectacular --file openapi-schema.yml.</task>
        <task status="done">[x] Validar comando load_demo_scenario e documentação de dados demo para staging local.</task>
        <task status="done">[x] Atualizar README, MKDocs, docs/deployment.md e documentação técnica de prontidão de release.</task>
        <task status="done">[x] Executar testes específicos da sprint com sucesso.</task>
      </sprint>
```

- [ ] **Step 7: Run tests after docs/PRD**

Run:

```bash
.venv/bin/pytest tests/test_release_readiness.py -q
```

Expected: PASS.

### Task 4: Full Verification And Sprint Commit

**Files:**
- Modify: files touched by Tasks 1-3 only.

**Interfaces:**
- Consumes: complete Sprint 36 implementation.
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

- [ ] **Step 2: Run release readiness command**

Run:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_release_readiness --fail-on-error
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_release_readiness --format json
```

Expected: text output contains `release_readiness: aprovado=True`; JSON output contains `"passed": true`.

- [ ] **Step 3: Run existing product and operational gates**

Run:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_product_acceptance --fail-on-error
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_operational_readiness --fail-on-error
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_backup_restore_readiness --fail-on-error
```

Expected: all three commands exit 0.

- [ ] **Step 4: Generate OpenAPI schema**

Run:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py spectacular --file /tmp/rgnfarmasystem-openapi-schema.yml
test -s /tmp/rgnfarmasystem-openapi-schema.yml
```

Expected: both commands exit 0 and `/tmp/rgnfarmasystem-openapi-schema.yml` is non-empty.

- [ ] **Step 5: Run relevant tests**

Run:

```bash
.venv/bin/pytest tests/test_release_readiness.py tests/test_product_acceptance.py tests/test_operational_readiness.py tests/test_backup_restore_readiness.py -q
```

Expected: PASS.

- [ ] **Step 6: Build documentation**

Run:

```bash
.venv/bin/mkdocs build --strict
```

Expected: exit 0. The Material for MkDocs warning about MkDocs 2.0 is informational if the strict build exits 0.

- [ ] **Step 7: Check git diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only Sprint 36 files modified before commit.

- [ ] **Step 8: Commit Sprint 36**

Run:

```bash
git add core/release_readiness.py base/management/commands/check_release_readiness.py tests/test_release_readiness.py README.md docs/index.md docs/deployment.md docs/architecture/release-readiness.md mkdocs.yml PRD.md
git diff --cached --check
git commit -m "feat: add release readiness gate"
```

Expected: commit created on the current branch.

- [ ] **Step 9: Push Sprint 36 branch**

Run:

```bash
git push
```

Expected: remote branch updated with the Sprint 36 design and implementation commits.
