# Global Sticky Footer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exibir um único rodapé global no fim da viewport em todas as telas, inclusive no login, sem sobrepor conteúdo e sem os itens “Ajuda”, “Termos” e “Privacidade”.

**Architecture:** Extrair o conteúdo do rodapé para um include Django compartilhado e consumi-lo pelos dois page shells existentes: `templates/base.html` e `templates/registration/login.html`. Aplicar sticky footer com contêineres Flexbox próprios, mantendo o `<footer>` no fluxo do documento e isolando os seletores do tema Duralux.

**Tech Stack:** Django 6, Django Templates, HTML5 semântico, CSS3 Flexbox, Bootstrap 5, pytest-django.

## Global Constraints

- Toda a UX/UI e todos os testes textuais devem permanecer em português do Brasil, com acentuação.
- O rodapé deve exibir somente copyright, ano atual, “RGN Farma System” e “Versão 1.0”.
- “Ajuda”, “Termos” e “Privacidade” não podem existir no rodapé renderizado.
- O rodapé deve ficar no fim da viewport em páginas curtas e depois do conteúdo em páginas longas.
- Não usar `position: fixed`, `bottom` ou `z-index` no rodapé.
- O rodapé deve permanecer oculto na impressão.
- Não alterar rodapés locais de cartões, modais, paginação ou formulários.
- Preservar as alterações locais preexistentes que não pertencem a esta funcionalidade.

---

## File Structure

- Create: `templates/includes/footer.html` — única fonte de verdade para o conteúdo semântico do rodapé.
- Create: `tests/test_global_footer.py` — contrato de inclusão e renderização do rodapé nos dois page shells.
- Modify: `templates/base.html:182-208` — identificar o page shell autenticado e consumir o include.
- Modify: `templates/registration/login.html:14-64` — transformar o login em page shell e consumir o include.
- Modify: `static/css/app.css:140-150,850-870` — implementar Flexbox, estilo compartilhado e responsividade.
- Modify: `tests/test_responsive_layout_css.py:132-160,364-415` — proteger o sticky footer e a ausência de sobreposição.

### Task 1: Componente compartilhado e contrato de renderização

**Files:**
- Create: `templates/includes/footer.html`
- Create: `tests/test_global_footer.py`
- Modify: `templates/base.html:196-208`
- Modify: `templates/registration/login.html:61-63`

**Interfaces:**
- Consumes: contexto padrão de templates Django e tag `{% now "Y" %}`.
- Produces: include `includes/footer.html` com raiz `<footer class="footer app-footer" data-ui="global-footer">`.

- [ ] **Step 1: Write the failing template contract tests**

Create `tests/test_global_footer.py`:

```python
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


ROOT = Path(settings.BASE_DIR)
REMOVED_LABELS = ('Ajuda', 'Termos', 'Privacidade')


def extract_global_footer(response) -> str:
    html = response.content.decode()
    marker_index = html.index('data-ui="global-footer"')
    start = html.rfind('<footer', 0, marker_index)
    end = html.index('</footer>', marker_index) + len('</footer>')
    return html[start:end]


class GlobalFooterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='usuario-rodape',
            email='rodape@example.com',
            password='senha-local-segura',
        )

    def test_page_shells_use_the_shared_footer_partial(self):
        partial = (ROOT / 'templates/includes/footer.html').read_text()
        base = (ROOT / 'templates/base.html').read_text()
        login = (ROOT / 'templates/registration/login.html').read_text()

        assert 'data-ui="global-footer"' in partial
        assert 'Direitos autorais' in partial
        assert 'Versão 1.0' in partial
        assert "{% include 'includes/footer.html' %}" in base
        assert "{% include 'includes/footer.html' %}" in login
        for label in REMOVED_LABELS:
            assert label not in partial

    def test_login_renders_the_global_footer_without_removed_links(self):
        response = self.client.get(reverse('accounts:login'))

        assert response.status_code == 200
        footer = extract_global_footer(response)
        assert 'Direitos autorais' in footer
        assert 'Versão 1.0' in footer
        for label in REMOVED_LABELS:
            assert label not in footer

    def test_authenticated_app_renders_the_same_global_footer(self):
        self.client.force_login(self.user)

        response = self.client.get('/app/')

        assert response.status_code == 200
        footer = extract_global_footer(response)
        assert 'Direitos autorais' in footer
        assert 'Versão 1.0' in footer
        for label in REMOVED_LABELS:
            assert label not in footer
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `.venv/bin/pytest -q tests/test_global_footer.py`

Expected: FAIL because `templates/includes/footer.html` does not exist and the page shells do not share the include.

- [ ] **Step 3: Create the shared footer partial**

Create `templates/includes/footer.html`:

```django
<footer class="footer app-footer" data-ui="global-footer">
    <p class="fs-11 text-muted fw-medium text-uppercase mb-0 copyright">
        Direitos autorais &copy; {% now "Y" %} RGN Farma System
    </p>
    <span class="app-footer__version fs-11 fw-semibold text-uppercase text-muted">Versão 1.0</span>
</footer>
```

- [ ] **Step 4: Replace the inline footer in the authenticated base**

Replace the footer block in `templates/base.html` with:

```django
        <!-- [ Footer ] start -->
        {% include 'includes/footer.html' %}
        <!-- [ Footer ] end -->
```

- [ ] **Step 5: Include the same footer after the login main region**

In `templates/registration/login.html`, place the include immediately after `</main>`:

```django
    </main>
    {% include 'includes/footer.html' %}
</body>
```

- [ ] **Step 6: Run the tests to verify GREEN**

Run: `.venv/bin/pytest -q tests/test_global_footer.py`

Expected: `3 passed`.

- [ ] **Step 7: Commit the semantic component**

```bash
git add templates/includes/footer.html templates/base.html templates/registration/login.html tests/test_global_footer.py
git commit -m "feat: share global footer across page shells"
```

### Task 2: Sticky footer por Flexbox e comportamento responsivo

**Files:**
- Modify: `templates/base.html:182`
- Modify: `templates/registration/login.html:14-15`
- Modify: `static/css/app.css:140-150,850-870`
- Modify: `tests/test_responsive_layout_css.py:132-160,364-415`

**Interfaces:**
- Consumes: `.app-footer` e `data-ui="global-footer"` produzidos na Task 1.
- Produces: page shells `.app-shell` e `.auth-page-shell`, com conteúdo flexível e rodapé em fluxo normal.

- [ ] **Step 1: Write the failing page-shell layout test**

Add to `tests/test_responsive_layout_css.py`:

```python
def test_page_shells_push_the_global_footer_to_the_viewport_end():
    css = (ROOT / 'static' / 'css' / 'app.css').read_text()
    base = (ROOT / 'templates' / 'base.html').read_text()
    login = (ROOT / 'templates' / 'registration' / 'login.html').read_text()

    assert 'class="nxl-container app-shell"' in base
    assert '<body class="auth-page-shell">' in login
    assert 'min-vh-100' not in login

    authenticated_shell = re.search(
        r'(?m)^\.nxl-container\.app-shell\s*\{(?P<body>[^}]*)\}',
        css,
    )
    authenticated_content = re.search(
        r'(?m)^\.nxl-container\.app-shell\s*>\s*\.nxl-content\s*\{(?P<body>[^}]*)\}',
        css,
    )
    login_shell = re.search(
        r'(?m)^\.auth-page-shell\s*\{(?P<body>[^}]*)\}',
        css,
    )
    login_content = re.search(
        r'(?m)^\.auth-page-shell\s*>\s*\.auth-main\s*\{(?P<body>[^}]*)\}',
        css,
    )

    assert authenticated_shell is not None
    assert authenticated_content is not None
    assert login_shell is not None
    assert login_content is not None
    assert re.search(r'display:\s*flex', authenticated_shell.group('body'))
    assert re.search(r'flex-direction:\s*column', authenticated_shell.group('body'))
    assert re.search(r'min-height:\s*calc\(100dvh\s*-\s*80px\)', authenticated_shell.group('body'))
    assert re.search(r'flex:\s*1\s+0\s+auto', authenticated_content.group('body'))
    assert re.search(r'display:\s*flex', login_shell.group('body'))
    assert re.search(r'flex-direction:\s*column', login_shell.group('body'))
    assert re.search(r'min-height:\s*100dvh', login_shell.group('body'))
    assert re.search(r'flex:\s*1\s+0\s+auto', login_content.group('body'))
```

- [ ] **Step 2: Replace the existing footer-flow assertions with the shared footer contract**

Update the footer selector in `test_rag_chat_toggle_remains_accessible_with_footer_in_document_flow` from `.nxl-container .footer` to `.app-footer`, retaining these assertions:

```python
    assert re.search(r'position:\s*static', footer_block.group('body'))
    assert 'z-index:' not in footer_block.group('body')
    assert re.search(r'bottom:\s*90px', chat_block.group('body'))
```

Replace `test_footer_follows_document_flow_at_desktop_tablet_and_mobile` and `test_mobile_footer_returns_to_document_flow_without_covering_content` with:

```python
def test_global_footer_stays_in_document_flow_without_covering_content():
    css = (ROOT / 'static' / 'css' / 'app.css').read_text()

    footer_block = re.search(r'(?m)^\.app-footer\s*\{(?P<body>[^}]*)\}', css)
    assert footer_block is not None
    footer_body = footer_block.group('body')
    assert re.search(r'position:\s*static', footer_body)
    assert re.search(r'flex:\s*0\s+0\s+auto', footer_body)
    assert not re.search(r'position:\s*fixed', footer_body)
    assert not re.search(r'(?:bottom|z-index):', footer_body)


def test_mobile_global_footer_stacks_its_metadata():
    css = (ROOT / 'static' / 'css' / 'app.css').read_text()
    mobile_block = re.search(
        r'@media \(max-width: 575\.98px\)\s*\{(?P<body>.*?)'
        r'(?=\n@media \(max-width: 360px\))',
        css,
        re.S,
    )

    assert mobile_block is not None
    assert re.search(
        r'\.app-footer\s*\{[^}]*flex-direction:\s*column',
        mobile_block.group('body'),
        re.S,
    )
    assert re.search(
        r'\.app-footer\s*\{[^}]*align-items:\s*flex-start',
        mobile_block.group('body'),
        re.S,
    )
```

- [ ] **Step 3: Run the responsive tests to verify RED**

Run: `.venv/bin/pytest -q tests/test_responsive_layout_css.py`

Expected: FAIL because the page-shell classes and Flexbox rules do not exist yet.

- [ ] **Step 4: Mark both page shells in the templates**

In `templates/base.html`, change the main element to:

```django
    <main id="main-content" class="nxl-container app-shell" tabindex="-1">
```

In `templates/registration/login.html`, change the body and main opening tags to:

```django
<body class="auth-page-shell">
    <main class="auth-main v1 d-flex align-items-center justify-content-center" data-ui="auth-login">
```

- [ ] **Step 5: Implement the desktop and login Flexbox layout**

Replace the current `.nxl-container .footer` block in `static/css/app.css` and add the page-shell rules:

```css
.nxl-container.app-shell {
    display: flex;
    min-height: calc(100vh - 80px);
    min-height: calc(100dvh - 80px);
    flex-direction: column;
}

.nxl-container.app-shell > .nxl-content {
    flex: 1 0 auto;
    padding-bottom: 0;
}

.auth-page-shell {
    display: flex;
    min-height: 100vh;
    min-height: 100dvh;
    flex-direction: column;
}

.auth-page-shell > .auth-main {
    flex: 1 0 auto;
}

.app-footer {
    position: static;
    display: flex;
    flex: 0 0 auto;
    min-height: 66px;
    padding: 20px 30px;
    align-items: center;
    justify-content: space-between;
    background-color: #fff;
    border-top: 1px solid #e5e7eb;
    box-shadow: 0 -6px 18px rgba(40, 60, 80, 0.06);
}
```

- [ ] **Step 6: Apply the responsive footer rule to both page shells**

Replace the mobile `.nxl-container .footer` rules in `static/css/app.css` with:

```css
    .app-footer {
        min-height: 104px;
        padding: 14px 20px;
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
    }
```

Keep the existing print selector `.footer` unchanged so the shared component remains hidden on paper.

- [ ] **Step 7: Run the focused tests to verify GREEN**

Run: `.venv/bin/pytest -q tests/test_global_footer.py tests/test_responsive_layout_css.py`

Expected: all tests in both files PASS.

- [ ] **Step 8: Commit the sticky layout**

```bash
git add templates/base.html templates/registration/login.html static/css/app.css tests/test_responsive_layout_css.py
git commit -m "fix: keep global footer at viewport end"
```

### Task 3: Quality gate and visual acceptance

**Files:**
- Verify: `templates/includes/footer.html`
- Verify: `templates/base.html`
- Verify: `templates/registration/login.html`
- Verify: `static/css/app.css`
- Verify: `tests/test_global_footer.py`
- Verify: `tests/test_responsive_layout_css.py`

**Interfaces:**
- Consumes: componente e page shells concluídos nas Tasks 1 e 2.
- Produces: evidência automatizada, HTTP e visual para os critérios de aceitação.

- [ ] **Step 1: Run the Django and migration checks**

Run: `.venv/bin/python manage.py check`

Expected: `System check identified no issues (0 silenced).`

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`

Expected: `No changes detected`.

- [ ] **Step 2: Run lint and focused regression tests**

Run: `.venv/bin/ruff check tests/test_global_footer.py`

Expected: `All checks passed!`.

Run: `.venv/bin/pytest -q tests/test_global_footer.py tests/test_responsive_layout_css.py tests/test_template_language.py`

Expected: all selected tests PASS.

- [ ] **Step 3: Run the complete SQLite test suite**

Run: `.venv/bin/pytest -q`

Expected: exit code `0`, with no failed tests.

- [ ] **Step 4: Restart the local development server and verify HTTP responses**

Stop the existing `runserver` with `Ctrl-C`, then run:

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
```

In another terminal, run:

```bash
curl -fsS -o /dev/null -w 'health=%{http_code}\n' http://127.0.0.1:8000/health/
curl -fsS -o /dev/null -w 'login=%{http_code}\n' http://127.0.0.1:8000/accounts/login/
```

Expected:

```text
health=200
login=200
```

- [ ] **Step 5: Validate the layout visually at three viewports**

Open `http://127.0.0.1:8000/accounts/login/` and inspect at:

- desktop: `1440 × 900`;
- tablet: `768 × 1024`;
- mobile: `390 × 844`.

For each viewport, verify that the rodapé touches the viewport end on the short login page, does not cover the login card, shows copyright and “Versão 1.0”, and does not show “Ajuda”, “Termos” or “Privacidade”. In mobile, verify that the two metadata items stack without horizontal overflow.

- [ ] **Step 6: Inspect the final diff and preserved local changes**

Run: `git status --short`.

Expected: only the user's preexisting local modifications remain unstaged; no generated files or unrelated changes are introduced.

Run: `git log -3 --oneline`.

Expected: the two implementation commits appear above `f63501b`.

---

## Completion Criteria

- The shared footer is rendered by the authenticated base and login templates.
- The three removed labels are absent from the rendered footer.
- The footer stays in document flow and reaches the viewport end on short pages.
- Long content remains fully visible and scrolls before the footer.
- Desktop, tablet, mobile and print behavior match the specification.
- Focused and complete test suites pass.
- Django check and migration consistency check pass.
- The local development server responds successfully after restart.
