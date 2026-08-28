# Dynamic Home and Workspace Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar `/app/` a única página inicial autenticada e consolidar os cockpits de operação, qualidade e workflow em um contrato configurável, permissionado e renderizado por um único template.

**Architecture:** `core.views.home` passa a redirecionar usuários autenticados para `app:index`. Um novo módulo `base.ui.workspaces` concentra configurações imutáveis, consultas de métricas, links resolvidos e filtragem por permissão; uma única `WorkspaceView` resolve a configuração e renderiza `templates/workspaces/workspace.html`, enquanto os nomes e caminhos atuais das três rotas permanecem inalterados.

**Tech Stack:** Python 3, Django 5.2, Django Templates, Bootstrap 5, Duralux e pytest-django.

## Global Constraints

- Preservar `app:operations_workspace`, `app:quality_workspace` e `app:workflow_workspace`, inclusive seus caminhos atuais.
- Preservar o redirecionamento de usuários anônimos da rota `/` para `accounts:login`.
- Não alterar models, migrations, serializers ou APIs REST.
- Não incorporar workspaces ao `DashboardHubView`.
- Não mudar fórmulas, estados ou escopo dos cálculos de métricas existentes.
- Resolver URLs com `reverse`; não concatenar caminhos no template.
- Aplicar autorização de módulo, cartão e atalho no servidor.
- Seguir TDD: toda mudança de produção deve ser precedida por um teste que falhe pelo motivo esperado.
- Não modificar nem incluir em commits as alterações locais preexistentes em `base/automatic_fields.py`, `crm/admin.py`, `docs/architecture/foundation.md`, `docs/architecture/inventory.md`, `finance/admin.py` e `tests/test_automatic_fields.py`.

---

## File Structure

- Create: `base/ui/workspaces.py` — contrato imutável, registro, builders de métricas e filtragem de itens.
- Create: `templates/workspaces/workspace.html` — única apresentação dos três cockpits.
- Create: `tests/test_home_navigation.py` — contrato de navegação da rota `/`.
- Create: `tests/test_workspace_ui.py` — contrato, autorização, conteúdo e isolamento de usuário dos workspaces.
- Modify: `core/views.py` — redirecionamento autenticado para `app:index`.
- Modify: `base/ui/views.py` — `WorkspaceView` compartilhada e remoção das três views especializadas.
- Modify: `base/ui/urls.py` — rotas existentes configuradas com slugs fixos.
- Modify: `TEMPLATES.md` — documentação da home autenticada e do workspace configurável.
- Delete: `templates/dashboard/home.html` — catálogo estático substituído por `/app/`.
- Delete: `templates/workspaces/operations.html` — substituído pelo template compartilhado.
- Delete: `templates/workspaces/quality.html` — substituído pelo template compartilhado.
- Delete: `templates/workspaces/workflow.html` — substituído pelo template compartilhado.

---

### Task 1: Tornar `/app/` a única home autenticada

**Files:**
- Create: `tests/test_home_navigation.py`
- Modify: `core/views.py:1-12`
- Delete: `templates/dashboard/home.html`

**Interfaces:**
- Consumes: nomes de rota `accounts:login` e `app:index`.
- Produces: `core.views.home(request)` com redirecionamentos determinísticos para usuários anônimos e autenticados.

- [ ] **Step 1: Escrever os testes de redirecionamento e remoção do template estático**

Criar `tests/test_home_navigation.py`:

```python
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomeNavigationTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('home'))

        self.assertRedirects(
            response,
            reverse('accounts:login'),
            fetch_redirect_response=False,
        )

    def test_authenticated_user_is_redirected_to_app_index(self):
        user = get_user_model().objects.create_user(
            username='home-user@example.com',
            email='home-user@example.com',
            password='HomeSecure!123',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('home'))

        self.assertRedirects(
            response,
            reverse('app:index'),
            fetch_redirect_response=False,
        )

    def test_static_dashboard_home_template_has_been_removed(self):
        self.assertFalse(Path('templates/dashboard/home.html').exists())
```

- [ ] **Step 2: Executar os testes e confirmar a falha correta**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_home_navigation.py
```

Expected: dois testes falham — o usuário autenticado recebe o template atual em vez de redirect e `templates/dashboard/home.html` ainda existe; o teste anônimo passa.

- [ ] **Step 3: Implementar o redirecionamento mínimo**

Alterar `core/views.py` para remover `render` do import e substituir `home` por:

```python
from django.http import JsonResponse
from django.shortcuts import redirect, render


def health_check(request):
    return JsonResponse({'status': 'ok'})


def home(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    return redirect('app:index')
```

Manter `render` porque `permission_denied` continua usando-o. Excluir `templates/dashboard/home.html` com `apply_patch`.

- [ ] **Step 4: Executar os testes e confirmar estado verde**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_home_navigation.py
```

Expected: `3 passed`.

- [ ] **Step 5: Commitar somente os arquivos da tarefa**

```bash
git add core/views.py tests/test_home_navigation.py templates/dashboard/home.html
git diff --cached --check
git commit -m "refactor: make app index the authenticated home"
```

---

### Task 2: Criar o contrato e o registro permissionado dos workspaces

**Files:**
- Create: `base/ui/workspaces.py`
- Create: `tests/test_workspace_ui.py`

**Interfaces:**
- Consumes: `base.ui.registry.get_module`, models atuais de produção, estoque, qualidade e workflow, `reverse` e permissões Django.
- Produces: `WorkspaceMetric`, `WorkspaceLink`, `WorkspaceContent`, `WorkspaceConfig`, `WORKSPACES` e `get_workspace(workspace_slug)`.

- [ ] **Step 1: Escrever os testes do registro imutável e das configurações**

Criar `tests/test_workspace_ui.py` com o contrato inicial:

```python
from dataclasses import FrozenInstanceError

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase

from base.ui.workspaces import WORKSPACES, get_workspace
from workflow.models import WorkflowNotification


class WorkspaceConfigurationTests(SimpleTestCase):
    def test_registry_contains_the_three_approved_workspaces(self):
        self.assertEqual(set(WORKSPACES), {'operations', 'quality', 'workflow'})
        self.assertEqual(get_workspace('operations').module_slug, 'production')
        self.assertEqual(get_workspace('quality').module_slug, 'quality')
        self.assertEqual(get_workspace('workflow').module_slug, 'workflow')

    def test_unknown_workspace_returns_none(self):
        self.assertIsNone(get_workspace('missing'))

    def test_workspace_configuration_is_immutable(self):
        workspace = get_workspace('operations')

        with self.assertRaises(FrozenInstanceError):
            workspace.title = 'Alterado'


class WorkspaceContentBuilderTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='workspace-builder@example.com',
            email='workspace-builder@example.com',
            password='WorkspaceSecure!123',
        )

    def request_for(self, user=None):
        request = RequestFactory().get('/app/workspaces/')
        request.user = user or self.admin
        return request

    def test_builders_preserve_metric_labels_and_primary_links(self):
        expectations = {
            'operations': (
                ('Ordens em execução', 'Lotes em estoque', 'Amostras pendentes'),
                '/app/production/orders/',
            ),
            'quality': (
                ('Amostras em análise', 'Análises pendentes', 'Investigações abertas'),
                '/app/quality/samples/',
            ),
            'workflow': (
                ('Aprovações pendentes', 'Notificações não lidas', 'Jobs em execução'),
                '/app/workflow/tasks/',
            ),
        }

        for slug, (labels, primary_url) in expectations.items():
            with self.subTest(slug=slug):
                content = get_workspace(slug).build_content(self.request_for())
                self.assertEqual(tuple(metric.label for metric in content.metrics), labels)
                self.assertEqual(content.metrics[0].url, primary_url)

    def test_workflow_notifications_are_scoped_to_request_user(self):
        other_user = get_user_model().objects.create_user(
            username='workspace-other@example.com',
            email='workspace-other@example.com',
            password='WorkspaceSecure!123',
        )
        for recipient in (self.admin, other_user, other_user):
            WorkflowNotification.objects.create(
                category=WorkflowNotification.Category.ALERT,
                recipient=recipient,
                title='Alerta de teste',
                message='Mensagem de teste',
                source_module=WorkflowNotification.SourceModule.QUALITY,
            )

        content = get_workspace('workflow').build_content(self.request_for())
        metric = next(
            item for item in content.metrics if item.label == 'Notificações não lidas'
        )

        self.assertEqual(metric.value, 1)
```

- [ ] **Step 2: Executar o teste e confirmar a falha correta**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q \
  tests/test_workspace_ui.py::WorkspaceConfigurationTests \
  tests/test_workspace_ui.py::WorkspaceContentBuilderTests
```

Expected: ERROR de importação porque `base.ui.workspaces` ainda não existe.

- [ ] **Step 3: Implementar o contrato e os builders completos**

Criar `base/ui/workspaces.py` com:

```python
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.urls import reverse

from base.ui.registry import get_module
from inventory.models import StockLot
from production.models import ProductionOrder
from quality.models import LaboratoryInvestigation, QualityAnalysis, QualitySample
from workflow.models import ApprovalTask, AsyncJobStatus, WorkflowNotification


@dataclass(frozen=True)
class WorkspaceMetric:
    label: str
    value: Any
    icon: str
    tone: str
    badge: str
    url: str
    required_permission: str = ''

    def can_view(self, user):
        return not self.required_permission or user.has_perm(self.required_permission)


@dataclass(frozen=True)
class WorkspaceLink:
    label: str
    icon: str
    url: str
    required_module_slug: str = ''

    def can_view(self, user):
        if not self.required_module_slug:
            return True
        module = get_module(self.required_module_slug)
        return module is not None and module.can_view(user)


@dataclass(frozen=True)
class WorkspaceContent:
    metrics: tuple[WorkspaceMetric, ...]
    quick_links: tuple[WorkspaceLink, ...]

    def visible_to(self, user):
        return WorkspaceContent(
            metrics=tuple(metric for metric in self.metrics if metric.can_view(user)),
            quick_links=tuple(link for link in self.quick_links if link.can_view(user)),
        )


@dataclass(frozen=True)
class WorkspaceConfig:
    slug: str
    title: str
    description: str
    breadcrumb_label: str
    module_slug: str
    quick_links_title: str
    builder: Callable[[Any], WorkspaceContent]

    def build_content(self, request):
        return self.builder(request).visible_to(request.user)
```

No mesmo arquivo, implementar integralmente os três builders:

```python
def _operations_content(request):
    production_orders = ProductionOrder.objects.all()
    stock_lots = StockLot.objects.all()
    samples = QualitySample.objects.all()
    return WorkspaceContent(
        metrics=(
            WorkspaceMetric(
                'Ordens em execução',
                production_orders.filter(status=ProductionOrder.Status.IN_PROGRESS).count(),
                'feather-play-circle',
                'primary',
                'Produção',
                reverse('app:resource_list', args=('production', 'orders')),
                'production.view_productionorder',
            ),
            WorkspaceMetric(
                'Lotes em estoque',
                stock_lots.count(),
                'feather-archive',
                'success',
                'Estoque',
                reverse('app:resource_list', args=('inventory', 'lots')),
                'inventory.view_stocklot',
            ),
            WorkspaceMetric(
                'Amostras pendentes',
                samples.exclude(
                    status__in=(
                        QualitySample.Status.APPROVED,
                        QualitySample.Status.REJECTED,
                        QualitySample.Status.CANCELLED,
                    )
                ).count(),
                'feather-check-square',
                'warning',
                'Qualidade',
                reverse('app:resource_list', args=('quality', 'samples')),
                'quality.view_qualitysample',
            ),
        ),
        quick_links=(
            WorkspaceLink(
                'Planejamento',
                'feather-calendar',
                reverse('app:module', args=('planning',)),
                'planning',
            ),
            WorkspaceLink(
                'Compras',
                'feather-shopping-cart',
                reverse('app:module', args=('procurement',)),
                'procurement',
            ),
            WorkspaceLink(
                'Qualidade',
                'feather-check-square',
                reverse('app:module', args=('quality',)),
                'quality',
            ),
        ),
    )


def _quality_content(request):
    samples = QualitySample.objects.all()
    analyses = QualityAnalysis.objects.all()
    investigations = LaboratoryInvestigation.objects.all()
    return WorkspaceContent(
        metrics=(
            WorkspaceMetric(
                'Amostras em análise',
                samples.filter(status=QualitySample.Status.IN_ANALYSIS).count(),
                'feather-droplet',
                'warning',
                'Amostragem',
                reverse('app:resource_list', args=('quality', 'samples')),
                'quality.view_qualitysample',
            ),
            WorkspaceMetric(
                'Análises pendentes',
                analyses.filter(status=QualityAnalysis.Status.PENDING).count(),
                'feather-activity',
                'primary',
                'Laboratório',
                reverse('app:resource_list', args=('quality', 'analyses')),
                'quality.view_qualityanalysis',
            ),
            WorkspaceMetric(
                'Investigações abertas',
                investigations.exclude(
                    status__in=(
                        LaboratoryInvestigation.Status.CONCLUDED,
                        LaboratoryInvestigation.Status.CANCELLED,
                    )
                ).count(),
                'feather-alert-triangle',
                'danger',
                'Investigação',
                reverse('app:resource_list', args=('quality', 'investigations')),
                'quality.view_laboratoryinvestigation',
            ),
        ),
        quick_links=(
            WorkspaceLink(
                'Garantia da qualidade',
                'feather-shield',
                reverse('app:module', args=('qa',)),
                'qa',
            ),
            WorkspaceLink(
                'Desvios',
                'feather-alert-circle',
                reverse('app:module', args=('deviations',)),
                'deviations',
            ),
            WorkspaceLink(
                'CAPA',
                'feather-target',
                reverse('app:module', args=('capa',)),
                'capa',
            ),
            WorkspaceLink(
                'Documentos',
                'feather-file-text',
                reverse('app:module', args=('documents',)),
                'documents',
            ),
        ),
    )


def _workflow_content(request):
    tasks = ApprovalTask.objects.all()
    notifications = WorkflowNotification.objects.filter(recipient=request.user)
    jobs = AsyncJobStatus.objects.all()
    return WorkspaceContent(
        metrics=(
            WorkspaceMetric(
                'Aprovações pendentes',
                tasks.filter(status=ApprovalTask.Status.PENDING).count(),
                'feather-check-square',
                'warning',
                'Aprovações',
                reverse('app:resource_list', args=('workflow', 'tasks')),
                'workflow.view_approvaltask',
            ),
            WorkspaceMetric(
                'Notificações não lidas',
                notifications.filter(status=WorkflowNotification.Status.UNREAD).count(),
                'feather-bell',
                'primary',
                'Avisos',
                reverse('app:resource_list', args=('workflow', 'notifications')),
                'workflow.view_workflownotification',
            ),
            WorkspaceMetric(
                'Jobs em execução',
                jobs.filter(
                    status__in=(AsyncJobStatus.Status.PENDING, AsyncJobStatus.Status.RUNNING)
                ).count(),
                'feather-loader',
                'info',
                'Processamento',
                reverse('app:resource_list', args=('workflow', 'async-jobs')),
                'workflow.view_asyncjobstatus',
            ),
        ),
        quick_links=(
            WorkspaceLink(
                'Todos os recursos',
                'feather-git-pull-request',
                reverse('app:module', args=('workflow',)),
                'workflow',
            ),
            WorkspaceLink(
                'Compliance',
                'feather-shield',
                reverse('app:module', args=('compliance',)),
                'compliance',
            ),
            WorkspaceLink(
                'Governança',
                'feather-settings',
                reverse('app:module', args=('governance',)),
                'governance',
            ),
        ),
    )
```

Declarar o registro final:

```python
WORKSPACES = {
    'operations': WorkspaceConfig(
        slug='operations',
        title='Cockpit operacional',
        description='Produção, estoque e qualidade em um único contexto.',
        breadcrumb_label='Operação',
        module_slug='production',
        quick_links_title='Acessos rápidos',
        builder=_operations_content,
    ),
    'quality': WorkspaceConfig(
        slug='quality',
        title='Cockpit de qualidade',
        description='Amostragem, análises e investigações sob controle.',
        breadcrumb_label='Qualidade',
        module_slug='quality',
        quick_links_title='Fluxos de qualidade',
        builder=_quality_content,
    ),
    'workflow': WorkspaceConfig(
        slug='workflow',
        title='Central de workflow',
        description='Aprovações, notificações e processamento assíncrono.',
        breadcrumb_label='Fluxo de trabalho',
        module_slug='workflow',
        quick_links_title='Governança operacional',
        builder=_workflow_content,
    ),
}


def get_workspace(workspace_slug):
    return WORKSPACES.get(workspace_slug)
```

- [ ] **Step 4: Executar o teste e confirmar estado verde**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q \
  tests/test_workspace_ui.py::WorkspaceConfigurationTests \
  tests/test_workspace_ui.py::WorkspaceContentBuilderTests
```

Expected: `5 passed`.

- [ ] **Step 5: Commitar somente o contrato e seu teste**

```bash
git add base/ui/workspaces.py tests/test_workspace_ui.py
git diff --cached --check
git commit -m "feat: add configurable workspace registry"
```

---

### Task 3: Integrar a view, as rotas e o template compartilhado

**Files:**
- Modify: `tests/test_workspace_ui.py`
- Modify: `base/ui/views.py:240-260,587-652`
- Modify: `base/ui/urls.py:14-21`
- Create: `templates/workspaces/workspace.html`

**Interfaces:**
- Consumes: `get_workspace(workspace_slug)` e `WorkspaceConfig.build_content(request)`.
- Produces: `WorkspaceView.workspace_slug`, `WorkspaceView.get_workspace()` e o contexto `workspace`, `metrics`, `quick_links`.

- [ ] **Step 1: Adicionar testes de rotas, template compartilhado, 403 e 404**

Acrescentar a `tests/test_workspace_ui.py`:

```python
from django.contrib.auth.models import Permission
from django.http import Http404
from django.urls import reverse

from base.ui.views import WorkspaceView
from production.models import ProductionOrder


def grant_view_permission(user, model):
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label=model._meta.app_label,
            content_type__model=model._meta.model_name,
            codename=f'view_{model._meta.model_name}',
        )
    )


class WorkspaceAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='workspace@example.com',
            email='workspace@example.com',
            password='WorkspaceSecure!123',
        )
        self.admin = get_user_model().objects.create_superuser(
            username='workspace-admin@example.com',
            email='workspace-admin@example.com',
            password='WorkspaceSecure!123',
        )

    def test_existing_route_names_and_paths_are_preserved(self):
        self.assertEqual(reverse('app:operations_workspace'), '/app/workspaces/operations/')
        self.assertEqual(reverse('app:quality_workspace'), '/app/workspaces/quality/')
        self.assertEqual(reverse('app:workflow_workspace'), '/app/workspaces/workflow/')

    def test_workspace_requires_login(self):
        response = self.client.get(reverse('app:operations_workspace'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('accounts:login')))

    def test_all_workspaces_render_the_shared_template(self):
        self.client.force_login(self.admin)

        for route_name in (
            'app:operations_workspace',
            'app:quality_workspace',
            'app:workflow_workspace',
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'workspaces/workspace.html')
                self.assertContains(response, 'data-ui="workspace"')

    def test_user_without_module_permission_receives_403(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('app:operations_workspace'))

        self.assertEqual(response.status_code, 403)

    def test_unknown_direct_workspace_configuration_raises_404(self):
        request = RequestFactory().get('/app/workspaces/missing/')
        request.user = self.admin

        with self.assertRaises(Http404):
            WorkspaceView.as_view(workspace_slug='missing')(request)

    def test_metric_cards_are_filtered_by_model_permission(self):
        grant_view_permission(self.user, ProductionOrder)
        self.client.force_login(self.user)

        response = self.client.get(reverse('app:operations_workspace'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ordens em execução')
        self.assertNotContains(response, 'Lotes em estoque')
        self.assertNotContains(response, 'Amostras pendentes')
        self.assertNotContains(response, '>Planejamento<')
```

- [ ] **Step 2: Executar os novos testes e confirmar a falha correta**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_workspace_ui.py::WorkspaceAccessTests
```

Expected: FAIL porque `WorkspaceView` e `workspaces/workspace.html` ainda não existem e as rotas apontam para classes especializadas.

- [ ] **Step 3: Implementar a view compartilhada**

Em `base/ui/views.py`, importar `get_workspace`, remover os imports agora exclusivos de workflow (`ApprovalTask`, `AsyncJobStatus` e `WorkflowNotification`) e substituir `ModuleWorkspaceMixin`, `OperationsWorkspaceView`, `QualityWorkspaceView` e `WorkflowWorkspaceView` por:

```python
class WorkspaceView(LoginRequiredMixin, TemplateView):
    template_name = 'workspaces/workspace.html'
    workspace_slug = ''
    workspace = None

    def get_workspace(self):
        if self.workspace is None:
            self.workspace = get_workspace(self.workspace_slug)
        if self.workspace is None:
            raise Http404('Workspace não encontrado.')
        return self.workspace

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        workspace = self.get_workspace()
        module = get_module(workspace.module_slug)
        if module is None or not module.can_view(request.user):
            raise PermissionDenied('Usuário sem permissão para visualizar este workspace.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workspace = self.get_workspace()
        content = workspace.build_content(self.request)
        context.update(
            {
                'workspace': workspace,
                'metrics': content.metrics,
                'quick_links': content.quick_links,
            }
        )
        return context
```

- [ ] **Step 4: Preservar as rotas com slugs fixos**

Alterar somente as três rotas em `base/ui/urls.py`:

```python
path(
    'workspaces/operations/',
    views.WorkspaceView.as_view(workspace_slug='operations'),
    name='operations_workspace',
),
path(
    'workspaces/quality/',
    views.WorkspaceView.as_view(workspace_slug='quality'),
    name='quality_workspace',
),
path(
    'workspaces/workflow/',
    views.WorkspaceView.as_view(workspace_slug='workflow'),
    name='workflow_workspace',
),
```

- [ ] **Step 5: Criar o template compartilhado**

Criar `templates/workspaces/workspace.html` integralmente:

```django
{% extends 'base.html' %}

{% block title %}{{ workspace.title }} | RGN Farma System{% endblock %}

{% block page_header %}
<div class="page-header">
    <div class="page-header-left d-flex align-items-center">
        <div class="page-header-title">
            <h5 class="m-b-10">{{ workspace.title }}</h5>
            <p class="text-muted mb-0">{{ workspace.description }}</p>
        </div>
        <ul class="breadcrumb mb-0">
            <li class="breadcrumb-item"><a href="{% url 'app:index' %}">Aplicativos</a></li>
            <li class="breadcrumb-item">{{ workspace.breadcrumb_label }}</li>
        </ul>
    </div>
</div>
{% endblock %}

{% block content %}
<section class="row g-4" data-ui="workspace" aria-label="Indicadores de {{ workspace.breadcrumb_label|lower }}">
    {% for metric in metrics %}
    <div class="col-xxl-4 col-md-6">
        <article class="card stretch stretch-full h-100">
            <div class="card-body d-flex flex-column">
                <div class="d-flex align-items-start justify-content-between mb-4">
                    <div class="d-flex gap-4 align-items-center">
                        <div class="avatar-text avatar-lg bg-soft-{{ metric.tone }} text-{{ metric.tone }}">
                            <i class="{{ metric.icon }}" aria-hidden="true"></i>
                        </div>
                        <div>
                            <div class="fs-4 fw-bold text-dark">{{ metric.value }}</div>
                            <h2 class="fs-13 fw-semibold mb-0">{{ metric.label }}</h2>
                        </div>
                    </div>
                    <span class="badge bg-soft-{{ metric.tone }} text-{{ metric.tone }}">{{ metric.badge }}</span>
                </div>
                <div class="pt-4 border-top mt-auto">
                    <a href="{{ metric.url }}" class="fs-12 fw-medium text-muted">Ver detalhes</a>
                </div>
            </div>
        </article>
    </div>
    {% empty %}
    <div class="col-12">
        {% include 'app/includes/empty_state.html' with title='Nenhum indicador disponível' message='Seu perfil não possui indicadores autorizados neste workspace.' %}
    </div>
    {% endfor %}
</section>

{% if quick_links %}
<section class="card stretch stretch-full mt-4">
    <div class="card-header">
        <h2 class="card-title h5 mb-0">{{ workspace.quick_links_title }}</h2>
    </div>
    <div class="card-body">
        <div class="d-flex flex-wrap gap-2">
            {% for link in quick_links %}
            <a class="btn btn-light-brand" href="{{ link.url }}">
                <i class="{{ link.icon }} me-2" aria-hidden="true"></i>{{ link.label }}
            </a>
            {% endfor %}
        </div>
    </div>
</section>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Executar os testes e confirmar estado verde**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_workspace_ui.py
```

Expected: todos os testes do arquivo passam.

- [ ] **Step 7: Commitar somente a integração compartilhada**

```bash
git add base/ui/views.py base/ui/urls.py templates/workspaces/workspace.html tests/test_workspace_ui.py
git diff --cached --check
git commit -m "refactor: render operational workspaces from shared view"
```

---

### Task 4: Remover templates duplicados e documentar o contrato

**Files:**
- Modify: `tests/test_workspace_ui.py`
- Modify: `TEMPLATES.md:1-35`
- Delete: `templates/workspaces/operations.html`
- Delete: `templates/workspaces/quality.html`
- Delete: `templates/workspaces/workflow.html`

**Interfaces:**
- Consumes: `workspaces/workspace.html`, rotas preservadas e regras de UI de `TEMPLATES.md`.
- Produces: uma única fonte de markup dos workspaces e documentação operacional atualizada.

- [ ] **Step 1: Escrever o teste de limpeza e documentação**

Adicionar a `WorkspaceConfigurationTests`:

```python
def test_legacy_workspace_templates_are_removed_and_contract_is_documented(self):
    from pathlib import Path

    legacy_templates = (
        Path('templates/workspaces/operations.html'),
        Path('templates/workspaces/quality.html'),
        Path('templates/workspaces/workflow.html'),
    )
    documentation = Path('TEMPLATES.md').read_text()

    self.assertTrue(all(not path.exists() for path in legacy_templates))
    self.assertIn('workspaces/workspace.html', documentation)
    self.assertIn('/app/', documentation)
    self.assertIn('WorkspaceConfig', documentation)
```

- [ ] **Step 2: Executar o teste e confirmar a falha correta**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_workspace_ui.py::WorkspaceConfigurationTests::test_legacy_workspace_templates_are_removed_and_contract_is_documented
```

Expected: FAIL porque os três templates antigos ainda existem e `TEMPLATES.md` ainda não descreve `WorkspaceConfig`.

- [ ] **Step 3: Remover os templates duplicados e atualizar a documentação**

Excluir os três templates legados com `apply_patch`. Em `TEMPLATES.md`, inserir após o parágrafo introdutório:

```markdown
## Página inicial e workspaces

Usuários autenticados que acessam `/` são redirecionados para `/app/`, o
catálogo dinâmico de módulos permitido ao perfil. A home não mantém um catálogo
estático paralelo.

Os cockpits de operação, qualidade e workflow usam configurações imutáveis
`WorkspaceConfig` em `base.ui.workspaces` e uma única apresentação em
`templates/workspaces/workspace.html`. As configurações fornecem textos,
métricas, tons, ícones e URLs já resolvidas. A view filtra módulos, cartões e
atalhos no servidor antes da renderização.

As rotas nomeadas `app:operations_workspace`, `app:quality_workspace` e
`app:workflow_workspace` permanecem estáveis. Novos workspaces devem ser
registrados no mesmo contrato, com teste de acesso ao módulo, visibilidade dos
itens e escopo das consultas.
```

- [ ] **Step 4: Executar o teste e confirmar estado verde**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q tests/test_workspace_ui.py::WorkspaceConfigurationTests::test_legacy_workspace_templates_are_removed_and_contract_is_documented
```

Expected: PASS.

- [ ] **Step 5: Commitar somente limpeza e documentação**

```bash
git add TEMPLATES.md tests/test_workspace_ui.py templates/workspaces/operations.html templates/workspaces/quality.html templates/workspaces/workflow.html
git diff --cached --check
git commit -m "docs: document shared workspace contract"
```

---

### Task 5: Verificação final proporcional ao risco

**Files:**
- Verify only; nenhum arquivo novo previsto.

**Interfaces:**
- Consumes: todos os entregáveis das Tasks 1–4.
- Produces: evidência fresca de testes, configuração Django, ausência de migrations e limpeza do diff.

- [ ] **Step 1: Executar a suíte direcionada completa**

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q \
  tests/test_home_navigation.py \
  tests/test_workspace_ui.py \
  tests/test_dashboard_hub.py \
  tests/test_app_ui.py
```

Expected: exit code `0`, sem falhas.

- [ ] **Step 2: Executar as verificações Django e de migrations**

```bash
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py makemigrations --check --dry-run
```

Expected: `System check identified no issues` e `No changes detected`.

- [ ] **Step 3: Verificar referências e integridade do diff**

```bash
rg -n "OperationsWorkspaceView|QualityWorkspaceView|WorkflowWorkspaceView|workspaces/(operations|quality|workflow)\.html|dashboard/home\.html" base core templates tests TEMPLATES.md
git diff --check
git status --short
```

Expected: `rg` não encontra referências de produção aos artefatos removidos; `git diff --check` não reporta erros; `git status --short` mantém visíveis, mas não alteradas por esta implementação, as modificações locais preexistentes listadas nas restrições globais.

- [ ] **Step 4: Revisar os critérios da especificação**

Confirmar explicitamente:

- `/` redireciona corretamente por estado de autenticação;
- `/app/` é a única home autenticada;
- três rotas antigas preservam nome e caminho;
- um único template renderiza os três workspaces;
- 403, 404 e filtragem de itens estão cobertos;
- notificações permanecem isoladas por destinatário;
- nenhum model, migration, serializer ou endpoint REST foi alterado;
- `TEMPLATES.md` corresponde ao comportamento entregue.
