# Menus e permissões

## Arquitetura single-instance

Este módulo opera em escopo global da instalação local. O acesso é controlado
por autenticação Django e permissões nativas `view`, `add`, `change` e
`delete`, administradas no Django Admin por usuário ou grupo.

As APIs e telas operacionais não exigem cabeçalho de escopo, seleção de empresa
ou vínculo de contrato por cliente. Listagens, formulários, detalhes e ações
usam o mesmo conjunto global de dados da instância.

## Regras de implementação

- Preservar as regras de negócio farmacêuticas do módulo.
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

Em ações REST `POST`, `create` e ações de coleção exigem `add`; ações de detalhe
que alteram estado exigem `change`. Quando uma ação cria outro registro, o
ViewSet declara `action_permission_map` com as permissões do objeto-fonte e do
modelo-alvo, como revisão documental, substituição de arquivo, link seguro,
execução de relatório e criação de análise.

Depois da autorização, `available_actions` aplica `allowed_states` ao objeto.
Esse filtro é somente de apresentação: o dispatcher chama o endpoint DRF, que
repete a autorização e a validação de estado dentro da transação de domínio.

Testes novos não recebem permissões automaticamente. Classes históricas de
fluxo funcional precisam declarar `@pytest.mark.legacy_api_permissions` para
simular explicitamente um papel de acesso total. Cenários de autorização usam
`@pytest.mark.permission_strict` e declaram as permissões mínimas necessárias.

## Agrupamento do sidebar por domínio

O context processor obtém primeiro `get_visible_modules(user)` e somente então
organiza essa coleção nos domínios Operações, Qualidade, Suprimentos,
Comercial, Financeiro e fiscal, Governança e conformidade, Tecnologia e
Administração. O agrupamento não concede permissões, não recupera módulos
ocultos e não substitui as verificações defensivas das views.

`SIDEBAR_DOMAINS` controla apenas rótulo e ordem visual. Um módulo visível que
ainda não tenha classificação explícita é exibido em “Outros”, evitando que a
inclusão de um novo módulo o torne inacessível por uma omissão de navegação.
Cada módulo aparece no máximo uma vez, mesmo se uma configuração futura repetir
seu slug em mais de um domínio.

Os grupos expansíveis usam botões com `aria-controls` e `aria-expanded`. O
listener desses botões interrompe a propagação do clique antes de atualizar o
submenu, pois o JavaScript legado do Duralux também observa o `<li>` pai; sem
esse isolamento, os dois handlers alternam o mesmo grupo em sentidos opostos.

## Verificação mínima

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check

TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q
```
