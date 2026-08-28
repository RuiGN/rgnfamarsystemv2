# Sidebar Workspace Navigation Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer sidebar e cabeçalho renderizarem somente workspaces autorizados a partir de `WorkspaceConfig`, com agrupamento semântico e estado acessível.

**Architecture:** `WorkspaceConfig` passa a concentrar metadados e URL de navegação. O context processor cruza os workspaces com os módulos visíveis e entrega uma tupla autorizada aos templates; sidebar e cabeçalho apenas iteram essa coleção. A `WorkspaceView` continua sendo a fronteira defensiva para acessos diretos.

**Tech Stack:** Python 3.13+, Django 6, Django Templates, Bootstrap 5/Duralux, pytest-django.

## Global Constraints

- Preservar os nomes e caminhos de `app:operations_workspace`, `app:quality_workspace` e `app:workflow_workspace`.
- Não criar migrations nem alterar regras de permissão Django.
- Manter o tema Duralux, o menu responsivo, o modo recolhido e o scroll existentes.
- Aplicar autorização no servidor antes da renderização; ocultar links não substitui a validação da `WorkspaceView`.
- Não alterar a ordem interna dos recursos de cada módulo.
- Executar os testes com `DATABASE_URL=sqlite:///baseline_base.sqlite3`, `TEST_DATABASE_URL=sqlite:///test_db.sqlite3` e `DJANGO_SETTINGS_MODULE=core.settings.test`.
- Preservar alterações locais preexistentes fora dos arquivos listados neste plano.

## File Structure

- Modify: `base/ui/workspaces.py` — metadados imutáveis e URL reversa dos workspaces.
- Modify: `base/ui/context_processors.py` — autorização e contexto único de navegação.
- Modify: `templates/includes/sidebar.html` — grupos Visão geral/Módulos e loop de workspaces.
- Modify: `templates/base.html` — atalhos e sino condicionados à mesma coleção autorizada.
- Modify: `tests/test_workspace_ui.py` — contrato do registro e integração de workspaces no shell.
- Modify: `tests/test_app_ui.py` — permissões, acessibilidade e menu Painéis vazio.
- Modify: `TEMPLATES.md` — contrato para adicionar navegação de novos workspaces.

---

### Task 1: Centralizar metadados de navegação em `WorkspaceConfig`

**Files:**
- Modify: `base/ui/workspaces.py:52-65,269-297`
- Modify: `tests/test_workspace_ui.py:16-52`

**Interfaces:**
- Consumes: nomes de rota Django existentes no namespace `app`.
- Produces: `WorkspaceConfig.route_name: str`, `navigation_label: str`, `icon: str`, `order: int` e `navigation_url: str`.

- [ ] **Step 1: Escrever o teste vermelho do contrato de navegação**

Adicionar a `WorkspaceConfigurationTests`:

```python
def test_workspace_navigation_metadata_and_urls_are_centralized(self):
    expectations = {
        'operations': (
            'app:operations_workspace',
            'Cockpit operacional',
            'feather-activity',
            10,
            '/app/workspaces/operations/',
        ),
        'quality': (
            'app:quality_workspace',
            'Cockpit de qualidade',
            'feather-check-square',
            20,
            '/app/workspaces/quality/',
        ),
        'workflow': (
            'app:workflow_workspace',
            'Central de workflow',
            'feather-git-pull-request',
            30,
            '/app/workspaces/workflow/',
        ),
    }

    for slug, expected in expectations.items():
        with self.subTest(slug=slug):
            workspace = get_workspace(slug)
            actual = (
                workspace.route_name,
                workspace.navigation_label,
                workspace.icon,
                workspace.order,
                workspace.navigation_url,
            )
            self.assertEqual(actual, expected)
```

- [ ] **Step 2: Executar o teste e confirmar falha por atributo ausente**

Run:

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q \
tests/test_workspace_ui.py::WorkspaceConfigurationTests::test_workspace_navigation_metadata_and_urls_are_centralized
```

Expected: FAIL com `AttributeError: 'WorkspaceConfig' object has no attribute 'route_name'`.

- [ ] **Step 3: Implementar os campos e a URL reversa**

Alterar o import e a dataclass em `base/ui/workspaces.py`:

```python
from django.urls import reverse


@dataclass(frozen=True)
class WorkspaceConfig:
    slug: str
    title: str
    description: str
    breadcrumb_label: str
    module_slug: str
    quick_links_title: str
    route_name: str
    navigation_label: str
    icon: str
    order: int
    builder: Callable[[Any], WorkspaceContent]

    @property
    def navigation_url(self) -> str:
        return reverse(self.route_name)

    def build_content(self, request: Any) -> WorkspaceContent:
        return self.builder(request).visible_to(request.user)
```

Completar as três configurações:

```python
'operations': WorkspaceConfig(
    slug='operations',
    title='Cockpit operacional',
    description='Produção, estoque e qualidade em um único contexto.',
    breadcrumb_label='Operação',
    module_slug='production',
    quick_links_title='Acessos rápidos',
    route_name='app:operations_workspace',
    navigation_label='Cockpit operacional',
    icon='feather-activity',
    order=10,
    builder=build_operations_content,
),
'quality': WorkspaceConfig(
    slug='quality',
    title='Cockpit de qualidade',
    description='Amostragem, análises e investigações sob controle.',
    breadcrumb_label='Qualidade',
    module_slug='quality',
    quick_links_title='Fluxos de qualidade',
    route_name='app:quality_workspace',
    navigation_label='Cockpit de qualidade',
    icon='feather-check-square',
    order=20,
    builder=build_quality_content,
),
'workflow': WorkspaceConfig(
    slug='workflow',
    title='Central de workflow',
    description='Aprovações, notificações e processamento assíncrono.',
    breadcrumb_label='Fluxo de trabalho',
    module_slug='workflow',
    quick_links_title='Governança operacional',
    route_name='app:workflow_workspace',
    navigation_label='Central de workflow',
    icon='feather-git-pull-request',
    order=30,
    builder=build_workflow_content,
),
```

- [ ] **Step 4: Executar os testes do registro**

Run:

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_workspace_ui.py::WorkspaceConfigurationTests
```

Expected: PASS em todos os testes da classe.

- [ ] **Step 5: Commitar o contrato centralizado**

```bash
git add base/ui/workspaces.py tests/test_workspace_ui.py
git diff --cached --check
git commit -m "refactor: centralize workspace navigation metadata"
```

---

### Task 2: Entregar somente workspaces autorizados pelo context processor

**Files:**
- Modify: `base/ui/context_processors.py:1-77`
- Modify: `tests/test_workspace_ui.py`

**Interfaces:**
- Consumes: `WORKSPACES: dict[str, WorkspaceConfig]` e `WorkspaceConfig.order`.
- Produces: `sidebar_workspaces: tuple[WorkspaceConfig, ...]`, `show_dashboard_navigation: bool` e `can_view_workflow_workspace: bool`.

- [ ] **Step 1: Escrever testes vermelhos de visibilidade e ordenação**

Adicionar imports:

```python
from unittest.mock import patch

from base.ui.context_processors import sidebar_menu
```

Adicionar a `WorkspaceAccessTests`:

```python
def navigation_context_for(self, user):
    request = RequestFactory().get('/app/')
    request.user = user
    return sidebar_menu(request)

def test_context_exposes_only_authorized_workspaces_in_configured_order(self):
    context = self.navigation_context_for(self.user)
    self.assertEqual(context['sidebar_workspaces'], ())

    grant_view_permission(self.user, ProductionOrder)
    self.user = get_user_model().objects.get(pk=self.user.pk)
    context = self.navigation_context_for(self.user)
    self.assertEqual(
        tuple(workspace.slug for workspace in context['sidebar_workspaces']),
        ('operations',),
    )

    admin_context = self.navigation_context_for(self.admin)
    self.assertEqual(
        tuple(workspace.slug for workspace in admin_context['sidebar_workspaces']),
        ('operations', 'quality', 'workflow'),
    )

def test_notification_query_is_skipped_without_workflow_access(self):
    grant_view_permission(self.user, ProductionOrder)

    with patch(
        'base.ui.context_processors.WorkflowNotification.objects.filter'
    ) as notification_filter:
        context = self.navigation_context_for(self.user)

    notification_filter.assert_not_called()
    self.assertFalse(context['can_view_workflow_workspace'])
    self.assertEqual(context['unread_workflow_notifications'], 0)

def test_anonymous_navigation_context_exposes_safe_empty_defaults(self):
    request = RequestFactory().get('/accounts/login/')
    request.user = AnonymousUser()

    context = sidebar_menu(request)

    self.assertEqual(context['sidebar_workspaces'], ())
    self.assertFalse(context['show_dashboard_navigation'])
    self.assertFalse(context['can_view_workflow_workspace'])
```

Adicionar também:

```python
from django.contrib.auth.models import AnonymousUser, Permission
```

- [ ] **Step 2: Executar e confirmar falhas pelas chaves ausentes**

Run:

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_workspace_ui.py::WorkspaceAccessTests
```

Expected: FAIL com `KeyError: 'sidebar_workspaces'` e chamada indevida da consulta de notificações.

- [ ] **Step 3: Implementar o contexto autorizado**

Adicionar o import:

```python
from base.ui.workspaces import WORKSPACES
```

Substituir `sidebar_menu` por:

```python
def sidebar_menu(request):
    user = getattr(request, 'user', None)
    resolver_match = getattr(request, 'resolver_match', None)
    route_kwargs = getattr(resolver_match, 'kwargs', {}) if resolver_match else {}
    navigation_context = {
        'active_module_slug': route_kwargs.get('module_slug', ''),
        'active_resource_slug': route_kwargs.get('resource_slug', ''),
    }
    brand_context = _institution_brand_context()
    if not getattr(user, 'is_authenticated', False):
        return {
            'sidebar_modules': (),
            'sidebar_workspaces': (),
            'dashboard_navigation': (),
            'show_dashboard_navigation': False,
            'can_view_workflow_workspace': False,
            'sidebar_admin_links': (),
            'unread_workflow_notifications': 0,
            **navigation_context,
            **brand_context,
        }

    modules = get_visible_modules(user)
    visible_module_slugs = {module.slug for module in modules}
    sidebar_workspaces = tuple(
        sorted(
            (
                workspace
                for workspace in WORKSPACES.values()
                if workspace.module_slug in visible_module_slugs
            ),
            key=lambda workspace: workspace.order,
        )
    )
    dashboard_navigation = tuple(
        (slug, label)
        for slug, label, module_slug in DASHBOARD_NAVIGATION
        if module_slug in visible_module_slugs
    )
    can_view_workflow_workspace = any(
        workspace.slug == 'workflow' for workspace in sidebar_workspaces
    )
    unread_notifications = 0
    if can_view_workflow_workspace:
        unread_notifications = WorkflowNotification.objects.filter(
            recipient=user,
            status=WorkflowNotification.Status.UNREAD,
        ).count()

    return {
        'sidebar_modules': modules,
        'sidebar_workspaces': sidebar_workspaces,
        'dashboard_navigation': dashboard_navigation,
        'show_dashboard_navigation': bool(dashboard_navigation),
        'can_view_workflow_workspace': can_view_workflow_workspace,
        'sidebar_admin_links': (),
        'unread_workflow_notifications': unread_notifications,
        **navigation_context,
        **brand_context,
    }
```

- [ ] **Step 4: Executar os testes do context processor**

Run:

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_workspace_ui.py::WorkspaceAccessTests
```

Expected: PASS em todos os testes da classe.

- [ ] **Step 5: Commitar a autorização de navegação**

```bash
git add base/ui/context_processors.py tests/test_workspace_ui.py
git diff --cached --check
git commit -m "fix: filter workspace navigation by permission"
```

---

### Task 3: Renderizar sidebar e cabeçalho a partir do contexto único

**Files:**
- Modify: `templates/includes/sidebar.html:1-63`
- Modify: `templates/base.html:75-94`
- Modify: `tests/test_app_ui.py:498-560,1302-1315`
- Modify: `tests/test_workspace_ui.py`

**Interfaces:**
- Consumes: `sidebar_workspaces`, `show_dashboard_navigation` e `can_view_workflow_workspace` produzidos na Task 2.
- Produces: navegação sem links proibidos, grupos semânticos e `aria-current="page"` no workspace ativo.

- [ ] **Step 1: Escrever testes vermelhos do HTML autorizado**

Adicionar a `WorkspaceAccessTests`:

```python
def test_shell_hides_unauthorized_workspaces_and_workflow_bell(self):
    grant_view_permission(self.user, ProductionOrder)
    self.client.force_login(self.user)

    response = self.client.get(reverse('app:index'))
    navigation = response.content.decode().split('</nav>', 1)[0]

    self.assertContains(response, 'href="/app/workspaces/operations/"')
    self.assertNotIn('href="/app/workspaces/quality/"', navigation)
    self.assertNotIn('href="/app/workspaces/workflow/"', navigation)
    self.assertNotContains(response, 'data-ui="workflow-notifications"')

def test_superuser_sees_workspaces_in_configured_order(self):
    self.client.force_login(self.admin)

    response = self.client.get(reverse('app:index'))
    navigation = response.content.decode().split('</nav>', 1)[0]
    positions = tuple(
        navigation.index(f'href="{get_workspace(slug).navigation_url}"')
        for slug in ('operations', 'quality', 'workflow')
    )

    self.assertEqual(positions, tuple(sorted(positions)))

def test_active_workspace_has_accessible_current_state(self):
    self.client.force_login(self.admin)

    response = self.client.get(reverse('app:operations_workspace'))

    self.assertContains(
        response,
        'href="/app/workspaces/operations/" class="nxl-link" '
        'aria-current="page"',
        html=False,
    )
```

Adicionar a `AppUiPermissionTests`:

```python
def test_dashboard_menu_is_hidden_when_no_dashboard_is_authorized(self):
    self.add_model_perm(Product, 'view')

    response = self.client.get('/app/')
    navigation = response.content.decode().split('</nav>', 1)[0]

    assert '>Painéis<' not in navigation
    assert '>Módulos<' in navigation
```

Atualizar `test_collapsed_sidebar_controls_keep_accessible_names` para verificar o loop:

```python
def test_collapsed_sidebar_controls_keep_accessible_names(self):
    template = Path('templates/includes/sidebar.html').read_text()

    assert 'aria-label="Aplicativos"' in template
    assert 'title="Aplicativos"' in template
    assert 'aria-label="{{ workspace.navigation_label }}"' in template
    assert 'title="{{ workspace.navigation_label }}"' in template
    assert 'aria-label="{{ module.label }}"' in template
    assert 'title="{{ module.label }}"' in template
```

- [ ] **Step 2: Executar e confirmar que links hardcoded quebram os testes**

Run:

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q \
tests/test_workspace_ui.py::WorkspaceAccessTests \
tests/test_app_ui.py::AppUiPermissionTests::test_dashboard_menu_is_hidden_when_no_dashboard_is_authorized \
tests/test_app_ui.py::AppUiSprint43ReadinessTests::test_collapsed_sidebar_controls_keep_accessible_names
```

Expected: FAIL porque qualidade/workflow ainda aparecem, Painéis ainda é renderizado vazio e não existe loop de workspaces.

- [ ] **Step 3: Substituir o sidebar por grupos e loops autorizados**

Usar a seguinte estrutura integral em `templates/includes/sidebar.html`:

```django
<ul class="nxl-navbar">
    <li class="nxl-item nxl-caption"><label>Visão geral</label></li>
    {% if show_dashboard_navigation %}
    <li class="nxl-item nxl-hasmenu{% if request.resolver_match.url_name == 'dashboard_hub' %} active nxl-trigger{% endif %}">
        <a href="javascript:void(0);" class="nxl-link" aria-label="Painéis" title="Painéis" aria-expanded="{% if request.resolver_match.url_name == 'dashboard_hub' %}true{% else %}false{% endif %}">
            <span class="nxl-micon"><i class="feather-bar-chart-2" aria-hidden="true"></i></span>
            <span class="nxl-mtext">Painéis</span>
            <span class="nxl-arrow"><i class="feather-chevron-right" aria-hidden="true"></i></span>
        </a>
        <ul class="nxl-submenu">
            {% for slug, label in dashboard_navigation %}
            <li class="nxl-item"><a href="{% url 'app:dashboard_hub' slug %}" class="nxl-link">{{ label }}</a></li>
            {% endfor %}
        </ul>
    </li>
    {% endif %}
    <li class="nxl-item{% if request.resolver_match.url_name == 'index' %} active{% endif %}">
        <a href="{% url 'app:index' %}" class="nxl-link" aria-label="Aplicativos" title="Aplicativos"{% if request.resolver_match.url_name == 'index' %} aria-current="page"{% endif %}>
            <span class="nxl-micon"><i class="feather-grid" aria-hidden="true"></i></span>
            <span class="nxl-mtext">Aplicativos</span>
        </a>
    </li>
    {% for workspace in sidebar_workspaces %}
    <li class="nxl-item{% if request.resolver_match.view_name == workspace.route_name %} active{% endif %}">
        <a href="{{ workspace.navigation_url }}" class="nxl-link"{% if request.resolver_match.view_name == workspace.route_name %} aria-current="page"{% endif %} aria-label="{{ workspace.navigation_label }}" title="{{ workspace.navigation_label }}">
            <span class="nxl-micon"><i class="{{ workspace.icon }}" aria-hidden="true"></i></span>
            <span class="nxl-mtext">{{ workspace.navigation_label }}</span>
        </a>
    </li>
    {% endfor %}
    {% if sidebar_modules %}
    <li class="nxl-item nxl-caption"><label>Módulos</label></li>
    {% endif %}
    {% for module in sidebar_modules %}
    <li class="nxl-item nxl-menu-group nxl-hasmenu{% if module.slug == active_module_slug %} active nxl-trigger{% endif %}">
        <a href="javascript:void(0);" class="nxl-link" aria-label="{{ module.label }}" title="{{ module.label }}" aria-expanded="{% if module.slug == active_module_slug %}true{% else %}false{% endif %}">
            <span class="nxl-micon"><i class="{{ module.icon }}" aria-hidden="true"></i></span>
            <span class="nxl-mtext">{{ module.label }}</span>
            <span class="nxl-arrow"><i class="feather-chevron-right" aria-hidden="true"></i></span>
        </a>
        <ul class="nxl-submenu">
            <li class="nxl-item{% if module.slug == active_module_slug and not active_resource_slug %} active{% endif %}">
                <a href="{% url 'app:module' module.slug %}" class="nxl-link"{% if module.slug == active_module_slug and not active_resource_slug %} aria-current="page"{% endif %}>Visão geral</a>
            </li>
            {% for resource in module.resources %}
            <li class="nxl-item{% if module.slug == active_module_slug and resource.slug == active_resource_slug %} active{% endif %}">
                <a href="{% url 'app:resource_list' module.slug resource.slug %}" class="nxl-link"{% if module.slug == active_module_slug and resource.slug == active_resource_slug %} aria-current="page"{% endif %}>
                    <span>{{ resource.label }}</span>
                    {% if resource.read_only %}
                        <span class="nxl-subbadge badge bg-primary text-white">Consulta</span>
                    {% endif %}
                </a>
            </li>
            {% endfor %}
        </ul>
    </li>
    {% endfor %}
</ul>
```

- [ ] **Step 4: Tornar atalhos e sino do cabeçalho permission-aware**

Substituir os atalhos da busca em `templates/base.html` por:

```django
{% if sidebar_workspaces %}
<div class="d-flex flex-wrap gap-1">
    {% for workspace in sidebar_workspaces %}
    <a href="{{ workspace.navigation_url }}" class="flex-fill border rounded py-1 px-2 text-center fs-11 fw-semibold">{{ workspace.breadcrumb_label }}</a>
    {% endfor %}
</div>
{% endif %}
```

Substituir o bloco do sino por:

```django
{% if request.user.is_authenticated and can_view_workflow_workspace %}
    <div class="dropdown nxl-h-item">
        <a href="{% url 'app:workflow_workspace' %}" class="nxl-head-link me-3 position-relative" data-ui="workflow-notifications" title="Central de workflow" aria-label="Central de workflow">
            <i class="feather-bell"></i>
            {% if unread_workflow_notifications %}
                <span class="badge bg-danger nxl-h-badge">{{ unread_workflow_notifications }}</span>
            {% endif %}
        </a>
    </div>
{% endif %}
```

- [ ] **Step 5: Executar os testes de integração do shell**

Run:

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q \
tests/test_workspace_ui.py \
tests/test_app_ui.py::AppUiPermissionTests \
tests/test_app_ui.py::AppUiSprint43ReadinessTests::test_collapsed_sidebar_controls_keep_accessible_names
```

Expected: PASS em todos os testes selecionados.

- [ ] **Step 6: Commitar a apresentação compartilhada**

```bash
git add templates/includes/sidebar.html templates/base.html tests/test_workspace_ui.py tests/test_app_ui.py
git diff --cached --check
git commit -m "refactor: render authorized workspaces in application shell"
```

---

### Task 4: Documentar e verificar o contrato completo

**Files:**
- Modify: `TEMPLATES.md:8-30`
- Modify: `tests/test_workspace_ui.py`

**Interfaces:**
- Consumes: `WorkspaceConfig` com metadados de navegação e `sidebar_workspaces` autorizado.
- Produces: documentação operacional e evidência final de compatibilidade.

- [ ] **Step 1: Escrever o teste vermelho da documentação**

Adicionar a `WorkspaceConfigurationTests`:

```python
def test_workspace_navigation_contract_is_documented(self):
    from pathlib import Path

    documentation = Path('TEMPLATES.md').read_text()

    self.assertIn('sidebar_workspaces', documentation)
    self.assertIn('route_name', documentation)
    self.assertIn('navigation_label', documentation)
    self.assertIn('links não autorizados', documentation)
```

- [ ] **Step 2: Executar e confirmar falha por documentação ausente**

Run:

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q \
tests/test_workspace_ui.py::WorkspaceConfigurationTests::test_workspace_navigation_contract_is_documented
```

Expected: FAIL porque `TEMPLATES.md` ainda não descreve `sidebar_workspaces`.

- [ ] **Step 3: Atualizar a documentação operacional**

Adicionar após a seção “Página inicial e workspaces” em `TEMPLATES.md`:

```markdown
### Navegação de workspaces

`WorkspaceConfig` é também a fonte de verdade para o sidebar e os atalhos do
cabeçalho. Todo workspace navegável declara `route_name`, `navigation_label`,
`icon` e `order`. O context processor publica somente configurações autorizadas
em `sidebar_workspaces`; os templates não mantêm listas paralelas nem exibem
links não autorizados.

Ao adicionar um workspace, registre esses metadados, associe um `module_slug`
válido e cubra: URL reversa, ordenação, visibilidade por permissão, estado
`aria-current` e ausência do item para perfis sem acesso.
```

- [ ] **Step 4: Executar a suíte relevante completa**

Run:

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q \
tests/test_home_navigation.py \
tests/test_workspace_ui.py \
tests/test_dashboard_hub.py \
tests/test_app_ui.py \
tests/test_responsive_layout_css.py
```

Expected: PASS sem falhas.

- [ ] **Step 5: Executar checks estruturais**

Run:

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/python manage.py check

DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/python manage.py makemigrations --check --dry-run

git diff --check
git status --short
```

Expected: Django sem issues, nenhuma migration, diff sem whitespace errors e somente arquivos esperados.

- [ ] **Step 6: Commitar documentação e evidência final**

```bash
git add TEMPLATES.md tests/test_workspace_ui.py
git diff --cached --check
git commit -m "docs: document permission-aware workspace navigation"
```

---

## Final Acceptance Checklist

- [ ] `WorkspaceConfig` contém todos os metadados de navegação e resolve sua URL.
- [ ] Sidebar e cabeçalho não contêm listas hardcoded dos três workspaces.
- [ ] Perfis sem acesso não veem links que resultariam em HTTP 403.
- [ ] O sino de workflow e sua consulta só existem para perfis autorizados.
- [ ] Painéis vazios não aparecem; módulos permanecem agrupados e filtrados.
- [ ] Workspace ativo possui `aria-current="page"`.
- [ ] Rotas públicas permanecem inalteradas.
- [ ] Testes relevantes, Django check e migration check passam.
- [ ] Documentação descreve como adicionar futuros workspaces.
