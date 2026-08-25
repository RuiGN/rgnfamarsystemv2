# Username Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Autenticar ERP, Control Plane e Django Admin pelo nome completo único cadastrado em `username`, disponibilizando o PostgreSQL local com todas as migrations aplicadas.

**Architecture:** O modelo customizado continuará baseado em `AbstractUser`, mas `username` voltará a ser o identificador obrigatório do Django e `email` permanecerá contato único. A normalização ficará centralizada no modelo/manager, a unicidade sem distinção de caixa será protegida por restrição funcional, e uma migration preencherá deterministicamente usuários legados antes de endurecer o schema.

**Tech Stack:** Python, Django, PostgreSQL 15, Docker Compose, pytest-django, Bootstrap 5.

## Global Constraints

- O nome completo de acesso é cadastrado no Django Admin, por exemplo `João Silva`.
- Nomes equivalentes por maiúsculas/minúsculas são proibidos.
- E-mail continua obrigatório e único, mas não autentica.
- IDs, senhas, permissões, tenants, memberships e dados existentes devem ser preservados.
- Não apagar volumes ou bancos existentes.
- A alteração local preexistente em `base/ui/forms.py` não pertence a esta implementação e deve ser preservada.

---

### Task 1: Contrato do modelo e gerenciador de usuários

**Files:**
- Modify: `tests/test_foundation.py`
- Modify: `accounts/models.py`

**Interfaces:**
- Produces: `normalize_login_name(value: str) -> str`
- Produces: `UserManager.create_user(username, email, password=None, **extra_fields)`
- Produces: `User.USERNAME_FIELD == 'username'`

- [ ] **Step 1: Escrever testes que falham para autenticação e normalização**

```python
def test_user_authenticates_with_full_name_as_username_field(self):
    assert User.USERNAME_FIELD == 'username'
    user = User.objects.create_user(
        username='  João   Silva  ', email='joao@example.com', password='S3curePass!123'
    )
    assert user.username == 'João Silva'
    assert authenticate(username='João Silva', password='S3curePass!123') == user

def test_user_rejects_case_insensitive_duplicate_username(self):
    User.objects.create_user(username='João Silva', email='joao1@example.com')
    with pytest.raises(IntegrityError):
        User.objects.create_user(username='joão silva', email='joao2@example.com')
```

- [ ] **Step 2: Executar os testes e confirmar RED**

Run: `./scripts/test.sh tests/test_foundation.py -q`

Expected: falha porque `USERNAME_FIELD` ainda é `email` e `username` não é normalizado/protegido.

- [ ] **Step 3: Implementar o contrato mínimo no modelo**

```python
def normalize_login_name(value):
    return ' '.join(str(value or '').split())

class UserManager(BaseUserManager):
    def _create_user(self, username, email, password, **extra_fields):
        username = normalize_login_name(username)
        if not username:
            raise ValueError('O nome do usuário é obrigatório.')
        if not email:
            raise ValueError('O email é obrigatório.')
        user = self.model(username=username, email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

class User(AbstractUser):
    username = models.CharField('nome do usuário', max_length=150, unique=True)
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']
```

Adicionar `UniqueConstraint(Lower('username'), name='accounts_user_username_ci_unique')` e normalizar `username` em `clean()`/`save()` para que Admin, manager e ORM persistam a mesma forma canônica de espaços.

- [ ] **Step 4: Executar testes focados e confirmar GREEN**

Run: `./scripts/test.sh tests/test_foundation.py -q`

Expected: todos os testes de foundation passam.

- [ ] **Step 5: Commit**

```bash
git add accounts/models.py tests/test_foundation.py
git commit -m "feat: authenticate users by unique full name"
```

### Task 2: Migration segura de usuários legados

**Files:**
- Create: `accounts/migrations/0006_username_login.py`
- Create: `tests/test_accounts_migrations.py`

**Interfaces:**
- Consumes: normalização e schema definidos na Task 1.
- Produces: função de migration `populate_usernames(apps, schema_editor)` e schema não nulo/único.

- [ ] **Step 1: Escrever teste de migration que falha**

```python
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_migration_populates_unique_deterministic_usernames():
    executor = MigrationExecutor(connection)
    old_target = ('accounts', '0005_tenantmembershipinvitation_unique_pending_tenant_invitation_and_more')
    executor.migrate([old_target])
    old_apps = executor.loader.project_state([old_target]).apps
    OldUser = old_apps.get_model('accounts', 'User')
    first = OldUser.objects.create(email='joao@example.com', first_name='João', last_name='Silva')
    second = OldUser.objects.create(email='outro@example.com', first_name='João', last_name='Silva')
    third = OldUser.objects.create(email='maria.souza@example.com')
    new_target = ('accounts', '0006_username_login')
    executor.loader.build_graph()
    executor.migrate([new_target])
    new_apps = executor.loader.project_state([new_target]).apps
    NewUser = new_apps.get_model('accounts', 'User')
    assert NewUser.objects.get(pk=first.pk).username == 'João Silva'
    assert NewUser.objects.get(pk=second.pk).username == 'João Silva 2'
    assert NewUser.objects.get(pk=third.pk).username == 'Maria Souza'
```

- [ ] **Step 2: Executar e confirmar RED**

Run: `./scripts/test.sh tests/test_accounts_migrations.py -q`

Expected: falha porque a migration `0006_username_login` não existe.

- [ ] **Step 3: Criar migration em fases**

Implementar operações nesta ordem: manter campo temporariamente permissivo; `RunPython` que usa `first_name + last_name`, depois prefixo de e-mail convertido de `.`, `_` e `-` para espaços, aplica title case e acrescenta sufixo numérico por comparação `casefold()`; alterar `username` para obrigatório e único; adicionar `UniqueConstraint(Lower('username'), ...)`. A reversão de dados deve ser noop para não apagar nomes.

- [ ] **Step 4: Confirmar migration e schema**

Run: `./scripts/test.sh tests/test_accounts_migrations.py -q`

Run: `TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py makemigrations --check --settings=core.settings.test`

Expected: teste passa e `No changes detected`.

- [ ] **Step 5: Commit**

```bash
git add accounts/migrations/0006_username_login.py tests/test_accounts_migrations.py
git commit -m "feat: migrate existing users to unique login names"
```

### Task 3: Formulários, telas e Django Admin

**Files:**
- Modify: `accounts/admin.py`
- Modify: `accounts/views.py`
- Modify: `accounts/urls.py`
- Modify: `control_plane/forms.py`
- Modify: `templates/registration/login.html`
- Modify: `templates/control_plane/login.html`
- Modify: `tests/test_auth_tenant_access.py`
- Modify: `tests/test_control_plane.py`
- Modify: `tests/test_admin_security.py`

**Interfaces:**
- Consumes: `User.USERNAME_FIELD = 'username'`.
- Produces: `UsernameLoginView`, rótulo “Nome do usuário” e Admin obrigatório.

- [ ] **Step 1: Escrever testes de interface e login que falham**

```python
def test_login_view_accepts_username_and_rejects_email(self):
    User.objects.create_user(
        username='João Silva', email='qa@example.com', password='S3curePass!123'
    )
    accepted = self.client.post('/accounts/login/', {'username': 'João Silva', 'password': 'S3curePass!123'})
    assert accepted.status_code == 302
    self.client.logout()
    rejected = self.client.post('/accounts/login/', {'username': 'qa@example.com', 'password': 'S3curePass!123'})
    assert rejected.status_code == 200

def test_login_page_labels_username(self):
    response = self.client.get('/accounts/login/')
    assert 'Nome do usuário' in response.content.decode()
    assert 'autocomplete="username"' in response.content.decode()
```

Adicionar equivalentes para `/platform/login/` e assertions do formulário de criação do Admin.

- [ ] **Step 2: Executar e confirmar RED**

Run: `./scripts/test.sh tests/test_auth_tenant_access.py tests/test_control_plane.py tests/test_admin_security.py -q`

Expected: falha no nome da view, rótulos/atributos e campos do Admin.

- [ ] **Step 3: Implementar interfaces**

Renomear `EmailLoginView` para `UsernameLoginView`; atualizar URL; configurar o widget `AuthenticationForm.username` com `autocomplete='username'`, `autofocus=True` e classe Bootstrap; trocar ambos os rótulos para “Nome do usuário”. Em `CustomUserAdmin`, usar `ordering=('username',)`, incluir `username` em `list_display`, `search_fields`, `fieldsets` e `add_fieldsets`, mantendo e-mail visível e obrigatório.

- [ ] **Step 4: Executar e confirmar GREEN**

Run: `./scripts/test.sh tests/test_auth_tenant_access.py tests/test_control_plane.py tests/test_admin_security.py -q`

Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add accounts/admin.py accounts/views.py accounts/urls.py control_plane/forms.py templates/registration/login.html templates/control_plane/login.html tests/test_auth_tenant_access.py tests/test_control_plane.py tests/test_admin_security.py
git commit -m "feat: expose username login across authentication screens"
```

### Task 4: Compatibilidade de criação, seeds e documentação

**Files:**
- Modify: `governance/demo_seeders.py`
- Modify: `tests/` (chamadas de `create_user` e `create_superuser` afetadas)
- Modify: `templates/dashboard/home.html`
- Modify: `templates/base.html`
- Modify: `docs/architecture/foundation.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: manager que exige `username`.
- Produces: todos os criadores passam nomes determinísticos e toda cópia descreve login por nome.

- [ ] **Step 1: Executar a suíte para enumerar criadores incompatíveis**

Run: `./scripts/test.sh -q -x`

Expected: primeiro erro informa ausência do argumento obrigatório `username`.

- [ ] **Step 2: Atualizar criadores de produção e testes**

Em seeds, fornecer nomes humanos explícitos. Nos factories/helpers de testes, gerar nomes determinísticos a partir do e-mail, garantindo unicidade por caso. Nas chamadas isoladas, passar `username='Nome descritivo único'`. Não relaxar o manager para aceitar usuário sem nome.

- [ ] **Step 3: Atualizar cópia e documentação**

Trocar “Login por email” por “Login por nome de usuário”, exibir `request.user.username` onde a identificação principal é mostrada e documentar que e-mail não autentica.

- [ ] **Step 4: Executar suíte completa**

Run: `./scripts/test.sh -q`

Expected: toda a suíte passa com cobertura igual ou superior ao gate do repositório.

- [ ] **Step 5: Commit**

```bash
git add governance/demo_seeders.py tests templates/dashboard/home.html templates/base.html docs/architecture/foundation.md README.md
git commit -m "test: align user fixtures with username authentication"
```

### Task 5: Criar PostgreSQL local, migrar e verificar entrega

**Files:**
- Modify only if evidence requires: `README.md`

**Interfaces:**
- Consumes: `.env.local`, `docker-compose.local.yml`, migrations completas.
- Produces: banco local saudável, schema migrado e evidência de ausência de pendências.

- [ ] **Step 1: Validar configuração sem revelar segredos**

Run: `docker compose --env-file .env.local -f docker-compose.local.yml config --quiet`

Expected: código 0.

- [ ] **Step 2: Criar/iniciar o PostgreSQL sem apagar volumes**

Run: `docker compose --env-file .env.local -f docker-compose.local.yml up -d db`

Run: `docker compose --env-file .env.local -f docker-compose.local.yml exec -T db pg_isready -U rgnfarmasystem -d rgnfarmasystem`

Expected: `accepting connections`.

- [ ] **Step 3: Aplicar migrations**

Run: `docker compose --env-file .env.local -f docker-compose.local.yml run --rm --no-deps app python manage.py migrate --noinput`

Expected: todas as migrations aplicadas sem erro.

- [ ] **Step 4: Verificar schema e quality gate**

Run: `docker compose --env-file .env.local -f docker-compose.local.yml run --rm --no-deps app python manage.py showmigrations --plan`

Run: `./scripts/quality_gate.sh`

Expected: todas as migrations marcadas `[X]`; lint, format, mypy, Bandit, audit, testes, OpenAPI e checks passam.

- [ ] **Step 5: Verificar estado final e commit documental, se necessário**

Run: `git status --short && git diff --check`

Expected: apenas alterações desta implementação e a alteração preexistente preservada em `base/ui/forms.py`; nenhum erro de whitespace nas alterações da implementação.

Se a operação local exigir documentação adicional:

```bash
git add README.md
git commit -m "docs: document username login and migrated local database"
```
