# Sprint 2 Generic Action Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar a infraestrutura genérica, segura e acessível que renderiza e executa ações DRF pela interface HTML.

**Architecture:** Metadados imutáveis descrevem campos, confirmação, permissão, estado e resposta. A descoberta lê as rotas DRF instaladas; o registro é construído uma vez; a view HTML resolve apenas callbacks registrados e preserva autenticação/CSRF/permissões do DRF. A Sprint 2 usa as sete ações de produção como corte vertical, sem ativar ainda o gate global de 253 itens.

**Tech Stack:** Python dataclasses/enum, Django Forms/Views/Templates, Django REST Framework, Bootstrap 5 e JavaScript Fetch API.

## Global Constraints

- Não chamar métodos de domínio diretamente a partir de views HTML.
- Não usar `force_authenticate`, não concatenar URLs e não confiar em usuário/payload do cliente.
- A view de fallback deve ser `csrf_protect` e despachar somente callbacks encontrados no registro.
- Tipos, nomes e assinaturas desta sprint ficam congelados para o catálogo da Sprint 3.
- Textos visíveis e mensagens de erro devem estar em pt-BR acentuado.

---

### Task 1: Tipos imutáveis e descoberta das ações DRF

**Files:**
- Create: `base/ui/actions/__init__.py`
- Create: `base/ui/actions/types.py`
- Create: `base/ui/actions/discovery.py`
- Create: `tests/test_action_discovery.py`

**Interfaces:**
- Produces: `FieldKind`, `SubmissionFormat`, `SuccessBehavior`, `ActionField`, `ActionConfirmation`, `ActionConfig`, `DiscoveredAction` e `discover_post_actions()`.
- Consumes: resolver Django, attributes `callback.actions`, `callback.cls`, `@action.detail`, queryset model e `action_permission_map`.

- [ ] **Step 1: escrever testes vermelhos para os 253 endpoints descobertos**

```python
def test_discovers_each_post_action_once_without_format_suffix_duplicates():
    actions = discover_post_actions()
    assert len(actions) == 253
    assert len({action.key for action in actions}) == 253
    assert sum(not action.detail for action in actions) == 6
    production = next(
        item for item in actions
        if item.app_label == 'production' and item.action_name == 'complete'
    )
    assert production.route_name == 'v1_production:order-complete'
    assert production.model._meta.label == 'production.ProductionOrder'
    assert production.permissions == ('production.change_productionorder',)
```

- [ ] **Step 2: executar o teste e confirmar falha**

Run: `./scripts/test.sh tests/test_action_discovery.py -q`

Expected: FAIL com `ModuleNotFoundError: base.ui.actions`.

- [ ] **Step 3: implementar os tipos congelados**

```python
class FieldKind(StrEnum):
    TEXT = 'text'
    TEXTAREA = 'textarea'
    INTEGER = 'integer'
    DECIMAL = 'decimal'
    BOOLEAN = 'boolean'
    DATE = 'date'
    DATETIME = 'datetime'
    CHOICE = 'choice'
    RELATION = 'relation'
    FILE = 'file'
    HIDDEN = 'hidden'
    JSON = 'json'

class SubmissionFormat(StrEnum):
    JSON = 'json'
    MULTIPART = 'multipart'

class SuccessBehavior(StrEnum):
    RELOAD = 'reload'
    REDIRECT = 'redirect'
    DOWNLOAD = 'download'

@dataclass(frozen=True, slots=True)
class ActionField:
    name: str
    label: str
    kind: FieldKind = FieldKind.TEXT
    required: bool = False
    help_text: str = ''
    placeholder: str = ''
    min_value: Decimal | int | None = None
    max_value: Decimal | int | None = None
    max_length: int | None = None
    choices: tuple[tuple[str, str], ...] = ()
    queryset_factory: Callable[[HttpRequest], QuerySet] | None = None
    initial_factory: Callable[[HttpRequest, Model | None], Any] | None = None
    widget_factory: Callable[[], forms.Widget] | None = None

@dataclass(frozen=True, slots=True)
class ActionConfirmation:
    title: str
    message: str
    typed_phrase: str = ''
    acknowledge_label: str = ''

@dataclass(frozen=True, slots=True)
class ActionConfig:
    module_slug: str
    resource_slug: str
    app_label: str
    model: type[Model]
    action_name: str
    route_name: str
    detail: bool
    label: str
    description: str
    success_message: str
    permissions: tuple[str, ...]
    icon: str = 'feather-play'
    tone: str = 'primary'
    fields: tuple[ActionField, ...] = ()
    allowed_states: tuple[str, ...] = ()
    state_field: str = 'status'
    confirmation: ActionConfirmation | None = None
    submission_format: SubmissionFormat = SubmissionFormat.JSON
    success_behavior: SuccessBehavior = SuccessBehavior.RELOAD
    redirect_route: str = ''

    @property
    def key(self) -> tuple[str, str, str]:
        return self.module_slug, self.resource_slug, self.action_name
```

`ActionConfig.api_url(pk=None)` usa `reverse(self.route_name, kwargs={'pk': pk})` para detalhe e `reverse(self.route_name)` para coleção. `is_available(user, obj=None)` exige `user.has_perms(self.permissions)` e, quando `allowed_states` não estiver vazio, compara `str(getattr(obj, self.state_field))`.

- [ ] **Step 4: implementar descoberta sem duplicar rotas de format suffix**

`discover_post_actions()` percorre apenas o include `api/v1/`, mantém padrões sem `format`, calcula namespace/nome reversível, model, `detail` e permissões. Para mapa customizado usa a tupla `viewset.action_permission_map[action_name]`; no padrão produz uma tupla unitária com `change_<model>` para detalhe ou `add_<model>` para coleção. O teste inclui `ai_agents.run`, que exige duas permissões. A chave de `DiscoveredAction` é `(model._meta.label_lower, action_name, detail)`.

- [ ] **Step 5: executar testes e commit**

Run: `./scripts/test.sh tests/test_action_discovery.py -q`

Expected: PASS com 253 ações, seis de coleção e zero duplicidades.

```bash
git add base/ui/actions tests/test_action_discovery.py
git commit -m "test: specify generic domain action registry"
```

### Task 2: Registro validado e formulário dinâmico

**Files:**
- Create: `base/ui/actions/registry.py`
- Create: `base/ui/actions/forms.py`
- Create: `base/ui/actions/modules/__init__.py`
- Create: `base/ui/actions/modules/production.py`
- Create: `tests/test_action_registry.py`
- Create: `tests/test_action_forms.py`

**Interfaces:**
- Produces: `ActionRegistry`, `action_registry`, `build_action_form(config, request, obj=None)`.
- Consumes: tipos da Task 1 e `base.ui.registry.get_resource()`.

- [ ] **Step 1: escrever testes vermelhos de invariantes**

```python
def test_registry_rejects_duplicate_missing_permission_and_unknown_resource():
    valid = production_action('approve')
    with pytest.raises(ImproperlyConfigured, match='duplicada'):
        ActionRegistry((valid, valid))
    with pytest.raises(ImproperlyConfigured, match='permissão'):
        ActionRegistry((replace(valid, permissions=()),))
    with pytest.raises(ImproperlyConfigured, match='recurso'):
        ActionRegistry((replace(valid, resource_slug='missing'),))

def test_form_builds_decimal_confirmation_and_relation_fields(rf, production_order):
    config = production_complete_config()
    form_class = build_action_form(config, rf.get('/'), production_order)
    form = form_class({'actual_yield_quantity': '98.750', 'confirmation_phrase': 'CONFIRMAR'})
    assert form.is_valid(), form.errors
    assert form.cleaned_payload() == {'actual_yield_quantity': Decimal('98.750')}
```

Testar individualmente os doze `FieldKind`, `choices`, queryset filtrado, JSON válido/inválido, multipart, limites, widget password, campo oculto e frase digitada. Campos extras devem ser ignorados pelo form e não entrar em `cleaned_payload()`.

- [ ] **Step 2: executar testes e confirmar falhas**

Run: `./scripts/test.sh tests/test_action_registry.py tests/test_action_forms.py -q`

Expected: FAIL porque registro e builder não existem.

- [ ] **Step 3: implementar `ActionRegistry`**

```python
class ActionRegistry:
    def __init__(self, configs: Iterable[ActionConfig]):
        self._by_key: dict[tuple[str, str, str], ActionConfig] = {}
        for config in configs:
            self._validate(config)
            if config.key in self._by_key:
                raise ImproperlyConfigured(f'Ação duplicada: {config.key!r}.')
            self._by_key[config.key] = config

    def all(self) -> tuple[ActionConfig, ...]:
        return tuple(self._by_key.values())

    def get(self, module_slug: str, resource_slug: str, action_name: str) -> ActionConfig:
        try:
            return self._by_key[(module_slug, resource_slug, action_name)]
        except KeyError as exc:
            raise Http404('Ação não encontrada.') from exc

    def for_resource(self, module_slug: str, resource_slug: str) -> tuple[ActionConfig, ...]:
        return tuple(c for c in self._by_key.values() if c.key[:2] == (module_slug, resource_slug))
```

`_validate()` exige recurso/model correspondentes, ao menos uma permissão, textos, rota reversível, confirmação para tons `danger`/`warning`, campos únicos e `allowed_states` pertencentes às choices do campo de estado.

- [ ] **Step 4: implementar formulário dinâmico**

Criar uma subclasse `ActionForm` por chamada, mapear cada `FieldKind` para o campo Django equivalente, aplicar widgets Bootstrap e adicionar `confirmation_phrase` quando configurado. `cleaned_payload()` retorna somente nomes declarados; booleanos permanecem booleanos, datas usam ISO, decimals usam string para JSON e arquivos permanecem `UploadedFile` no multipart.

- [ ] **Step 5: cadastrar o corte vertical de produção**

`modules/production.py` contém exatamente `approve`, `release`, `start`, `pause`, `resume`, `complete(actual_yield_quantity: decimal obrigatório)` e `cancel(cancel_reason: textarea obrigatório)`. Todos usam `permissions=('production.change_productionorder',)`, rotas `v1_production:order-<action>`, cópia pt-BR e estados copiados das precondições de `ProductionOrder` em `production/models.py`. `complete` e `cancel` têm confirmação explícita; `cancel` usa tom `danger`.

- [ ] **Step 6: executar testes e commit**

Run: `./scripts/test.sh tests/test_action_registry.py tests/test_action_forms.py tests/test_production.py -q`

Expected: PASS.

```bash
git add base/ui/actions tests/test_action_registry.py tests/test_action_forms.py
git commit -m "feat: add generic action metadata and forms"
```

### Task 3: Contexto, dispatcher DRF e fallback sem JavaScript

**Files:**
- Create: `base/ui/actions/context.py`
- Create: `base/ui/actions/views.py`
- Modify: `base/ui/urls.py`
- Modify: `base/ui/views.py`
- Create: `tests/test_action_dispatch.py`

**Interfaces:**
- Produces: `available_actions(request, resource, obj=None)`, `ResourceActionView` e rotas `app:resource_action`/`app:collection_action`.
- Consumes: `action_registry`, `build_action_form`, `resolve(config.api_url())` e o `HttpRequest` autenticado original.

- [ ] **Step 1: escrever testes de segurança e resposta**

Cobrir GET de formulário, POST sem CSRF (`403`), usuário sem permissão (`403`), objeto inexistente (`404`), ação fora do estado (`409`), payload inválido (`200` com erros), sucesso (`302` com mensagem), erro DRF `400`, `403`, `409` e `500` seguro. Usar `Client(enforce_csrf_checks=True)` e patch apenas no callback resolvido para provar que usuário, cookies e headers permanecem.

Também medir disponibilidade com `assertNumQueries(0)` após o objeto estar carregado e verificar que chamadas repetidas retornam as mesmas configs congeladas; os metadados não podem consultar banco por ação nem reconstruir o registro.

```python
def test_fallback_dispatches_to_registered_drf_callback(client_with_csrf, approved_order):
    url = reverse('app:resource_action', kwargs={
        'module_slug': 'production', 'resource_slug': 'orders',
        'pk': approved_order.pk, 'action_name': 'release',
    })
    response = client_with_csrf.post(url, {'confirm': 'on'}, HTTP_X_REQUEST_ID='ui-123')
    assert response.status_code == 302
    approved_order.refresh_from_db()
    assert approved_order.status == ProductionOrder.Status.RELEASED
```

- [ ] **Step 2: executar testes e confirmar falhas**

Run: `./scripts/test.sh tests/test_action_dispatch.py -q`

Expected: FAIL com rota não encontrada.

- [ ] **Step 3: implementar contexto e rotas**

`available_actions()` retorna somente configurações cujo `detail` coincide, cujo usuário possui a permissão e cujo estado é permitido. Adicionar antes das rotas genéricas com `<int:pk>`:

```python
path(
    '<slug:module_slug>/<slug:resource_slug>/actions/<slug:action_name>/',
    views.CollectionResourceActionView.as_view(), name='collection_action',
),
path(
    '<slug:module_slug>/<slug:resource_slug>/<int:pk>/actions/<slug:action_name>/',
    views.ResourceActionView.as_view(), name='resource_action',
),
```

`ResourceDetailView.get_context_data()` passa `resource_actions`; `ResourceListView` passa `collection_actions`.

- [ ] **Step 4: implementar o dispatcher sem contornar DRF**

As views herdam `LoginRequiredMixin`, `ResourceContextMixin` e `View`, aplicam `method_decorator(csrf_protect, name='dispatch')`, carregam config/obj, validam disponibilidade e form. No POST válido, resolvem `config.api_url(pk)`, garantem que `match.func.cls` e `match.func.actions['post']` correspondem à descoberta registrada, substituem `request.POST` por payload imutável preservando `csrfmiddlewaretoken`, substituem `request.FILES` somente pelos uploads declarados e chamam `match.func(request, **match.kwargs)`. Não usar `force_authenticate`. Renderizar a `Response` antes de ler `.data`; converter erros para o form; em sucesso aplicar `RELOAD`, `REDIRECT` ou `DOWNLOAD` somente conforme a config. Os testes cobrem JSON, multipart e os três comportamentos.

- [ ] **Step 5: executar testes e commit**

Run: `./scripts/test.sh tests/test_action_dispatch.py tests/test_app_ui.py -q`

Expected: PASS.

```bash
git add base/ui/actions base/ui/urls.py base/ui/views.py tests/test_action_dispatch.py
git commit -m "feat: dispatch HTML actions through DRF"
```

### Task 4: Templates, JavaScript e pt-BR

**Files:**
- Create: `templates/app/includes/resource_actions.html`
- Create: `templates/app/resource_action_form.html`
- Modify: `templates/app/resource_detail.html`
- Modify: `templates/app/resource_list.html`
- Modify: `templates/base.html`
- Create: `static/js/resource-actions.js`
- Modify: `static/css/app.css`
- Create: `tests/test_action_frontend.py`

**Interfaces:**
- Produces: botões, formulário acessível, modal progressivo e feedback seguro.
- Consumes: contexto `resource_actions`/`collection_actions`, URLs HTML e metadados do form.

- [ ] **Step 1: escrever testes vermelhos de UI e acentuação**

Testar botões autorizados, ausência para usuário sem permissão/estado incompatível, página de formulário sem JS, atributos `aria-*`, CSRF, `data-action-*`, script carregado com `defer`, ausência de `innerHTML` com resposta remota e mensagens acentuadas. O lint textual normaliza somente strings visíveis extraídas dos templates e campos `label`, `description`, `success_message`, `help_text`, bloqueando as nove formas sem acento aprovadas na especificação.

- [ ] **Step 2: executar testes e confirmar falhas**

Run: `./scripts/test.sh tests/test_action_frontend.py -q`

Expected: FAIL por templates/script ausentes.

- [ ] **Step 3: implementar templates e estilos**

O include renderiza um `<section aria-labelledby="resource-actions-title">`, botões como links para a rota HTML e estado vazio somente quando apropriado. A página genérica usa `<form method="post" enctype>`, `{% csrf_token %}`, mensagens de campo com `role="alert"`, bloco de confirmação e botões “Confirmar ação”/“Cancelar”. Usar classes Bootstrap 5 já disponíveis e adicionar apenas estilos de foco, grupo responsivo e modal em `app.css`.

- [ ] **Step 4: implementar aprimoramento JavaScript progressivo**

`resource-actions.js` intercepta apenas elementos `[data-domain-action]`, abre modal via DOM APIs seguras, carrega o formulário HTML com `fetch(..., {credentials: 'same-origin'})`, envia `FormData`, bloqueia uma única submissão e substitui o documento somente por HTML originado da própria view. Respostas JSON são convertidas com `textContent`; nunca usar `innerHTML` para mensagens da API. Sem JavaScript, links e forms continuam funcionais.

- [ ] **Step 5: executar gate da Sprint 2**

Run: `./scripts/test.sh tests/test_action_discovery.py tests/test_action_registry.py tests/test_action_forms.py tests/test_action_dispatch.py tests/test_action_frontend.py tests/test_app_ui.py tests/test_production.py -q`

Run: `.venv/bin/ruff check base tests/test_action_*.py && .venv/bin/ruff format --check base tests/test_action_*.py && git diff --check`

Expected: todos PASS; registro contém sete ações de produção e o conjunto global descoberto permanece em 253 para a Sprint 3.

- [ ] **Step 6: commit do frontend**

```bash
git add templates/app templates/base.html static/js/resource-actions.js static/css/app.css tests/test_action_frontend.py
git commit -m "feat: add accessible domain action frontend"
```
