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

## PostgreSQL local

Docker não é requisito para desenvolvimento, testes ou execução imediata. Use
PostgreSQL local:

```env
DATABASE_URL=postgres://rgnfarmasystem:rgnfarmasystem@localhost:5432/rgnfarmasystem
TEST_DATABASE_URL=postgres://rgn_test:<senha-local>@127.0.0.1:5433/rgn_test
```

O perfil `core.settings.test` usa o banco definido em `TEST_DATABASE_URL`
diretamente, sem criar um banco `test_*`, para manter a validação no PostgreSQL
local isolado.

Copie `.env.development.example` para `.env` como ponto de partida. O
`.env.example` é reservado ao contrato de publicação em containers.

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

## Inventário multi-tenant removido

Em 18/07/2026, a busca no código Python e nos templates de runtime, excluindo
migrations históricas e testes de regressão, encontrou zero arquivos para cada
contrato legado: `TenantOwnedModel`, `request.tenant`, `IsTenantMember`,
`TenantMembership`, `TenantModuleSetting`, `active_tenant_id` e
`X-Tenant-Slug`. Referências preservadas em migrations existem apenas para
permitir reconstrução e evolução segura do schema histórico.

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

Em PostgreSQL local:

```bash
DJANGO_SETTINGS_MODULE=core.settings.test \
DATABASE_URL="$TEST_DATABASE_URL" \
TEST_DATABASE_URL="$TEST_DATABASE_URL" \
.venv/bin/python manage.py check

DJANGO_SETTINGS_MODULE=core.settings.test \
DATABASE_URL="$TEST_DATABASE_URL" \
TEST_DATABASE_URL="$TEST_DATABASE_URL" \
.venv/bin/pytest -q
```
