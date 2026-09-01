# Relatórios, BI e Indicadores

## Arquitetura single-instance

Este módulo opera em escopo global da instalação local. O acesso é controlado
por autenticação Django e permissões nativas `view`, `add`, `change` e
`delete`, administradas no Django Admin por usuário ou grupo.

As APIs e telas operacionais não exigem cabeçalho de escopo, seleção de empresa
ou vínculo de contrato por cliente. Listagens, formulários, detalhes e ações
usam o mesmo conjunto global de dados da instância.

## Regras de implementação

- Preservar as regras de negócio da indústria de cosméticos do módulo.
- Validar relacionamentos pelo contexto funcional do domínio, não por escopo
  SaaS herdado.
- Manter trilha de auditoria, logs e justificativas quando aplicável.
- Expor menus e botões somente conforme permissões Django reais.
- Criar migrations consistentes para qualquer alteração de modelo.
- Cobrir novas regras com testes automatizados.

## APIs e UI

Endpoints REST devem usar `IsAuthenticated` e permissões Django de modelo. A UI
operacional em `/app/` deve usar o shell, cards, tabelas, formulários, badges,
modais, paginação e estados do design system.

## Catálogo curado

A instalação mantém 15 definições de relatório operacionais gerenciadas pelo
sistema, identificadas pelos códigos `REL-FIN-001` a `REL-FIN-004`,
`REL-FIS-001` a `REL-FIS-003`, `REL-EST-001` a `REL-EST-003`, `REL-COM-001` a
`REL-COM-002` e `REL-PRO-001` a `REL-PRO-003`. Cada definição aponta para uma
chave fixa do registro de executores e exige a permissão Django do domínio
financeiro, fiscal, estoque/rastreabilidade, compras ou produção.

Nenhuma definição operacional pode fornecer SQL, caminho de model, lista de
campos ou expressão executável. O código do executor é resolvido exclusivamente
em uma lista registrada no servidor.

O catálogo versão 1 é:

| Código | Título exato | Filtros disponíveis | Filtros obrigatórios |
|---|---|---|---|
| `REL-FIN-001` | Contas a receber em aberto e vencidas | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`), Cliente (`customer`) | Nenhum |
| `REL-FIN-002` | Contas a pagar em aberto e vencidas | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`), Fornecedor (`supplier`) | Nenhum |
| `REL-FIN-003` | Fluxo de caixa realizado e projetado | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`), Cliente (`customer`), Fornecedor (`supplier`) | Data inicial (`period_start`), Data final (`period_end`) |
| `REL-FIN-004` | Resultado financeiro por período | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`), Cliente (`customer`), Fornecedor (`supplier`) | Data inicial (`period_start`), Data final (`period_end`) |
| `REL-FIS-001` | Documentos fiscais por período e situação | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`), Fornecedor (`supplier`), Cliente (`customer`) | Data inicial (`period_start`), Data final (`period_end`) |
| `REL-FIS-002` | Apuração de tributos | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`) | Data inicial (`period_start`), Data final (`period_end`) |
| `REL-FIS-003` | Livro de entradas e saídas | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`), Fornecedor (`supplier`), Cliente (`customer`) | Data inicial (`period_start`), Data final (`period_end`) |
| `REL-EST-001` | Posição de estoque | Produto (`product`), Lote (`lot`), Situação (`status`), Fornecedor (`supplier`) | Nenhum |
| `REL-EST-002` | Lotes próximos do vencimento ou vencidos | Data inicial (`period_start`), Data final (`period_end`), Produto (`product`), Lote (`lot`), Situação (`status`), Fornecedor (`supplier`) | Data final (`period_end`) |
| `REL-EST-003` | Genealogia e rastreabilidade de lotes | Produto (`product`), Lote (`lot`) | Nenhum |
| `REL-COM-001` | Pedidos de compra abertos ou atrasados | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`), Fornecedor (`supplier`), Produto (`product`) | Nenhum |
| `REL-COM-002` | Divergências de recebimento e fornecedores | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`), Fornecedor (`supplier`), Produto (`product`) | Data inicial (`period_start`), Data final (`period_end`) |
| `REL-PRO-001` | Ordens de produção por situação e atraso | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`), Produto (`product`) | Nenhum |
| `REL-PRO-002` | Consumo planejado versus realizado | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`), Produto (`product`), Lote (`lot`) | Data inicial (`period_start`), Data final (`period_end`) |
| `REL-PRO-003` | Rendimento, perdas e custo por ordem | Data inicial (`period_start`), Data final (`period_end`), Situação (`status`), Produto (`product`) | Data inicial (`period_start`), Data final (`period_end`) |

No catálogo atual, `period_start` e `period_end` são datas; `product`,
`customer` e `supplier` são inteiros; `status` e `lot` são textos. A
infraestrutura também aceita `choice` em schemas controlados pelo servidor,
incluindo uma opção vazia inicial. Cada definição curada permite exatamente
`pdf`, `xlsx` e `csv`.

`reports.catalog.sync_curated_report_catalog()` é a única rotina runtime
autorizada a reconciliar campos técnicos dessas definições. A operação:

- valida o catálogo completo antes de gravar;
- cria somente códigos ausentes;
- atualiza definições já gerenciadas mantendo suas chaves primárias e os
  vínculos de agendamentos e execuções;
- falha antes de qualquer escrita se um código canônico pertencer a uma
  definição criada pelo usuário;
- grava cópias independentes dos valores JSON.

Todo o ciclo de reconciliação usa o alias retornado pelo roteador Django para
escrita: lock, leitura de colisões e persistência são ligados explicitamente ao
mesmo banco primário e à mesma transação. Se dois processos partirem de um
catálogo vazio, uma violação de unicidade faz a transação inteira voltar e ser
repetida uma única vez. Assim, um vencedor gerenciado converge de forma
idempotente; um vencedor criado pelo usuário produz erro de colisão sem deixar
definições parciais. Uma segunda falha de integridade não é ocultada.

As listas explícitas aceitas pelos executores são a fonte de verdade para
`filter_schema`. Um teste compara o catálogo com as chamadas
`normalize_report_filters()` para impedir divergência entre o formulário e a
consulta executada.

A migration `0005_seed_curated_report_catalog` contém uma cópia congelada do
catálogo versão 1. Sua reversão é intencionalmente vazia: relatórios,
agendamentos e execuções históricas nunca são apagados. Reaplicar a migration
reconcilia os metadados canônicos e preserva as chaves existentes.

## Execução operacional e download

### Acesso e validação

O catálogo operacional fica em `/app/reports/catalog/`. Ele lista somente
definições ativas gerenciadas pelo sistema e filtra cada item pela
`required_permission` do domínio. As definições técnicas continuam disponíveis
na UI e na API apenas para usuários com `reports.change_reportdefinition`.

Consultar o catálogo exige `reports.view_reportdefinition`. Executar exige
também `reports.add_reportexecution` e a permissão de domínio gravada na
definição. A definição canônica é relida com lock e precisa continuar ativa
antes da criação da execução.

O formulário de execução é construído exclusivamente a partir de
`filter_schema`. Os tipos aceitos são `date`, `choice`, `text` e `integer`;
qualquer outro tipo ou configuração de escolhas malformada falha fechado.
Campos obrigatórios seguem `required_filters`. Para definições gerenciadas pelo
sistema, formulário, API e model usam o mesmo compilador: somente campos
declarados são aceitos e cada valor deve respeitar exatamente o tipo e as
escolhas do schema. A validação global histórica por nomes permitidos permanece
apenas para definições não gerenciadas, preservando compatibilidade explícita.
Campos `choice` começam com uma opção vazia: os obrigatórios exigem seleção
explícita, os opcionais podem ser omitidos, e valores válidos preservam o tipo
declarado (`str` ou `int`) depois da submissão HTML.

A orquestração recarrega e bloqueia a definição canônica na transação antes de
validar atividade, permissões, formato e filtros. Uma definição inativa ou
alterada concorrentemente é rejeitada antes de criar `ReportExecution`,
evitando registros pendentes órfãos.

### Ciclo de vida, concorrência e falhas

Execuções transitam por `pending`, `running`, `completed`, `failed` ou
`cancelled`. A entrada — definição, filtros, formato, solicitante, agendamento,
número e instante da solicitação — forma um snapshot imutável, verificado
novamente antes da conclusão. O claim usa lock e lease padrão de 300 segundos.
Uma segunda tentativa durante um lease válido recebe "já está em andamento";
um lease expirado pode ser retomado depois da reconciliação de reservas
anteriores.

Somente `ConnectionError`, `TimeoutError` e `OSError` capturados durante a
execução são classificados como falhas recuperáveis. Nesses casos, o serviço
devolve a execução a `pending`, expurga o artefato parcial ou o marca para
reconciliação e levanta `ReportExecutionRetryableError`. Exceções Django de
banco de dados não são consideradas recuperáveis apenas por sua origem; quando
não pertencem a uma dessas três classes, seguem o tratamento de falha
definitiva.

O retry automático existe somente no caminho Celery:
`reports.tasks.generate_report_execution` captura
`ReportExecutionRetryableError` e chama `self.retry`. A task usa `acks_late`,
rejeita perda do worker, permite até cinco retries e calcula backoff a partir
de 15 segundos, limitado a 300 segundos. Esgotado o limite, a execução passa a
`failed`. Já a execução direta síncrona pela interface HTML ou API devolve erro
seguro ao chamador e permanece `pending`, sem enfileirar automaticamente uma
nova tentativa; uma retomada requer redisparo explícito e autorizado. Falhas
de validação ou internas não transitórias terminam em `failed`, com mensagem
pública genérica; detalhes ficam nos logs técnicos.

Claims, retomadas, retries, falhas, esgotamento e conclusão tentam registrar
eventos funcionais por `_record_execution_audit`. Essa gravação é
**best-effort**: uma falha em `GovernanceAuditLog.record` é capturada e
registrada no log técnico, sem bloquear ou reverter o ciclo de vida do
relatório. Não há outbox durável nem replay automático desses eventos. O
monitoramento deve alertar para a mensagem de falha de auditoria, e a
homologação deve simular sua indisponibilidade para comprovar que o lifecycle
prossegue e que a ocorrência é encaminhada como desvio/incidente para
reconciliação.

### Agendamentos, Celery e notificações

`ReportSchedule` armazena definição, filtros, formato, proprietário,
destinatários, frequência (`daily`, `weekly`, `monthly` ou `cron`),
`next_run_at`, `last_run_at` e estado ativo. A chamada de serviço
`trigger_now(run_immediately=False)` cria a execução, envia
`reports.tasks.generate_report_execution` ao Celery e persiste o ID da task.
A ação REST `trigger_now` existente usa `run_immediately=True` e, portanto,
executa no próprio request.

Após uma execução agendada concluída, `record_run()` registra `last_run_at` e
avança `next_run_at`: um dia para diário, sete dias para semanal, trinta dias
para mensal e, no código atual, um dia para `cron`. A expressão cron é exigida
no cadastro, mas não é interpretada por `_next_run_after`. O repositório atual
também não contém uma task que procure automaticamente agendamentos vencidos.
Assim, cadastrar `next_run_at` isoladamente não dispara o relatório; uma
orquestração aprovada precisa chamar o caminho de disparo.

Na conclusão, notificações internas são criadas para os destinatários do
agendamento ou, se não houver destinatários, para o solicitante. O fluxo
automático atual usa o canal `internal`; falha ao atualizar o agendamento ou
notificar é registrada em log, e falha de notificação também tenta registrar
auditoria de warning, sem desfazer um relatório já concluído.

### Artefato protegido, integridade e download

O resultado é reservado como `ProtectedFile` de origem de sistema e tipo
relatório. Os bytes renderizados são criptografados com AES-256-GCM e recebem
hash SHA-256 do conteúdo em claro; a execução concluída registra o mesmo hash e
a quantidade de linhas. Em falha ou retry, blobs e reservas parciais são
excluídos de forma controlada antes de desvincular a execução.

Downloads de relatórios concluídos exigem simultaneamente
`reports.view_reportexecution` e `files.view_protectedfile`. A rota
`/api/reports/executions/<id>/download/` delega ao mesmo caminho canônico usado
por `/api/files/protected-files/<id>/download/`: disponibilidade, regra de
acesso do arquivo, leitura AES-256-GCM, MIME/nome seguros e auditoria com IP e
user agent. Estados não concluídos, artefatos ausentes, blobs ausentes e falhas
de cifra nunca retornam bytes nem referências internas. Respostas REST de
execuções, arquivos e uso de links seguros não expõem caminhos de storage.
Downloads bem-sucedidos usam `private, no-store, max-age=0`, `Pragma:
no-cache`, `Expires: 0`, `nosniff` e `Vary` para credenciais. Tentativas de
download de execução não concluída com artefato associado registram
`access_denied`; sem artefato, nenhuma trilha de arquivo artificial é criada.
Somente arquivos `active`, associados a execução `completed`, criptografados e
autorizados pela regra de acesso são lidos. Upload cifrado, geração/uso de link,
download, negação, expiração e exclusão usam os eventos de
`ProtectedFileAuditTrail` implementados diretamente no fluxo do arquivo
protegido. IP e user agent são registrados somente nos fluxos que recebem
esses metadados da requisição, como download, negação e geração ou uso de link;
não há essa garantia geral para upload interno, expiração ou exclusão. Esses
eventos não devem ser confundidos com a auditoria best-effort do lifecycle do
relatório e também não possuem garantia de outbox ou replay automático.

## Verificação mínima

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check

TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q
```
