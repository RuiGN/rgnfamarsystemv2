# Design: Remover Centro de Custo, remover ícones dos templates e gerar códigos automaticamente

Data: 2026-08-25
Perfil de execução: `core.settings.sqlite` (SQLite local, sem Postgres/Redis/RabbitMQ).

## Objetivo

Três mudanças independentes, executadas como sub-projetos sequenciados:

1. Remover o model `costing.CostCenter` ("centro de custo") e **todas** as suas referências.
2. Remover **todos** os ícones Feather dos templates, deixando apenas texto.
3. Gerar automaticamente o campo `code` dos modelos (formato `PREFIXO-SEQUENCIAL`).

---

## Sub-projeto 1 — Remover `CostCenter` e todas as referências

### Decisão aprovada
Remoção completa: model, FKs, lógica, UI, admin, serializers, seeders, templates, testes e
migrations para dropar colunas e a tabela `costing_costcenter`.

### Modelos que perdem o campo `cost_center`
- `costing.StandardCost` — FK obrigatória (PROTECT) → removida.
- `costing.CostSimulation` — FK obrigatória → removida.
- `costing.ProductionCostCapture` — FK obrigatória → removida.
- `finance.FinancialTitle` — FK opcional → removida.
- `procurement.PurchaseRequisition` — campo **CharField** livre `cost_center` (max 80, blank=True)
  → removido (também é uma referência a "centro de custo").

### Impacto comportamental (risco principal)
`production/services.py::calculate_cost(*, cost_center, period_start, period_end)` e o fluxo de
captura de custos de produção usam `cost_center` como parâmetro obrigatório. A refatoração remove
`cost_center` do serviço e de `ProductionCostCapture`; a captura passa a ser por
**ordem + período** apenas. `reports/executors/production.py` que referencia `cost_center_id`
também é ajustado.

### Arquivos afetados (não-testes)
- `costing/`: `models.py`, `admin.py`, `views.py`, `serializers.py`, `urls.py`
- `finance/`: `models.py`, `admin.py`, `views.py`, `serializers.py`
- `production/`: `services.py`, `serializers.py`
- `procurement/`: `models.py`, `admin.py`, `views.py`, `serializers.py`
- `base/ui/`: `registry.py`, `views.py`, `actions/modules/production.py`, `actions/inventory.py`
- `governance/demo_seeders.py`
- `reports/executors/production.py`
- `templates/app/production_order_map.html`

### Testes afetados
`tests/test_production_operations.py`, `tests/test_costing.py`,
`tests/test_costing_migrations.py`, `tests/test_finance.py`, `tests/test_app_ui.py`,
`tests/test_report_engine.py`, `tests/test_single_instance_schema.py`.
Remover/asjustar criações de `CostCenter`, FKs `cost_center` e asserções relacionadas.

### Migrations
Novas migrations em `costing`, `finance`, `procurement`:
- remover FKs `cost_center` das tabelas citadas;
- remover índices que referenciam `cost_center`;
- remover a tabela `costing_costcenter` (e o model do estado de migrações).

### Critério de aceite
- `manage.py check` sem issues; `manage.py migrate` em SQLite sem erros.
- Nenhuma referência a `CostCenter`/`cost_center` no código (exceto histórico de migrations removido
  do estado ativo).
- Testes ajustados passam (ou são removidos quando o próprio conceito deixa de existir).

---

## Sub-projeto 2 — Remover ícones dos templates

### Decisão aprovada
Remover **todos** os `<i class="feather-...">` dos templates; remover as chaves
`'icon': 'feather-...'` do menu em `base/ui/views.py`; ajustar `templates/includes/sidebar.html`
para não renderizar o span do ícone; remover o **CSS/JS do Feather** de `templates/base.html`
(fica sem uso).

### Arquivos afetados
- `templates/base.html` (ícones do chrome + referência CSS/JS do feather)
- `templates/includes/`: `sidebar.html`, `form_actions.html`, `page_header.html`,
  `empty_state.html`, `status_badge.html`, `processing_modal.html`
- `templates/app/*.html` (~15 arquivos), `templates/dashboards/*`, `templates/workspaces/*`,
  `templates/accounts/*`, `templates/registration/*`
- `base/ui/views.py` (remover `'icon'` das definições de menu)

### Risco
Baixo. Limpar contêineres puramente de ícone (spans vazios). Não afeta lógica de negócio.

### Critério de aceite
- Nenhuma tag `<i class="feather-...">` nos templates; sem import de CSS/JS feather.
- `manage.py check` ok; páginas renderizam sem erro (login, dashboard, listas).

---

## Sub-projeto 3 — Geração automática de `code`

### Decisão aprovada
- **Abordagem:** mixin `AutoCodeMixin` + utilitário `base/codegen.py`; geração no `save()` quando
  `code` vazio. Cada modelo declara `CODE_PREFIX` (class attribute).
- **Formato:** `{PREFIX}-{SEQ zero-pad}` (ex.: `PRD-0001`). Largura do SEQ calculada por modelo a
  partir de `max_length` (default 4 dígitos; ajusta para caber em `max_length`).
- **Algoritmo:** localiza o maior SEQ existente para o prefixo (`code__startswith=PREFIX-`),
  incrementa, com retry em colisão (concorrência via IntegrityError).
- **Campo:** `code` mantém UniqueConstraint existente; passa a `blank=True` e **não-editável** no
  admin/form na criação (read-only/exibido depois). Serializers que exigiam `code` tornam-no
  opcional (gerado se vazio).
- **Sem backfill:** apenas novos registros recebem código automático (banco dev local novo).

### Escopo — modelos com `code`
Auto-gerar (30) com prefixos:

| app.model | prefixo | | app.model | prefixo |
|---|---|---|---|---|
| masters.Product | PRD | | formulations.MasterFormula | MF |
| masters.BusinessPartner | BP | | formulations.ManufacturingRoute | RT |
| masters.Site | ST | | finance.ChartOfAccount | COA |
| masters.Warehouse | WH | | finance.FinancialCategory | FC |
| masters.StorageLocation | SL | | finance.FinancialAccount | FA |
| masters.MasterCategory | CAT | | crm.CustomerGroup | CG |
| costing.CostElement | CE | | crm.SalesChannel | SC |
| planning.MasterProductionSchedule | MPS | | crm.SalesRepresentative | SR |
| planning.CapacityResource | CAP | | crm.Campaign | CMP |
| qa.TrainingRequirement | TRQ | | training.JobPosition | JP |
| documents.ControlledDocument | DOC | | training.WorkFunction | WF |
| ai_agents.AIAgentProfile | AGT | | training.Competency | CPT |
| auxiliary.AuxiliaryCatalog | AUX | | training.TrainingRequirement | TR |
| knowledge.KnowledgeSource | KS | | reports.ReportDefinition | RPT |
| reports.DashboardWorkspace | DASH | | workflow.ApprovalQueue | APV |

**Excluir da auto-geração (códigos externos/padronizados):**
- `auxiliary.Currency` (ISO BRL/USD)
- `fiscal.FiscalMunicipality` (código IBGE)
- `fiscal.TaxSituation` (CST padronizado)
- `fiscal.FiscalDocument` (número/chave de documento fiscal)
- `fiscal.FiscalUnit` (unidades padronizadas)
- `masters.UnitOfMeasure` (UN/KG padronizados)
- `costing.CostCenter` (removido no Sub-projeto 1)

### Arquivos afetados
- Novo: `base/codegen.py` (utilitário) + `AutoCodeMixin` em `base/models.py` (ou `base/codegen.py`).
- ~31 `models.py` de apps: adicionar `CODE_PREFIX` + herdar `AutoCodeMixin` + `code` para `blank=True`.
- Admin/forms/serializers: tornar `code` read-only/omitido na criação onde aplicável.
- Migrations: `AlterField` de `code` para `blank=True` nos modelos alterados.

### Risco
Médio. Testes que criam registros sem `code` passam a receber automático; testes que fornecem
`code` explícito continuam funcionando (gera só se vazio).

### Critério de aceite
- Criar um registro de cada modelo no escopo sem informar `code` gera um `PREFIX-NNNN` único.
- `code` informado explicitamente é preservado.
- `manage.py check` + `migrate` ok; testes relevantes passam.

---

## Ordem de execução
1 → 2 → 3. Cada sub-projeto: editar → `manage.py check` → `migrate` (SQLite) → rodar testes
relevantes. Verificação final consolidada.

## Observações
- Sem repositório git no diretório atual: a spec é apenas gravada em arquivo (sem commit).
- Perfil usado: `core.settings.sqlite` (manage.py já o usa por padrão).
