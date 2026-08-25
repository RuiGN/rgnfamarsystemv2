# Publicação Docker Local com PostgreSQL

## Objetivo

Disponibilizar o RGN Farma System localmente em uma topologia próxima à de
produção, com Control Plane e ERP separados por hostname, dependências
persistentes e provisionamento idempotente de acessos administrativos.

## Escopo

O ambiente será acessível pelos seguintes endereços:

- Control Plane: `http://control.localhost:4127/platform/`
- ERP: `http://erp.localhost:4127/app/`

O navegador resolve os subdomínios de `localhost` para `127.0.0.1`, sem exigir
alteração em `/etc/hosts`.

## Arquitetura

O Docker Compose local terá os seguintes serviços:

- Nginx como ponto único de entrada na porta `4127`;
- Django executado por Gunicorn, sem porta publicada diretamente;
- PostgreSQL com volume nomeado persistente;
- Redis para cache e resultados Celery;
- RabbitMQ como broker Celery;
- Celery Worker para tarefas assíncronas;
- Celery Beat para tarefas agendadas.

O Nginx preservará o cabeçalho `Host` ao encaminhar as requisições ao Django.
O middleware existente continuará responsável por distinguir Control Plane e
ERP conforme `CONTROL_PLANE_HOSTS`.

## Configuração e segredos

Uma configuração local específica definirá:

- `DEBUG=False`;
- `ALLOWED_HOSTS=control.localhost,erp.localhost,localhost,127.0.0.1`;
- origens CSRF para os dois hosts e a porta `4127`;
- URLs públicas HTTP correspondentes ao Control Plane e ao ERP;
- conexão PostgreSQL interna;
- conexões Redis e RabbitMQ internas;
- chave Django, chave de criptografia e senhas locais fortes.

Valores secretos efetivos permanecerão em arquivo ignorado pelo Git. Um
arquivo de exemplo versionado documentará somente nomes e formatos, sem
credenciais utilizáveis.

## Inicialização

O entrypoint da aplicação continuará executando as migrations e a coleta de
arquivos estáticos. Um comando Django idempotente de bootstrap será responsável
por criar ou atualizar os dados locais solicitados:

1. usuário operador ativo do Control Plane;
2. concessão de `is_platform_operator` e `is_staff` ao operador;
3. credencial MFA local compatível com as exigências do Control Plane;
4. tenant ativo com `module_contract_enforced=True`;
5. um `TenantModuleSetting` ativo e habilitado para cada módulo conhecido;
6. usuário proprietário ativo do ERP;
7. membership ativa com papel `OWNER` no tenant.

O comando aceitará os dados por variáveis de ambiente, atualizará registros
existentes sem duplicá-los e executará as alterações em transação. Senhas não
serão impressas nos logs dos containers.

## Persistência e segurança operacional

Os volumes existentes não serão removidos ou recriados automaticamente. O
bootstrap poderá ser repetido após reinicializações sem apagar dados. A remoção
de volumes será documentada como operação manual e destrutiva.

PostgreSQL, Redis, RabbitMQ e Django terão healthchecks. Nginx só iniciará sua
exposição após a aplicação estar saudável. PostgreSQL, Redis e RabbitMQ não
publicarão portas no host por padrão.

## Testes e critérios de aceitação

A entrega será aceita quando:

- `docker compose config` validar a configuração;
- a imagem for construída sem erros;
- todos os serviços obrigatórios estiverem em execução e saudáveis;
- o backend ativo for PostgreSQL;
- todas as migrations estiverem aplicadas e não houver migrations ausentes;
- Control Plane e ERP responderem somente nos hosts previstos;
- o operador conseguir autenticar no Control Plane com o fluxo MFA local;
- o proprietário conseguir autenticar no ERP e acessar o tenant criado;
- todos os módulos estiverem ativos no contrato do tenant;
- a documentação contiver comandos de subida, parada, logs, bootstrap e
  diagnóstico;
- links e credenciais locais forem entregues ao usuário ao final.

## Fora de escopo

- TLS público ou certificados locais;
- Cloudflare Tunnel;
- SMTP real;
- exposição externa da máquina;
- remoção automática de bancos ou volumes existentes;
- dados mestres e transacionais de demonstração além do tenant e dos acessos.
