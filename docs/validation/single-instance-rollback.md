# Plano de rollback single-instance

## Objetivo

Restaurar uma versão anterior com perda controlada e evidência auditável caso a
conversão single-instance apresente falha impeditiva. Rollback não deve ser
usado para contornar correções normais nem executado sem autorização do
responsável técnico e da Qualidade quando houver dados GxP.

## Pré-condições

1. interromper novas escritas e registrar o início da janela;
2. identificar commit, migration alvo, banco e artefatos afetados;
3. gerar backup PostgreSQL e de mídia com `scripts/backup.sh`;
4. validar gzip, hash, local de armazenamento e possibilidade de leitura;
5. executar `scripts/restore.sh --dry-run` com artefatos explícitos;
6. registrar responsável, motivo, impacto e decisão de rollback.

## Estratégia

### Falha somente de aplicação

Republique a imagem/commit anterior compatível com o schema atual. Não reverta
migrations se a versão anterior tolerar colunas e tabelas adicionais. Valide
healthcheck, login, leitura, permissões e filas antes de liberar escrita.

### Falha em migration reversível

Pare app e workers, confirme a migration aplicada e use:

```bash
.venv/bin/python manage.py migrate APP MIGRATION_ANTERIOR --plan
.venv/bin/python manage.py migrate APP MIGRATION_ANTERIOR
```

Revise o SQL antes da execução. A migration de limpeza do nome legado em
`compliance.0007` é condicional e reversível em PostgreSQL 15 e 18.

As remoções de `TenantMembershipInvitation`, `TenantMembership`,
`TenantModuleSetting` e `Tenant.module_contract_enforced` usam operações Django
reversíveis. `tenants.0006` depende das exclusões em `accounts` e `governance`,
garantindo que a tabela `tenants_tenant` seja recriada antes das FKs ao voltar.
O ciclo de schema cria novamente tabelas, coluna, índices e constraints; ele
não recupera linhas que já tenham sido descartadas.

### Retorno à arquitetura anterior

Para retorno integral dos dados administrativos antigos, não use apenas
`migrate backwards`: restaure o backup completo capturado antes da conversão,
junto ao código compatível daquele instante.

```bash
.venv/bin/python scripts/run_with_env.py --env-file .env -- \
  bash scripts/restore.sh \
  --postgres CAMINHO/postgres-AAAAMMDD-HHMMSS.sql.gz \
  --media CAMINHO/media-AAAAMMDD-HHMMSS.tar.gz \
  --yes
```

O restore gera backup pré-restauração antes de recriar o schema `public`.

## Validação pós-rollback

- `manage.py check` e `migrate --plan` sem erro;
- versão do PostgreSQL e contagem de migrations registradas;
- autenticação e acesso administrativo;
- permissões de leitura/escrita em UI e API;
- integridade referencial e contagens antes/depois;
- leitura de arquivos protegidos e hashes;
- conectividade Redis/RabbitMQ e retomada controlada dos workers;
- registro do resultado, anomalias e decisão de reabrir o serviço.

## Critério de encerramento

O rollback termina somente após reconciliação dos dados, aprovação dos
responsáveis e preservação dos artefatos de antes/depois. Falha de restauração
mantém o sistema em modo sem escrita e aciona o plano de continuidade.
