# Local Docker Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the complete application locally behind Nginx with PostgreSQL and provision repeatable Control Plane and ERP access for one all-modules tenant.

**Architecture:** `docker-compose.local.yml` will expose only Nginx on port 4127 and keep Django/Gunicorn, PostgreSQL, Redis, RabbitMQ, Celery Worker and Celery Beat on the internal network. A one-shot bootstrap service will call an idempotent Django management command after migrations, while a separate read-only command will display local access information and a current TOTP code on demand.

**Tech Stack:** Docker Compose v2, Nginx 1.27, PostgreSQL 15, Redis 7, RabbitMQ 3, Python 3.13, Django, django-otp, Gunicorn, Celery.

## Global Constraints

- Control Plane URL is `http://control.localhost:4127/platform/`.
- ERP URL is `http://erp.localhost:4127/app/`.
- Do not expose PostgreSQL, Redis, RabbitMQ or Gunicorn ports on the host.
- Do not commit effective passwords, Django secrets, encryption keys or TOTP seeds.
- Do not delete or recreate existing Docker volumes automatically.
- Bootstrap must be idempotent and transactional.
- The tenant must use `module_contract_enforced=True` and enable every value in `TenantModuleSetting.Module`.
- Control Plane and ERP identities must remain separate.
- Preserve the current uncommitted dashboard changes.

---

### Task 1: Idempotent local publication bootstrap

**Files:**
- Create: `control_plane/management/commands/bootstrap_local_publication.py`
- Create: `tests/test_local_publication.py`

**Interfaces:**
- Consumes environment variables `LOCAL_CONTROL_EMAIL`, `LOCAL_CONTROL_PASSWORD`, `LOCAL_CONTROL_TOTP_SEED`, `LOCAL_ERP_EMAIL`, `LOCAL_ERP_PASSWORD`, `LOCAL_TENANT_NAME`, `LOCAL_TENANT_SLUG`, and `LOCAL_TENANT_DOMAIN`.
- Produces command `python manage.py bootstrap_local_publication` with no secret output.
- Produces one active platform operator, one active ERP owner, one active tenant and a complete module contract.

- [ ] **Step 1: Write failing bootstrap tests**

Add `LocalPublicationBootstrapTests(TestCase)` covering:

```python
@override_settings(DEBUG=False)
class LocalPublicationBootstrapTests(TestCase):
    env = {
        'LOCAL_CONTROL_EMAIL': 'control@local.test',
        'LOCAL_CONTROL_PASSWORD': 'Control-Local-Only!2026',
        'LOCAL_CONTROL_TOTP_SEED': 'local-control-seed-for-tests',
        'LOCAL_ERP_EMAIL': 'owner@local.test',
        'LOCAL_ERP_PASSWORD': 'ERP-Local-Only!2026',
        'LOCAL_TENANT_NAME': 'RGN Farma Local',
        'LOCAL_TENANT_SLUG': 'rgn-farma-local',
        'LOCAL_TENANT_DOMAIN': 'erp.localhost',
    }

    @patch.dict(os.environ, env, clear=False)
    def test_bootstrap_creates_separate_control_and_erp_identities(self):
        call_command('bootstrap_local_publication')
        operator = get_user_model().objects.get(email=self.env['LOCAL_CONTROL_EMAIL'])
        owner = get_user_model().objects.get(email=self.env['LOCAL_ERP_EMAIL'])
        tenant = Tenant.objects.get(slug=self.env['LOCAL_TENANT_SLUG'])
        assert operator.is_platform_operator and operator.is_staff and operator.is_active
        assert not operator.has_tenant_access(tenant)
        assert owner.check_password(self.env['LOCAL_ERP_PASSWORD'])
        assert TenantMembership.objects.get(user=owner, tenant=tenant).role == TenantMembership.Role.OWNER
        assert TOTPDevice.objects.get(user=operator, confirmed=True).key

    @patch.dict(os.environ, env, clear=False)
    def test_bootstrap_enables_every_module_and_is_idempotent(self):
        call_command('bootstrap_local_publication')
        call_command('bootstrap_local_publication')
        tenant = Tenant.objects.get(slug=self.env['LOCAL_TENANT_SLUG'])
        settings = TenantModuleSetting.objects.filter(tenant=tenant)
        assert tenant.module_contract_enforced is True
        assert settings.count() == len(TenantModuleSetting.Module.values)
        assert set(settings.filter(status='active', is_enabled=True).values_list('module', flat=True)) == set(TenantModuleSetting.Module.values)
        assert TenantMembership.objects.filter(tenant=tenant, role='owner', is_active=True).count() == 1

    def test_bootstrap_rejects_missing_or_equal_identity_emails(self):
        with patch.dict(os.environ, {'LOCAL_CONTROL_EMAIL': '', 'LOCAL_ERP_EMAIL': ''}, clear=False):
            with pytest.raises(CommandError):
                call_command('bootstrap_local_publication')
```

Also assert captured command output contains emails and tenant slug but contains neither password nor TOTP seed.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" pytest tests/test_local_publication.py -q
```

Expected: FAIL because `bootstrap_local_publication` does not exist.

- [ ] **Step 3: Implement the transactional command**

Implement a `BaseCommand` with `@transaction.atomic` and these private helpers:

```python
REQUIRED_ENVIRONMENT = (
    'LOCAL_CONTROL_EMAIL', 'LOCAL_CONTROL_PASSWORD', 'LOCAL_CONTROL_TOTP_SEED',
    'LOCAL_ERP_EMAIL', 'LOCAL_ERP_PASSWORD', 'LOCAL_TENANT_NAME',
    'LOCAL_TENANT_SLUG', 'LOCAL_TENANT_DOMAIN',
)

def _required_environment() -> dict[str, str]:
    values = {name: os.environ.get(name, '').strip() for name in REQUIRED_ENVIRONMENT}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise CommandError(f'Variáveis obrigatórias ausentes: {", ".join(missing)}.')
    if values['LOCAL_CONTROL_EMAIL'].lower() == values['LOCAL_ERP_EMAIL'].lower():
        raise CommandError('Os usuários do Control Plane e do ERP devem ser distintos.')
    return values

def _totp_key(seed: str) -> str:
    return hashlib.sha256(seed.encode('utf-8')).hexdigest()
```

The command must:

1. reject absent values and equal Control/ERP emails with `CommandError`;
2. use `update_or_create` for tenant, users, membership and module settings;
3. call `set_password` on both users on every explicit bootstrap run;
4. keep the operator out of tenant memberships and set `is_superuser=False`;
5. set the ERP owner to `is_staff=False`, `is_superuser=False`, `is_platform_operator=False`;
6. create exactly one confirmed `TOTPDevice` named `Publicação local`, using the SHA-256-derived key;
7. activate all module settings with deterministic `menu_order`, clear deactivation fields and set `activated_by`/`activated_at`;
8. print only a success summary containing emails, tenant slug and enabled-module count.

- [ ] **Step 4: Run tests to verify GREEN**

Run the command from Step 2. Expected: all tests in `tests/test_local_publication.py` pass.

- [ ] **Step 5: Run related identity and module tests**

Run:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" pytest tests/test_control_plane.py tests/test_tenant_module_access.py tests/test_local_publication.py -q
```

Expected: PASS with no regressions.

- [ ] **Step 6: Commit the bootstrap command**

```bash
git add control_plane/management/commands/bootstrap_local_publication.py tests/test_local_publication.py
git commit -m "feat: add local publication bootstrap"
```

---

### Task 2: Safe local access information command

**Files:**
- Create: `control_plane/management/commands/local_access_info.py`
- Modify: `tests/test_local_publication.py`

**Interfaces:**
- Consumes the records created by `bootstrap_local_publication` and settings `CONTROL_PLANE_BASE_URL`/`CUSTOMER_APP_BASE_URL`.
- Produces `python manage.py local_access_info`, which prints URLs, usernames, tenant slug and the current six-digit TOTP token but never prints passwords or the seed.

- [ ] **Step 1: Write failing access-info tests**

Add tests that run the bootstrap and then:

```python
output = StringIO()
call_command('local_access_info', stdout=output)
rendered = output.getvalue()
assert 'http://control.localhost:4127/platform/' in rendered
assert 'http://erp.localhost:4127/app/' in rendered
assert self.env['LOCAL_CONTROL_EMAIL'] in rendered
assert self.env['LOCAL_ERP_EMAIL'] in rendered
assert self.env['LOCAL_TENANT_SLUG'] in rendered
assert re.search(r'Código MFA atual: \d{6}', rendered)
assert self.env['LOCAL_CONTROL_PASSWORD'] not in rendered
assert self.env['LOCAL_CONTROL_TOTP_SEED'] not in rendered
```

Add missing-record tests expecting `CommandError` instead of partial information.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" pytest tests/test_local_publication.py -q
```

Expected: FAIL because `local_access_info` does not exist.

- [ ] **Step 3: Implement the read-only command**

Resolve the operator, owner, tenant and confirmed device using the environment identifiers. Generate the current token with the same project-tested API:

```python
token = TOTP(
    device.bin_key, device.step, device.t0, device.digits, device.drift
).token()
current_token = str(token).zfill(device.digits)
```

Append `/platform/` and `/app/` safely to configured base URLs. Clearly label the MFA token as temporary and instruct the user to rerun the command when it expires.

- [ ] **Step 4: Run tests to verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Commit the access-info command**

```bash
git add control_plane/management/commands/local_access_info.py tests/test_local_publication.py
git commit -m "feat: report local access information"
```

---

### Task 3: Nginx and production-shaped local Compose topology

**Files:**
- Create: `deploy/nginx/local.conf`
- Modify: `docker-compose.local.yml`
- Modify: `.env.local.example`
- Modify: `.dockerignore`
- Test: `tests/test_deployment_artifacts.py`

**Interfaces:**
- Consumes `.env.local`, the existing application image and the bootstrap command from Task 1.
- Produces Nginx entrypoint on host port `4127`, internal app port `8000`, and a one-shot `bootstrap` service.

- [ ] **Step 1: Write failing deployment artifact tests**

Extend `tests/test_deployment_artifacts.py` with assertions that:

```python
compose = yaml.safe_load(Path('docker-compose.local.yml').read_text())
services = compose['services']
assert set(('nginx', 'app', 'bootstrap', 'celery_worker', 'celery_beat', 'db', 'redis', 'rabbitmq')) <= services.keys()
assert services['nginx']['ports'] == ['4127:80']
assert 'ports' not in services['app']
for internal in ('db', 'redis', 'rabbitmq'):
    assert 'ports' not in services[internal]
assert services['bootstrap']['command'] == ['python', 'manage.py', 'bootstrap_local_publication']
assert services['bootstrap']['depends_on']['app']['condition'] == 'service_healthy'
```

Also assert the Nginx file contains `proxy_set_header Host $host;`, `proxy_set_header X-Forwarded-Proto $scheme;`, static/media locations, and an HTTP `/health/` proxy.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
pytest tests/test_deployment_artifacts.py -q
```

Expected: FAIL because local Nginx and bootstrap topology are absent.

- [ ] **Step 3: Add Nginx configuration**

Create one server listening on port 80 with:

```nginx
server_name control.localhost erp.localhost localhost 127.0.0.1;
client_max_body_size 50m;
location /static/ { alias /app/staticfiles/; }
location /media/ { alias /app/media/; }
location / {
    proxy_pass http://app:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

- [ ] **Step 4: Reshape `docker-compose.local.yml`**

Make these exact topology changes:

- add `nginx:1.27-alpine`, port `4127:80`, read-only Nginx config, shared static/media volumes and healthcheck;
- remove the app host port and keep `expose: [8000]`;
- add `bootstrap` using the app image, normal image entrypoint, command from the interface, `.env.local`, and `restart: "no"`;
- make Nginx depend on both healthy `app` and successfully completed `bootstrap`;
- retain PostgreSQL 15, Redis 7, RabbitMQ 3, Worker and Beat healthchecks;
- use `${POSTGRES_*}` and `${RABBITMQ_*}` in service credentials instead of literal defaults;
- use named volumes for PostgreSQL and bind mounts for media/static files;
- add `restart: unless-stopped` to long-running services.

- [ ] **Step 5: Harden environment examples and build context**

Update `.env.local.example` to use the two approved hostnames, `DEBUG=False`, placeholder local secrets, all bootstrap variables and no usable credential. Ensure `.dockerignore` still excludes `.env*` but explicitly allows the example with:

```dockerignore
.env*
!.env.example
!.env.local.example
```

- [ ] **Step 6: Validate tests and Compose rendering**

Run:

```bash
pytest tests/test_deployment_artifacts.py -q
docker compose --env-file .env.local.example -f docker-compose.local.yml config --quiet
```

Expected: tests pass and Compose exits 0.

- [ ] **Step 7: Commit Docker topology**

```bash
git add deploy/nginx/local.conf docker-compose.local.yml .env.local.example .dockerignore tests/test_deployment_artifacts.py
git commit -m "feat: add production-shaped local Docker stack"
```

---

### Task 4: Local secret generation and operator workflow

**Files:**
- Create: `scripts/prepare_local_publication.sh`
- Create: `scripts/local_access_info.sh`
- Modify: `tests/test_deployment_artifacts.py`

**Interfaces:**
- Produces ignored `.env.local` from `.env.local.example` without overwriting an existing file unless `--force` is supplied.
- Produces a wrapper that runs `docker compose --env-file .env.local -f docker-compose.local.yml exec app python manage.py local_access_info`.

- [ ] **Step 1: Write failing script contract tests**

Add artifact assertions for executable scripts and shell syntax. Add a subprocess test in a temporary directory that copies the example and runs the preparation script with an overridable `ENV_OUTPUT`, then verifies:

```python
assert env['DEBUG'] == 'False'
assert len(env['SECRET_KEY']) >= 50
assert env['SECRET_KEY'] != 'local-only-change-this-key'
assert env['POSTGRES_PASSWORD'] not in ('', 'rgnfarmasystem')
assert env['RABBITMQ_DEFAULT_PASS'] not in ('', 'rgnfarmasystem')
assert len(env['LOCAL_CONTROL_PASSWORD']) >= 16
assert len(env['LOCAL_ERP_PASSWORD']) >= 16
assert env['LOCAL_CONTROL_EMAIL'] != env['LOCAL_ERP_EMAIL']
```

Assert a second run refuses to overwrite the generated file.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
pytest tests/test_deployment_artifacts.py -q
```

Expected: FAIL because scripts do not exist.

- [ ] **Step 3: Implement secure preparation script**

Use `set -eu`, `umask 077`, `openssl rand` and a temporary file with a cleanup trap. Generate:

- Django `SECRET_KEY`;
- URL-safe 32-byte `DATA_ENCRYPTION_KEYS` value;
- PostgreSQL password;
- RabbitMQ password;
- Control Plane password;
- ERP password;
- local TOTP seed.

Use safe placeholder replacement without logging generated values. Validate dependencies (`docker`, `openssl`) and end by printing only the output path and next command.

- [ ] **Step 4: Implement access-info wrapper**

Use `set -eu`, verify `.env.local` exists and execute the interface command without echoing the environment file.

- [ ] **Step 5: Run script tests and ShellCheck/syntax checks**

Run:

```bash
pytest tests/test_deployment_artifacts.py -q
sh -n scripts/prepare_local_publication.sh scripts/local_access_info.sh
```

If `shellcheck` is installed, also run `shellcheck` on both scripts. Expected: PASS.

- [ ] **Step 6: Commit local workflow scripts**

```bash
git add scripts/prepare_local_publication.sh scripts/local_access_info.sh tests/test_deployment_artifacts.py
git commit -m "feat: automate local publication secrets"
```

---

### Task 5: Documentation and smoke validation

**Files:**
- Create: `docs/local-publication.md`
- Modify: `README.md`
- Modify: `scripts/smoke_local.sh`
- Modify: `tests/test_deployment_artifacts.py`

**Interfaces:**
- Documents and verifies the complete workflow from an empty local environment to authenticated Control Plane and ERP access.

- [ ] **Step 1: Write failing documentation/smoke contracts**

Assert documentation contains the approved URLs and exact commands:

```bash
./scripts/prepare_local_publication.sh
docker compose --env-file .env.local -f docker-compose.local.yml up -d --build
docker compose --env-file .env.local -f docker-compose.local.yml ps
./scripts/local_access_info.sh
docker compose --env-file .env.local -f docker-compose.local.yml logs -f app nginx bootstrap
docker compose --env-file .env.local -f docker-compose.local.yml down
```

Assert the smoke script sends explicit `Host` headers to both local surfaces and checks `/health/`, the Control Plane login redirect/page, and the ERP login redirect/page.

- [ ] **Step 2: Run tests to verify RED**

Run `pytest tests/test_deployment_artifacts.py -q`. Expected: FAIL for missing documentation and host-aware smoke behavior.

- [ ] **Step 3: Write the runbook**

Document prerequisites, first start, service health, access-info retrieval, MFA token expiry, login flows, logs, restart, safe shutdown, backups and explicit destructive reset warning. State that `docker compose down -v` permanently removes PostgreSQL data and must never be part of normal startup.

- [ ] **Step 4: Update README and smoke script**

Add a short README link to the runbook. Make `scripts/smoke_local.sh` test both host boundaries through `http://127.0.0.1:4127` with `Host: control.localhost` and `Host: erp.localhost`, so validation does not depend on resolver behavior.

- [ ] **Step 5: Run artifact tests**

Run `pytest tests/test_deployment_artifacts.py -q`. Expected: PASS.

- [ ] **Step 6: Commit documentation and smoke flow**

```bash
git add docs/local-publication.md README.md scripts/smoke_local.sh tests/test_deployment_artifacts.py
git commit -m "docs: add local publication runbook"
```

---

### Task 6: Build, provision and verify the actual local environment

**Files:**
- Runtime-only: `.env.local` (ignored)
- Runtime-only: Docker volumes and containers
- Verify: all files modified in Tasks 1–5 plus the existing dashboard fix

**Interfaces:**
- Produces the running environment and final user-facing URLs/credentials.

- [ ] **Step 1: Verify repository state and preserve unrelated work**

Run `git status --short` and confirm the pre-existing dashboard files remain present and are not overwritten. Run `git diff --check`.

- [ ] **Step 2: Generate effective local secrets**

Run:

```bash
./scripts/prepare_local_publication.sh
```

If `.env.local` already exists, inspect its variable names without printing values and merge only missing variables; do not use `--force` without explicit authorization.

- [ ] **Step 3: Run code-level verification**

Run:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" pytest tests/test_local_publication.py tests/test_deployment_artifacts.py tests/test_control_plane.py tests/test_tenant_module_access.py tests/test_dashboard_hub.py -q
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test python manage.py check
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test python manage.py makemigrations --check --dry-run
```

Expected: all targeted tests pass, system check reports no issues and no model changes are detected.

- [ ] **Step 4: Render and build Compose**

Run:

```bash
docker compose --env-file .env.local -f docker-compose.local.yml config --quiet
docker compose --env-file .env.local -f docker-compose.local.yml build
```

Expected: both exit 0.

- [ ] **Step 5: Start without deleting volumes**

Run:

```bash
docker compose --env-file .env.local -f docker-compose.local.yml up -d
docker compose --env-file .env.local -f docker-compose.local.yml ps
```

Wait for Nginx, app, PostgreSQL, Redis and RabbitMQ to report healthy, bootstrap to exit 0, and both Celery services to remain running.

- [ ] **Step 6: Verify PostgreSQL and provisioned records**

Run read-only checks through Django:

```bash
docker compose --env-file .env.local -f docker-compose.local.yml exec app python manage.py shell -c "from django.db import connection; print(connection.vendor)"
docker compose --env-file .env.local -f docker-compose.local.yml exec app python manage.py shell -c "from governance.models import TenantModuleSetting; from tenants.models import Tenant; t=Tenant.objects.get(slug='rgn-farma-local'); print(t.is_active, t.module_contract_enforced, TenantModuleSetting.objects.filter(tenant=t, is_enabled=True, status='active').count(), len(TenantModuleSetting.Module.values))"
```

Expected: vendor `postgresql`, tenant flags `True True`, and equal enabled/known module counts.

- [ ] **Step 7: Run host-aware smoke tests**

Run:

```bash
./scripts/smoke_local.sh
```

Then verify login POST behavior for both users using a temporary cookie jar, CSRF token and a fresh MFA token from `./scripts/local_access_info.sh`. Do not place passwords in shell history or command arguments; read them interactively or from the protected environment inside a purpose-built Python verification process.

Expected: Control Plane reaches MFA verification and then `/platform/`; ERP reaches `/app/` with the tenant available.

- [ ] **Step 8: Collect final access information safely**

Run `./scripts/local_access_info.sh` for URLs, emails, tenant and current MFA code. Read only `LOCAL_CONTROL_PASSWORD` and `LOCAL_ERP_PASSWORD` from the protected `.env.local` for the final response; do not include infrastructure passwords, encryption keys, Django secret or TOTP seed.

- [ ] **Step 9: Final verification and handoff**

Run:

```bash
docker compose --env-file .env.local -f docker-compose.local.yml ps
git diff --check
git status --short
```

Report service health, test counts, PostgreSQL confirmation, all-modules count, URLs, Control Plane email/password/current MFA code, ERP email/password and tenant slug. Mention that the MFA code expires and `./scripts/local_access_info.sh` generates a fresh one.
