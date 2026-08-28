# Notificações, Tarefas e Workflow

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

## Prévia autorizada no cabeçalho

O context processor `base.ui.context_processors.sidebar_menu` é o dono da
autorização da prévia. Ele só consulta notificações quando o usuário autenticado
enxerga o workspace de workflow e possui
`workflow.view_workflownotification`. A consulta é sempre limitada a
`recipient=request.user`, ordenada por `created_at` decrescente e restrita às
cinco entradas mais recentes; notificações de outro destinatário nunca chegam
ao template.

Cada registro é convertido em `NotificationPreview`, com título, criticidade em
português, origem, tom, ícone, data/hora, estado de leitura e URL autorizada para
o detalhe. O dropdown exibe “Ver todas as notificações” e, quando a consulta
autorizada não retorna linhas, “Nenhuma notificação recente.” Se o usuário
enxerga o workflow mas não possui a permissão do model, o cabeçalho conserva o
link direto para a central, sem executar a consulta de prévia.

Os prazos do cockpit usam `DeadlineItem`. Tarefas de aprovação são limitadas a
`assigned_to=request.user`; notificações com vencimento usam o mesmo escopo de
destinatário. Cada fonte só é acessada depois da permissão `view` correspondente.
O estado vazio é “Nenhum prazo operacional encontrado.”

## Verificação mínima

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check

TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q
```
