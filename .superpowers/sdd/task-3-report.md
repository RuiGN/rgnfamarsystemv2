# Task 3 — Catálogos mestres cross-app

## Status

Implementação concluída localmente, sem deploy, push, acesso a VPS ou escrita em banco
persistente. A carga usa apenas o PostgreSQL isolado de testes provido por
`scripts/test.sh`.

## TDD: RED e GREEN

- RED inicial: `bash scripts/test.sh tests/test_production_reference_catalogs.py --reuse-db -q`
  terminou com `ModuleNotFoundError: No module named 'reference_data.cosmetics_catalogs'`,
  confirmando que a interface nova ainda não existia.
- GREEN focal após implementação: 7 testes passaram.
- A atomicidade recebeu prova de mutação: ao remover temporariamente o decorador
  `transaction.atomic`, o teste tardio de `full_clean()` falhou porque as escritas
  anteriores permaneceram; restaurado o decorador, o mesmo teste passou e confirmou
  rollback integral.
- RED da correção de review: os três cenários novos falharam como esperado. O seeder
  não encontrava `BPC-COS-MAN`; a função de manutenção apontava para processo de outra
  área; e uma falha de validação no último CFOP observou **168 sinais `pre_save`** antes
  de abortar.
- GREEN da correção: os processos/departamento dedicados foram adicionados, todas as
  relações de cargo/função ficaram coerentes com a área e o lote inteiro passou por
  `full_clean()` antes do primeiro `save`.
- RED/GREEN adicional: corromper a área de `DEP-COS-AUD` ou `BPC-COS-MAN` inicialmente
  não causava rejeição (**2 failed**); após validar a coerência auxiliar na fase
  estrutural, os dois casos passaram (**2 passed**).
- Gate requerido final: `bash scripts/test.sh tests/test_production_reference_catalogs.py
  tests/test_cosmetics_auxiliary_data.py --reuse-db -q`.
- Regressões focadas: `bash scripts/test.sh tests/test_costing.py tests/test_crm.py
  tests/test_finance.py tests/test_training.py tests/test_fiscal.py --reuse-db -q`.

## Arquivos

- `reference_data/cosmetics_catalogs.py`: valores canônicos, relações derivadas dos 17
  `ORGANIZATIONAL_ROLES`, payload e `COSMETICS_CATALOG_MANIFEST`.
- `auxiliary/cosmetics_seed.py`: processos dedicados de manutenção e auditoria e
  departamento dedicado de auditoria interna.
- `reference_data/loaders.py`: validação estrutural e relacional completa, upsert com
  `full_clean()`, loaders em ordem de dependência, transação única e contadores.
- `tests/test_production_reference_catalogs.py`: conteúdo pt-BR, manifesto, relações,
  idempotência, preservação local, pré-validação, rollback e escopo fiscal/operacional
  negativo.

Nenhum model ou migration foi alterado.

## Fontes e limite fiscal

- Unidades: **Sistema Internacional de Unidades (SI), Inmetro/IPQ, 2ª edição da
  tradução luso-brasileira, 2025** —
  <https://www.gov.br/inmetro/pt-br/assuntos/metrologia-cientifica/documentos-tecnicos-em-metrologia/si_versao_final.pdf/view>.
- Taxonomia interna: **RGN Cosmetics Catalog 2026.1**.
- CFOP: tabela oficial da Receita Federal, atualizada em 2026-06-03 —
  <https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/facilitacao/anexo-ecf-cfop>.
- Fundamento CFOP: Convênio SINIEF s/nº, de 15 de dezembro de 1970, referenciado pela
  SEFAZ-SP em <https://legislacao.fazenda.sp.gov.br/Paginas/art597.aspx>.

O manifesto registra expressamente que CFOP é referência descritiva e que a seleção
do código continua dependente da análise fiscal aplicável. Os pares interestaduais e
internos preservam o mesmo rótulo canônico; a direção é inferida apenas do primeiro
dígito para validar o campo `direction`, sem acrescentar texto ao rótulo.

## Contagens gerenciadas por model

| Model | Registros |
| --- | ---: |
| `masters.UnitOfMeasure` | 21 |
| `masters.MasterCategory` | 42 |
| `costing.CostElement` | 10 |
| `crm.CustomerGroup` | 5 |
| `crm.SalesChannel` | 5 |
| `finance.ChartOfAccount` | 12 |
| `finance.FinancialCategory` | 6 |
| `training.JobPosition` | 17 |
| `training.WorkFunction` | 17 |
| `training.Competency` | 11 |
| `fiscal.FiscalUnit` | 11 |
| `fiscal.FiscalOperationCode` | 12 |
| **Total** | **169** |

Os 17 cargos e as 17 funções usam exatamente os nomes de `ORGANIZATIONAL_ROLES`.
`area_ref`, `department_ref` e `process_ref` são procurados pelos códigos auxiliares
`BA-COS-*`, `DEP-COS-*` e `BPC-COS-*`; qualquer ausência interrompe a carga antes da
primeira escrita. O catálogo auxiliar gerencia agora 14 áreas, 24 processos, 17
departamentos e 17 papéis organizacionais. Todas as relações usadas pelos papéis
satisfazem `department.area == role.area` e `process.area == role.area`.

## Comportamento e segurança da carga

- `validate_catalogs()` confere duplicidade, prefixos reservados, `TextChoices`,
  parents, contas contábeis, cardinalidade/hash do manifesto, derivação das funções,
  estrutura/direção dos CFOPs e dependências auxiliares.
- `apply_catalogs()` executa duas fases dentro de uma única transação: primeiro monta
  o estado final de todos os 169 candidatos e executa `full_clean()` em todos; somente
  após concluir o lote inteiro inicia os upserts e escritas.
- O teste da fronteira envolve a conexão do Django e registra qualquer SQL `INSERT`,
  `UPDATE` ou `DELETE`; uma falha no último candidato encerra com lista de escritas vazia.
- Candidatos de atualização reutilizam a instância existente, preservando `pk` e
  `_state`, para que `validate_unique()` e `validate_constraints()` excluam corretamente
  a própria linha. Relações para pais novos são validadas estruturalmente e excluídas
  apenas da validação de FK enquanto o pai ainda não possui PK.
- Cada registro, inclusive inalterado, passa por `full_clean()`.
- Upserts só usam os códigos enumerados pelo catálogo; registros locais não listados
  são preservados.
- Segunda aplicação retorna os itens como `unchanged` e não muda cardinalidade.
- Registros gerenciados inativos são reativados e valores gerenciados incorretos são
  corrigidos.

## Escopo negativo comprovado

- Nenhum `Product`, `BusinessPartner`, `StockLot` ou `StockMovement` é criado.
- Nenhum NCM (`FiscalNCM`) ou CST/CSOSN (`TaxSituation`) é criado.
- Nenhuma alíquota, regra tributária ou automatização de decisão fiscal foi adicionada.
- Nenhum dado operacional, schema, migration, configuração de produção ou infraestrutura
  foi modificado.

## Verificações

- Gate catálogos + seeder auxiliar: **16 passed**.
- Regressões `costing`, `crm`, `finance`, `training` e `fiscal`: **60 passed**.
- Ruff lint: sem achados.
- Ruff format: arquivos tocados formatados.
- mypy nos módulos novos: sem erros.
- `manage.py check`: 0 issues.
- `manage.py makemigrations --check --dry-run`, com PostgreSQL de teste explícito:
  `No changes detected`.
- `git diff --check`: sem erros.

## Limite mantido

- A lista CFOP é deliberadamente pequena e descritiva. Ela não substitui parametrização
  fiscal por estabelecimento, UF, regime, produto ou operação.
