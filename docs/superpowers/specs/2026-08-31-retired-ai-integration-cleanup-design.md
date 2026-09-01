# Remoção integral de integração de IA aposentada — Design

**Data:** 31/08/2026  
**Status:** aprovado conceitualmente; aguardando revisão da especificação escrita

## Objetivo

Eliminar do projeto todas as referências textuais, configurações e dados
persistidos relacionados à integração de IA aposentada. A limpeza deve
preservar a integração OpenAI e manter disponível o provedor local
determinístico para cadastros futuros, mas excluir todos os perfis locais
existentes e seus registros dependentes.

## Decisões aprovadas

- Remover as quatro configurações com o prefixo da integração aposentada do
  runtime e do ambiente local.
- Remover referências de código, dados demo, documentação e artefatos gerados.
- Excluir todos os `AIAgentProfile` existentes com `provider='local'`.
- Excluir integralmente execuções, sugestões e logs de auditoria relacionados
  aos perfis locais removidos.
- Preservar perfis, execuções, sugestões e auditorias relacionados a OpenAI.
- Manter `AIAgentProfile.Provider.LOCAL` e o fallback local determinístico no
  código para permitir configurações futuras.
- A exclusão de dados será irreversível por migration; recuperação dependerá
  do backup externo produzido antes da aplicação.

## Arquitetura da limpeza

### Configuração e runtime

As quatro settings específicas da integração aposentada — chave, URL-base,
modelo e timeout — serão removidas de `core/settings/base.py` e dos arquivos de
ambiente. Nenhum consumidor ativo dessas settings foi encontrado.

### Dados demo

O bloco demo que cria o perfil `DEMO-RAG-QA`, sua execução e sua sugestão será
removido integralmente. Ele não será convertido em outro agente, pois a decisão
aprovada é excluir os registros relacionados, não normalizá-los.

### Dados persistidos

Uma migration de dados atômica, dependente da migration mais recente de
`ai_agents`, selecionará todos os perfis com `provider='local'` e executará:

1. coleta dos IDs dos perfis e execuções afetados;
2. exclusão de `AIPromptAuditLog`, que usa `PROTECT` para execução e perfil;
3. exclusão de `AIInsightSuggestion` vinculada às execuções;
4. exclusão de `AIAgentRun`, que usa `PROTECT` para o perfil;
5. exclusão de `AIAgentProfile` local.

A função reversa será `RunPython.noop`. A migration não codificará o nome do
serviço aposentado; o critério será exclusivamente o contrato de dados aprovado
para os perfis locais existentes.

## Integridade, segurança e recuperação

- A migration será executada dentro da transação padrão do Django/PostgreSQL.
- Antes de aplicá-la ao banco persistente local, será criado um `pg_dump` fora
  do repositório, com timestamp e hash SHA-256 registrados no relatório final.
- O backup não será versionado nem incluído na varredura do projeto.
- Nenhum banco de VPS, staging ou produção será alterado sem autorização
  específica adicional.
- Se o banco persistente local não estiver acessível ou o backup falhar, a
  migration não será aplicada manualmente e o estado será reportado como
  pendente.

## Estratégia de testes

### RED

Um teste de migration criará, no estado anterior:

- um perfil local com execução, sugestão e log de auditoria;
- um perfil OpenAI equivalente com seus registros dependentes.

Antes da migration de limpeza existir ou operar, o teste deve falhar porque os
registros locais permanecem.

### GREEN

Após a migration:

- nenhum perfil local criado no cenário permanece;
- nenhum log, sugestão ou execução ligado ao perfil local permanece;
- todos os registros OpenAI permanecem inalterados;
- o estado atual dos models não apresenta migration drift.

Testes de contrato também verificarão que apenas as configurações de IA ativas
permanecem e que os seeders não recriam os registros removidos.

## Documentação e artefatos gerados

A especificação técnica passará a citar somente as integrações ativas. O site
MkDocs será reconstruído com limpeza do diretório de saída para remover HTML e
índice de busca obsoletos.

## Verificação e critérios de aceitação

- Busca case-insensitive pelo nome comercial aposentado e suas variações
  retorna zero ocorrências em conteúdo e nomes de arquivos do projeto,
  incluindo arquivos ignorados e site gerado, com exclusão apenas de ambientes
  virtuais, mídia e dependências externas.
- Nenhuma variável com o prefixo aposentado permanece no `.env` local.
- Teste de migration e testes focados de agentes, seeder e contrato passam em
  PostgreSQL isolado.
- Ruff, `compileall`, `manage.py check`, `makemigrations --check --dry-run` e
  `git diff --check` terminam com código zero.
- A revisão do diff confirma que alterações preexistentes do worktree foram
  preservadas.
- Menus e permissões não exigem alteração, pois nenhum módulo ou rota será
  criado ou removido.

## Fora do escopo

- Remover o provedor local determinístico do enum ou do runtime.
- Alterar perfis ou históricos OpenAI.
- Aplicar migrations em VPS, staging ou produção.
- Corrigir as falhas globais preexistentes de backup scheduler, catálogo de
  evidências ou contrato do Compose.
