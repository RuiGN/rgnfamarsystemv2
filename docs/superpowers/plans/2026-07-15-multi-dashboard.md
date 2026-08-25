# Multi-dashboard Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Add a tenant-scoped dashboard hub with six area dashboards, ApexCharts widgets, and sidebar navigation.

**Architecture:** A shared `DashboardHubView` resolves an allowed dashboard slug and builds a normalized context from tenant-scoped querysets. A shared template renders KPI cards, chart containers, and empty states; a small page-specific JavaScript module initializes ApexCharts from JSON data. Sidebar links are permission-aware through existing module visibility checks.

**Tech Stack:** Django class-based views, Django ORM aggregations, Bootstrap 5/Duralux, ApexCharts, vanilla JavaScript, Django TestCase.

## Global Constraints

- Every queryset must be filtered by `request.tenant`.
- Dashboard values are real counts or explicit empty states; no fabricated data.
- Existing Duralux/Bootstrap tokens and `feather-*` icons must be reused.
- Existing routes and workspaces must remain compatible.

### Task 1: Dashboard domain context and routes

**Files:**
- Modify: `base/ui/views.py`
- Modify: `base/ui/urls.py`
- Test: `tests/test_dashboard_hub.py`

- [ ] Add a `DashboardHubView(LoginRequiredMixin, TemplateView)` with slugs `executive`, `operations`, `inventory`, `quality`, `regulatory`, and `finance`.
- [ ] Add tenant-scoped metric builders for available models; missing/empty querysets return zero and empty-series metadata.
- [ ] Reject unknown or disabled dashboard modules with `Http404`/`PermissionDenied` consistently with `ModuleWorkspaceMixin`.
- [ ] Add `/app/dashboards/<slug>/` route and tests for access, tenant isolation, and unknown slugs.

### Task 2: Shared dashboard template and design-system styling

**Files:**
- Create: `templates/dashboards/hub.html`
- Modify: `static/css/app.css`

- [ ] Render page header, dashboard selector, date filter controls, KPI cards, chart cards, tables, and explicit empty states using existing Duralux classes.
- [ ] Serialize chart data with `json_script` and preserve keyboard focus/semantic headings.
- [ ] Add responsive grid styles and reduced-motion handling without changing global theme behavior.

### Task 3: ApexCharts initialization

**Files:**
- Create: `static/js/dashboard-hub.js`
- Modify: `templates/base.html`

- [ ] Load ApexCharts only for dashboard pages.
- [ ] Initialize line/bar/donut charts from JSON payloads, skipping charts with no data.
- [ ] Add accessible chart summaries and resilient error handling.

### Task 4: Sidebar and documentation

**Files:**
- Modify: `templates/includes/sidebar.html`
- Modify: `docs/architecture/sidebar-permissions.md`

- [ ] Add a Dashboards submenu with the six routes and active-state handling.
- [ ] Document the permission/module mapping and tenant isolation.

### Task 5: Verification

- [ ] Run targeted dashboard tests.
- [ ] Run Django system checks and the relevant UI test suite.
- [ ] Verify migrations are unchanged unless required, and inspect git diff for secrets or unrelated changes.
