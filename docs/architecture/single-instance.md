# Arquitetura single-instance

## Decisão

O RGN Farma System opera como uma instância única. O runtime operacional não
exige seleção de empresa, header de escopo, subdomínio dedicado ou contrato de
módulos para acessar `/app/`.

Usuários, grupos e permissões nativas do Django Admin são a fonte de verdade
para acesso operacional. A UI genérica usa `view`, `add`, `change` e `delete`
dos models para exibir módulos, recursos e ações.

O login único usa `username` e senha. O nome é normalizado antes da persistência
e não pode se repetir por diferença de caixa; o e-mail é apenas contato.

## PostgreSQL em Docker

Desenvolvimento, testes e produção usam PostgreSQL containerizado. Para o
ambiente local, suba o Compose canônico:

```bash
cp .env.local.example .env.local
docker compose --env-file .env.local -f docker-compose.local.yml up -d --build
```

O perfil `core.settings.test` exige `TEST_DATABASE_URL` PostgreSQL. O script
`scripts/test.sh` inicia o serviço isolado `postgres_test` em Docker.

O `.env.example` documenta a VPS; `.env.local.example` documenta o ambiente
local. Ambos apontam para o serviço privado `db` dentro do Compose.

## Runtime convertido

- Middlewares de resolução de escopo SaaS foram removidos do stack principal.
- `/accounts/login/` permanece como login único.
- Rotas HTML de seleção, convite e administração de acesso SaaS foram
  desconectadas da UI operacional.
- `/api/accounts/me/` exige apenas usuário autenticado.
- O shell operacional não renderiza seletor de escopo nem atributos de escopo
  por cliente.
- Listagens, campos relacionados e ViewSets DRF usam escopo global.
- APIs DRF usam `SingleInstanceDjangoModelPermissions`, baseado nas permissões
  Django `view`, `add`, `change` e `delete`.

## Inventário do escopo legado removido

Em 18/07/2026, a busca no código Python e nos templates de runtime confirmou
que não há resolução de cliente, seleção de contexto, associação de acesso ou
header de segmentação. O sistema usa somente usuários, grupos e permissões
nativas do Django para autorização.

## Banco e migrations

As colunas operacionais de escopo SaaS foram removidas por migrations
faseadas. Constraints e indexes que dependiam desse escopo foram substituídos
por regras globais ou por contexto funcional quando aplicável.

`makemigrations --check --dry-run` deve continuar sem pendências após qualquer
alteração de modelo.

## Contrato interno

`SingleInstanceModel` é a base abstrata dos registros operacionais globais. Ele
mantém timestamps e validações transversais sem aceitar parâmetros ou filtros de
escopo SaaS no runtime.

## Ações operacionais

A interface HTML cobre as mesmas 258 ações `POST` publicadas pelos ViewSets
DRF: 252 ações de detalhe e seis ações de coleção. O callback DRF continua sendo
o executor único da mutação, incluindo permissão, transação, validação de
domínio, auditoria e resposta de erro.

O catálogo declara o campo e os valores de ciclo de vida usados para decidir a
visibilidade de cada botão. As restrições reproduzem os guards dos métodos de
domínio e serviços; ações sem restrição de origem recebem todos os valores do
respectivo `TextChoices`. Campos alternativos, como `stage`, `decision`,
`release_status`, `quality_status`, `emission_status`, `result_status` e
`response_status`, são tratados explicitamente.

Na cardinalidade vigente, 238 ações de detalhe possuem ciclo de vida declarado,
14 atuam sobre models sem um campo de ciclo de vida e as seis ações de coleção
não dependem de objeto. A API sempre revalida o estado no envio, protegendo
também contra alterações concorrentes ocorridas após a renderização da página.

## Verificação executada

Em PostgreSQL Docker:

```bash
bash scripts/test.sh tests/test_foundation.py -q
bash scripts/test.sh
```
