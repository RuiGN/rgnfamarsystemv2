# Catálogo de Templates

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

Ações de domínio usam os componentes `resource_actions.html` e
`resource_action_form.html`. O primeiro apresenta somente ações autorizadas e
compatíveis com o estado; o segundo fornece confirmação, CSRF, erros por campo
e fallback navegável sem JavaScript. O modal nunca é a única forma de concluir
uma ação.

## Verificação mínima

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check

TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q
```
