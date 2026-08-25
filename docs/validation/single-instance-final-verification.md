# Verificação final da conversão single-instance

Data: 20/07/2026

Escopo: `MODIFICACAGERAL.prd`

Banco principal de desenvolvimento: PostgreSQL local

## Resultado técnico

O quality gate integral terminou com sucesso após a revisão independente e as
correções de regressão:

- 537 testes aprovados;
- cobertura total de 83,86%, acima do mínimo de 80%;
- Ruff lint e formatação aprovados;
- mypy aprovado em 451 arquivos-fonte;
- Bandit e `pip-audit` aprovados, sem vulnerabilidades conhecidas;
- `manage.py check` aprovado e nenhuma migration pendente;
- OpenAPI, MkDocs strict, readiness operacional, backup/restore, aceite de
  produto e prontidão técnica de release aprovados;
- catálogo de 11 evidências íntegro e aprovado.

## Itens confirmados após revisão

- edição 1:N carrega filhos existentes e cobre alteração, exclusão permitida e
  rollback de pai/filho;
- decisões e confirmações reguladas foram removidas dos inlines genéricos;
- recursos GxP bloqueiam hard delete e usam retenção/transições controladas;
- mutações da UI são transacionais e registram ator/alvo no
  `GovernanceAuditLog`;
- criação de documento pela UI também registra o evento `CREATED` na
  `DocumentAuditTrail`, dentro da mesma transação;
- ações REST que criam outro registro exigem permissões do objeto-fonte e do
  modelo-alvo;
- testes não recebem permissões globais sem marcador explícito, e cenários de
  autorização declaram permissões mínimas;
- `/accounts/login/` é a única tela de login e redireciona para `/app/`; MFA do
  operador continua como segunda etapa;
- listagens de arquivos, links e auditoria respeitam o vínculo funcional de
  acesso ao arquivo;
- restore de mídia local funciona sem Docker, rejeita path traversal e publica
  o staging por troca atômica;
- migrations de limpeza geram SQL reverso real. Ciclos reverso/direto foram
  executados em clones isolados no PostgreSQL 15.18 e 18.4.
- uma instalação integral desde banco PostgreSQL vazio confirmou que todas as
  migrations de limpeza precedem `tenants.0006_delete_tenant`, sem referências
  históricas não resolvidas e com zero colunas `tenant_id` ao final.
- o banco PostgreSQL local de desenvolvimento recebeu
  `control_plane.0005_preserve_evidence_and_delete_runtime_models` e
  `accounts.0012_remove_user_is_platform_operator`; antes da aplicação foi
  criado um dump custom-format, validado por `pg_restore --list` e SHA-256,
  retido fora do Git em `local-pre-single-instance-20260720T135500Z`.

## Limites de encerramento

A implementação técnica do PRD está concluída. O encerramento regulatório e a
liberação operacional permanecem condicionados aos itens externos registrados
em `known-pending-items.md`: aprovação formal do incidente `INC-2026-001` e
provisionamento do primeiro superusuário pelo responsável da instalação.

Nenhuma credencial real foi incluída nas evidências ou no histórico Git.
