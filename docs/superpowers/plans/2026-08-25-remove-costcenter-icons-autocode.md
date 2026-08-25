# Remover Centro de Custo, Ícones e Auto-gerar Códigos — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remover o model `CostCenter` e todas as referências; remover todos os ícones Feather dos templates; gerar `code` automaticamente (`PREFIX-SEQ`) em 30 modelos.

**Architecture:** Refatoração em 3 sub-projetos sequenciados (1→2→3). Auto-código via mixin `AutoCodeMixin` + utilitário `base/codegen.py` aplicado por modelo. Remoção de `CostCenter` via migrations que dropam FKs/colunas/tabela. Ícones removidos diretamente nos templates.

**Tech Stack:** Django 5.2, DRF, django-environ, SQLite (`core.settings.sqlite`), pytest-django.

## Global Constraints

- Perfil de execução: `core.settings.sqlite` (manage.py já usa por padrão).
- Sem repositório git neste diretório: os passos de "Commit" são **checkpoints** de verificação (`manage.py check`).
- Verificação primária rápida: `python manage.py check` e `python manage.py migrate` (DB local `db.sqlite3` já migrado).
- Testes: o DB de teste (`test_db.sqlite3`) exige build de schema (~lento na 1ª vez). Para testes que não dependem de schema, use `pytest --no-migrations`. Para smoke tests de behavior, use `python manage.py shell` contra o DB dev.
- Português pt-BR nos verbose_names; seguir padrões existentes (SingleInstanceModel, UniqueConstraint já presentes).
- Não quebrar os perfis `core.settings.production` e `core.settings.test` (mantêm guardas PostgreSQL).

## File Structure

**Novos:**
- `base/codegen.py` — utilitário `generate_code(model_cls)` + `AutoCodeMixin`.

**Modificados (Parte 1 — CostCenter):**
- `costing/models.py`, `costing/admin.py`, `costing/views.py`, `costing/serializers.py`, `costing/urls.py`
- `finance/models.py`, `finance/admin.py`, `finance/views.py`, `finance/serializers.py`
- `production/services.py`, `production/serializers.py`
- `procurement/models.py`, `procurement/admin.py`, `procurement/views.py`, `procurement/serializers.py`
- `base/ui/registry.py`, `base/ui/views.py`, `base/ui/actions/modules/production.py`, `base/ui/actions/inventory.py`
- `governance/demo_seeders.py`, `reports/executors/production.py`, `templates/app/production_order_map.html`
- Novas migrations: `costing/migrations/0005_*`, `finance/migrations/0003_*`, `procurement/migrations/00XX_*`

**Modificados (Parte 2 — Ícones):** `templates/base.html`, `templates/includes/*.html`, `templates/app/*.html`, `templates/{dashboards,workspaces,accounts,registration}/*.html`, `base/ui/views.py`.

**Modificados (Parte 3 — Auto-código):** `base/codegen.py` (novo), 30 arquivos `*/models.py`, respectivas migrations `AlterField(code, blank=True)`, admin/serializers onde `code` era obrigatório.

---

# PARTE 1 — Remover CostCenter e referências

### Task 1.1: Remover FK cost_center dos models de costing

**Files:**
- Modify: `costing/models.py` (classes `StandardCost`, `CostSimulation`, `ProductionCostCapture`)

**Changes:**
- `StandardCost`: remover o `cost_center = models.ForeignKey(CostCenter, ...)` (linhas ~104-109). Remover `CostCenter` do `select_related`/filtros onde aparecer. Remover `models.Index(fields=['cost_center', 'status'])` e `models.Index(fields=['cost_center'])` das `Meta` de StandardCost/CostSimulation.
- `CostSimulation`: remover FK `cost_center` (linhas ~348-353) e o `Index(fields=['cost_center'])`.
- `ProductionCostCapture`: remover FK `cost_center` (linhas ~488-493); alterar a UniqueConstraint `unique_order_center_cost_period` de `fields=['production_order','cost_center','period_start','period_end']` para `fields=['production_order','period_start','period_end']` (renomear p/ `unique_order_cost_period`); remover `Index(fields=['cost_center'])`.
- Manter o `from costing.models import ... CostCenter` removido apenas após a Task 1.5 (o model ainda existe até lá). Por ora, **deixar o import** (ainda usado pelo próprio model CostCenter nesta mesmo arquivo).

- [ ] Step 1: Editar `costing/models.py` removendo as 3 FKs e ajustando constraints/indexes conforme acima.
- [ ] Step 2: `python manage.py check` → esperado: erros de migração pendente (ok por ora); sem SyntaxError.
- [ ] Step 3: Checkpoint — não rodar migrate ainda (aguardar Task 1.8).

### Task 1.2: Remover cost_center de finance

**Files:** `finance/models.py`, `finance/admin.py`, `finance/views.py`, `finance/serializers.py`

**Changes:**
- `finance/models.py`: remover `from costing.models import CostCenter` (linha 10), remover FK `cost_center` em `FinancialTitle` (linhas ~206-212), remover `cost_center` do método `create_from_purchase_order` (param `cost_center=None` linha 277 e kwargs linha 286) e de qualquer `fields`/`search_fields`/`list_display` (linha ~376).
- `finance/admin.py`: remover `'cost_center'` de `list_display`/`search_fields` (linha 63).
- `finance/views.py`: remover `'cost_center'` de filtros/fields (linha 77).
- `finance/serializers.py`: remover `'cost_center'` dos `fields` (linhas 110, 142).

- [ ] Step 1: Editar os 4 arquivos conforme acima.
- [ ] Step 2: `python manage.py check` → sem SyntaxError; erros de migrate pendente ok.

### Task 1.3: Remover cost_center (CharField) de procurement

**Files:** `procurement/models.py`, `procurement/admin.py`, `procurement/views.py`, `procurement/serializers.py`

**Changes:**
- `procurement/models.py`: remover `cost_center = models.CharField('centro de custo', max_length=80, blank=True)` (linha 60).
- `procurement/admin.py`: remover `'cost_center'` de `search_fields` (linha 26).
- `procurement/views.py`: remover `'cost_center'` de `search_fields` (linha 54).
- `procurement/serializers.py`: remover `'cost_center'` de `fields` (linha 54).

- [ ] Step 1: Editar os 4 arquivos.
- [ ] Step 2: `python manage.py check`.

### Task 1.4: Refatorar production/services.calculate_cost e serializers

**Files:** `production/services.py`, `production/serializers.py`

**Changes em `production/services.py::calculate_cost`:**
- Assinatura: `def calculate_cost(self, *, period_start, period_end):` (remover `cost_center`).
- Remover o bloco `if not cost_center.is_active: raise ValidationError({'cost_center': ...})`.
- No filtro de `StandardCost`: remover `cost_center=cost_center,` (linha ~620). A seleção passa a ser por product+unit+status+vigência.
- Nas mensagens de erro que usam chave `{'cost_center': ...}` (linhas ~640, e a do "Custo padrão... ausente"), trocar a chave por `{'period_start': ...}` ou `{'standard_cost': ...}` (manter texto, mudar só a chave de dict de erro).
- No filtro/criação de `ProductionCostCapture`: remover `cost_center=cost_center` do `filter(...)` (linha ~665) e do `ProductionCostCapture(...)` (linha ~673).
- `_audit` payload permanece `{'capture_id': capture.pk}`.

**Changes em `production/serializers.py`:**
- Remover `from costing.models import CostCenter` (linha 6).
- Remover o campo `cost_center = serializers.PrimaryKeyRelatedField(queryset=CostCenter.objects.filter(is_active=True))` (linhas 304-305) e `'cost_center'` de fields se presente.

- [ ] Step 1: Editar `production/services.py` (calculate_cost) conforme acima.
- [ ] Step 2: Editar `production/serializers.py`.
- [ ] Step 3: `python manage.py check`.
- [ ] Step 4: Smoke — `python manage.py shell -c "from production.services import ProductionOrderService; import inspect; print('cost_center' not in inspect.signature(ProductionOrderService.calculate_cost).parameters)"` → esperado `True`.

### Task 1.5: Remover o model CostCenter e seu CRUD (costing)

**Files:** `costing/models.py`, `costing/admin.py`, `costing/views.py`, `costing/serializers.py`, `costing/urls.py`

**Changes:**
- `costing/models.py`: remover a `class CostCenter` inteira (linhas ~31-58). Remover `CostCenter` de quaisquer imports/remoções já feitas. (CostElement permanece.)
- `costing/admin.py`: remover o `CostCenterAdmin`/registro de CostCenter (15 refs).
- `costing/views.py`: remover `CostCenter` do import, `CostCenterSerializer` do import, a `class CostCenterViewSet`, e `cost_center` de `select_related`/`filterset_fields`/`search_fields` das demais viewsets (StandardCostViewSet, CostSimulationViewSet).
- `costing/serializers.py`: remover `CostCenterSerializer` e referências a `cost_center` (9 refs).
- `costing/urls.py`: remover a rota de `CostCenterViewSet` (2 refs).

- [ ] Step 1: Editar os 5 arquivos.
- [ ] Step 2: `python manage.py check` → agora sem referências a CostCenter em código (erros só de migrate pendente).

### Task 1.6: Remover CostCenter do base/ui

**Files:** `base/ui/registry.py`, `base/ui/views.py`, `base/ui/actions/modules/production.py`, `base/ui/actions/inventory.py`

**Changes:**
- `base/ui/registry.py`: remover `CostCenter` do import (linha 51) e de listagens/filtros (linhas 1027, 1336, 1354, 1363-1364, 1374, 1387, 1397) — remover linções `cost_center`/`cost_center__code`/`cost_center__name` de `fields`/`search_fields`/`list_display`/`select_related` do registry de ProductionCostCapture/StandardCost.
- `base/ui/views.py`: remover `.select_related('cost_center')` (linha 1154).
- `base/ui/actions/modules/production.py`: remover `from costing.models import CostCenter` (linha 7), o campo `'cost_center'`/`'Centro de custo'`/`queryset_factory=CostCenter...` (linhas 215-219).
- `base/ui/actions/inventory.py`: remover `cost_center:r` da action `calculate_cost` (linha 43) e `'cost_center': 'Centro de custo'` do mapping (linha 171).

- [ ] Step 1: Editar os 4 arquivos.
- [ ] Step 2: `python manage.py check`.

### Task 1.7: Remover CostCenter de seeders, reports e template

**Files:** `governance/demo_seeders.py`, `reports/executors/production.py`, `templates/app/production_order_map.html`

**Changes:**
- `governance/demo_seeders.py`: remover o bloco que cria `CostCenter` (linhas ~1024, 1076-1093, 1116) e `'cost_center': 'DEMO-PCP'` (linha 799); em `StandardCost` seed, remover `cost_center=cost_center`.
- `reports/executors/production.py`: remover `'cost_center_id'` do relatório (linha 169).
- `templates/app/production_order_map.html`: remover a célula `{{ capture.cost_center }}` (linha 314) e o `<th>` correspondente.

- [ ] Step 1: Editar os 3 arquivos.
- [ ] Step 2: `python manage.py check`.

### Task 1.8: Gerar e rodar migrations; remover histórico obsoleto

**Files:** criar `costing/migrations/0005_remove_costcenter_refs.py`, `finance/migrations/0003_remove_financialtitle_cost_center.py`, `procurement/migrations/00XX_remove_cost_center.py` (via `makemigrations`).

**Steps:**
- [ ] Step 1: `python manage.py makemigrations costing finance procurement` → gera migrations RemoveField/AlterField/RemoveConstraint.
- [ ] Step 2: Inspecionar as migrations geradas; confirmar que removem as FKs/CharField e a UniqueConstraint antiga (e adicionam a nova `unique_order_cost_period`).
- [ ] Step 3: `python manage.py migrate` → esperado: aplica sem erros no SQLite.
- [ ] Step 4: Confirmar que a tabela `costing_costcenter` foi dropada: `python manage.py shell -c "from django.db import connection; print('costing_costcenter' not in connection.introspection.table_names())"` → `True`.

### Task 1.9: Ajustar testes e verificar Parte 1

**Files:** `tests/test_costing.py`, `tests/test_costing_migrations.py`, `tests/test_production_operations.py`, `tests/test_finance.py`, `tests/test_app_ui.py`, `tests/test_report_engine.py`, `tests/test_single_instance_schema.py`

**Changes:**
- Remover fixtures/helpers que criam `CostCenter` (ex.: `create_cost_center` em `test_costing.py`).
- Remover `cost_center=...` de criações de `StandardCost`, `CostSimulation`, `ProductionCostCapture`, `FinancialTitle`.
- Remover asserções sobre `cost_center` em listagens/UI/relatórios.
- `test_costing_migrations.py`: este teste valida migration 0002 de CostCenter — remover ou adaptar (o histórico de migração de CostCenter pode ser compactado; se preferir, manter migrations antigas e apenas adicionar as de remoção — **decisão: manter histórico, apenas adicionar migrations de remoção**, assim o teste de migração 0002 pode continuar válido para CostElement; remover apenas as partes que testam CostCenter).
- `calculate_cost`: testes que chamam `calculate_cost(cost_center=...)` → ajustar para `calculate_cost(period_start=..., period_end=...)`.

- [ ] Step 1: Editar os testes.
- [ ] Step 2: `python manage.py check`.
- [ ] Step 3: `grep -rniE "CostCenter|cost_center" --include="*.py" --include="*.html" . | grep -v ".venv" | grep -viE "openapi-schema" | grep -v "/migrations/"` → esperado: **0 ocorrências** (migrations antigas mantêm o nome, mas estão fora do grep de `/migrations/`; confirmar manualmente que só restam em migrations históricas).
- [ ] Step 4: Smoke — `python manage.py shell -c "from costing.models import StandardCost, CostSimulation, ProductionCostCapture, CostElement; print('ok')"` → `ok`.
- [ ] Step 5: Checkpoint Parte 1 concluída.

---

# PARTE 2 — Remover ícones dos templates

### Task 2.1: Remover Feather CSS/JS e ícones do base.html

**Files:** `templates/base.html`

**Changes:**
- Remover a tag/link do CSS do Feather e o `<script>` do Feather (localizar `feather` em `<link>`/`<script>` e a chamada `feather.replace()` se houver).
- Remover todos os `<i class="feather-..."></i>` do arquivo (chrome: search, bell, maximize, moon/sun, user, log-out, menu toggles, setas).
- Onde o `<i>` estava dentro de um elemento funcional (ex.: botão, `<span class="input-group-text">`), deixar o texto/estrutura sem o `<i>`.

- [ ] Step 1: Editar `templates/base.html`.
- [ ] Step 2: `grep -n "feather" templates/base.html` → esperado: 0 ocorrências.

### Task 2.2: Remover ícones dos includes

**Files:** `templates/includes/sidebar.html`, `form_actions.html`, `page_header.html`, `empty_state.html`, `status_badge.html`, `processing_modal.html`

**Changes:**
- Remover todas as tags `<i class="feather-...">...</i>`.
- `sidebar.html`: remover o `<span class="nxl-micon"><i ...></i></span>` (container puramente de ícone) e o `<span class="nxl-arrow"><i class="feather-chevron-right"></i></span>`. Para o item dinâmico `<i class="{{ module.icon }}">`, remover o `<i>` (e o span `nxl-micon` ao redor).
- `form_actions.html`: `<i class="feather-save">Salvar</i>` → `Salvar`; `<i class="feather-x">Cancelar</i>` → `Cancelar` (remover só o `<i>`).
- `page_header.html`, `empty_state.html`, `status_badge.html`, `processing_modal.html`: remover `<i>`s.

- [ ] Step 1: Editar os 6 includes.
- [ ] Step 2: `grep -rn "feather-" templates/includes/` → esperado: 0.

### Task 2.3: Remover ícones dos templates app/outros + chaves 'icon' do menu

**Files:** todos `templates/app/*.html`, `templates/dashboards/*`, `templates/workspaces/*`, `templates/accounts/*`, `templates/registration/*`; `base/ui/views.py`

**Changes:**
- Em cada template: remover todas as tags `<i class="feather-...">...</i>`.
- `base/ui/views.py`: remover todas as linhas `'icon': 'feather-...',` das definições de menu (linhas ~406-590 e demais). Deixar o restante da estrutura do item de menu.

- [ ] Step 1: Remover `<i class="feather-...">` de todos os templates app/dashboards/workspaces/accounts/registration.
- [ ] Step 2: Remover as chaves `'icon'` de `base/ui/views.py`.
- [ ] Step 3: `grep -rn "feather" templates/ base/ui/views.py` → esperado: 0 ocorrências.
- [ ] Step 4: `python manage.py check`.

### Task 2.4: Verificar renderização

- [ ] Step 1: Reiniciar runserver (se ativo) e abrir `http://127.0.0.1:8000/accounts/login/` → 200, sem ícones.
- [ ] Step 2: Após login, `/app/` e uma listagem renderizam sem erro e sem ícones.
- [ ] Step 3: Checkpoint Parte 2 concluída.

---

# PARTE 3 — Geração automática de `code`

### Task 3.1: Criar base/codegen.py (utilitário + mixin) com testes

**Files:**
- Create: `base/codegen.py`
- Test: `tests/test_codegen.py`

**`base/codegen.py` (conteúdo completo):**

```python
"""Geração automática de códigos no formato PREFIX-SEQ para modelos que declaram CODE_PREFIX."""

from django.db import IntegrityError, transaction

DEFAULT_WIDTH = 4


def _next_sequence(model_cls, prefix):
    """Maior sequência numérica existente entre códigos 'PREFIX-NNNN' para o modelo."""
    prefix_filter = f"{prefix}-"
    qs = model_cls.objects.filter(code__startswith=prefix_filter).values_list("code", flat=True)
    highest = 0
    for code in qs.iterator():
        tail = code[len(prefix_filter):]
        try:
            n = int(tail)
        except ValueError:
            continue
        if n > highest:
            highest = n
    return highest + 1


def _width_for(model_cls):
    max_length = model_cls._meta.get_field("code").max_length or 40
    prefix = model_cls.CODE_PREFIX
    # PREFIX- + dígitos deve caber em max_length; reserve 1 para o '-'.
    available = max_length - len(prefix) - 1
    return max(2, min(DEFAULT_WIDTH, available))


def generate_code(model_cls):
    """Gera um código único 'PREFIX-NNNN' para o modelo, com retry em colisão."""
    prefix = getattr(model_cls, "CODE_PREFIX", None)
    if not prefix:
        raise ValueError(f"{model_cls.__name__} não define CODE_PREFIX.")
    width = _width_for(model_cls)
    seq = _next_sequence(model_cls, prefix)
    for _ in range(100):
        candidate = f"{prefix}-{seq:0{width}d}"
        if not model_cls.objects.filter(code=candidate).exists():
            return candidate
        seq += 1
    raise IntegrityError(f"Não foi possível gerar um código único para {model_cls.__name__}.")


class AutoCodeMixin:
    """Mixin que gera `code` automaticamente no save() quando vazio.

    O modelo deve definir `CODE_PREFIX` (str). Se `code` já vier preenchido, é preservado.
    """

    CODE_PREFIX = None

    def save(self, *args, **kwargs):
        if not self.code and self.CODE_PREFIX:
            with transaction.atomic():
                self.code = generate_code(type(self))
        return super().save(*args, **kwargs)
```

**Teste `tests/test_codegen.py` (conteúdo completo):**

```python
import pytest
from django.core.exceptions import ValidationError

pytestmark = pytest.mark.django_db


def test_generate_code_returns_prefix_sequence():
    from base.codegen import generate_code
    from masters.models import Product

    code = generate_code(Product)
    assert code.startswith("PRD-")
    assert code[4:].isdigit()


def test_auto_code_on_save_when_blank():
    from masters.models import Product
    from masters.models import UnitOfMeasure

    p = Product.objects.create(name="Produto Teste", unit=UnitOfMeasure.objects.first() or UnitOfMeasure.objects.create(name="UN", code="UN"))
    assert p.code.startswith("PRD-")
    assert p.code != ""


def test_explicit_code_is_preserved():
    from masters.models import Product
    from masters.models import UnitOfMeasure

    unit = UnitOfMeasure.objects.first() or UnitOfMeasure.objects.create(name="UN", code="UN")
    p = Product.objects.create(code="MEU-CODIGO", name="Produto X", unit=unit)
    assert p.code == "MEU-CODIGO"


def test_generated_codes_are_sequential_and_unique():
    from base.codegen import generate_code
    from masters.models import Product
    from masters.models import UnitOfMeasure

    unit = UnitOfMeasure.objects.first() or UnitOfMeasure.objects.create(name="UN", code="UN")
    c1 = Product.objects.create(name="A", unit=unit).code
    c2 = Product.objects.create(name="B", unit=unit).code
    assert c1 != c2
    n1, n2 = int(c1.split("-")[1]), int(c2.split("-")[1])
    assert n2 == n1 + 1
```

> Nota: o teste cria `UnitOfMeasure` (excluído da auto-geração) manualmente com code, pois `Product.unit` é FK obrigatória. Ajuste o helper conforme o modelo real de Product (verificar campos obrigatórios em `masters/models.py` antes de rodar).

- [ ] Step 1: Criar `base/codegen.py` com o código acima.
- [ ] Step 2: Criar `tests/test_codegen.py`.
- [ ] Step 3: `python manage.py check`.
- [ ] Step 4: `pytest tests/test_codegen.py -v` → esperado: PASS (na 1ª vez, build do test_db.sqlite3 é lento; use `pytest tests/test_codegen.py -v --no-migrations` se houver problema de schema, mas o teste usa Product que precisa das tabelas — se --no-migrations não criar tabelas, rodar sem ele e aguardar o build).

### Task 3.2: Aplicar AutoCodeMixin + CODE_PREFIX + blank=True nos 30 modelos

**Files:** 30 arquivos `*/models.py` + migrations geradas.

**Padrão por modelo (aplicar a cada um da tabela):**
1. Em `*/models.py`: importar `from base.codegen import AutoCodeMixin` (ou já importado em conjunto com `base.models`).
2. Trocar a base do model de `class X(SingleInstanceModel):` para `class X(AutoCodeMixin, SingleInstanceModel):`.
3. Adicionar `CODE_PREFIX = '<PREFIX>'` dentro da classe.
4. Trocar `code = models.CharField('código', max_length=N)` para `code = models.CharField('código', max_length=N, blank=True)`.

**Tabela (app.model → prefixo):**
masters.Product→PRD; masters.BusinessPartner→BP; masters.Site→ST; masters.Warehouse→WH; masters.StorageLocation→SL; masters.MasterCategory→CAT; costing.CostElement→CE; planning.MasterProductionSchedule→MPS; planning.CapacityResource→CAP; qa.TrainingRequirement→TRQ; documents.ControlledDocument→DOC; ai_agents.AIAgentProfile→AGT; auxiliary.AuxiliaryCatalog→AUX; knowledge.KnowledgeSource→KS; reports.DashboardWorkspace→DASH; formulations.MasterFormula→MF; formulations.ManufacturingRoute→RT; finance.ChartOfAccount→COA; finance.FinancialCategory→FC; finance.FinancialAccount→FA; crm.CustomerGroup→CG; crm.SalesChannel→SC; crm.SalesRepresentative→SR; crm.Campaign→CMP; training.JobPosition→JP; training.WorkFunction→WF; training.Competency→CPT; training.TrainingRequirement→TR; reports.ReportDefinition→RPT; workflow.ApprovalQueue→APV.

- [ ] Step 1: Aplicar o padrão aos 30 modelos (editar cada `models.py`).
- [ ] Step 2: `python manage.py check`.
- [ ] Step 3: `python manage.py makemigrations` → gera `AlterField(code, blank=True)` para os 30. Inspecionar.
- [ ] Step 4: `python manage.py migrate`.
- [ ] Step 5: Smoke — criar um Product sem code via shell e confirmar `PRD-0001`:
  `python manage.py shell -c "from masters.models import Product, UnitOfMeasure; u=UnitOfMeasure.objects.first(); p=Product.objects.create(name='T', unit=u); print(p.code)"` → `PRD-0001`.

### Task 3.3: Tornar `code` não-editável na criação (admin/serializers)

**Files:** admin.py e serializers.py dos apps do escopo, onde `code` aparecia como obrigatório/editável.

**Padrão:**
- **Admin:** nos `ModelAdmin`/`SingleInstance*Admin` dos modelos do escopo, adicionar `code` a `readonly_fields` OU remover de `fields`/`fieldsets` no add. Abordagem simples e segura: `readonly_fields = ('code',)` (exibido, não editável). Se já houver `readonly_fields`, estender.
- **Serializers (DRF):** tornar `code = serializers.CharField(read_only=True)` nos serializers dos modelos do escopo (ou usar `extra_kwargs = {'code': {'read_only': True}}`). Em serializers que não declaravam `code` explicitamente (vinha via `fields = '__all__'` ou `Meta.fields`), adicionar `extra_kwargs`.

> Atenção: alguns fluxos legados/testes podem criar registros passando `code` explicitamente via serializer. Como `read_only=True` ignora o input, o code seria sempre auto-gerado. Se houver testes que dependem de informar code via API, marcar `read_only` pode quebrá-los. **Decisão:** usar `read_only=True` (auto-geração é o objetivo); ajustar os testes que dependiam de informar code via API para não esperar um code específico.

- [ ] Step 1: Editar admin.py dos apps do escopo (adicionar `code` a `readonly_fields`).
- [ ] Step 2: Editar serializers.py dos apps do escopo (`code` read_only).
- [ ] Step 3: `python manage.py check`.
- [ ] Step 4: Rodar testes relevantes (`pytest tests/test_costing.py tests/test_masters*.py ...` conforme existirem) e ajustar falhas de testes que esperavam code informado via API.

### Task 3.4: Verificação final consolidada

- [ ] Step 1: `python manage.py check` → sem issues.
- [ ] Step 2: `python manage.py migrate` → sem erros.
- [ ] Step 3: `grep -rniE "CostCenter|cost_center" --include="*.py" --include="*.html" . | grep -v ".venv" | grep -viE "openapi-schema" | grep -v "/migrations/"` → 0.
- [ ] Step 4: `grep -rn "feather" templates/ base/ui/views.py` → 0.
- [ ] Step 5: `pytest tests/test_codegen.py -v` → PASS.
- [ ] Step 6: Smoke final via shell — criar registros de alguns modelos (Product, BusinessPartner, CostElement) sem code e confirmar códigos `PREFIX-0001` únicos.
- [ ] Step 7: Reiniciar runserver; login + navegação básica sem erros.
- [ ] Step 8: Checkpoint final — todas as 3 partes concluídas.

---

## Self-Review do Plano

- **Cobertura da spec:** Parte 1 cobre remoção de CostCenter + FKs + procurement CharField + refatoro calculate_cost + migrations + testes (spec ✓). Parte 2 cobre todos os templates + CSS/JS + chaves icon (spec ✓). Parte 3 cobre mixin/util + 30 modelos + prefixos + read-only + migrations (spec ✓). Exclusões (7 modelos) respeitadas.
- **Placeholders:** nenhum TBD/TODO; código completo para codegen, mixin e testes; tabelas DRY para repetição mecânica.
- **Consistência de tipos:** `AutoCodeMixin.save` chama `generate_code(type(self))`; `CODE_PREFIX` lido em `generate_code` via `getattr`. Nomes consistentes entre Task 3.1 e 3.2. Migration `unique_order_cost_period` referenciada igual em 1.1 e 1.8.
- **Risco de testes:** `test_codegen.py` depende de campos obrigatórios de `Product` (verificar `unit` e outros required fields em `masters/models.py` antes de rodar — Step "Nota" já alerta).
