# Sprint 45 — Deploy local/staging e observabilidade

## Objetivo

Disponibilizar um ambiente Docker Compose local reproduzível para o RGN Farma
System, com healthchecks, diagnóstico e smoke tests das rotas críticas, sem
depender de Swarm, Cloudflare, GHCR ou credenciais de produção.

## Escopo

- Criar um perfil Compose local explícito e isolado do stack de produção.
- Construir a imagem da aplicação uma única vez e reutilizá-la nos processos
  web, Celery worker, Celery beat e backup.
- Configurar PostgreSQL, Redis e RabbitMQ com credenciais locais documentadas.
- Garantir healthchecks funcionais para infraestrutura e processos.
- Adicionar smoke test local para `/health/`, `/`, `/api/schema/` e `/api/docs/`.
- Documentar inicialização, parada, logs, diagnóstico e limpeza.
- Registrar a Sprint 45 no `PRD.md` após a validação.

## Fora de escopo

- Deploy em VPS, Docker Swarm ou domínio público.
- Uso de Cloudflare, GHCR privado ou certificados reais.
- Credenciais, tokens ou segredos reais.
- Alteração de modelos de negócio ou geração de migrations.

## Arquitetura

`docker-compose.local.yml` será autocontido para desenvolvimento e staging
local. Os serviços de infraestrutura usam imagens oficiais; os processos da
aplicação usam uma imagem local construída a partir do `Dockerfile`. Um arquivo
`.env.local.example` documentará apenas valores seguros de desenvolvimento.

Um script de smoke test aguardará o endpoint de saúde e verificará as rotas
críticas, retornando código diferente de zero quando qualquer resposta
esperada falhar. Os healthchecks Docker permanecerão independentes do script,
permitindo diagnóstico por `docker compose ps` e `docker compose logs`.

## Observabilidade e segurança

- Healthchecks terão timeout, retries e período de inicialização explícitos.
- Logs serão consultáveis por serviço, sem imprimir variáveis sensíveis.
- O backup para Google Drive permanecerá desabilitado no perfil local.
- O segredo de cifragem local será gerado/documentado fora do controle de
  versão.
- O perfil Cloudflare não será iniciado por padrão.

## Critérios de aceite

1. `docker compose -f docker-compose.local.yml config` termina com sucesso.
2. `docker compose -f docker-compose.local.yml up -d --build` inicia os
   serviços sem exigir credenciais externas.
3. PostgreSQL, Redis, RabbitMQ, web, worker e beat ficam saudáveis.
4. O smoke test retorna sucesso para `/health/`, `/`, `/api/schema/` e
   `/api/docs/`.
5. `manage.py check` e a suíte automatizada passam usando o banco local.
6. A documentação permite repetir o fluxo sem conhecimento implícito.
7. O `PRD.md` registra todos os itens da Sprint 45 como executados.
