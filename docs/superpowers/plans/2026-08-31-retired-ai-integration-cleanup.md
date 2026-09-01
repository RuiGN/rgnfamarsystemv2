# Retired AI Integration Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remover integralmente a integração de IA aposentada e excluir do banco local todos os perfis de agente com provedor local, incluindo seus registros dependentes, sem afetar OpenAI.

**Architecture:** Uma migration de dados atômica elimina logs protegidos, sugestões, execuções e perfis locais nessa ordem. Código/configuração/demo/documentação são limpos separadamente; o banco persistente local só recebe a migration depois de um backup externo válido.

**Tech Stack:** Python 3.14, Django 6.0.8, PostgreSQL, pytest-django, Docker Compose, MkDocs.

## Global Constraints

- Preservar todas as alterações preexistentes do worktree; não usar reset ou checkout amplo.
- Não criar commit, push, PR ou deploy sem autorização específica.
- Excluir todos os `AIAgentProfile` existentes com `provider='local'` e seus dependentes.
- Preservar integralmente os dados relacionados a OpenAI.
- Manter o provedor local determinístico disponível no enum e no runtime.
- Não aplicar a migration em VPS, staging ou produção.
- Não aplicar a migration ao banco persistente local sem backup externo válido e hash SHA-256.
- A migration é irreversível; `reverse_code` deve ser `migrations.RunPython.noop`.
- A verificação final deve encontrar zero referências textuais ou nomes de arquivo relacionados à integração aposentada.

---

### Task 1: Excluir dados locais por migration atômica

**Files:**
- Modify: `tests/test_ai_agents_migrations.py`
- Create: `ai_agents/migrations/0003_purge_existing_local_agent_records.py`

**Interfaces:**
- Consumes: estado histórico `ai_agents.0002_normalize_agent_profile_providers`.
- Produces: `purge_existing_local_agent_records(apps, schema_editor)`, que remove dependências e perfis locais na ordem segura.

- [ ] **Step 1: Adicionar cenário de migration que inicialmente permanece em 0002**

Adicionar um segundo teste transacional. Ele deve criar perfis local e OpenAI, uma execução, sugestão e auditoria para cada perfil usando os models históricos. Na primeira execução, manter `new_target = ('ai_agents', '0002_normalize_agent_profile_providers')` e afirmar que o perfil local não existe após migrar, produzindo o RED esperado.

```python
def create_profile(AgentProfile, *, code, provider):
    return AgentProfile.objects.create(
        code=code,
        name=f'Agente {provider}',
        agent_type='summary',
        source_module='documents',
        provider=provider,
        model_name='local' if provider == 'local' else 'gpt-5.5-mini',
        system_prompt='Resuma o documento.',
        allowed_source_modules=['documents'],
    )


def create_run(AgentRun, profile, run_number):
    return AgentRun.objects.create(
        run_number=run_number,
        agent=profile,
        source_module='documents',
        source_model='ControlledDocument',
        source_record_id=run_number,
        status='succeeded',
        prompt_text='Resuma o documento.',
        model_name=profile.model_name,
        input_payload={'document_id': run_number},
        output_payload={'summary': 'Resumo sintético.'},
        output_text='Resumo sintético.',
    )


def create_dependents(Suggestion, AuditLog, profile, run):
    Suggestion.objects.create(
        run=run,
        suggestion_type='summary',
        title=f'Sugestão {run.run_number}',
        description='Descrição sintética.',
        confidence='0.80',
        source_module='documents',
        source_model='ControlledDocument',
        source_record_id=run.source_record_id,
    )
    AuditLog.objects.create(
        run=run,
        agent=profile,
        prompt_text=run.prompt_text,
        model_name=run.model_name,
        input_payload=run.input_payload,
        output_payload=run.output_payload,
        output_text=run.output_text,
        status=run.status,
    )


@pytest.mark.django_db(transaction=True)
def test_existing_local_agent_records_are_purged_without_touching_openai(
    restore_latest_migrations,
):
    old_target = ('ai_agents', '0002_normalize_agent_profile_providers')
    new_target = old_target
    executor = MigrationExecutor(connection)
    executor.migrate([old_target])
    old_apps = executor.loader.project_state([old_target]).apps

    AgentProfile = old_apps.get_model('ai_agents', 'AIAgentProfile')
    AgentRun = old_apps.get_model('ai_agents', 'AIAgentRun')
    Suggestion = old_apps.get_model('ai_agents', 'AIInsightSuggestion')
    AuditLog = old_apps.get_model('ai_agents', 'AIPromptAuditLog')

    local_profile = create_profile(AgentProfile, code='AGT-LOCAL-PURGE', provider='local')
    openai_profile = create_profile(AgentProfile, code='AGT-OPENAI-KEEP', provider='openai')
    local_run = create_run(AgentRun, local_profile, 'AIRUN-LOCAL-PURGE')
    openai_run = create_run(AgentRun, openai_profile, 'AIRUN-OPENAI-KEEP')
    create_dependents(Suggestion, AuditLog, local_profile, local_run)
    create_dependents(Suggestion, AuditLog, openai_profile, openai_run)

    executor = MigrationExecutor(connection)
    executor.migrate([new_target])
    migrated_apps = executor.loader.project_state([new_target]).apps

    assert not migrated_apps.get_model('ai_agents', 'AIAgentProfile').objects.filter(
        pk=local_profile.pk
    ).exists()
    assert migrated_apps.get_model('ai_agents', 'AIAgentProfile').objects.filter(
        pk=openai_profile.pk
    ).exists()
```

- [ ] **Step 2: Executar o teste e registrar o RED**

Run:

```bash
./scripts/test.sh --reuse-db tests/test_ai_agents_migrations.py::test_existing_local_agent_records_are_purged_without_touching_openai -q
```

Expected: FAIL porque o perfil local ainda existe no estado `0002`.

- [ ] **Step 3: Criar a migration destrutiva e apontar o teste para 0003**

Criar `ai_agents/migrations/0003_purge_existing_local_agent_records.py`:

```python
from django.db import migrations


def purge_existing_local_agent_records(apps, schema_editor):
    database_alias = schema_editor.connection.alias
    AgentProfile = apps.get_model('ai_agents', 'AIAgentProfile')
    AgentRun = apps.get_model('ai_agents', 'AIAgentRun')
    Suggestion = apps.get_model('ai_agents', 'AIInsightSuggestion')
    AuditLog = apps.get_model('ai_agents', 'AIPromptAuditLog')

    profile_ids = list(
        AgentProfile.objects.using(database_alias)
        .filter(provider='local')
        .values_list('pk', flat=True)
    )
    if not profile_ids:
        return

    run_ids = list(
        AgentRun.objects.using(database_alias)
        .filter(agent_id__in=profile_ids)
        .values_list('pk', flat=True)
    )
    AuditLog.objects.using(database_alias).filter(agent_id__in=profile_ids).delete()
    Suggestion.objects.using(database_alias).filter(run_id__in=run_ids).delete()
    AgentRun.objects.using(database_alias).filter(pk__in=run_ids).delete()
    AgentProfile.objects.using(database_alias).filter(pk__in=profile_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ai_agents', '0002_normalize_agent_profile_providers'),
    ]

    operations = [
        migrations.RunPython(
            purge_existing_local_agent_records,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
```

Alterar o teste para `new_target = ('ai_agents', '0003_purge_existing_local_agent_records')` e afirmar também que execução, sugestão e auditoria locais desapareceram, enquanto os quatro registros OpenAI permanecem.

- [ ] **Step 4: Executar os testes de migration**

Run:

```bash
./scripts/test.sh --reuse-db tests/test_ai_agents_migrations.py -q
```

Expected: os dois testes passam, sem warnings.

- [ ] **Step 5: Revisar o diff da Task 1 sem commit**

Run:

```bash
git diff --check -- tests/test_ai_agents_migrations.py ai_agents/migrations/0003_purge_existing_local_agent_records.py
git status --short -- tests/test_ai_agents_migrations.py ai_agents/migrations/0003_purge_existing_local_agent_records.py
```

Expected: nenhum erro de whitespace; somente os dois arquivos planejados aparecem.

---

### Task 2: Remover configuração, demo e documentação aposentados

**Files:**
- Modify: `tests/test_cosmetics_platform_contract.py`
- Modify: `core/settings/base.py`
- Modify: `.env`
- Modify: `governance/demo_seeders.py`
- Modify: `docs/pdf/especificacao_tecnica.md`
- Generated: `site/`

**Interfaces:**
- Consumes: contrato ativo com OpenAI e fallback local determinístico.
- Produces: runtime sem settings aposentadas, seeder sem agentes locais predefinidos e documentação alinhada.

- [ ] **Step 1: Escrever contratos positivos para settings e seeder**

Adicionar ao teste de contrato:

```python
def test_ai_configuration_and_demo_use_only_active_contracts():
    settings_source = read('core/settings/base.py')
    demo_source = read('governance/demo_seeders.py')

    assert "OPENAI_API_KEY = env('OPENAI_API_KEY'" in settings_source
    assert "OPENAI_MODEL = env('OPENAI_MODEL'" in settings_source
    assert "def _seed_ai_agents(self):" in demo_source
    assert "'ai_agents.profiles'" not in demo_source
    assert "'ai_agents.runs'" not in demo_source
    assert "'ai_agents.suggestions'" not in demo_source
```

- [ ] **Step 2: Executar o contrato e registrar o RED**

Run:

```bash
./scripts/test.sh --reuse-db tests/test_cosmetics_platform_contract.py::test_ai_configuration_and_demo_use_only_active_contracts -q
```

Expected: FAIL porque o seeder ainda cria os três recursos de IA.

- [ ] **Step 3: Remover apenas o bloco de agentes da função demo**

Em `governance/demo_seeders.py`, manter `IntegrationConnector`,
`ApiClientApplication`, `connector` e `integration_connector`, mas remover os
imports de `AIAgentProfile`, `AIAgentRun`, `AIInsightSuggestion`, o perfil demo,
a execução, a sugestão e a chave `ai_agent` de `self.refs`.

- [ ] **Step 4: Remover settings e variáveis locais sem expor valores**

Remover de `core/settings/base.py` as quatro linhas consecutivas de settings com
o prefixo aposentado. Em `.env`, remover somente as linhas cujos nomes usam o
mesmo prefixo, sem imprimir seus valores em terminal ou relatório.

- [ ] **Step 5: Atualizar a especificação técnica**

Em `docs/pdf/especificacao_tecnica.md`, substituir a lista de integrações por:

```markdown
O módulo de integrações registra conectores, clientes de API, chamadas e eventos. O projeto contempla provedores fiscais, e-mail, backup, OpenAI e mecanismos de upload/criptografia. Chamadas externas devem ser configuradas por variáveis de ambiente e segredos externos, sem credenciais reais versionadas.
```

- [ ] **Step 6: Executar contratos focados**

Run:

```bash
./scripts/test.sh --reuse-db tests/test_cosmetics_platform_contract.py tests/test_ai_agents.py -q
```

Expected: todos os testes passam.

- [ ] **Step 7: Reconstruir documentação gerada**

Run:

```bash
.venv/bin/python -m mkdocs build --clean
```

Expected: exit 0; warnings preexistentes de navegação podem permanecer, mas o
site e o índice de busca são reconstruídos.

- [ ] **Step 8: Revisar o diff da Task 2 sem commit**

Run:

```bash
git diff --check -- core/settings/base.py governance/demo_seeders.py docs/pdf/especificacao_tecnica.md tests/test_cosmetics_platform_contract.py
git status --short -- core/settings/base.py governance/demo_seeders.py docs/pdf/especificacao_tecnica.md tests/test_cosmetics_platform_contract.py
```

Expected: nenhum erro de whitespace; mudanças limitadas ao escopo planejado.

---

### Task 3: Fazer backup, aplicar a migration local e verificar a limpeza

**Files:**
- Verify only: banco PostgreSQL persistente local
- Backup outside repository: diretório temporário `rgn-ai-cleanup-backup-*`

**Interfaces:**
- Consumes: migration validada nas Tasks 1–2 e configuração atual do `.env`.
- Produces: backup recuperável, banco local saneado e evidência de ausência final.

- [ ] **Step 1: Confirmar o alvo sem revelar credenciais**

Run:

```bash
.venv/bin/python manage.py showmigrations ai_agents
.venv/bin/python manage.py shell -c "from django.conf import settings; from ai_agents.models import AIAgentProfile; print('engine=' + settings.DATABASES['default']['ENGINE']); print('local_profiles=' + str(AIAgentProfile.objects.filter(provider='local').count()))"
```

Expected: engine PostgreSQL e contagem numérica; não imprimir URL, usuário ou senha.

- [ ] **Step 2: Criar backup externo recuperável**

Criar um diretório externo e fazer o dump com as configurações já carregadas
pelo Django. O comando não imprime URL, usuário ou senha:

```bash
cleanup_backup_dir=$(mktemp -d /tmp/rgn-ai-cleanup-backup-XXXXXX)
cleanup_backup_path="$cleanup_backup_dir/postgres-before-cleanup.sql.gz"
CLEANUP_BACKUP_PATH="$cleanup_backup_path" .venv/bin/python -c '
import gzip
import os
import subprocess

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.conf import settings

database = settings.DATABASES["default"]
process_environment = os.environ.copy()
process_environment["PGPASSWORD"] = database.get("PASSWORD", "")
command = [
    "pg_dump",
    "-h", database.get("HOST") or "127.0.0.1",
    "-p", str(database.get("PORT") or 5432),
    "-U", database.get("USER") or "",
    "-d", database["NAME"],
    "--no-owner",
    "--no-acl",
]
with gzip.open(os.environ["CLEANUP_BACKUP_PATH"], "wb") as backup_file:
    subprocess.run(command, env=process_environment, stdout=backup_file, check=True)
'
test -s "$cleanup_backup_path"
sha256sum "$cleanup_backup_path"
```

Expected: dump PostgreSQL não vazio e um hash SHA-256. Se o `pg_dump` não puder
alcançar o banco, parar sem aplicar a migration.

- [ ] **Step 3: Aplicar migrations apenas ao banco local identificado**

Run:

```bash
.venv/bin/python manage.py migrate ai_agents
```

Expected: `0003_purge_existing_local_agent_records... OK`.

- [ ] **Step 4: Provar exclusão e preservação no banco local**

Run:

```bash
.venv/bin/python manage.py shell -c "from ai_agents.models import AIAgentProfile, AIAgentRun, AIInsightSuggestion, AIPromptAuditLog; print('local_profiles=' + str(AIAgentProfile.objects.filter(provider='local').count())); print('openai_profiles=' + str(AIAgentProfile.objects.filter(provider='openai').count())); print('orphan_runs=' + str(AIAgentRun.objects.filter(agent__isnull=True).count())); print('orphan_suggestions=' + str(AIInsightSuggestion.objects.filter(run__isnull=True).count())); print('orphan_audits=' + str(AIPromptAuditLog.objects.filter(run__isnull=True).count()))"
```

Expected: `local_profiles=0` e todas as contagens de órfãos iguais a zero;
registrar a contagem OpenAI sem exigir valor mínimo.

- [ ] **Step 5: Executar verificação estrutural e testes focados frescos**

Run:

```bash
.venv/bin/python -m ruff check ai_agents governance/demo_seeders.py tests/test_ai_agents.py tests/test_ai_agents_migrations.py tests/test_cosmetics_platform_contract.py
.venv/bin/python -m compileall -q ai_agents governance/demo_seeders.py tests/test_ai_agents.py tests/test_ai_agents_migrations.py tests/test_cosmetics_platform_contract.py
env TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py check --settings=core.settings.test
env TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test .venv/bin/python manage.py makemigrations --check --dry-run --settings=core.settings.test
./scripts/test.sh --reuse-db tests/test_ai_agents.py tests/test_ai_agents_migrations.py tests/test_cosmetics_platform_contract.py -q
git diff --check
```

Expected: todos os comandos terminam com código zero.

- [ ] **Step 6: Executar varredura negativa ampla**

Executar uma busca case-insensitive pelo nome comercial aposentado e pelas
variações com espaço/hífen, excluindo somente `.git`, `.venv`, `htmlcov`,
`node_modules`, `media` e `staticfiles`. Repetir com `find` para nomes de arquivo.

Expected: zero ocorrências e zero nomes de arquivo no projeto, incluindo
arquivos ignorados e `site/`.

- [ ] **Step 7: Revisar o diff completo e registrar limitações do gate global**

Run:

```bash
git diff --stat
git status --short --branch
```

Expected: alterações desta implementação identificáveis no worktree sujo. O
relatório final deve distinguir os testes focados aprovados das sete falhas
globais preexistentes já diagnosticadas.
