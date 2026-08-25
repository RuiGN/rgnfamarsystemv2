# Sprint 1 Control Plane Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converter o runtime para domínio único, preservar as evidências legadas e restaurar o Django Admin padrão.

**Architecture:** Uma migration em `control_plane` copia os dois models legados para `GovernanceAuditLog` e só então exclui suas tabelas; uma migration posterior remove `User.is_platform_operator`. O app permanece instalado somente para carregar seu grafo histórico, sem URLs, models funcionais, middleware ou templates.

**Tech Stack:** Django migrations, PostgreSQL JSONB, Django Auth/Admin e pytest-django.

## Global Constraints

- Preservar `legacy_source`, `legacy_id`, ator, alvo, timestamps e todos os campos da sessão em `safe_context` sanitizado.
- A cópia deve ser idempotente e reversível no limite dos dados preservados.
- `/platform/` deve retornar `404`; `/admin/` deve seguir o comportamento padrão do Django.
- Remover django-otp e todas as variáveis `CONTROL_PLANE_*`, sem remover migrations históricas.
- Manter login por nome de usuário e redirecionamento local seguro para `/app/`.

---

### Task 1: Especificar a migration de preservação de evidências

**Files:**
- Create: `tests/test_control_plane_removal_migrations.py`
- Create: `control_plane/migrations/0005_preserve_evidence_and_delete_runtime_models.py`
- Create: `accounts/migrations/0012_remove_user_is_platform_operator.py`

**Interfaces:**
- Consumes: `control_plane.PlatformAuditEvent`, `control_plane.SupportSession`, `governance.GovernanceAuditLog` e `accounts.User` nos estados históricos.
- Produces: logs com `safe_context.legacy_source` e `safe_context.legacy_id`; estado final sem os dois models e sem `User.is_platform_operator`.

- [ ] **Step 1: escrever o teste vermelho de ida e volta**

Criar um teste `transaction=True` com `MigrationExecutor`: migrar para `control_plane.0004`, `governance.0006` e `accounts.0011`; criar um evento e uma sessão contendo todos os timestamps/atores; migrar para `control_plane.0005` e `accounts.0012`; verificar duas linhas em `GovernanceAuditLog`, timestamps preservados, campos legados sanitizados e ausência dos três artefatos no estado final. Reexecutar `copy_legacy_evidence()` diretamente e confirmar que a contagem não muda. Reverter aos alvos antigos e confirmar a reidratação.

```python
@pytest.mark.django_db(transaction=True)
def test_control_plane_evidence_is_preserved_before_models_are_removed():
    executor = MigrationExecutor(connection)
    old_targets = [
        ('control_plane', '0004_remove_platformauditevent_tenant_and_more'),
        ('governance', '0006_delete_tenantmodulesetting'),
        ('accounts', '0011_update_platform_operator_help'),
    ]
    executor.migrate(old_targets)
    old_apps = executor.loader.project_state(old_targets).apps
    User = old_apps.get_model('accounts', 'User')
    Event = old_apps.get_model('control_plane', 'PlatformAuditEvent')
    Session = old_apps.get_model('control_plane', 'SupportSession')
    operator = User.objects.create(
        username='Operador legado', email='legacy@example.com', password='!'
    )
    event = Event.objects.create(
        actor_id=operator.pk,
        action='platform.legacy',
        target_model='Record',
        target_record_id='42',
        message='Evidência histórica.',
        metadata={'ticket': 'SUP-42'},
        ip_address='192.0.2.10',
        user_agent='pytest',
        request_id='req-42',
    )
    support = Session.objects.create(
        operator_id=operator.pk,
        access_mode='read',
        status='ended',
        reason='Diagnóstico SUP-42.',
        duration_minutes=30,
        ended_at=timezone.now(),
    )
    assert event.pk and support.pk

    new_targets = [
        ('control_plane', '0005_preserve_evidence_and_delete_runtime_models'),
        ('accounts', '0012_remove_user_is_platform_operator'),
    ]
    executor.loader.build_graph()
    executor.migrate(new_targets)
    new_apps = executor.loader.project_state(new_targets).apps
    Log = new_apps.get_model('governance', 'GovernanceAuditLog')
    assert Log.objects.filter(safe_context__legacy_source='PlatformAuditEvent').count() == 1
    assert Log.objects.filter(safe_context__legacy_source='SupportSession').count() == 1
    with pytest.raises(LookupError):
        new_apps.get_model('control_plane', 'PlatformAuditEvent')
    assert 'is_platform_operator' not in {
        field.name for field in new_apps.get_model('accounts', 'User')._meta.fields
    }
```

- [ ] **Step 2: executar o teste e confirmar a falha esperada**

Run: `./scripts/test.sh tests/test_control_plane_removal_migrations.py -q`

Expected: FAIL porque as migrations `0005` e `0012` ainda não existem.

- [ ] **Step 3: implementar a migration de evidência**

Em `0005`, definir `copy_legacy_evidence(apps, schema_editor)` e `restore_legacy_evidence(apps, schema_editor)`. Usar `apps.get_model`, `transaction.atomic()`, `sanitize_safe_context`, `module='governance'`, `log_type='security'`, severidade `info` e `occurred_at` original. Para cada linha, usar `get_or_create(safe_context__legacy_source=..., safe_context__legacy_id=...)`; após a cópia, comparar IDs fonte com IDs contidos nos logs e lançar `RuntimeError` se houver diferença. As operações devem estar nesta ordem:

```python
operations = [
    migrations.RunPython(copy_legacy_evidence, restore_legacy_evidence),
    migrations.DeleteModel(name='SupportSession'),
    migrations.DeleteModel(name='PlatformAuditEvent'),
]
```

O contexto de `PlatformAuditEvent` inclui `metadata`, `ip_address`, `user_agent` e `request_id`. O contexto de `SupportSession` inclui os IDs de `operator`, `approved_by`, `denied_by` e `revoked_by`, `access_mode`, `status`, `reason`, `duration_minutes` e todos os campos temporais. O reverse recria registros somente quando o `legacy_id` ainda não existir.

Em `accounts.0012`, depender de `accounts.0011` e `control_plane.0005` e usar `migrations.RemoveField(model_name='user', name='is_platform_operator')`.

- [ ] **Step 4: executar testes de migration e schema**

Run: `./scripts/test.sh tests/test_control_plane_removal_migrations.py tests/test_accounts_migrations.py tests/test_single_instance_schema.py -q`

Expected: PASS; PostgreSQL não contém tabelas funcionais do Control Plane nem a coluna removida.

- [ ] **Step 5: commit da migration**

```bash
git add control_plane/migrations/0005_preserve_evidence_and_delete_runtime_models.py accounts/migrations/0012_remove_user_is_platform_operator.py tests/test_control_plane_removal_migrations.py
git commit -m "test: specify control-plane evidence migration"
```

### Task 2: Remover autenticação e administração paralelas

**Files:**
- Modify: `accounts/models.py`
- Modify: `accounts/views.py`
- Modify: `accounts/admin.py`
- Modify: `core/settings/base.py`
- Modify: `core/settings.py`
- Modify: `core/settings/production.py`
- Modify: `core/urls.py`
- Modify: `core/views.py`
- Modify: `core/middleware.py`
- Modify: `core/product_acceptance.py`
- Delete: `core/admin_apps.py`
- Modify: `docker-compose.local.yml`
- Delete: `scripts/prepare_local_publication.sh`
- Delete: `scripts/local_access_info.sh`
- Modify: `templates/base.html`
- Delete: `templates/control_plane/audit_list.html`
- Delete: `templates/control_plane/base.html`
- Delete: `templates/control_plane/index.html`
- Delete: `templates/control_plane/mfa_setup.html`
- Delete: `templates/control_plane/mfa_verify.html`
- Delete: `templates/control_plane/support_activate.html`
- Delete: `templates/control_plane/support_form.html`
- Delete: `templates/control_plane/support_list.html`
- Modify: `requirements.txt`
- Create: `tests/test_single_instance_admin_runtime.py`
- Modify: `tests/test_product_acceptance.py`
- Modify: `tests/test_local_compose_contract.py`
- Delete: `tests/test_control_plane.py`
- Delete: `tests/test_control_plane_onboarding.py`
- Delete: `tests/test_local_publication.py`
- Delete: `tests/test_support_sessions.py`

**Interfaces:**
- Consumes: Django `AdminConfig`, `LoginView`, `is_staff` e `is_active`.
- Produces: `/accounts/login/`, `/app/`, `/admin/` e `/platform/` sem dependência de operador/MFA/suporte.

- [ ] **Step 1: escrever testes vermelhos de runtime**

```python
class SingleInstanceAdminRuntimeTests(TestCase):
    def test_platform_route_is_gone(self):
        assert self.client.get('/platform/').status_code == 404

    def test_admin_uses_standard_staff_boundary(self):
        staff = User.objects.create_user('Staff', 'staff@example.com', 'Secret123!', is_staff=True)
        ordinary = User.objects.create_user('Ordinary', 'user@example.com', 'Secret123!')
        self.client.force_login(staff)
        assert self.client.get('/admin/').status_code == 200
        self.client.force_login(ordinary)
        assert self.client.get('/admin/').status_code == 302

    def test_settings_have_no_control_plane_runtime(self):
        serialized = repr((settings.INSTALLED_APPS, settings.MIDDLEWARE, vars(settings)))
        assert 'django_otp' not in serialized
        assert 'ControlPlaneHostMiddleware' not in serialized
        assert not any(name.startswith('CONTROL_PLANE_') for name in dir(settings))
```

Também testar login válido com `next=/admin/`, `next=https://evil.example/` e ausência de ramificação de operador; o primeiro preserva o caminho local, o segundo redireciona para `/app/`.

- [ ] **Step 2: executar o teste e confirmar falhas**

Run: `./scripts/test.sh tests/test_single_instance_admin_runtime.py -q`

Expected: FAIL para `/platform/`, Admin, OTP e campo legado.

- [ ] **Step 3: implementar o runtime mínimo**

Trocar `core.admin_apps.PlatformAdminConfig` por `django.contrib.admin`, remover apps/middleware/configurações OTP e `CONTROL_PLANE_*` dos dois settings vigentes, remover a validação da URL de controle em produção e remover o include `/platform/`. Renomear `PLATFORM_LOGIN_MAX_ATTEMPTS`/`PLATFORM_LOGIN_WINDOW_SECONDS` para `LOGIN_MAX_ATTEMPTS`/`LOGIN_WINDOW_SECONDS` em settings, view e exemplos de ambiente. Excluir as três classes de middleware. Simplificar `UsernameLoginView.form_valid()` para `return super().form_valid(form)` e manter o rate limit existente; remover imports de `django_otp` e `control_plane`. Remover o campo do model e do `UserAdmin`. `core.views.home()` passa a decidir somente entre login e dashboard, sem inspecionar host. Remover o banner `request.support_session` de `templates/base.html` e ajustar `<html lang="pt-BR">` e `aria-label="Navegação principal"`.

- [ ] **Step 4: remover módulos funcionais do pacote tombstone**

Excluir `control_plane/access.py`, `admin_site.py`, `forms.py`, `models.py`, `services.py`, `tasks.py`, `urls.py`, `views.py` e os três commands. Manter apenas `__init__.py`, `apps.py`, `migrations/__init__.py` e migrations. `ControlPlaneConfig` deve usar `verbose_name = 'Histórico do Control Plane'` e não importar runtime.

- [ ] **Step 5: remover o bootstrap local de duas identidades**

Remover o serviço `bootstrap` de `docker-compose.local.yml` e os scripts que geravam operador/TOTP. Atualizar `tests/test_local_compose_contract.py` para exigir somente app, PostgreSQL, Redis, RabbitMQ, worker e beat; o provisionamento local passa a usar `manage.py createsuperuser`. Em `core.product_acceptance`, substituir a leitura de `templates/control_plane/base.html` por verificações de `admin.site`, rota `/admin/` e ausência do link no sidebar operacional. Excluir `tests/test_local_publication.py` e manter cobertura equivalente de compose/admin nos testes atualizados.

- [ ] **Step 6: validar autenticação, Admin e aceite de produto**

Run: `./scripts/test.sh tests/test_single_instance_admin_runtime.py tests/test_single_instance_auth_access.py tests/test_admin_security.py tests/test_settings_profiles.py tests/test_local_compose_contract.py tests/test_product_acceptance.py -q`

Expected: PASS.

- [ ] **Step 7: validar migrations e imports órfãos**

Run: `.venv/bin/ruff check accounts core control_plane tests/test_single_instance_admin_runtime.py`

Run: `rg -n "control_plane|CONTROL_PLANE|PLATFORM_LOGIN_|is_platform_operator|django_otp|OTP_|support_session" accounts core templates scripts docker-compose.local.yml requirements.txt --glob '!**/migrations/**'`

Expected: Ruff PASS e `rg` sem resultados de runtime.

- [ ] **Step 8: commit do runtime**

```bash
git add accounts core control_plane templates requirements.txt tests
git commit -m "feat: remove control-plane runtime"
```

### Task 3: Gate da Sprint 1

**Files:**
- Test: `tests/test_single_instance_admin_runtime.py`
- Test: `tests/test_control_plane_removal_migrations.py`
- Test: `tests/test_single_instance_schema.py`

**Interfaces:**
- Produces: baseline single-domain consumida pela Sprint 2.

- [ ] **Step 1: verificar código e migrations**

Run: `TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py check --settings=core.settings.test`

Run: `TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py makemigrations --check --dry-run --settings=core.settings.test`

Expected: zero problemas e `No changes detected`.

- [ ] **Step 2: executar o gate da sprint**

Run: `./scripts/test.sh tests/test_accounts_migrations.py tests/test_admin_security.py tests/test_settings_profiles.py tests/test_single_instance_admin_runtime.py tests/test_control_plane_removal_migrations.py tests/test_single_instance_auth_access.py tests/test_single_instance_runtime.py tests/test_single_instance_schema.py -q`

Expected: todos PASS.

- [ ] **Step 3: verificar diff e registrar evidência**

Run: `git diff --check && git status --short`

Expected: sem erro de whitespace e sem mudanças fora do escopo da sprint, exceto as duas alterações preexistentes reservadas para a Sprint 4.
