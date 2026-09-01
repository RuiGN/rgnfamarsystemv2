# Cosmetics Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adapt the legacy split-login composition into a focused, accessible login for the cosmetics ERP while preserving current authentication contracts.

**Architecture:** Keep `UsernameLoginView` untouched, reduce the template to semantic markup, and isolate page-specific presentation in `auth.css`. Use one local background asset and a traceability process line on desktop; collapse to the branded form on mobile.

**Tech Stack:** Django templates, Bootstrap/Duralux assets already vendored, local CSS/WebP, pytest-django.

## Global Constraints

- Preserve username/password authentication, CSRF, safe `next`, admin redirect and rate limiting.
- Keep the global footer on the login page.
- Do not add remote assets, fonts, JavaScript libraries or password-reset routes.
- Do not mention pharmaceuticals, pharmacovigilance or medicinal products.
- Support 320 px width, short mobile landscape, keyboard focus and `prefers-reduced-motion`.
- Run tests only through `bash scripts/test.sh` or `.venv/bin/python -m <tool>`.

---

## File map

- Modify `templates/registration/login.html`: semantic split layout and unchanged form contract.
- Create `static/css/auth.css`: scoped responsive presentation.
- Copy `static/vendor/duralux/images/login-bg.webp`: local legacy background.
- Modify `tests/test_app_ui.py`: content/auth/accessibility contracts.
- Modify `tests/test_responsive_layout_css.py`: responsive and reduced-motion contracts.
- Preserve `tests/test_global_footer.py`: footer regression.

### Task 1: Freeze the login contracts before redesign

**Files:**
- Modify: `tests/test_app_ui.py`
- Modify: `tests/test_responsive_layout_css.py`
- Verify: `tests/test_global_footer.py`

**Interfaces:**
- Consumes: `reverse('accounts:login')` and current `UsernameLoginView`.
- Produces: regression expectations for the new semantic hooks.

- [ ] **Step 1: Add failing presentation tests**

Assert the rendered page contains `data-ui="auth-login"`, `data-auth-story`, `data-auth-trace`, the four labels “Formulação”, “Produção”, “Qualidade” and “NF-e”, the institutional logo fallback, one username field, one password field, one submit button and the global footer. Assert it does not contain “Farmacovigilância”, “ERP farmacêutico” or “92 Relatórios”.

- [ ] **Step 2: Add failing responsive CSS tests**

Assert `auth.css` exists, all selectors are rooted in `.auth-page-shell`, a 991.98 px media query hides the story panel, a 640 px height query enables top alignment/scrolling, focus-visible is styled, and `@media (prefers-reduced-motion: reduce)` disables transitions/animations.

- [ ] **Step 3: Prove the new tests fail while auth still passes**

Run: `bash scripts/test.sh tests/test_app_ui.py tests/test_responsive_layout_css.py tests/test_global_footer.py -k 'login or auth' -q`

Expected: presentation tests fail; current login/auth/footer tests remain green.

- [ ] **Step 4: Commit the contract tests**

```bash
git add tests/test_app_ui.py tests/test_responsive_layout_css.py
git commit -m "test(ui): define cosmetics login contract"
```

### Task 2: Add the local visual asset and scoped styles

**Files:**
- Create: `static/css/auth.css`
- Create: `static/vendor/duralux/images/login-bg.webp`
- Test: `tests/test_responsive_layout_css.py`

**Interfaces:**
- Produces: `.auth-layout`, `.auth-story`, `.auth-card-column`, `.auth-card`, `.auth-trace`.

- [ ] **Step 1: Copy the approved local background**

Run:

```bash
cp /mnt/2c8d19a3-3bbb-4f90-b09f-9e17c780ce6a/Projects/rgnfarmasystem/static/vendor/duralux/images/login-bg.webp static/vendor/duralux/images/login-bg.webp
```

Verify: `sha256sum` of source and destination must match.

- [ ] **Step 2: Implement `auth.css`**

Define variables under `.auth-page-shell` for `#08162B`, `#3454D1`, `#36D6D0`, `#F4F7FB`, `#283C50` and `#FFFFFF`. Use a flex column shell, a two-column grid with `minmax(0, 1fr) minmax(360px, 460px)`, a background/overlay on `.auth-story`, a white card with visible focus rings, and a four-node traceability line. Keep all selectors scoped to `.auth-page-shell`.

At `max-width: 991.98px`, set the layout to one column, hide `.auth-story`, center the card and allow document scrolling. At `max-height: 640px`, align the card at the top and reduce vertical padding. Under reduced motion, set `animation-duration: 0.01ms`, `animation-iteration-count: 1` and `transition-duration: 0.01ms` for descendants.

- [ ] **Step 3: Run CSS contract tests**

Run: `bash scripts/test.sh tests/test_responsive_layout_css.py -k 'login' -q`

Expected: PASS for asset/CSS contracts; markup-dependent tests may still fail.

- [ ] **Step 4: Commit assets and styles**

```bash
git add static/css/auth.css static/vendor/duralux/images/login-bg.webp tests/test_responsive_layout_css.py
git commit -m "feat(ui): add cosmetics login visual system"
```

### Task 3: Replace the login markup without changing authentication

**Files:**
- Modify: `templates/registration/login.html`
- Test: `tests/test_app_ui.py`
- Test: `tests/test_global_footer.py`

**Interfaces:**
- Consumes: `form`, `next`, `institution_logo_url`, `institution_name`.
- Produces: semantic split page using the CSS hooks from Task 2.

- [ ] **Step 1: Link the scoped stylesheet**

After `app.css`, add:

```django
<link rel="stylesheet" href="{% static 'css/auth.css' %}">
```

- [ ] **Step 2: Build the desktop story panel**

Use one `<section class="auth-story" data-auth-story aria-labelledby="auth-story-title">` with the institution logo, heading “Gestão industrial com rastreabilidade de ponta a ponta”, supporting copy “Da formulação ao recebimento fiscal, cada etapa permanece conectada.” and an ordered trace line containing exactly Formulação, Produção, Qualidade and NF-e.

- [ ] **Step 3: Preserve the form contract in the card column**

Keep `{% csrf_token %}`, `<input type="hidden" name="next" value="{{ next }}">`, `name="username"`, `autocomplete="username"`, `name="password"`, `autocomplete="current-password"`, existing field error IDs/ARIA attributes and `form.non_field_errors`. Use the title “Acesso ao sistema”, support copy “Entre para acessar seus módulos e operações.” and one primary button “Entrar”.

Keep `{% include 'includes/footer.html' %}` after `</main>` inside `<body class="auth-page-shell">`.

- [ ] **Step 4: Run login, authentication and footer tests**

Run: `bash scripts/test.sh tests/test_app_ui.py tests/test_single_instance_auth_access.py tests/test_single_instance_admin_runtime.py tests/test_global_footer.py tests/test_responsive_layout_css.py -k 'login or auth or admin_login or footer' -q`

Expected: PASS.

- [ ] **Step 5: Commit the markup**

```bash
git add templates/registration/login.html tests/test_app_ui.py tests/test_global_footer.py
git commit -m "feat(ui): adapt split login for cosmetics"
```

### Task 4: Visually verify real geometry

**Files:**
- Verify only.

- [ ] **Step 1: Start the isolated target server**

Run the project through its configured local PostgreSQL environment and open `/accounts/login/` without authenticating. Do not reuse a server from another checkout.

- [ ] **Step 2: Inspect desktop and mobile sizes**

Capture 1440×900, 1024×768, 390×844, 320×568 and 844×390. Verify no horizontal overflow, the submit button remains reachable, focus order is username → password → Entrar, the story is hidden below 992 px, and the footer remains in document flow.

- [ ] **Step 3: Inspect reduced motion and error state**

Emulate `prefers-reduced-motion: reduce`, submit invalid credentials and verify the error is announced without layout overlap.

- [ ] **Step 4: Run final login gates**

Run: `bash scripts/test.sh tests/test_app_ui.py tests/test_responsive_layout_css.py tests/test_global_footer.py tests/test_single_instance_auth_access.py tests/test_single_instance_admin_runtime.py -q`

Expected: all tests pass.

- [ ] **Step 5: Verify forbidden copy**

Run: `git grep -n -i -E 'farmacovigil|ERP farmacêutico|92 Relatórios' -- templates/registration static/css/auth.css tests ':!docs/superpowers/**'`

Expected: no matches.
