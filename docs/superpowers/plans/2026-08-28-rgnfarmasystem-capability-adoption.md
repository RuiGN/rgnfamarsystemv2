# RGN Farma Capability Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incorporar ao projeto atual as funcionalidades comprovadamente úteis do repositório `rgnfarmasystem`, começando por navegação, área pessoal e busca global seguras, sem regredir o design system ou os controles de acesso existentes.

**Architecture:** A primeira entrega amplia a camada `base.ui` atual: o context processor agrupa somente módulos já autorizados, um serviço dedicado compõe a área pessoal com consultas explicitamente permissionadas e a busca global consulta sempre o queryset escopado de cada `ResourceConfig`. Agenda, Regulatório, Notificações, Comissões e Logística permanecem subprojetos independentes, executados somente após a entrega anterior passar pelos gates de segurança, migrations, testes e documentação.

**Tech Stack:** Python, Django 5.2, Django Templates, Bootstrap 5/Duralux, JavaScript sem dependência adicional e pytest-django.

## Global Constraints

- Toda UX e todo texto visível devem permanecer em português do Brasil, com acentuação correta.
- Preservar as rotas, workspaces, dashboards, sidebar responsivo e design system existentes.
- Aplicar autorização e escopo de dados no servidor; ocultar controles no template não constitui autorização.
- Não copiar `base.html`, `resource_list.html`, `resource_detail.html`, CSS global ou migrations do repositório de origem.
- Não capturar `Exception` genericamente nem ocultar falhas de banco.
- Não criar visualizações salvas, modo operador, escrita offline ou edição regulada em massa nesta entrega.
- Seguir TDD e executar cada teste vermelho antes da implementação correspondente.
- Preservar as alterações locais preexistentes em `base/ui/registry.py`, `tests/test_app_ui.py`, `tests/test_dashboard_hub.py` e `tests/test_workspace_ui.py`.
- Executar testes com `DATABASE_URL=sqlite:///baseline_base.sqlite3`, `TEST_DATABASE_URL=sqlite:///test_db.sqlite3` e `DJANGO_SETTINGS_MODULE=core.settings.test`, salvo teste explicitamente PostgreSQL.

## Delivery Map

1. **Entrega A — UX segura:** sidebar por domínios, Minha Área e busca global/paleta de comandos.
2. **Entrega B — Agenda:** equipes, tarefas, eventos, API e integração com Minha Área.
3. **Entrega C — Regulatório:** dossiês, registros, petições, exigências, compromissos e evidências.
4. **Entrega D — Notificações:** preferências, digest Celery, histórico e eventos obrigatórios.
5. **Entrega E — Comissões:** regras, apuração, ajustes, eventos e integração financeira.
6. **Entrega F — Logística:** ondas, remessas, volumes, evidências de entrega e devoluções.
7. **Entrega G — Novos PRDs:** OEE, Autoinspeção e PIF Cosmético, cada um como projeto independente.

Somente a Entrega A está detalhada para execução neste documento. Cada entrega posterior deve receber especificação e plano próprios antes de alterar código; isso impede que migrations e regras de domínios independentes sejam aprovadas como um único pacote inseparável.

---

### Task 1: Agrupar módulos autorizados por domínio no sidebar

**Files:**
- Modify: `base/ui/context_processors.py`
- Modify: `templates/includes/sidebar.html`
- Create: `tests/test_sidebar_domains.py`
- Modify: `docs/architecture/sidebar-permissions.md`

**Interfaces:**
- Consumes: `get_visible_modules(user) -> tuple[ModuleConfig, ...]`.
- Produces: `sidebar_domains: tuple[tuple[str, str, tuple[ModuleConfig, ...]], ...]`.

- [ ] **Step 1: Escrever os testes vermelhos de agrupamento, permissão e fallback**

Adicionar testes que construam módulos visíveis falsos e comprovem:

```python
def test_sidebar_groups_only_modules_already_visible_to_the_user():
    context = sidebar_context_for(user_with_production_and_quality_permissions)

    assert [domain[0] for domain in context['sidebar_domains']] == [
        'operations',
        'quality',
    ]
    assert tuple(module.slug for module in context['sidebar_domains'][0][2]) == (
        'production',
    )


def test_sidebar_places_unmapped_visible_module_in_other_domain():
    context = sidebar_context_with_visible_modules(('knowledge',))

    key, label, modules = context['sidebar_domains'][-1]
    assert (key, label) == ('other', 'Outros')
    assert tuple(module.slug for module in modules) == ('knowledge',)
```

- [ ] **Step 2: Executar os testes e confirmar falha por contexto ausente**

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
pytest -q tests/test_sidebar_domains.py
```

Expected: FAIL porque `sidebar_domains` ainda não existe.

- [ ] **Step 3: Implementar o mapa de domínios e o agrupador puro**

Adicionar em `base/ui/context_processors.py` uma constante ordenada e uma função pura:

```python
SIDEBAR_DOMAINS = (
    ('operations', 'Operações', ('production', 'mrp', 'inventory', 'maintenance')),
    ('quality', 'Qualidade', ('quality', 'capa', 'deviations', 'changes', 'risks')),
    ('supply', 'Suprimentos', ('procurement', 'suppliers')),
    ('commercial', 'Comercial', ('crm', 'recalls')),
    ('finance', 'Financeiro e fiscal', ('finance', 'fiscal', 'costing')),
    ('compliance', 'Governança e conformidade', (
        'documents', 'training', 'audits', 'compliance', 'workflow', 'governance',
    )),
    ('administration', 'Administração', ('masters', 'auxiliary', 'accounts')),
)


def group_sidebar_modules(modules):
    modules_by_slug = {module.slug: module for module in modules}
    grouped = []
    classified = set()
    for key, label, slugs in SIDEBAR_DOMAINS:
        items = tuple(modules_by_slug[slug] for slug in slugs if slug in modules_by_slug)
        if items:
            grouped.append((key, label, items))
            classified.update(module.slug for module in items)
    other = tuple(module for module in modules if module.slug not in classified)
    if other:
        grouped.append(('other', 'Outros', other))
    return tuple(grouped)
```

O context processor deve calcular `modules` uma única vez e expor `sidebar_domains=group_sidebar_modules(modules)`. Para usuário anônimo, deve retornar `sidebar_domains=()`.

- [ ] **Step 4: Renderizar os domínios sem mover autorização para o template**

Substituir somente o loop de módulos em `templates/includes/sidebar.html` por loops aninhados de domínio e módulo. Preservar classes Duralux, `aria-expanded`, `aria-current`, badges de consulta e estado ativo já existentes.

- [ ] **Step 5: Executar testes direcionados e de regressão do shell**

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
pytest -q tests/test_sidebar_domains.py tests/test_app_ui.py \
  tests/test_workspace_ui.py tests/test_dashboard_hub.py
```

Expected: PASS.

- [ ] **Step 6: Documentar e commitar**

Documentar em `docs/architecture/sidebar-permissions.md` que a associação a domínio é apenas apresentação e que `get_visible_modules()` continua sendo a fonte de autorização.

```bash
git add base/ui/context_processors.py templates/includes/sidebar.html \
  tests/test_sidebar_domains.py docs/architecture/sidebar-permissions.md
git diff --cached --check
git commit -m "feat: group authorized sidebar modules by domain"
```

---

### Task 2: Criar o contrato permissionado da Minha Área

**Files:**
- Create: `base/ui/personal_area.py`
- Create: `tests/test_personal_area.py`

**Interfaces:**
- Consumes: usuário autenticado, permissões Django, `ApprovalTask`, `WorkflowNotification`, `QualityEvent`, `CapaRecord` e `TrainingEnrollment`.
- Produces: `PersonalAreaItem`, `PersonalAreaSection` e `build_personal_area(request) -> tuple[PersonalAreaSection, ...]`.

- [ ] **Step 1: Escrever testes vermelhos do contrato e isolamento**

Os testes devem provar que:

```python
def test_personal_area_returns_only_records_assigned_to_request_user():
    sections = build_personal_area(request_for(owner))
    identifiers = {item.identifier for section in sections for item in section.items}

    assert owner_task.pk in identifiers
    assert other_user_task.pk not in identifiers


def test_personal_area_omits_section_without_model_view_permission():
    sections = build_personal_area(request_for(user_without_deviation_permission))

    assert 'deviations' not in {section.key for section in sections}
```

- [ ] **Step 2: Executar os testes e confirmar erro de importação**

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_personal_area.py
```

Expected: ERROR porque `base.ui.personal_area` ainda não existe.

- [ ] **Step 3: Implementar tipos imutáveis e builders explícitos**

Criar dataclasses congeladas:

```python
@dataclass(frozen=True)
class PersonalAreaItem:
    identifier: int
    title: str
    subtitle: str
    url: str
    status_label: str
    due_date: date | None = None


@dataclass(frozen=True)
class PersonalAreaSection:
    key: str
    title: str
    icon: str
    items: tuple[PersonalAreaItem, ...]
    empty_message: str
```

Cada builder deve declarar uma permissão, filtrar pelo usuário responsável ou destinatário e limitar a dez registros. A composição não deve capturar exceções genéricas. A primeira versão deve conter apenas aprovações, notificações, desvios, CAPAs e treinamentos cuja relação com o usuário seja inequívoca; lotes e amostras globais ficam fora.

- [ ] **Step 4: Executar testes unitários e inspeção de consultas**

Adicionar `assertNumQueries` para impedir uma consulta por item e executar:

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_personal_area.py
```

Expected: PASS.

- [ ] **Step 5: Commitar o contrato sem apresentação**

```bash
git add base/ui/personal_area.py tests/test_personal_area.py
git diff --cached --check
git commit -m "feat: add permission-scoped personal area service"
```

---

### Task 3: Publicar a página Minha Área em PT-BR

**Files:**
- Create: `templates/app/personal_area.html`
- Modify: `base/ui/views.py`
- Modify: `base/ui/urls.py`
- Modify: `templates/includes/sidebar.html`
- Modify: `tests/test_personal_area.py`
- Modify: `TEMPLATES.md`

**Interfaces:**
- Consumes: `build_personal_area(request)` da Task 2.
- Produces: rota nomeada `app:personal_area` em `/app/minha-area/` e `PersonalAreaView`.

- [ ] **Step 1: Escrever testes vermelhos da rota, login, conteúdo e acessibilidade**

Cobrir redirecionamento anônimo, HTTP 200 autenticado, ausência de dados de outro usuário, textos acentuados, heading único, estados vazios e `aria-current="page"` no sidebar.

- [ ] **Step 2: Executar e confirmar `NoReverseMatch`**

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_personal_area.py -k 'view or template or sidebar'
```

Expected: FAIL porque `app:personal_area` não existe.

- [ ] **Step 3: Implementar view e rota**

```python
class PersonalAreaView(LoginRequiredMixin, TemplateView):
    template_name = 'app/personal_area.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sections'] = build_personal_area(self.request)
        return context
```

Registrar `path('minha-area/', views.PersonalAreaView.as_view(), name='personal_area')` antes das rotas genéricas de módulo.

- [ ] **Step 4: Criar template responsivo e link de Visão geral**

O template deve usar componentes e tokens existentes, renderizar um cartão por seção, apresentar `empty_message` quando a coleção estiver vazia e nunca consultar models. O link “Minha área” deve ficar em “Visão geral”, entre “Aplicativos” e os workspaces.

- [ ] **Step 5: Executar testes de UI e documentação**

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_personal_area.py tests/test_app_ui.py \
  tests/test_responsive_layout_css.py
```

Expected: PASS.

- [ ] **Step 6: Commitar**

```bash
git add base/ui/views.py base/ui/urls.py templates/app/personal_area.html \
  templates/includes/sidebar.html tests/test_personal_area.py TEMPLATES.md
git diff --cached --check
git commit -m "feat: add secure personal area workspace"
```

---

### Task 4: Implementar busca global escopada no servidor

**Files:**
- Create: `base/ui/search.py`
- Create: `tests/test_global_search.py`
- Modify: `base/ui/views.py`
- Modify: `base/ui/urls.py`

**Interfaces:**
- Consumes: `get_visible_modules(user)`, `ResourceConfig.search_fields` e `ResourceConfig.get_queryset(request)`.
- Produces: `search_visible_resources(request, query, *, limit=20) -> tuple[GlobalSearchResult, ...]` e endpoint `app:global_search`.

- [ ] **Step 1: Escrever testes vermelhos de escopo e limites**

Cobrir consulta com menos de três caracteres, recurso sem permissão, registro excluído pelo `queryset_scope`, limite global de vinte resultados, limite de cinco por recurso e URL de detalhe resolvida no servidor.

- [ ] **Step 2: Executar e confirmar erro de importação**

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_global_search.py
```

Expected: ERROR porque `base.ui.search` ainda não existe.

- [ ] **Step 3: Implementar busca com queryset do recurso**

O núcleo deve usar:

```python
queryset = resource.get_queryset(request)
criteria = Q()
for field_name in resource.search_fields:
    criteria |= Q(**{f'{field_name}__icontains': normalized_query})
objects = queryset.filter(criteria).distinct()[:per_resource_limit]
```

O serviço deve retornar dataclasses serializáveis pela view, nunca usar `_default_manager` diretamente e ignorar somente `FieldError` de configuração inválida, registrando o recurso mal configurado com `logger.exception`.

- [ ] **Step 4: Criar endpoint somente GET autenticado**

O endpoint deve retornar `{'results': [...]}`, exigir requisição autenticada, rejeitar método diferente de GET e não usar o cabeçalho `X-Requested-With` como mecanismo de segurança.

- [ ] **Step 5: Executar testes direcionados**

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_global_search.py tests/test_knowledge_ui_registry.py
```

Expected: PASS.

- [ ] **Step 6: Commitar o backend**

```bash
git add base/ui/search.py base/ui/views.py base/ui/urls.py tests/test_global_search.py
git diff --cached --check
git commit -m "feat: add scoped global resource search"
```

---

### Task 5: Conectar busca global e paleta de comandos ao shell

**Files:**
- Create: `static/js/global-search.js`
- Create: `static/js/command-palette.js`
- Create: `templates/includes/components/command_palette.html`
- Modify: `templates/base.html`
- Modify: `tests/test_global_search.py`
- Modify: `tests/test_app_ui.py`
- Modify: `TEMPLATES.md`

**Interfaces:**
- Consumes: endpoint `app:global_search` e navegação já autorizada no contexto do shell.
- Produces: busca com debounce, resultados acessíveis e paleta acionada por `Ctrl+K`/`⌘K`.

- [ ] **Step 1: Escrever testes vermelhos do contrato HTML e JavaScript**

Os testes devem exigir campo com rótulo “Buscar no sistema”, região de resultados com `aria-live="polite"`, navegação por setas, Escape para fechar, debounce mínimo de 250 ms, cancelamento da requisição anterior e comandos gerados somente a partir de links já renderizados para o usuário.

- [ ] **Step 2: Executar e confirmar ausência dos assets**

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_global_search.py tests/test_app_ui.py -k 'search or palette'
```

Expected: FAIL porque os assets e atributos ainda não existem.

- [ ] **Step 3: Implementar busca progressiva e segura**

`global-search.js` deve usar `AbortController`, `URLSearchParams`, `textContent` para conteúdo retornado e tratamento explícito de estados carregando, vazio e indisponível. Não deve inserir HTML retornado pelo servidor.

- [ ] **Step 4: Implementar paleta sobre comandos autorizados**

A paleta deve indexar links de navegação existentes marcados com `data-command-label` e `data-command-url`; ela não deve manter catálogo hardcoded de rotas. Assim, um comando só existe quando o servidor já autorizou e renderizou o destino.

- [ ] **Step 5: Executar suíte de shell, acessibilidade e segurança**

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_global_search.py tests/test_app_ui.py \
  tests/test_workspace_ui.py tests/test_dashboard_hub.py
.venv/bin/ruff check base/ui tests/test_global_search.py
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check
```

Expected: todos os comandos terminam com código zero.

- [ ] **Step 6: Documentar e commitar**

```bash
git add static/js/global-search.js static/js/command-palette.js \
  templates/includes/components/command_palette.html templates/base.html \
  tests/test_global_search.py tests/test_app_ui.py TEMPLATES.md
git diff --cached --check
git commit -m "feat: add accessible global search and command palette"
```

---

### Task 6: Gate final da Entrega A

**Files:**
- Modify only if evidence fails: files already listed in Tasks 1–5.

**Interfaces:**
- Consumes: todos os contratos da Entrega A.
- Produces: evidência de que a UX segura está pronta para revisão antes da Agenda.

- [ ] **Step 1: Executar verificações estáticas e Django**

```bash
.venv/bin/ruff check .
DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check
```

Expected: código zero.

- [ ] **Step 2: Executar suíte direcionada completa**

```bash
DATABASE_URL=sqlite:///baseline_base.sqlite3 \
TEST_DATABASE_URL=sqlite:///test_db.sqlite3 \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest -q tests/test_personal_area.py tests/test_global_search.py \
  tests/test_app_ui.py tests/test_workspace_ui.py tests/test_dashboard_hub.py \
  tests/test_responsive_layout_css.py tests/test_knowledge_ui_registry.py
```

Expected: PASS sem testes ignorados inesperadamente.

- [ ] **Step 3: Executar revisão manual responsiva e permissionada**

Validar em 360 px, 768 px e 1440 px: sidebar aberto/recolhido, domínio ativo, Minha Área vazia e preenchida, busca por teclado, paleta, tema claro/escuro e usuário com permissões restritas.

- [ ] **Step 4: Registrar resultado e abrir o planejamento da Agenda**

Somente após o gate verde, criar a especificação da Entrega B cobrindo models, migrations recriadas sobre o projeto atual, APIs, permissões, menu, integração com Minha Área, trilha de auditoria e documentação funcional.

## Acceptance Criteria

- Sidebar exibe somente módulos autorizados e agrupados em português correto.
- Minha Área nunca apresenta registros pertencentes exclusivamente a outro usuário.
- Seção sem permissão não aparece e sua consulta não é executada.
- Busca global respeita `ResourceConfig.get_queryset(request)` em todos os recursos.
- Paleta não cria comandos para links ausentes por permissão.
- Nenhum template ou stylesheet global do repositório de origem é copiado integralmente.
- Testes direcionados, Ruff e `manage.py check` passam.
- Documentação do shell e das permissões fica atualizada.

## Subsequent Project Gates

- **Agenda:** aprovar modelo de responsabilidade, recorrência, prazos e relação com workflow antes das migrations.
- **Regulatório:** aprovar taxonomia ANVISA, estados, assinatura, evidências e retenção antes das APIs.
- **Notificações:** distinguir eventos obrigatórios de preferências optativas e registrar tentativas de entrega.
- **Comissões:** aprovar competência, estorno, arredondamento, fechamento e integração contábil.
- **Logística:** aprovar reserva, expedição, cadeia de custódia, devolução e integração fiscal/estoque em transação.
- **OEE, Autoinspeção e PIF:** produzir PRD, modelagem, riscos GxP, critérios de aceitação e plano CSV próprios.
