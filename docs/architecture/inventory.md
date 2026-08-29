# Estoque, Almoxarifado e Rastreabilidade

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

## Etiqueta de lote

O detalhe de um lote apresenta **Imprimir etiqueta** somente ao usuário que
possui `inventory.view_stocklot`. A ação envia, uma única vez, TSPL2 pela VPN
à impressora ativa configurada na porta TCP 9100 por padrão.

O layout contém exclusivamente Produto, Lote, Validade e assinatura
operacional (nome do usuário autenticado e data/hora do servidor). Não contém
código de barras, data de fabricação ou sublote. A assinatura operacional não
substitui uma assinatura eletrônica GxP.

O retorno de sucesso confirma o envio ao socket; não confirma a saída física
da etiqueta. O fluxo funciona sem repetição automática. Diante de timeout ou
resultado incerto, o operador deve conferir a impressora antes de reenviar.

Os identificadores já gerados pelo servidor são apresentados desabilitados nos
formulários da aplicação e como somente leitura na API e no Django Admin. A
política deriva códigos do contrato `AutoCodeMixin`/`CODE_PREFIX`; os demais
identificadores são declarados no próprio model por `AUTOMATIC_IDENTIFIERS`,
preservando códigos e números manuais.

## Verificação mínima

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check

TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q
```
