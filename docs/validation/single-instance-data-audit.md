# Auditoria de dados e schema single-instance

## Escopo e execução

Auditoria executada em 18/07/2026 no PostgreSQL local 18.4 antes do fechamento
da Sprint 4 do `MODIFICACAGERAL.prd`. O objetivo foi identificar colisões de
chaves anteriormente segmentadas e qualquer artefato físico de tenant.

O banco possuía um registro operacional em `integrations.ApiCallLog`; os
cadastros sujeitos à mudança de unicidade estavam vazios. Nenhum registro foi
alterado, mesclado, renumerado ou excluído.

## Resultado de duplicidades

| Model | Chave funcional | Registros | Grupos duplicados |
| --- | --- | ---: | ---: |
| `masters.Product` | `code` | 0 | 0 |
| `masters.UnitOfMeasure` | `code` | 0 | 0 |
| `masters.BusinessPartner` | `code` | 0 | 0 |
| `inventory.StockLot` | `product + lot_number + sublot_number` | 0 | 0 |
| `production.ProductionOrder` | `order_number` | 0 | 0 |
| `production.ProductionOrder` | `batch_number` | 0 | 0 |
| `documents.ControlledDocument` | `code + version` | 0 | 0 |
| `capa.CapaRecord` | `capa_number` | 0 | 0 |
| `deviations.QualityEvent` | `event_number` | 0 | 0 |
| `regulatory.RegulatoryRegistration` | `registration_number` | 0 | 0 |

As chaves acima possuem constraints globais ou por contexto funcional no model
atual. A aplicação de todas as migrations também comprova que não havia colisão
incompatível com essas constraints.

## Resultado físico

| Verificação no schema `public` | Resultado final |
| --- | ---: |
| Models Django com campo `tenant` | 0 |
| Colunas `tenant_id` | 0 |
| Índices cuja definição contém `tenant` | 0 |
| Constraints cujo nome contém `tenant` | 0 |
| Migrations pendentes | 0 |

O PostgreSQL 18 preservou inicialmente um nome de constraint `NOT NULL` após o
`RenameField` de `require_tenant_scope`. A migration
`compliance.0007_rename_legacy_tenant_not_null_constraint` renomeia o artefato
de forma condicional e reversível; em PostgreSQL anterior, onde a constraint
nomeada não existe, a operação é um no-op seguro.

## Evidências automatizadas

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/pytest tests/test_single_instance_schema.py tests/test_master_data.py \
  tests/test_formulations.py tests/test_production.py tests/test_inventory.py -q
```

Resultado: 31 testes aprovados, nenhuma migration ou operação planejada.
