# RAG Chat Offcanvas Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ocultar o módulo Conhecimento RAG da navegação e apresentar o chat RAG global em um painel lateral Bootstrap aberto pela direita.

**Architecture:** O módulo `knowledge` permanece no registry, mas ganha uma flag declarativa para não integrar os módulos visíveis usados pelo menu e pela página Aplicativos. O chat global preserva endpoint, permissão e lógica de sessão; somente o contêiner visual passa a usar o `offcanvas` nativo do Bootstrap, enquanto o botão se torna um elemento fixo independente para não criar um stacking context abaixo do backdrop.

**Tech Stack:** Python 3, Django, Django Templates, Bootstrap 5, JavaScript, CSS3 e pytest.

## Global Constraints

- Preservar o endpoint `/api/knowledge/chat/` e a permissão `knowledge.view_ragchatsession`.
- Não importar o fluxo de geração de relatórios do `sistema_assorrp_v2`.
- Não excluir o app `knowledge`, modelos, rotas, APIs ou telas administrativas.
- Preservar a renderização segura de conteúdo remoto com `textContent`.
- Manter compatibilidade com `templates/app/resource_chat.html`, que compartilha `static/js/rag-chat.js`.
- Seguir TDD: cada mudança de produção deve ser precedida por um teste que falhe pelo motivo esperado.

---

## File Structure

- `base/ui/registry.py`: declara a visibilidade de navegação dos módulos e filtra os módulos apresentados ao usuário.
- `templates/includes/rag_chat.html`: contém o botão flutuante e a estrutura Bootstrap do painel lateral global.
- `static/js/rag-chat.js`: mantém a lógica do RAG e integra o foco ao evento de abertura do offcanvas.
- `static/css/app.css`: posiciona o botão acima do footer e dimensiona o painel lateral e suas regiões.
- `tests/test_knowledge_ui_registry.py`: prova que o módulo permanece registrado, mas não é navegável.
- `tests/test_app_ui.py`: prova a visibilidade por permissão e o contrato HTML/CSS do layout autenticado.
- `tests/test_rag_chat_frontend.py`: prova o contrato seguro e a integração Bootstrap do partial e do cliente.
- `tests/test_responsive_layout_css.py`: prova a ordem de empilhamento e os offsets responsivos do botão.
- `README.md`: documenta o novo ponto de entrada do assistente e a ocultação intencional do módulo técnico.

---

### Task 1: Ocultar Conhecimento RAG da navegação sem remover o registry

**Files:**
- Modify: `tests/test_knowledge_ui_registry.py:1-35`
- Modify: `base/ui/registry.py:379-394`
- Modify: `base/ui/registry.py:4223-4278`
- Modify: `base/ui/registry.py:4525-4532`

**Interfaces:**
- Consumes: `ModuleConfig`, `get_module(module_slug)` e `get_visible_modules(user)`.
- Produces: `ModuleConfig.show_in_navigation: bool`, com padrão `True`; o módulo `knowledge` usa `False`.

- [ ] **Step 1: Escrever o teste que exige registry preservado e navegação oculta**

Alterar o import do registry e adicionar o teste abaixo em `KnowledgeUiRegistryTests`:

```python
from base.ui.registry import get_module, get_visible_modules


def test_knowledge_module_stays_registered_but_is_hidden_from_navigation(self):
    self.user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label='knowledge',
            codename='view_ragchatsession',
        )
    )

    module = get_module('knowledge')
    visible_slugs = {item.slug for item in get_visible_modules(self.user)}
    response = self.client.get(reverse('app:index'))

    self.assertIsNotNone(module)
    self.assertNotIn('knowledge', visible_slugs)
    self.assertEqual(response.status_code, 200)
    self.assertNotContains(response, 'Conhecimento RAG')
    self.assertNotContains(response, '/app/knowledge/')
    self.assertContains(response, 'id="rag-chat-root"')
```

- [ ] **Step 2: Executar o teste e confirmar a falha correta**

Run:

```bash
set -a
source .env
set +a
.venv/bin/pytest -q tests/test_knowledge_ui_registry.py::KnowledgeUiRegistryTests::test_knowledge_module_stays_registered_but_is_hidden_from_navigation
```

Expected: FAIL em `self.assertNotIn('knowledge', visible_slugs)` porque o módulo ainda integra `get_visible_modules()`.

- [ ] **Step 3: Adicionar a flag declarativa e marcar o módulo knowledge como oculto**

Adicionar o campo ao final de `ModuleConfig` para preservar todas as chamadas posicionais existentes:

```python
@dataclass(frozen=True)
class ModuleConfig:
    slug: str
    label: str
    description: str
    icon: str = 'feather-grid'
    resources: tuple[ResourceConfig, ...] = field(default_factory=tuple)
    operational_permission: str = ''
    show_in_navigation: bool = True
```

No fechamento do módulo técnico `knowledge`, inserir a flag depois da tupla de recursos:

```python
            ResourceConfig(
                'ingestion-logs',
                'Logs de ingestão RAG',
                KnowledgeIngestionLog,
                ('source', 'document', 'status', 'chunks_created', 'started_at', 'completed_at'),
                ('source__code', 'source__title', 'error_message'),
                read_only=True,
            ),
        ),
        show_in_navigation=False,
    ),
```

Alterar o filtro de apresentação:

```python
def get_visible_modules(user):
    if not getattr(user, 'is_authenticated', False):
        return ()
    return tuple(
        replace(module, resources=visible_resources)
        for module in MODULES
        if module.show_in_navigation
        and (visible_resources := module.visible_resources(user))
    )
```

- [ ] **Step 4: Executar os testes do registry e da página Aplicativos**

Run:

```bash
.venv/bin/pytest -q tests/test_knowledge_ui_registry.py tests/test_app_ui.py::AppUiFoundationTests::test_authenticated_layout_loads_global_rag_chat_with_permission
```

Expected: PASS; o módulo não aparece na navegação e o chat global continua condicionado à permissão.

- [ ] **Step 5: Commitar a ocultação declarativa**

```bash
git add base/ui/registry.py tests/test_knowledge_ui_registry.py
git commit -m "feat: hide RAG knowledge from app navigation"
```

---

### Task 2: Converter o chat global para Bootstrap offcanvas

**Files:**
- Modify: `tests/test_rag_chat_frontend.py:7-39`
- Modify: `tests/test_app_ui.py:202-263`
- Modify: `tests/test_responsive_layout_css.py:100-128`
- Modify: `templates/includes/rag_chat.html:1-53`
- Modify: `static/js/rag-chat.js:101-157`
- Modify: `static/js/rag-chat.js:218-230`
- Modify: `static/css/app.css:571-646`
- Modify: `static/css/app.css:648-763`
- Modify: `static/css/app.css:811-858`

**Interfaces:**
- Consumes: elemento `[data-rag-chat-endpoint]`, endpoint `/api/knowledge/chat/`, eventos Bootstrap `shown.bs.offcanvas` e contrato do chat dedicado.
- Produces: botão `.rag-chat__toggle` com `data-bs-toggle="offcanvas"`; painel `#rag-chat-panel.offcanvas.offcanvas-end`; cliente que foca o compositor quando o painel termina de abrir.

- [ ] **Step 1: Escrever os testes do contrato Bootstrap antes do markup**

Acrescentar a `tests/test_rag_chat_frontend.py`:

```python
def test_global_widget_uses_bootstrap_offcanvas_without_manual_visibility_control():
    template = (ROOT / 'templates/includes/rag_chat.html').read_text(encoding='utf-8')
    script = (ROOT / 'static/js/rag-chat.js').read_text(encoding='utf-8')

    assert 'data-bs-toggle="offcanvas"' in template
    assert 'data-bs-target="#rag-chat-panel"' in template
    assert 'class="offcanvas offcanvas-end rag-chat__panel"' in template
    assert 'data-bs-dismiss="offcanvas"' in template
    assert 'aria-labelledby="rag-chat-title"' in template
    assert 'shown.bs.offcanvas' in script
    assert 'panel.hidden =' not in script
    assert 'function openPanel()' not in script
    assert 'function closePanel(' not in script
```

Atualizar `test_authenticated_layout_loads_global_rag_chat_with_permission` em `tests/test_app_ui.py` com:

```python
assert 'data-bs-toggle="offcanvas"' in content
assert 'offcanvas offcanvas-end rag-chat__panel' in content
```

Substituir `test_rag_chat_hidden_panel_is_not_overridden_by_panel_display_rule` por:

```python
def test_rag_chat_offcanvas_uses_reference_width_contract(self):
    css = Path('static/css/app.css').read_text()

    panel = re.search(r'\.rag-chat \.rag-chat__panel\s*\{(?P<body>[^}]*)\}', css)

    assert panel is not None
    assert re.search(r'width:\s*min\(560px,\s*96vw\)', panel.group('body'))
```

- [ ] **Step 2: Atualizar o teste responsivo para validar o botão, não o contêiner**

Em `test_rag_chat_toggle_stays_above_the_fixed_footer`, substituir a busca do bloco do chat por:

```python
chat_block = re.search(
    r'(?m)^\.rag-chat \.rag-chat__toggle\s*\{(?P<body>[^}]*)\}',
    css,
)
```

E substituir a asserção mobile por:

```python
assert re.search(
    r'\.rag-chat \.rag-chat__toggle\s*\{[^}]*bottom:\s*120px',
    mobile_block.group('body'),
    re.S,
)
```

- [ ] **Step 3: Executar os testes e confirmar as falhas corretas**

Run:

```bash
.venv/bin/pytest -q \
  tests/test_rag_chat_frontend.py::test_global_widget_uses_bootstrap_offcanvas_without_manual_visibility_control \
  tests/test_app_ui.py::AppUiFoundationTests::test_authenticated_layout_loads_global_rag_chat_with_permission \
  tests/test_app_ui.py::AppUiFoundationTests::test_rag_chat_offcanvas_uses_reference_width_contract \
  tests/test_responsive_layout_css.py::test_rag_chat_toggle_stays_above_the_fixed_footer
```

Expected: FAIL por ausência das classes/atributos offcanvas, presença de `panel.hidden` e largura antiga de 420 px.

- [ ] **Step 4: Substituir o partial global pela estrutura offcanvas**

Substituir `templates/includes/rag_chat.html` por:

```django
<section
    id="rag-chat-root"
    class="rag-chat"
    data-rag-chat-endpoint="/api/knowledge/chat/"
    aria-label="Assistente do manual RGN Farma System"
>
    <button
        type="button"
        class="rag-chat__toggle"
        data-bs-toggle="offcanvas"
        data-bs-target="#rag-chat-panel"
        aria-controls="rag-chat-panel"
        aria-label="Abrir assistente do manual"
    >
        <i class="feather-message-circle" aria-hidden="true"></i>
    </button>

    <div
        id="rag-chat-panel"
        class="offcanvas offcanvas-end rag-chat__panel"
        tabindex="-1"
        aria-labelledby="rag-chat-title"
    >
        <div class="offcanvas-header rag-chat__header">
            <div>
                <h2 id="rag-chat-title" class="offcanvas-title h5 mb-0">Assistente RGN Farma System</h2>
                <span>Consulta ao manual do ERP — somente leitura</span>
            </div>
            <button
                type="button"
                class="btn-close"
                data-bs-dismiss="offcanvas"
                aria-label="Fechar assistente"
            ></button>
        </div>

        <div class="offcanvas-body rag-chat__body p-0">
            <div class="rag-chat__messages" role="log" aria-live="polite" aria-relevant="additions"></div>
            <div class="rag-chat__composer">
                <p class="rag-chat__status" role="status" aria-live="polite" data-rag-chat-status></p>
                <button type="button" class="btn btn-light btn-sm" data-rag-chat-retry hidden>
                    Tentar novamente
                </button>
                <form class="rag-chat__form no-loader">
                    <label class="sr-only" for="rag-chat-question">Mensagem para o assistente</label>
                    <textarea
                        id="rag-chat-question"
                        name="question"
                        class="form-control"
                        rows="3"
                        maxlength="4000"
                        placeholder="Ex.: Como cadastro uma fórmula mestra?"
                        required
                    ></textarea>
                    <div class="d-flex gap-2">
                        <button type="button" class="btn btn-light btn-sm" data-rag-chat-new>
                            Nova conversa
                        </button>
                        <button type="submit" class="btn btn-primary flex-fill">
                            <span class="rag-chat__submit-label">Enviar</span>
                            <span class="rag-chat__spinner" aria-hidden="true"></span>
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</section>
```

- [ ] **Step 5: Delegar a abertura e o fechamento ao Bootstrap no cliente**

Remover de `init(root)` as variáveis `toggle` e `close`, as funções `openPanel()` e `closePanel()` e os listeners manuais correspondentes. Após a validação dos elementos obrigatórios, adicionar somente o foco pós-animação:

```javascript
if (panel && panel.classList.contains('offcanvas')) {
    panel.addEventListener('shown.bs.offcanvas', function () {
        input.focus();
    });
}
```

Não alterar `submitQuestion`, `newConversation`, `retry`, `appendMessage`, `apiErrorMessage` ou o listener de submit.

- [ ] **Step 6: Reestruturar o CSS para evitar que o backdrop cubra o painel**

Mover o posicionamento fixo e o `z-index` do contêiner para o botão:

```css
.rag-chat .rag-chat__toggle {
    position: fixed;
    right: 24px;
    bottom: 90px;
    z-index: 1050;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    color: #fff;
    background: #174ea6;
    border: 1px solid #0b3a82;
    border-radius: 50%;
    box-shadow: 0 14px 28px rgba(24, 33, 48, 0.24);
    cursor: pointer;
}
```

Substituir as regras do painel e cabeçalho por:

```css
.rag-chat .rag-chat__panel {
    width: min(560px, 96vw);
    background: #fff;
    border-left: 1px solid #cbd5e1;
}

.rag-chat .rag-chat__header {
    gap: 12px;
    padding: 16px 20px;
    border-bottom: 1px solid #e2e8f0;
}

.rag-chat .rag-chat__header span {
    display: block;
    margin-top: 2px;
    color: #64748b;
    font-size: 12px;
}

.rag-chat .rag-chat__body {
    display: flex;
    min-height: 0;
    flex-direction: column;
    overflow: hidden;
}
```

Complementar a região de mensagens sem alterar bubbles e citações:

```css
.rag-chat .rag-chat__messages {
    display: grid;
    min-height: 320px;
    flex: 1 1 auto;
    align-content: start;
    gap: 12px;
    overflow-y: auto;
    padding: 16px;
    background: #f8fafc;
}

.rag-chat .rag-chat__composer {
    flex: 0 0 auto;
    background: #fff;
    border-top: 1px solid #e2e8f0;
}
```

Remover `.rag-chat .rag-chat__panel[hidden]`, `.rag-chat .rag-chat__close` e o ajuste mobile antigo que desloca `.rag-chat__panel`. Atualizar somente os offsets responsivos do botão:

```css
@media (max-width: 1024px) {
    .rag-chat .rag-chat__toggle {
        right: 16px;
        bottom: 82px;
    }
}

@media (max-width: 575.98px) {
    .rag-chat .rag-chat__toggle {
        bottom: 120px;
    }
}
```

Manter `.rag-chat.rag-chat--dedicated { position: static; min-height: 65vh; }` para o chat embutido.

- [ ] **Step 7: Executar todos os testes direcionados do frontend e layout**

Run:

```bash
.venv/bin/pytest -q \
  tests/test_rag_chat_frontend.py \
  tests/test_responsive_layout_css.py \
  tests/test_app_ui.py::AppUiFoundationTests::test_authenticated_layout_hides_global_rag_chat_without_permission \
  tests/test_app_ui.py::AppUiFoundationTests::test_authenticated_layout_loads_global_rag_chat_with_permission \
  tests/test_app_ui.py::AppUiFoundationTests::test_rag_chat_offcanvas_uses_reference_width_contract \
  tests/test_additional_resource_views.py::AdditionalResourceViewsTests::test_chat_view_resolves_and_renders_properly
```

Expected: PASS; o chat global usa offcanvas e o chat dedicado continua renderizando o endpoint e o cliente compartilhado.

- [ ] **Step 8: Commitar a conversão visual**

```bash
git add \
  templates/includes/rag_chat.html \
  static/js/rag-chat.js \
  static/css/app.css \
  tests/test_rag_chat_frontend.py \
  tests/test_responsive_layout_css.py \
  tests/test_app_ui.py
git commit -m "feat: present RAG chat in Bootstrap offcanvas"
```

---

### Task 3: Documentar e verificar a integração completa

**Files:**
- Modify: `README.md:182-188`
- Verify: `docs/superpowers/specs/2026-08-26-rag-chat-offcanvas-navigation-design.md`

**Interfaces:**
- Consumes: comportamento implementado nas Tasks 1 e 2.
- Produces: documentação operacional coerente e evidência final de testes, checks Django e integridade do diff.

- [ ] **Step 1: Atualizar a documentação funcional do assistente**

Substituir o parágrafo inicial de `## Assistente RAG do manual` por:

```markdown
O endpoint `POST /api/knowledge/chat/` e o assistente global exigem a permissão
`knowledge.view_ragchatsession`. O botão flutuante abre o chat em um painel
lateral pela direita; o módulo técnico **Conhecimento RAG** não aparece no menu
nem na grade de aplicativos. As conversas têm isolamento por usuário e o
assistente opera em modo **somente leitura**: consulta o corpus elegível do
manual, devolve citações e não executa SQL, workflows ou mutações no ERP.
```

- [ ] **Step 2: Executar checks do Django e testes integrados afetados**

Run:

```bash
set -a
source .env
set +a
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/pytest -q \
  tests/test_knowledge_ui_registry.py \
  tests/test_rag_chat_frontend.py \
  tests/test_responsive_layout_css.py \
  tests/test_app_ui.py \
  tests/test_additional_resource_views.py \
  tests/test_knowledge_api.py \
  tests/test_knowledge_chat_service.py
```

Expected: `System check identified no issues`, `No changes detected` e todos os testes selecionados passando.

- [ ] **Step 3: Validar formatação e ausência de alterações acidentais**

Run:

```bash
git diff --check
git status --short
git diff --stat
```

Expected: nenhum erro em `git diff --check`; somente `README.md` permanece sem commit nesta task.

- [ ] **Step 4: Commitar a documentação**

```bash
git add README.md
git commit -m "docs: describe RAG chat offcanvas access"
```

- [ ] **Step 5: Fazer a verificação pós-commit**

Run:

```bash
.venv/bin/pytest -q \
  tests/test_knowledge_ui_registry.py \
  tests/test_rag_chat_frontend.py \
  tests/test_responsive_layout_css.py
git status --short
git log -4 --oneline
```

Expected: todos os testes passam; `git status --short` não apresenta arquivos e o histórico contém os commits de navegação, offcanvas, documentação e design.
