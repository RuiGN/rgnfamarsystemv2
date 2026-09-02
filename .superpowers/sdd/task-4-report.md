# Task 4 — carga unificada dos catálogos de produção

## Escopo

- Serviço `seed_production_reference_data()` e resultado imutável com hashes e contagens.
- Transação global com compatibilidade das APIs transacionais existentes.
- Flag `--production-catalogs`, mantendo o comportamento histórico sem a flag.
- Documentação dos namespaces, fontes, atualização fora do deploy e exclusões.

## TDD

### RED 1 — rollback global

Comando:

```bash
bash scripts/test.sh tests/test_production_reference_catalogs.py::test_global_reference_load_rolls_back_every_domain -q
```

Resultado esperado observado: exit `4`, coleta interrompida por
`ModuleNotFoundError: No module named 'reference_data.services'`.

### GREEN 1 — rollback global

Resultado inicial observado: `1 passed in 321.75s`. Após fortalecer a injeção
para falhar no último CFOP, depois das escritas dos demais domínios, o teste
passou novamente com `--reuse-db`: `1 passed in 73.89s`.

### RED 2 — reutilização da transação

Resultado esperado observado: `1 failed in 211.79s`; o fake exigiu
`use_current_transaction` e o serviço ainda não fornecia o argumento.

### GREEN 2 — reutilização e resultado

Resultado observado: `1 passed in 255.13s`.
O contrato de integração com os manifestos e contagens reais também passou:
`1 passed in 94.07s`.

### RED/GREEN 3 — ordem de pré-validação

RED esperado observado: a ordem era `load`, aplicação oficial, auxiliares,
validação e domínios. O teste falhou em `1.18s`. Após mover a validação estática
antes da primeira escrita e manter a validação relacional dentro da aplicação,
o teste ficou verde: `1 passed in 1.22s`.

### RED/GREEN 4 — compatibilidade da validação pública

O self-review identificou que remover a validação relacional de
`validate_catalogs()` mudaria o contrato anterior. O RED exigiu o novo keyword
explícito no serviço e falhou com `TypeError` em `1.56s`. O padrão público foi
mantido completo, enquanto apenas a pré-validação coordenada usa
`include_auxiliary_dependencies=False`; GREEN: `1 passed in 0.93s`.

### RED/GREEN 5 — comando de produção

RED esperado observado em `2.13s`: o módulo do comando ainda não expunha
`seed_production_reference_data`. GREEN observado: `1 passed in 1.34s`.

## Segurança e integridade

- Nenhum `.env` foi lido ou impresso.
- Nenhum banco persistente foi usado; todos os testes usam PostgreSQL isolado via
  `scripts/test.sh`.
- Nenhum loader interno usa `durable=True`.
- A saída do comando abrevia hashes para 12 caracteres e contém somente versões
  e contagens dos catálogos.
- O serviço unificado é a transação externa; loaders isolados mantêm a transação
  própria quando chamados sem `use_current_transaction=True`.
- `auxiliary/reference_snapshots.py` e `reference_data/loaders.py` foram tocados
  somente para introduzir essa compatibilidade: o caminho padrão continua
  abrindo `atomic()`, enquanto o serviço coordenador evita savepoints internos.

## Arquivos

- `reference_data/services.py`
- `reference_data/loaders.py`
- `auxiliary/reference_snapshots.py`
- `auxiliary/cosmetics_seed.py`
- `auxiliary/management/commands/load_cosmetics_auxiliary_data.py`
- `tests/test_production_reference_catalogs.py`
- `docs/architecture/auxiliary.md`
- `docs/architecture/master-data.md`
- `docs/deployment.md`
- `.superpowers/sdd/task-4-report.md`

## Self-review e verificações finais

- Gate focado com os dez arquivos de teste do brief, repetido após a última
  adição de contrato: `108 passed in 318.58s`.
- Compatibilidade histórica `--with-official-references`: `1 passed in 2.72s`.
- Comando novo e compatibilidade histórica após o ajuste final: `2 passed in
  3.20s`.
- Ruff: `All checks passed!`.
- Ruff format: `6 files already formatted`.
- mypy nos cinco módulos Python tocados: `Success: no issues found in 5 source files`.
- Django system check: `System check identified no issues (0 silenced)`.
- Migrations: `No changes detected`.
- `git diff --check`: exit `0`.

O primeiro mypy após o gate detectou reutilização incompatível do nome `counts`
entre os dois ramos do comando. O nome do resumo textual foi isolado como
`count_summary`; o teste focado e todos os gates estáticos acima foram repetidos
com sucesso.
