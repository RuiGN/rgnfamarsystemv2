# Arquivos Protegidos

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

## Download canônico

`files.downloads.protected_file_download_response()` é o caminho compartilhado
para downloads autenticados. A autorização combina a permissão Django aplicada
pela rota com `ProtectedFile.user_can_access()`, disponibilidade do registro e
descriptografia AES-256-GCM. Somente uma leitura concluída registra
`download`; negações, blob ausente e falhas de cifra registram
`access_denied` com metadados do cliente e retornam erro genérico sem expor a
referência de storage. Apenas arquivos em estado `active` podem ser lidos,
independentemente de `valid_until`; `expired`, `superseded` e `deleted` falham
fechado. Erros de envelope ou nonce AES também são convertidos em negação
genérica auditada, sem registrar `download`.

Tanto a ação `protected-files/<id>/download/` quanto downloads originados por
execuções de relatório reutilizam esse serviço. Essa centralização evita duas
implementações divergentes para regra de acesso, auditoria, MIME e
`Content-Disposition`. O MIME aceita somente sintaxe sem quebras de linha e
usa `application/octet-stream` como fallback. As respostas aplicam
`Cache-Control: private, no-store, max-age=0`, `Pragma: no-cache`, `Expires: 0`,
`X-Content-Type-Options: nosniff` e `Vary: Authorization, Cookie`.

Serializadores externos ocultam `file_reference`, `result_reference` e chaves
equivalentes dentro de detalhes de auditoria. O caminho de storage continua
disponível apenas internamente para persistência, criptografia e manutenção do
artefato.

## Verificação mínima

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check

TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q
```
