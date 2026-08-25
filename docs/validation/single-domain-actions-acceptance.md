# Aceite single-domain e ações operacionais

Este registro separa evidência técnica reproduzível de aprovações externas. Os
resultados remotos refletem a execução real na Contabo; bloqueios externos não
são convertidos em aprovação por este documento.

## Snapshot histórico — release de 20/07/2026 (`dda7ab1`)

Este snapshot preserva os resultados válidos para o código identificado abaixo.
As contagens locais foram recuperadas do artefato documental versionado naquele
commit; atualizações posteriores do catálogo não alteram retroativamente este
registro.

| Evidência | Valor |
|---|---|
| SHA do código | `dda7ab13524e6ddab3e63323ffac1ef35b2448f7` |
| Data/hora UTC do gate local | 2026-07-20T14:29:03Z |
| Data/hora UTC da verificação remota | 2026-07-20T13:44:58Z |
| Ações cadastradas | 253 |
| Ações de detalhe | 247 |
| Ações de coleção | 6 |
| Matriz de estados | 233 ações com ciclo de vida; 14 sem campo; 6 de coleção |
| Cobertura | 83,86% (`534 passed`) |
| Migrations | Aprovado: `No changes detected`; zero migrations locais não aplicadas |
| Evidência do catálogo | `EV-SIA-ACTION-253` no artefato histórico imutável |

### Verificações históricas

| Verificação | Resultado | Evidência |
|---|---|---|
| Catálogo 253/253 | Aprovado localmente | `EV-SIA-ACTION-253`: `docs/validation/evidence/archive/sia-action-253/test_action_catalog_completeness.py` |
| Cópia pt-BR | Aprovado localmente | `tests/test_action_copy_ptbr.py` |
| Administração single-instance | Aprovado localmente | `tests/test_single_instance_admin_runtime.py` |
| Gate integral local | Aprovado | 534 testes; Ruff, MyPy, Bandit, pip-audit, OpenAPI e MkDocs aprovados |
| Perfil e segurança de produção | Aprovado remotamente | `core.settings.production`; `check --deploy --fail-level WARNING` sem achados; HSTS 31536000/subdomínios/preload |
| Migrations remotas | Aprovado | Zero migrations não aplicadas |
| Healthcheck interno | Aprovado | `/health/` = 200 às 2026-07-20T13:13:35Z |
| Healthcheck público | Aprovado | HTTPS 200, TLS válido e HSTS `max-age=31536000; includeSubDomains; preload` |
| Cloudflare Tunnel | Aprovado | Token aceito, quatro conexões QUIC, rota publicada e zero reinícios |
| Smoke `/app/`, `/admin/`, `/api/docs/` | Aprovado publicamente | 302, 302 e 200, respectivamente; redirecionamentos exigem autenticação |
| Superfície removida `/platform/` | Aprovado publicamente | 404 |
| Administrador `Rui` | Pendente de credencial segura | Conta ainda ausente; senha não foi inventada nem registrada em logs |
| Backup pré-release | Aprovado | `backups/release-20260720T125422Z`; PostgreSQL e mídia validados por SHA-256 |

O runtime Django, Nginx, PostgreSQL, Redis, RabbitMQ e Celery está operacional e
o acesso público está liberado em `rgnfarmasystem.rgnsystems.com.br`. O backup e
o stash de preservação permanecem retidos até o provisionamento do administrador
e o aceite final.

`INC-2026-001` permanecia aberto neste snapshot; as verificações técnicas não
substituíam as aprovações formais de Segurança/DPO e Qualidade.

## Candidato atual — 27/07/2026 (`2fa9472`)

Este é um registro separado do candidato atual. Ele não reescreve o snapshot de
20/07/2026 nem atribui migrations posteriores ao release histórico.

| Evidência | Valor |
|---|---|
| SHA do código | `2fa9472` |
| Data do candidato | 27/07/2026 |
| Ações cadastradas | 258 |
| Ações de detalhe | 252 |
| Ações de coleção | 6 |
| Matriz de estados | 238 ações com ciclo de vida; 14 sem campo; 6 de coleção |
| Migration de produção | `production.0007` aplicada |
| Testes operacionais | 273 aprovados |
| Testes de produção/UI | 14 aprovados |
| Testes de catálogo/documentação | 62 aprovados |
| Evidência do catálogo | `EV-SIA-ACTION-258` com SHA-256 conferido |

### Gates do candidato atual

| Verificação | Resultado | Evidência |
|---|---|---|
| Catálogo 258/258 | Aprovado | 252 ações de detalhe e 6 de coleção |
| Matriz de estados | Aprovado | 238 ações com estado, 14 sem estado e 6 de coleção |
| Operação de produção | Aprovado | 273 testes em `tests/test_production_operations.py` |
| Produção e UI | Aprovado | 7 testes de produção e 7 testes focados de UI |
| Catálogo e documentação | Aprovado | 62 testes |
| Django system check | Aprovado | `manage.py check` sem issues |
| Migrations | Aprovado | `production.0007` aplicada e `makemigrations --check --dry-run` sem alterações |
| Qualidade estática | Aprovado | Ruff e `git diff --check` sem achados |
| Integridade `EV-SIA-ACTION-258` | Aprovado | SHA-256 do artefato confere com o catálogo de evidências |

O snapshot histórico `EV-SIA-ACTION-253` permanece independente do candidato
`EV-SIA-ACTION-258`: cada ID aponta para seu próprio artefato e SHA-256. A
aprovação histórica não representa aprovação do código atual.

Os hashes `EV-SI-005`, `EV-SI-006` e `EV-SI-008` foram reconciliados em
28/07/2026 após a execução integral dos respectivos testes. O comando
`check_evidence_audit --fail-on-error` confirma a integridade e a aprovação de
todas as entradas do catálogo.

## Pendências regulatórias

`INC-2026-001` permanece aberto até evidências formais externas de rotação,
análise, saneamento e aprovação por Segurança/DPO e Qualidade. Este documento
não simula nem substitui essas aprovações.
