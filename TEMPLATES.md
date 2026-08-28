# Templates operacionais

A UI operacional usa uma experiência single-instance em `/app/`, sem seleção de
escopo por cliente. O objetivo é oferecer navegação por módulo, CRUD HTML,
permissões Django e testes automatizados sem substituir as APIs REST nem o
Django Admin.

## Página inicial e workspaces

Usuários autenticados que acessam `/` são redirecionados para `/app/`, o
catálogo dinâmico de módulos permitido ao perfil. A home não mantém um catálogo
estático paralelo.

Os cockpits de operação, qualidade e workflow usam configurações imutáveis
`WorkspaceConfig` em `base.ui.workspaces` e uma única apresentação em
`templates/workspaces/workspace.html`. As configurações fornecem textos,
métricas, tons, ícones e URLs já resolvidas. A view filtra módulos, cartões e
atalhos no servidor antes da renderização.

As rotas nomeadas `app:operations_workspace`, `app:quality_workspace` e
`app:workflow_workspace` permanecem estáveis. Novos workspaces devem ser
registrados no mesmo contrato, com teste de acesso ao módulo, visibilidade dos
itens e escopo das consultas.

## Regras

- Menus usam permissões `view` dos models.
- Botões de criação, edição e exclusão usam `add`, `change` e `delete`.
- Formulários não expõem campos preenchidos pelo sistema, trilhas de auditoria,
  hashes ou timestamps técnicos.
- Listagens preservam filtros, ordenação, paginação e exportação CSV.
- Telas de detalhe exibem badges semânticos para status, criticidade e severidade.
- Relações 1-N prioritárias devem ser editadas no formulário principal com
  transação atômica.

## Como adicionar novos recursos ao CRUD HTML generico

1. Registre o model em `base.ui.registry` com `ResourceConfig`, título, ícone,
   campos de listagem, `form_fields` e permissões esperadas.
2. Garanta que o usuário possua permissões Django `view`, `add`, `change` e
   `delete` conforme a ação desejada.
3. Use validações de model e serializer já existentes; não duplique regra de
   negócio no template.
4. Para relações 1-N, configure inline formsets no recurso pai e salve tudo em
   transação.
5. Adicione testes de listagem, detalhe, criação, edição, exclusão e visibilidade
   dos botões por permissão.

Campos derivados, hashes, timestamps técnicos e trilhas de auditoria devem
ficar fora de `form_fields` ou ser marcados como `read_only=True` quando
precisarem aparecer em detalhe/API.

## Como publicar uma nova ação operacional

Uma futura `@action(detail=..., methods=['post'])` deve continuar usando o DRF
como executor único. Para disponibilizá-la na interface:

1. Adicione `(resource_slug, action_name)` a `ACTION_KEYS` do app em
   `base/ui/actions/modules/`.
2. Declare o payload em `FIELD_SPECS`, com tipo, obrigatoriedade, limites,
   choices do model/serializer e queryset de relações autorizado.
3. Se o método restringir o estado de origem, registre o campo e os valores em
   `RESTRICTED_ACTION_STATES`; ações com ciclo de vida sem guard recebem todos
   os valores do `TextChoices`.
4. Adicione o texto visível em `ACTION_LABELS`, sempre em pt-BR e sem fallback
   em inglês. Configure confirmação para operações críticas.
5. Execute `test_html_catalog_exactly_matches_post_actions` e os testes do
   domínio. A igualdade deve permanecer em 258/258 até que uma nova ação seja
   aprovada e altere deliberadamente essa cardinalidade.

Não concatene URL, não replique a regra de negócio no template e não chame o
model diretamente pela view HTML.

## Verificação

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/pytest tests/test_app_ui.py tests/test_formula_inline_components_ui.py -q
```
