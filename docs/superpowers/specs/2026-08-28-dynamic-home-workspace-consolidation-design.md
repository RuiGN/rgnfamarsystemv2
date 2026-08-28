# Consolidação da Home Dinâmica e dos Workspaces

## Objetivo

Eliminar a página inicial estática duplicada e consolidar os cockpits de
operação, qualidade e workflow em uma única infraestrutura configurável, sem
alterar URLs públicas, APIs REST, models ou regras de negócio.

## Escopo

Esta entrega compreende:

- redirecionamento da rota `/` para `/app/` após autenticação;
- preservação do redirecionamento de usuários anônimos para o login;
- substituição das três views especializadas de workspace por uma view
  configurável;
- substituição dos três templates de workspace por um template compartilhado;
- preservação das rotas existentes de operação, qualidade e workflow;
- filtragem de cartões e atalhos conforme permissões Django;
- atualização dos testes e da documentação operacional.

Não fazem parte desta entrega:

- registros agregados de mudanças, fiscal, compras ou outros módulos;
- alterações em models, migrations, serializers ou APIs REST;
- incorporação dos workspaces ao hub analítico de dashboards;
- mudança no cálculo funcional das métricas existentes.

## Arquitetura

### Página inicial

`core.views.home` continuará sendo a entrada da aplicação. Para requisições
anônimas, redirecionará para `accounts:login`. Para usuários autenticados,
redirecionará para `app:index`.

O template estático `templates/dashboard/home.html` deixará de fazer parte do
fluxo de navegação e será removido. O catálogo dinâmico e permissionado de
módulos em `/app/` será a única página inicial funcional.

### Registro dos workspaces

A camada de UI manterá um registro imutável, indexado pelos slugs:

- `operations`;
- `quality`;
- `workflow`.

Cada configuração declarará:

- slug;
- título;
- descrição;
- rótulo do breadcrumb;
- módulo usado para autorização;
- função construtora do contexto;
- cartões de métricas;
- atalhos rápidos.

A função construtora continuará responsável pelas consultas ORM. O template
receberá somente estruturas normalizadas e não consultará models nem executará
regras de negócio.

### Contrato normalizado

Cada cartão disponibilizará:

- `label`;
- `value`;
- `icon`;
- `tone`;
- `badge`;
- `url`;
- permissão opcional.

Cada atalho disponibilizará:

- `label`;
- `icon`;
- `url`;
- permissão opcional.

Os itens cuja permissão opcional não seja concedida ao usuário serão omitidos
antes da renderização. O template não fará concatenação de URLs e receberá URLs
resolvidas com `reverse`.

## Views e rotas

Uma única `WorkspaceView` resolverá `workspace_slug`, verificará a permissão do
módulo e renderizará `workspaces/workspace.html`.

As URLs atuais serão preservadas com seus nomes existentes:

- `app:operations_workspace`;
- `app:quality_workspace`;
- `app:workflow_workspace`.

Cada rota fornecerá um `workspace_slug` fixo para a view compartilhada. Isso
mantém compatibilidade com menus, favoritos, testes e links existentes. Um slug
desconhecido, caso a view seja chamada diretamente, produzirá `Http404`.

## Permissões e segurança

O acesso ao workspace exigirá a permissão de visualização do módulo associado,
reutilizando a semântica atual de `ModuleConfig.can_view`.

- falta de permissão do módulo: resposta 403;
- workspace inexistente: resposta 404;
- cartão ou atalho sem permissão: item omitido;
- consultas e métricas: somente leitura;
- nenhuma regra de autorização dependerá exclusivamente do template.

O workspace de workflow continuará restringindo notificações ao usuário
autenticado. Os demais cálculos manterão os querysets e estados utilizados pela
implementação existente.

## Template compartilhado

`templates/workspaces/workspace.html` renderizará:

1. título, descrição e breadcrumb;
2. grade responsiva de cartões de métricas;
3. estado vazio explícito caso nenhum cartão seja visível;
4. bloco de atalhos rápidos quando houver itens autorizados.

O layout utilizará Bootstrap 5 e as classes Duralux já adotadas pelo projeto.
Ícones e tons serão fornecidos pelo contrato, evitando condições específicas de
módulo no template.

## Tratamento de erros

- consultas manterão o comportamento transacional e de banco atual;
- erros inesperados de banco não serão ocultados pelo template;
- referências de configuração inválidas deverão falhar durante os testes;
- URLs serão resolvidas no servidor para detectar rotas inexistentes;
- valores numéricos ausentes serão apresentados como zero somente quando essa
  for a característica explícita da métrica.

## Testes

Os testes automatizados deverão comprovar:

- usuário anônimo em `/` é redirecionado para o login;
- usuário autenticado em `/` é redirecionado para `/app/`;
- cada uma das três URLs existentes renderiza o template compartilhado;
- títulos, métricas e atalhos permanecem corretos para cada workspace;
- notificações do workflow são calculadas somente para o usuário atual;
- usuário sem permissão do módulo recebe 403;
- cartões e atalhos com permissão ausente não aparecem;
- configuração ou slug desconhecido retorna 404;
- os templates antigos não são mais referenciados;
- a suíte de UI existente continua passando.

## Documentação

`TEMPLATES.md` será atualizado para documentar o contrato dos workspaces e o
uso de `/app/` como página inicial autenticada. A documentação de arquitetura
afetada será ajustada apenas quando já descrever a antiga home ou os workspaces
especializados.

## Critérios de aceitação

- não existe duplicação de markup entre os três workspaces;
- todas as URLs e nomes de rota existentes continuam válidos;
- `/` não renderiza mais o painel estático;
- permissões de módulo e de itens são aplicadas no servidor;
- não existem alterações de banco ou API;
- testes direcionados e verificações Django passam;
- documentação operacional está consistente com a implementação.
