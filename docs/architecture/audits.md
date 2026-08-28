# Auditorias

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

## Trilha persistida na UI operacional

A tela de detalhe é somente leitura e só solicita a trilha quando o
`ResourceConfig` declara `audit_trail=True`. A autorização do registro continua
pertencendo à `ResourceDetailView`; o template recebe apenas entradas já
isoladas para o objeto visível. Não há usuário fixo, timestamp gerado no
template, linha demonstrativa ou botão de exportação sem rota real e autorizada.

`base.ui.audit.get_audit_entries(obj, limit=25)` normaliza as fontes em
`AuditEntry`, contrato imutável com data/hora persistida, ator, ação, detalhes,
motivo e `StatusPresentation`. O limite é normalizado entre zero e 25, e a
ordenação é decrescente por timestamp com chave primária como desempate.

As fontes reais são:

- `DocumentAuditTrail`, acessada por `ControlledDocument.audit_trail`, com
  `select_related('actor')`; fornece `created_at`, ação traduzida, snapshot,
  motivo e ator;
- `RecordStatusHistory`, filtrada por `source_module`, `target_model` e
  `target_record_id`, também com ator carregado; fornece `occurred_at`, ação,
  transição `previous_status → new_status` e motivo.

Ator ou motivo ausente são apresentados como “—”. Quando não existe evento
persistido, a interface informa “Nenhum evento de auditoria disponível para
este registro.”. A cópia visível deve permanecer em português do Brasil com
acentuação correta, e o estado sempre combina rótulo, ícone e tom — nunca apenas
cor.

## Verificação mínima

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check

TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q
```
