# Módulos Legados

Este documento registra a remoção dos módulos legados do sistema (transição da
arquitetura multi-tenant para single-instance e do escopo farmacêutico para
cosmético).

## Status: REMOVIDOS

Os módulos `tenants`, `control_plane`, `regulatory`, `pharmacovigilance` e
`knowledge` foram completamente removidos:

- Diretórios apagados.
- Removidos de `INSTALLED_APPS`, URLs, menus, catálogo de ações UI e seeders.
- Histórico de migrations consolidado (reset completo; todas as apps iniciam em
  migrations novas geradas dos models vigentes).
- Trigger PostgreSQL da máquina de estados de `StandardCost` preservado em
  `costing/migrations/0003_standard_cost_state_machine.py`.
- Seed do catálogo curado de relatórios preservado em
  `reports/migrations/0002_seed_curated_report_catalog.py`.
- Testes de transição e de replay de migrações históricas removidos.
- Evidências históricas (`docs/validation/evidence/archive/`) preservadas como
  registro imutável.
