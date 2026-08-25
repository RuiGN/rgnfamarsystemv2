# Sprint 35 Product Acceptance Hardening Design

## Contexto

O `PRD.md` registra as Sprints 1 a 34 como executadas. Elas cobrem a fundação
Django/DRF, multi tenant, módulos farmacêuticos, APIs, governança,
conformidade, prontidão operacional, backup e restauração.

A Sprint 35 fecha a primeira linha de entrega com um gate de aceite técnico
automatizado. O objetivo não é criar novo domínio de negócio, nova app Django
ou migrations. O objetivo é provar que o produto integrado continua coerente,
navegável, documentado e verificável após todos os módulos anteriores.

## Objetivo

Criar um avaliador de aceite final do RGN Farma System que gere evidência
estruturada para lançamento interno, revisão técnica e auditoria de prontidão.

## Escopo

- Criar um módulo Python em `core/product_acceptance.py` com função pública
  `evaluate_product_acceptance(project_root=None)`.
- Criar o comando Django `check_product_acceptance` com saída texto, saída JSON
  e opção `--fail-on-error`.
- Validar rotas críticas: `/health/`, `/`, `/api/schema/`, `/api/docs/` e
  namespaces principais de `/api/v1/*`.
- Validar presença dos menus administrativos críticos em `templates/base.html`.
- Validar disponibilidade dos comandos operacionais já entregues:
  `check_operational_readiness`, `check_backup_restore_readiness` e
  `check_transversal_compliance`.
- Validar documentação navegável no MKDocs para deploy, compliance, prontidão
  operacional, backup/restauração e aceite de produto.
- Registrar a Sprint 35 no `PRD.md` como executada ao fim da implementação.
- Atualizar `README.md`, `docs/index.md` e criar
  `docs/architecture/product-acceptance.md`.

## Fora De Escopo

- Criar novo app Django.
- Criar ou alterar models persistentes.
- Gerar migrations.
- Implementar CI/CD remoto no GitHub Actions.
- Alterar layout visual do dashboard.
- Executar restore real de banco ou mídia.
- Exigir serviços externos, segredos ou credenciais de produção.

## Arquitetura

O avaliador segue o mesmo padrão das Sprints 33 e 34:

- Uma função pura de avaliação em `core/product_acceptance.py`.
- Uma estrutura de resultado simples, serializável em JSON.
- Um comando Django fino que apenas invoca o avaliador, imprime o resultado e
  define o exit code quando `--fail-on-error` estiver ativo.
- Testes unitários focados em comportamento, com arquivos temporários quando
  for necessário simular falha sem modificar o projeto real.

O avaliador deve funcionar sem banco de dados. Ele inspeciona arquivos do
repositório, rotas Django carregáveis e comandos registrados no Django. Isso
mantém o check leve, reprodutível e seguro para rodar em ambiente local,
container, deploy e revisão operacional.

## Contrato Do Resultado

`evaluate_product_acceptance(project_root=None)` retorna um objeto com:

- `passed`: booleano agregado.
- `checks`: lista ordenada de checks.

Cada check contém:

- `code`: identificador estável em inglês.
- `title`: título em português brasileiro.
- `passed`: booleano.
- `success`: mensagem objetiva em português brasileiro.
- `failure`: mensagem objetiva em português brasileiro.

O comando `check_product_acceptance --format json` deve serializar esse contrato
sem expor segredos, variáveis de ambiente sensíveis ou caminhos privados além
dos caminhos relativos do projeto.

## Checks De Aceite

### Rotas E APIs

O check confirma que:

- `core.urls` contém `health`, `home`, `schema`, `swagger-ui`, `api/v1/` e
  `admin/`.
- `core.api_v1_urls` inclui os módulos principais entregues nas sprints:
  accounts, tenants, masters, formulations, production, planning, procurement,
  inventory, costing, finance, fiscal, crm, quality, qa, documents, deviations,
  capa, changes, audits, risks, regulatory, pharmacovigilance, recalls,
  maintenance, training, files, reports, workflow, integrations, ai-agents,
  governance e compliance.

### Menus

O check confirma que `templates/base.html` contém links administrativos para
os módulos críticos do ERP, incluindo produção, estoque, qualidade,
documentos, desvios, CAPA, governança e conformidade.

### Comandos Operacionais

O check confirma que os comandos abaixo são descobertos pelo Django:

- `check_operational_readiness`
- `check_backup_restore_readiness`
- `check_transversal_compliance`

### Documentação

O check confirma que `mkdocs.yml`, `docs/index.md`, `docs/deployment.md` e
arquivos de arquitetura referenciam:

- prontidão operacional;
- backup e restauração;
- conformidade transversal;
- aceite de produto;
- comandos de verificação.

### PRD

O check confirma que o `PRD.md` registra a Sprint 35 com status `executed` e
tarefas de aceite técnico marcadas como concluídas.

Durante o desenvolvimento, esse check começa vermelho até a atualização final
do PRD. Ele é o último item de fechamento da sprint.

## Tratamento De Erros

- Arquivos ausentes geram checks falhos com mensagem objetiva.
- Falha ao carregar rotas ou comandos gera check falho sem stack trace na saída
  padrão do comando.
- O comando retorna código 1 somente quando existir falha e `--fail-on-error`
  tiver sido informado.
- A saída JSON permanece válida mesmo quando há falhas.

## Testes

Os testes seguem TDD:

- Primeiro teste falha por ausência de `core.product_acceptance`.
- Testes seguintes cobrem o contrato do resultado, saída texto, saída JSON,
  `--fail-on-error`, falha simulada por documentação incompleta e presença dos
  checks críticos.
- A suíte relevante deve rodar com `pytest tests/test_product_acceptance.py`.
- Antes de concluir, devem rodar também `manage.py check`, `makemigrations
  --check --dry-run`, `check_product_acceptance --fail-on-error` e os checks
  operacionais das Sprints 33 e 34.

## Documentação

Atualizações obrigatórias:

- `README.md`: adicionar comando de aceite de produto.
- `docs/index.md`: adicionar a Sprint 35 ao índice funcional.
- `docs/architecture/product-acceptance.md`: documentar objetivo, execução,
  checks e critérios de aceite.
- `mkdocs.yml`: expor a nova página.
- `PRD.md`: registrar a Sprint 35 executada com checklist.

## Critérios De Aceite

- O comando `check_product_acceptance --fail-on-error` passa no repositório.
- A saída JSON do comando contém `passed=true`.
- Os testes específicos da Sprint 35 passam.
- `manage.py check` passa.
- `makemigrations --check --dry-run` não detecta migrations pendentes.
- Os comandos `check_operational_readiness --fail-on-error` e
  `check_backup_restore_readiness --fail-on-error` continuam passando.
- A documentação nova aparece no MKDocs.
- `PRD.md` registra a Sprint 35 como executada.
- Não existem migrations novas.

## Riscos E Mitigações

- Risco: o check ficar frágil por depender de texto exato demais.
  Mitigação: usar identificadores estáveis de rotas, comandos, arquivos e
  nomes de módulos, não frases longas de documentação.

- Risco: duplicar lógica dos checks das Sprints 33 e 34.
  Mitigação: a Sprint 35 valida integração e presença dos gates, sem reexecutar
  internamente cada detalhe operacional.

- Risco: transformar aceite em CI/CD.
  Mitigação: CI/CD fica fora de escopo. O entregável é um gate local e
  containerizável.
