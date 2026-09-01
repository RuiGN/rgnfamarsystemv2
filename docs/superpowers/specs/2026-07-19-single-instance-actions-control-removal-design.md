# Instância Única, Remoção do Control Plane e Ações Operacionais HTML

## Contexto

O RGN Farma System já concluiu a conversão funcional dos models, APIs e CRUD
operacional para single-instance. O banco local usa schema global, as
migrations de limpeza estão aplicadas e o runtime depende apenas de usuários,
grupos e permissões nativas do Django.

Ainda permanecem dois desvios em relação ao produto desejado:

1. o Control Plane continua instalado, com host, URLs, middlewares, models,
   templates, MFA e fluxo de suporte próprios;
2. o CRUD HTML genérico cobre 223 recursos, mas as 253 ações POST de domínio
   expostas pelo DRF não possuem uma interface HTML equivalente.

Esta especificação remove o Control Plane do runtime, mantém o Django Admin em
`/admin/` e disponibiliza todas as ações POST de domínio na interface
operacional, em português brasileiro com acentuação correta.

## Objetivos

- Operar em um único domínio e uma única instância.
- Manter somente o login `/accounts/login/` para a aplicação.
- Manter o Django Admin em `/admin/`, usando autenticação padrão de usuários
  staff e superusuários.
- Remover rotas, hosts, middlewares, templates, MFA e sessões de suporte do
  Control Plane.
- Preservar a rastreabilidade histórica do Control Plane antes de remover suas
  tabelas funcionais.
- Expor na interface HTML todas as ações POST registradas nos ViewSets DRF.
- Reutilizar as APIs existentes como fonte de verdade para validação,
  autorização, transações, regras de domínio e auditoria.
- Garantir textos visíveis em português brasileiro, com acentuação correta.
- Manter PostgreSQL, Redis, RabbitMQ, Celery, Docker, Nginx e Cloudflare Tunnel
  no ambiente de produção da VPS Contabo.

## Fora do escopo

- Reintroduzir segmentação, organizações ou domínios por cliente.
- Criar um template separado para cada model ou ação.
- Duplicar regras de negócio da API em views HTML.
- Alterar regras farmacêuticas já cobertas pelos métodos de domínio.
- Substituir o Django Admin por uma administração própria.
- Remover migrations históricas necessárias para reconstruir bancos antigos.

## Arquitetura final

### Superfícies públicas

O sistema terá apenas estas superfícies:

- `/accounts/login/`: login único;
- `/app/`: aplicação operacional;
- `/admin/`: Django Admin padrão para usuários staff e superusuários;
- `/api/`: APIs REST autenticadas;
- `/api/schema/` e `/api/docs/`: contrato OpenAPI e documentação;
- `/health/`: healthcheck.

O único domínio público será `rgnfarmasystem.rgnsystems.com.br`. O domínio
`control.rgnfarmasystem.rgnsystems.com.br` e todas as variáveis
`CONTROL_PLANE_*` serão removidos dos settings, arquivos `.env` de exemplo,
Docker Compose, Nginx, Cloudflare Tunnel e documentação operacional.

### Autenticação e autorização

- A aplicação continuará usando sessão Django e CSRF.
- O login sempre redirecionará usuários autenticados para `/app/`, respeitando
  um parâmetro `next` local e seguro quando presente.
- `/admin/` usará o comportamento padrão do Django: `is_staff`, `is_active` e
  permissões nativas.
- `is_platform_operator` será removido do usuário por migration.
- A visibilidade de módulos, recursos, botões e ações continuará baseada em
  `User.has_perm()`.
- Ocultar um botão nunca substituirá a autorização no servidor. A API deverá
  revalidar a permissão em toda requisição.

## Remoção segura do Control Plane

### Runtime removido

Serão removidos:

- include de `control_plane.urls` em `core.urls`;
- `ControlPlaneHostMiddleware`;
- `PlatformAdminAccessMiddleware`;
- `SupportSessionMiddleware`;
- configuração customizada `PlatformAdminConfig`;
- ramificação de login para operador e MFA;
- templates `templates/control_plane/`;
- formulários, services, views, commands e admin específicos;
- dependências de `django-otp` usadas exclusivamente pelo Control Plane;
- campos e métodos de usuário exclusivos de operador da plataforma;
- testes de host, MFA, onboarding e sessão de suporte;
- variáveis de ambiente, rotas de proxy e documentação do domínio de controle.

### Preservação de evidência

Antes de excluir `PlatformAuditEvent` e `SupportSession`, uma migration de dados
copiará seus registros para `GovernanceAuditLog`. O conteúdo original será
preservado em contexto seguro, incluindo identificador, ator, ação, alvo,
mensagem, timestamps, status, modo de acesso, motivo, aprovador e expiração
quando disponíveis.

Os eventos usarão `module=governance`. Eventos de auditoria serão convertidos
para o tipo e a severidade equivalentes; sessões de suporte serão registradas
como eventos de segurança, com ação estável derivada do status legado. O ator
será associado a `user` quando ainda existir e os demais campos sem equivalente
direto ficarão em `safe_context`, junto com `legacy_source` e `legacy_id`.

A migration deverá:

1. ser idempotente pela combinação do tipo legado e identificador original;
2. preservar timestamps históricos sem reescrevê-los como horário atual;
3. sanitizar metadados com o helper já usado pelo projeto;
4. registrar contagens antes e depois da cópia;
5. falhar antes da exclusão se as contagens não coincidirem;
6. excluir os models do Control Plane somente após a cópia íntegra.

O pacote `control_plane` permanecerá apenas como tombstone de migrations,
equivalente ao app histórico de escopo por cliente. Ele não terá URLs, models funcionais,
templates ou imports no runtime. Isso preserva a reconstrução e o rollback do
grafo histórico sem manter uma superfície administrativa paralela.

## Interface HTML de ações de domínio

### Princípio

A API existente será a única executora das ações. A interface HTML fornecerá
descoberta, formulários, confirmação e feedback, enviando requisições para os
endpoints DRF na mesma origem.

Não haverá cópia de chamadas como `approve()`, `release()`, `close()` ou
`cancel()` para views HTML. A API continuará responsável por:

- buscar o objeto;
- verificar permissões;
- validar o estado atual;
- abrir transações;
- executar o método de domínio;
- registrar auditoria;
- serializar sucesso ou erro.

### Estrutura do registro

O código ficará dividido por responsabilidade:

- `base/ui/actions/types.py`: tipos imutáveis `ActionConfig`, `ActionField` e
  `ActionConfirmation`;
- `base/ui/actions/registry.py`: registro agregado, validação de duplicidades e
  consultas por módulo/recurso;
- `base/ui/actions/modules/`: um arquivo por app Django com suas ações;
- `base/ui/actions/context.py`: ações disponíveis para o usuário e o objeto;
- `base/ui/actions/forms.py`: geração de formulários Django a partir dos
  metadados;
- `base/ui/actions/views.py`: endpoint HTML de preparação e fallback POST com
  despacho interno para o callback DRF registrado;
- `templates/app/includes/resource_actions.html`: botões e estados vazios;
- `templates/app/resource_action_form.html`: formulário reutilizável;
- `static/js/resource-actions.js`: modal, CSRF, envio e apresentação de erros.

`ActionConfig` declarará:

- módulo e recurso do CRUD genérico;
- nome estável da ação DRF;
- nome reversível do endpoint;
- se a ação é de detalhe ou coleção;
- rótulo, descrição e mensagem de sucesso em pt-BR;
- ícone Feather e tom visual Bootstrap;
- permissão Django obrigatória;
- estados em que a ação pode aparecer;
- campos e tipos do payload;
- modo de confirmação;
- formato de envio JSON ou multipart;
- comportamento de resposta: atualizar página, redirecionar ou baixar arquivo.

`ActionField` suportará:

- texto curto;
- texto longo;
- inteiro e decimal;
- booleano;
- data e data/hora;
- seleção com choices;
- UUID ou chave de relacionamento;
- arquivo;
- campo oculto preenchido pelo contexto.

Cada campo declarará nome do payload, rótulo pt-BR, obrigatoriedade, ajuda,
placeholder, limites, choices e widget. O registro não armazenará segredos nem
valores de usuário.

### Descoberta e completude

Um teste introspectará todos os ViewSets instalados e coletará métodos marcados
com `@action(..., methods=['post'])`. O conjunto encontrado deverá ser idêntico
ao conjunto do registro HTML.

O teste falhará quando:

- uma ação DRF não possuir `ActionConfig`;
- o registro apontar para uma ação inexistente;
- houver chave duplicada;
- o recurso genérico não existir;
- a rota não puder ser revertida;
- uma ação não declarar permissão;
- rótulo, confirmação ou mensagem estiverem vazios.

A contagem inicial aprovada é de 253 ações POST. A comparação por conjuntos,
e não apenas pela contagem, garantirá que futuras ações também exijam UI.

### Fluxo no frontend

1. A página de detalhe recebe apenas ações compatíveis com o recurso, o usuário
   e o estado atual do objeto.
2. Ações sem payload e de baixo risco podem usar uma confirmação simples.
3. Ações com campos abrem o formulário reutilizável em modal ou página própria
   acessível sem JavaScript.
4. O JavaScript lê o cookie CSRF, envia JSON ou `FormData` e mantém o botão
   bloqueado enquanto a requisição estiver em andamento.
5. Respostas `2xx` exibem mensagem acentuada e executam o comportamento de
   sucesso configurado.
6. Erros `400` são associados aos campos e preservam os valores digitados.
7. Erros `403` mostram falta de permissão sem revelar dados do objeto.
8. Erros `409` ou validações de estado informam que o registro mudou e pedem
   atualização da página.
9. Erros inesperados usam mensagem segura, identificador de requisição e log no
   servidor, sem traceback ou segredo no frontend.

No fallback sem JavaScript, o formulário será recebido por uma view Django com
proteção CSRF explícita. A view resolverá somente a URL imutável declarada no
`ActionConfig` e despachará a mesma requisição autenticada para o callback DRF,
sem `force_authenticate`, alteração de usuário ou chamada direta ao método de
domínio. A resposta DRF será convertida no redirect ou no template genérico de
erros. Assim, autenticação, permissões, validações e transações continuam sendo
executadas exatamente pelo endpoint da API também nesse fluxo.

### Ações críticas e GxP

Ações de aprovação, rejeição, liberação, cancelamento, encerramento,
obsolescência, revogação, exclusão lógica e restauração exigirão confirmação
explícita. Quando a API exigir motivo, comentário, evidência ou significado de
assinatura, o campo será obrigatório no formulário.

O registro poderá exigir uma frase de confirmação para operações de maior
impacto. O frontend não habilitará a submissão até a frase coincidir, mas a API
continuará responsável pela validação definitiva.

## Português brasileiro

Todo texto novo visível ao usuário deverá:

- usar português brasileiro;
- preservar acentos e cedilha em UTF-8;
- usar verbos claros no infinitivo ou no imperativo conforme o contexto;
- evitar nomes internos de classes, campos ou endpoints;
- manter mensagens de erro objetivas e acionáveis;
- usar `lang="pt-BR"` no documento HTML.

Um teste estático rejeitará formas não acentuadas conhecidas em metadados e
templates novos, incluindo `aprovacao`, `producao`, `execucao`, `nao`,
`relatorio`, `rejeicao`, `alteracao`, `confirmacao` e `exclusao`, sem aplicar a
regra a identificadores de código, URLs ou chaves JSON.

## Desempenho

- O contexto de ações não fará consultas por ação.
- Predicados de estado usarão atributos já carregados do objeto.
- Relacionamentos usados para disponibilidade serão declarados no recurso e
  carregados com `select_related()` ou `prefetch_related()`.
- Metadados do registro serão imutáveis e construídos uma vez por processo.
- A página não carregará os 253 formulários; somente metadados resumidos dos
  botões e o formulário da ação selecionada serão renderizados.

## Segurança

- Todas as requisições de ação exigirão usuário autenticado, sessão válida e
  CSRF.
- URLs serão geradas com `reverse()`, nunca concatenadas a partir de entrada do
  usuário.
- Campos extras enviados pelo cliente serão ignorados ou rejeitados pela API.
- A resposta não poderá inserir HTML não confiável em mensagens.
- Uploads continuarão sujeitos às validações existentes de tamanho, tipo,
  hash, armazenamento protegido e autorização.
- A interface respeitará `DjangoModelPermissions` e permissões adicionais das
  ações DRF.
- A remoção do Control Plane não reduzirá permissões do ERP nem tornará o Admin
  público; `/admin/` continuará exigindo staff/superusuário.

## Deploy em domínio único

Os artefatos de produção serão ajustados para:

- publicar somente `rgnfarmasystem.rgnsystems.com.br`;
- remover qualquer rota de borda e host Cloudflare de `control`;
- remover `CONTROL_PLANE_DOMAIN`, `CONTROL_PLANE_HOSTS` e
  `CONTROL_PLANE_BASE_URL`;
- configurar `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` somente com o domínio
  principal e endpoints locais necessários;
- manter Nginx interno em porta sem conflito com os demais projetos da VPS;
- usar Cloudflare Tunnel dedicado apontando para o Nginx interno;
- validar `/health/`, `/accounts/login/`, `/app/`, `/admin/` e `/api/docs/`.

O deploy deverá interromper se o túnel não registrar conexão estável. Um
container em ciclo de reinício ou resposta pública diferente de `200` no
healthcheck será tratado como falha, não como sucesso parcial.

## Estratégia de implementação

O trabalho será dividido em quatro entregas testáveis:

1. **Runtime single-domain:** remover Control Plane, restaurar Admin padrão,
   migrar evidências e atualizar autenticação.
2. **Infraestrutura de ações:** tipos, registro, formulários, contexto, rota,
   template, JavaScript, segurança e testes de completude.
3. **Catálogo completo:** cadastrar as 253 ações por módulo, com testes por
   lote e fluxos críticos end-to-end.
4. **Operação e evidência:** domínio único na Contabo, documentação, usuário
   administrador, testes completos e evidências de aceite.

Cada entrega seguirá TDD: teste vermelho, implementação mínima, teste verde,
refatoração e gate do módulo. Nenhum lote poderá reduzir a cobertura total
abaixo de 80%.

## Testes

### Control Plane e autenticação

- `/platform/` retorna `404`.
- host `control.*` não recebe tratamento especial.
- login redireciona para `/app/`.
- `/admin/` aceita staff/superusuário e rejeita usuário comum.
- settings não contêm `CONTROL_PLANE_*` nem middlewares removidos.
- usuário não possui `is_platform_operator` após a migration.
- registros legados são copiados integralmente para auditoria de governança.

### Registro e interface de ações

- igualdade entre ações POST DRF e `ActionConfig`.
- permissão obrigatória e ocultação sem autorização.
- disponibilidade por estado do objeto.
- reversão de todas as URLs.
- renderização de cada tipo de campo.
- CSRF obrigatório.
- suporte a JSON e multipart.
- feedback de sucesso, validação, permissão, conflito e erro inesperado.
- fallback sem JavaScript.
- nenhuma ação duplicada ou órfã.

### Testes regulados por módulo

Cada módulo terá pelo menos um fluxo HTML completo para ação de sucesso e um
fluxo inválido. Produção, Qualidade, QA, Documentos, Desvios, CAPA, Mudanças,
Auditorias, Riscos, Regulatório, Farmacovigilância e Recall terão também testes
de permissão, estado incompatível, motivo obrigatório e auditoria.

### Gate final

- `manage.py check`;
- `makemigrations --check --dry-run`;
- migrations em banco PostgreSQL vazio e banco atualizado;
- Ruff lint e format check;
- mypy no escopo configurado;
- Bandit e auditoria de dependências;
- suite pytest integral com cobertura mínima de 80%;
- geração OpenAPI;
- MkDocs strict;
- healthchecks internos e públicos na VPS.

## Documentação

Serão atualizados:

- `MODIFICACAGERAL.prd`;
- arquitetura single-instance;
- autenticação e permissões;
- extensão do CRUD genérico;
- catálogo de ações HTML;
- deploy Contabo em domínio único;
- backup e restauração;
- inventário de secrets;
- pendências conhecidas;
- evidências de validação e rollback.

Documentos históricos em `docs/superpowers/` poderão conservar referências ao
estado antigo quando identificados explicitamente como históricos. Runbooks e
arquitetura vigentes não poderão instruir uso de escopo por cliente ou Control Plane.

## Rollback

- Fazer backup PostgreSQL e de mídia antes da migration de remoção.
- Registrar contagem e hash das evidências migradas.
- Manter migrations reversíveis para recriar tabelas e reidratar dados do
  contexto preservado quando tecnicamente possível.
- Manter o release anterior e sua imagem disponíveis.
- Em falha de ação HTML, desabilitar somente a nova superfície e preservar a
  API existente.
- Em falha de túnel, manter o backend interno saudável e reverter a configuração
  do túnel sem alterar o banco.

## Critérios de aceite

- Não existe rota, host, middleware, template ou login do Control Plane.
- `/admin/` funciona com autenticação padrão do Django.
- O domínio público único responde com TLS válido e healthcheck `200`.
- O registro HTML cobre exatamente todas as ações POST DRF.
- Todas as ações aparecem somente para usuários autorizados e estados válidos.
- Todas as ações podem ser executadas com e sem JavaScript.
- Regras de domínio, transações e auditoria continuam concentradas na API.
- Textos do frontend estão em português brasileiro com acentuação correta.
- Models e schema permanecem globais para a instalação.
- Migrations executam em banco vazio e atualizado.
- Testes, documentação, menus, permissões e evidências estão atualizados.
- Não restam pendências técnicas conhecidas relacionadas a esta mudança.
