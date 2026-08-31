# Deploy Compose e Retirada do Conector Off-site

## Objetivo

Preparar o RGN Farma System para produção no domínio
`rgnfarmasystem.rgnsystems.com.br`, publicado pelo Cloudflare Tunnel contra a
origem `http://localhost:8081`, e remover integralmente o conector off-site
aposentado sem perder os backups locais de PostgreSQL e mídia.

## Topologia aprovada

O `docker-compose.vps.yml` é o manifesto canônico da VPS. O Nginx publica
somente `127.0.0.1:8081:80`; PostgreSQL, aplicação, Redis e RabbitMQ permanecem
na rede privada do Compose. O serviço `cloudflared` usa rede do host, recebe o
token pelo `.env` ignorado pelo Git e encaminha o domínio público para a origem
loopback.

Os serviços de aplicação dependem de healthchecks reais. A aplicação executa
migrations com lock antes de ficar saudável; workers aguardam aplicação,
RabbitMQ e Redis. O script `scripts/deploy-vps.sh` valida configuração, cria
backup de release, promove a revisão, sobe o Compose e exige readiness do túnel
antes de concluir.

## Contrato do ambiente de produção

O `.env.example` documenta somente chaves e valores não confidenciais. O `.env`
local permanece ignorado pelo Git e com modo `0600`. A configuração preserva
tokens e chaves externas já existentes e gera valores fortes para segredos
internos ausentes:

- `SECRET_KEY` do Django;
- senha do PostgreSQL;
- senha do RabbitMQ;
- chave AES-256 identificada por `DATA_ENCRYPTION_KEY_ID`;
- URLs internas derivadas dessas credenciais.

O perfil usa `DEBUG=false`, settings de produção, cookies seguros, redirecionamento
HTTPS, HSTS, hosts/origens restritos ao domínio aprovado e serviços internos por
nome DNS do Compose. O preflight rejeita placeholders, valores vazios obrigatórios,
duplicidades e permissões inseguras sem imprimir segredos.

## Retirada do conector off-site

A retirada será física e funcional:

- excluir cliente, OAuth, comandos de autenticação e upload;
- remover o script de envio externo e seus testes exclusivos;
- remover bibliotecas cliente e variáveis de configuração;
- remover serviço, segredo e volume de logs exclusivos do manifesto VPS;
- remover imagens, exemplos de design e documentação específica;
- remover o modelo de auditoria exclusivo e suas exposições em Admin/UI por
  migration aditiva;
- atualizar readiness, catálogo de evidências e testes dependentes.

Arquivos e criptografia genéricos de backup permanecem. O comando de decifragem
e os scripts `backup.sh`/`restore.sh` continuam válidos para recuperação local.

## Agendador de backup local

O serviço `backup_scheduler` substitui o uploader aposentado. Ele executa um
script dedicado com lock, janela diária configurável, retenção local, marcadores
de prontidão e healthcheck. Cada ciclo chama `scripts/backup.sh`, que produz
artefatos atômicos de PostgreSQL e mídia nos volumes `backups` e `media`.

Falha no dump, mídia vazia, lock concorrente ou artefato inválido impede a
atualização do marcador de sucesso. O restore mantém dry-run obrigatório antes
da confirmação real e cria backup pré-restore.

## Integridade de dados

A migration remove o modelo e a tabela exclusivos do envio aposentado. Antes
da remoção, o teste de migration prova aplicação e reversão do estado do schema.
Não há transformação para outro modelo porque os registros armazenam IDs e
links do provedor removido e não representam evidência de backup local.

## Testes e critérios de aceitação

1. Um teste de contrato falha enquanto qualquer marcador textual, nome de
   arquivo, dependência ou variável do conector aposentado existir em arquivos
   próprios do projeto.
2. Testes do agendador provam execução única, lock, janela, falha segura,
   retenção e marcadores de saúde.
3. Testes de migration provam remoção e reversão da tabela de auditoria.
4. `docker compose config --quiet` passa usando o `.env` configurado.
5. Todos os serviços possuem healthcheck e política de restart adequada.
6. `manage.py check`, drift de migrations, Ruff e testes relevantes passam.
7. O Nginx fica acessível apenas em `127.0.0.1:8081` e a prontidão do túnel é
   validada sem revelar o token.
8. Nenhum segredo é versionado, impresso em logs ou incluído na resposta final.

## Limites

Esta mudança prepara e valida os artefatos locais. Ela não executa deploy na
VPS, não altera DNS no Cloudflare, não envia commits e não expõe credenciais.
