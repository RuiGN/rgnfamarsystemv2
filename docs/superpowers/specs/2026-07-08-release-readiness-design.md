# Sprint 36 Release Readiness Design

## Contexto

O `PRD.md` registra as Sprints 1 a 35 como executadas. As Sprints 33, 34 e
35 entregaram gates automatizados para prontidão operacional, backup e
restauração, e aceite técnico final do produto.

A Sprint 36 transforma esses gates em um processo de prontidão de release e
staging local. O objetivo é gerar evidência objetiva antes de publicar uma
versão interna, sem depender de VPS real, domínio público, Cloudflare ou
credenciais de produção.

## Objetivo

Criar um gate de release local/containerizado para comprovar que o RGN Farma
System está pronto para staging interno, com comandos reprodutíveis, smoke
checks documentados, geração de OpenAPI e evidência consolidada de release.

## Escopo

- Criar `core/release_readiness.py` com função pública
  `evaluate_release_readiness(project_root=None)`.
- Criar comando Django `check_release_readiness` com saída texto, saída JSON e
  opção `--fail-on-error`.
- Validar presença e documentação dos gates:
  `check_operational_readiness`, `check_backup_restore_readiness`,
  `check_product_acceptance` e `check_release_readiness`.
- Validar que rotas de smoke local estão documentadas: `/health/`, `/`,
  `/api/schema/`, `/api/docs/` e `/api/v1/`.
- Validar que `load_demo_scenario` existe e está documentado para carga de
  dados de demonstração em staging local.
- Validar que a geração de OpenAPI está disponível via comando
  `spectacular --file`.
- Criar documentação canônica em `docs/architecture/release-readiness.md`.
- Atualizar `README.md`, `docs/index.md`, `docs/deployment.md`, `mkdocs.yml`
  e `PRD.md`.
- Criar testes automatizados da Sprint 36 em `tests/test_release_readiness.py`.

## Fora De Escopo

- Executar deploy real em VPS.
- Criar ou exigir Docker Swarm real durante os testes.
- Acessar Cloudflare, GHCR, domínio público ou certificados reais.
- Exigir segredos, tokens ou credenciais de produção.
- Criar nova app Django.
- Criar ou alterar models persistentes.
- Gerar migrations.
- Criar dados demo profundos para todos os módulos; a sprint valida o comando
  e a documentação existentes.
- Executar smoke HTTP contra servidor remoto.

## Arquitetura

O avaliador segue o padrão já usado por:

- `core.operational_readiness.evaluate_operational_readiness()`;
- `core.backup_restore_readiness.evaluate_backup_restore_readiness()`;
- `core.product_acceptance.evaluate_product_acceptance()`.

A Sprint 36 adiciona uma camada de orquestração leve:

- `core/release_readiness.py` inspeciona arquivos, comandos Django e rotas
  carregáveis, sem acessar banco de dados.
- `base/management/commands/check_release_readiness.py` invoca o avaliador,
  imprime relatório em texto ou JSON e retorna erro apenas quando
  `--fail-on-error` é usado e há falhas.
- `tests/test_release_readiness.py` cobre o contrato do relatório, serialização
  JSON, comportamento do comando e falhas simuladas por documentação
  incompleta.
- `docs/architecture/release-readiness.md` documenta o runbook de staging
  local e os critérios de aceite.

O gate deve ser seguro para rodar em ambiente local, container, CI e revisão de
release. Ele não deve abrir conexão com serviços externos nem ler segredos.

## Contrato Do Resultado

`evaluate_release_readiness(project_root=None)` retorna um objeto com:

- `passed`: booleano agregado.
- `checks`: lista ordenada de checks.

Cada check contém:

- `code`: identificador estável em inglês.
- `title`: título em português brasileiro.
- `status`: `pass`, `fail` ou `warning`.
- `evidence`: mensagem objetiva em português brasileiro.

O comando `check_release_readiness --format json` serializa esse contrato com
`ensure_ascii=False` e sem expor caminhos privados, variáveis sensíveis ou
segredos.

## Checks De Release

### Gates Obrigatórios

Confirma que os comandos abaixo são descobertos pelo Django e aparecem na
documentação operacional:

- `check_operational_readiness`;
- `check_backup_restore_readiness`;
- `check_product_acceptance`;
- `check_release_readiness`.

### Smoke Local

Confirma que o runbook de release documenta smoke checks locais para:

- `/health/`;
- `/`;
- `/api/schema/`;
- `/api/docs/`;
- `/api/v1/`.

O avaliador valida documentação e roteamento carregável. Ele não inicia
servidor HTTP por conta própria.

### OpenAPI

Confirma que o projeto possui `drf-spectacular`, rota `/api/schema/`, rota
`/api/docs/` e documentação para gerar schema com:

```bash
.venv/bin/python manage.py spectacular --file openapi-schema.yml
```

### Dados Demo Para Staging

Confirma que `load_demo_scenario` está registrado como comando Django e que
README/documentação descrevem uso com `--tenant-slug` e `--scenario`.

### Evidência De Release

Confirma que a documentação orienta uma sequência mínima:

1. Executar `manage.py check`.
2. Executar `makemigrations --check --dry-run`.
3. Executar gates operacional, backup/restore, produto e release.
4. Gerar OpenAPI.
5. Executar smoke local.
6. Registrar evidência de release.

### PRD

Confirma que o `PRD.md` registra a Sprint 36 como executada com checklist de
prontidão de release.

### Segurança

Confirma que a documentação da Sprint 36 usa variáveis simbólicas e não contém
padrões óbvios de tokens reais, chaves privadas ou credenciais sensíveis.

## Tratamento De Erros

- Arquivos ausentes produzem checks falhos com mensagem objetiva.
- Comando ausente no registry Django produz falha de release.
- Rotas não resolvíveis produzem falha de smoke local.
- Saída JSON permanece válida mesmo quando há falhas.
- `--fail-on-error` retorna exit code 1 somente quando `passed=false`.
- Falhas não devem imprimir stack trace na saída normal do comando.

## Testes

Os testes seguem TDD:

- Primeiro teste falha pela ausência de `core.release_readiness`.
- Testes de contrato validam todos os códigos críticos.
- Teste de JSON valida `passed=true` e lista de checks.
- Teste de falha simulada usa raiz temporária ou fixture sem documentação de
  release para garantir `passed=false`.
- Testes do comando cobrem `--format json` e `--fail-on-error`.

Suíte relevante:

```bash
.venv/bin/pytest tests/test_release_readiness.py -q
```

Verificação final esperada:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py makemigrations --check --dry-run
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_product_acceptance --fail-on-error
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check_release_readiness --fail-on-error
.venv/bin/pytest tests/test_release_readiness.py tests/test_product_acceptance.py -q
.venv/bin/mkdocs build --strict
```

## Documentação

Atualizações obrigatórias:

- `README.md`: adicionar comandos de prontidão de release.
- `docs/index.md`: adicionar a Sprint 36 ao índice funcional.
- `docs/deployment.md`: adicionar runbook de staging local e release.
- `docs/architecture/release-readiness.md`: documentar objetivo, execução,
  smoke checks, OpenAPI, dados demo e critérios de aceite.
- `mkdocs.yml`: expor a nova página.
- `PRD.md`: registrar Sprint 36 executada.

## Critérios De Aceite

- `check_release_readiness --fail-on-error` passa no repositório.
- `check_release_readiness --format json` retorna `passed=true`.
- `pytest tests/test_release_readiness.py` passa.
- `manage.py check` passa.
- `makemigrations --check --dry-run` não detecta migrations pendentes.
- `check_product_acceptance --fail-on-error` continua passando.
- `mkdocs build --strict` inclui a página de release readiness.
- `PRD.md` registra a Sprint 36 como executada.
- Não existem migrations novas.
- Nenhum segredo real é introduzido em documentação ou código.

## Riscos E Mitigações

- Risco: duplicar checks das Sprints 33 a 35.
  Mitigação: a Sprint 36 valida orquestração de release e documentação, sem
  reimplementar internamente todos os checks anteriores.

- Risco: transformar o gate local em deploy real.
  Mitigação: VPS, Cloudflare, GHCR e certificados reais ficam fora de escopo.

- Risco: smoke checks ficarem frágeis por dependerem de servidor em execução.
  Mitigação: o avaliador valida rotas e runbook; execução HTTP real fica como
  comando documentado para staging local.

- Risco: evidência de release virar documento manual sem teste.
  Mitigação: o comando `check_release_readiness` falha quando README, deploy
  docs, MKDocs ou PRD deixam de registrar o processo.
