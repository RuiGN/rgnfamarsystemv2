# Physical Equipment Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Excluir definitivamente o app `maintenance`, suas tabelas e todas as referências funcionais a equipamento/manutenção, preservando documentos transacionais de Compras e suportando bancos existentes e instalações novas.

**Architecture:** A remoção será entregue em duas fases. A Fase A limpa valores legados, remove relacionamentos e usa operações de migration do próprio app para apagar seus models e metadados; após todas as bases aplicarem essa fase, a Fase B remove o pacote e repara o histórico para bancos novos, com uma migration defensiva que rejeita bases que tenham pulado o checkpoint.

**Tech Stack:** Python 3, Django 6.0.8, Django migrations, PostgreSQL, SQLite de teste, pytest/pytest-django.

## Global Constraints

- A exclusão dos dados de manutenção é deliberadamente irreversível.
- Não executar a Fase B enquanto qualquer base persistente ainda possuir tabelas `maintenance_*`.
- Excluir conectores de Integrações, recursos/cargas de Planejamento e vínculos de Riscos classificados como `equipment`.
- Converter requisições de Compras com `source='maintenance'` para `source='manual'`.
- Preservar o risco relacionado ao excluir um `RiskLink` e preservar eventos de Integrações com `connector_id=NULL`.
- Preservar menções legítimas a equipamento físico de impressão e instruções regulatórias gerais.
- Não usar `DROP ... CASCADE` genérico nem apagar tabelas por padrão de nome sem lista/checagem explícita.
- Não misturar no commit alterações locais preexistentes de campos automáticos, layout ou acessibilidade; revisar o índice antes de cada commit.
- Seguir RED → GREEN → REFACTOR em cada comportamento novo.

---

## File Map

- `tests/test_equipment_removal.py`: contrato final de ausência de campos, choices, app, rotas e schema.
- `tests/test_equipment_removal_migrations.py`: teste de upgrade dos valores legados entre migrations.
- `integrations/migrations/0003_remove_equipment_provider.py`: exclui conectores de equipamento e altera a choice.
- `planning/migrations/0002_remove_equipment_capacity_resource.py`: exclui cargas/recursos de equipamento e altera a choice.
- `procurement/migrations/0002_remove_maintenance_requisition_source.py`: converte origem para manual e altera a choice.
- `risks/migrations/0002_remove_equipment_risk_links.py`: exclui vínculos de equipamento e altera a choice.
- `maintenance/migrations/0002_delete_maintenance_schema.py`: Fase A, remove os seis models e metadados do app.
- `base/migrations/0002_prune_maintenance_history.py`: Fase B, impede salto de fase e limpa o catálogo de migrations.
- `training/migrations/0001_initial.py`: histórico final para bancos novos, sem dependência ou FKs de `maintenance`.
- `core/settings/base.py`: retira o app somente na Fase B.
- `base/ui/converters.py` e `base/ui/urls.py`: removem a reserva especial de slug após o app desaparecer.
- `scripts/ci/quality-gate.sh`: retira o app excluído das verificações enumeradas.
- `README.md`, `PRD.md`, `docs/architecture/production.md`, `docs/pdf/especificacao_funcional.md`, `docs/pdf/manual_usuario.md`, `knowledge/step_by_step_manual.py`, `auxiliary/cosmetics_seed.py`: alinham documentação e dados auxiliares ao domínio restante.

---

### Task 1: Limpar choices e dados legados nos apps sobreviventes

**Files:**
- Create: `tests/test_equipment_removal_migrations.py`
- Modify: `tests/test_equipment_removal.py`
- Modify: `integrations/models.py`
- Create: `integrations/migrations/0003_remove_equipment_provider.py`
- Modify: `planning/models.py`
- Create: `planning/migrations/0002_remove_equipment_capacity_resource.py`
- Modify: `procurement/models.py`
- Create: `procurement/migrations/0002_remove_maintenance_requisition_source.py`
- Modify: `risks/models.py`
- Modify: `tests/test_risks.py`
- Create: `risks/migrations/0002_remove_equipment_risk_links.py`

**Interfaces:**
- Consumes: valores legados `equipment` e `maintenance` gravados pelos models atuais.
- Produces: migrations que deixam os quatro apps sem valores legados e sem choices removidas; os nomes dessas migrations serão dependências da Fase A.

- [ ] **Step 1: Write the failing choice contract**

Adicionar a `tests/test_equipment_removal.py`:

```python
from integrations.models import IntegrationConnector
from planning.models import CapacityResource
from procurement.models import PurchaseRequisition
from risks.models import RiskLink


def test_active_choices_no_longer_offer_equipment_or_maintenance():
    assert 'equipment' not in IntegrationConnector.ProviderType.values
    assert 'equipment' not in CapacityResource.ResourceType.values
    assert 'equipment' not in RiskLink.LinkType.values
    assert 'maintenance' not in PurchaseRequisition.Source.values
```

Em `tests/test_risks.py`, retirar `RiskLink.LinkType.EQUIPMENT` do conjunto esperado.

- [ ] **Step 2: Run the contract and verify RED**

Run:

```bash
pytest -q tests/test_equipment_removal.py::test_active_choices_no_longer_offer_equipment_or_maintenance tests/test_risks.py
```

Expected: FAIL porque as quatro choices ainda contêm os valores removidos.

- [ ] **Step 3: Write the migration-upgrade test**

Criar `tests/test_equipment_removal_migrations.py` com um `TransactionTestCase` que migra os quatro apps para as versões anteriores, cria um conector e evento, um recurso e carga, uma requisição e um risco/vínculo, e então migra para as versões novas:

```python
from datetime import date

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class EquipmentReferenceCleanupMigrationTests(TransactionTestCase):
    migrate_from = [
        ('integrations', '0002_labelprintersettings'),
        ('planning', '0001_initial'),
        ('procurement', '0001_initial'),
        ('risks', '0001_initial'),
    ]
    migrate_to = [
        ('integrations', '0003_remove_equipment_provider'),
        ('planning', '0002_remove_equipment_capacity_resource'),
        ('procurement', '0002_remove_maintenance_requisition_source'),
        ('risks', '0002_remove_equipment_risk_links'),
    ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        app_label, model_name = settings.AUTH_USER_MODEL.split('.')
        User = old_apps.get_model(app_label, model_name)
        owner = User.objects.create(username='equipment-removal-owner')

        Connector = old_apps.get_model('integrations', 'IntegrationConnector')
        Event = old_apps.get_model('integrations', 'IntegrationEvent')
        connector = Connector.objects.create(
            code='LEGACY-EQUIPMENT', name='Legacy', provider_type='equipment'
        )
        Event.objects.create(connector=connector, event_type='configured')

        Resource = old_apps.get_model('planning', 'CapacityResource')
        Load = old_apps.get_model('planning', 'CapacityLoad')
        resource = Resource.objects.create(
            code='LEGACY-EQP', name='Legacy', resource_type='equipment',
            daily_capacity_minutes='480.00',
        )
        Load.objects.create(
            resource=resource, period_date=date(2026, 8, 29),
            required_minutes='60.00', available_minutes='480.00',
        )

        Requisition = old_apps.get_model('procurement', 'PurchaseRequisition')
        self.requisition_pk = Requisition.objects.create(
            requisition_number='REQ-LEGACY', source='maintenance',
            justification='Registro transacional preservado.',
        ).pk

        Risk = old_apps.get_model('risks', 'RiskRecord')
        Link = old_apps.get_model('risks', 'RiskLink')
        risk = Risk.objects.create(
            risk_number='RISK-LEGACY', risk_category='operations', title='Legacy',
            description='Legacy', process_area='Operações', owner=owner,
            due_date=date(2026, 12, 1), next_review_date=date(2026, 12, 1),
        )
        self.risk_pk = risk.pk
        Link.objects.create(
            risk=risk, link_type='equipment', reference_code='EQP-01',
            impact_description='Vínculo removido.',
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_legacy_values_are_cleaned_without_losing_preserved_records(self):
        Connector = self.apps.get_model('integrations', 'IntegrationConnector')
        Event = self.apps.get_model('integrations', 'IntegrationEvent')
        Resource = self.apps.get_model('planning', 'CapacityResource')
        Load = self.apps.get_model('planning', 'CapacityLoad')
        Requisition = self.apps.get_model('procurement', 'PurchaseRequisition')
        Risk = self.apps.get_model('risks', 'RiskRecord')
        Link = self.apps.get_model('risks', 'RiskLink')

        assert not Connector.objects.filter(provider_type='equipment').exists()
        assert Event.objects.filter(connector__isnull=True).exists()
        assert not Resource.objects.filter(resource_type='equipment').exists()
        assert not Load.objects.filter(resource_id__isnull=False).exists()
        assert Requisition.objects.get(pk=self.requisition_pk).source == 'manual'
        assert Risk.objects.filter(pk=self.risk_pk).exists()
        assert not Link.objects.filter(link_type='equipment').exists()
```

- [ ] **Step 4: Run the migration test and verify RED**

Run:

```bash
pytest -q tests/test_equipment_removal_migrations.py
```

Expected: ERROR/FAIL porque as quatro migrations de destino ainda não existem.

- [ ] **Step 5: Remove the choices and their runtime validation branches**

Remover exatamente:

```python
# integrations/models.py
EQUIPMENT = 'equipment', 'Equipamento'

# planning/models.py
EQUIPMENT = 'equipment', 'Equipamento'

# procurement/models.py
MAINTENANCE = 'maintenance', 'Manutenção'

# risks/models.py
EQUIPMENT = 'equipment', 'Equipamento'
```

Em `RiskLink.clean()`, trocar:

```python
if self.link_type in {self.LinkType.PROCESS, self.LinkType.EQUIPMENT} and not self.reference_code:
```

por:

```python
if self.link_type == self.LinkType.PROCESS and not self.reference_code:
```

- [ ] **Step 6: Generate and customize the four migrations**

Run:

```bash
python manage.py makemigrations integrations planning procurement risks
```

Antes de cada `AlterField`, inserir um `RunPython` irreversível que use models históricos e o alias correto:

```python
def clean_legacy_values(apps, schema_editor):
    alias = schema_editor.connection.alias
    # integrations: preservar IntegrationEvent por SET_NULL.
    apps.get_model('integrations', 'IntegrationConnector').objects.using(alias).filter(
        provider_type='equipment'
    ).delete()

    # planning: CapacityLoad usa PROTECT, portanto excluir cargas primeiro.
    Resource = apps.get_model('planning', 'CapacityResource')
    Load = apps.get_model('planning', 'CapacityLoad')
    resource_ids = Resource.objects.using(alias).filter(
        resource_type='equipment'
    ).values_list('pk', flat=True)
    Load.objects.using(alias).filter(resource_id__in=resource_ids).delete()
    Resource.objects.using(alias).filter(resource_type='equipment').delete()

    # procurement: preservar o documento transacional.
    apps.get_model('procurement', 'PurchaseRequisition').objects.using(alias).filter(
        source='maintenance'
    ).update(source='manual')

    # risks: preservar RiskRecord; o FK do link usa CASCADE apenas no sentido risco -> link.
    apps.get_model('risks', 'RiskLink').objects.using(alias).filter(
        link_type='equipment'
    ).delete()
```

Cada arquivo conterá somente o trecho correspondente ao próprio app, calculará
a quantidade afetada a partir do retorno de `delete()`/`update()`, registrará
essa quantidade com `logging.getLogger(__name__).info(...)` sem incluir dados
dos registros e terminará com:

```python
migrations.RunPython(clean_legacy_values),
```

Sem `reverse_code`, a reversão deve levantar `IrreversibleError`.

- [ ] **Step 7: Verify GREEN**

Run:

```bash
pytest -q tests/test_equipment_removal.py tests/test_equipment_removal_migrations.py tests/test_integrations.py tests/test_planning.py tests/test_procurement.py tests/test_risks.py
python manage.py makemigrations --check --dry-run
```

Expected: todos os testes passam e `No changes detected`.

- [ ] **Step 8: Commit only Task 1 changes**

```bash
git add tests/test_equipment_removal.py tests/test_equipment_removal_migrations.py tests/test_risks.py \
  integrations/models.py integrations/migrations/0003_remove_equipment_provider.py \
  planning/models.py planning/migrations/0002_remove_equipment_capacity_resource.py \
  procurement/models.py procurement/migrations/0002_remove_maintenance_requisition_source.py \
  risks/models.py risks/migrations/0002_remove_equipment_risk_links.py
git diff --cached --check
git commit -m "refactor: remove equipment reference choices"
```

---

### Task 2: Fase A — transformar maintenance em tombstone e apagar o schema

**Files:**
- Modify: `tests/test_equipment_removal.py`
- Delete: `tests/test_maintenance.py`
- Create: `maintenance/migrations/0002_delete_maintenance_schema.py`
- Delete: `maintenance/models.py`
- Delete: `maintenance/admin.py`
- Delete: `maintenance/serializers.py`
- Delete: `maintenance/urls.py`
- Delete: `maintenance/views.py`
- Keep: `maintenance/__init__.py`
- Keep: `maintenance/apps.py`
- Keep: `maintenance/migrations/0001_initial.py`
- Keep: `maintenance/migrations/__init__.py`
- Modify: external model/admin/serializer/view/UI files already changed in the working tree.

**Interfaces:**
- Consumes: migrations de remoção externa de Task 1 e as migrations já presentes em Changes, Desvios, Formulações, Produção, QA, Qualidade e Treinamentos.
- Produces: app instalado sem models de runtime e banco sem tabelas, permissões ou content types `maintenance`.

- [ ] **Step 1: Write the failing Phase A schema contract**

Adicionar a `tests/test_equipment_removal.py`:

```python
from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection


def test_phase_a_maintenance_app_is_an_empty_tombstone():
    assert list(apps.get_app_config('maintenance').get_models()) == []


@pytest.mark.django_db
def test_phase_a_maintenance_schema_and_metadata_are_deleted():
    tables = set(connection.introspection.table_names())
    assert not {name for name in tables if name.startswith('maintenance_')}
    assert not ContentType.objects.filter(app_label='maintenance').exists()
    assert not Permission.objects.filter(content_type__app_label='maintenance').exists()
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
pytest -q tests/test_equipment_removal.py::test_phase_a_maintenance_app_is_an_empty_tombstone tests/test_equipment_removal.py::test_phase_a_maintenance_schema_and_metadata_are_deleted
```

Expected: FAIL porque o app ainda possui seis models e suas tabelas.

- [ ] **Step 3: Create the destructive DeleteModel migration**

Criar `maintenance/migrations/0002_delete_maintenance_schema.py`:

```python
from django.db import migrations


def delete_maintenance_metadata(apps, schema_editor):
    alias = schema_editor.connection.alias
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    content_types = ContentType.objects.using(alias).filter(app_label='maintenance')
    Permission.objects.using(alias).filter(content_type__in=content_types).delete()
    content_types.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('maintenance', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('changes', '0003_remove_changecontrol_equipment_reference_and_more'),
        ('compliance', '0002_alter_compliancechecklistitem_source_module_and_more'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('deviations', '0003_remove_qualityevent_equipment_reference'),
        ('formulations', '0002_remove_routestep_equipment_code'),
        ('governance', '0002_alter_governanceauditlog_module_and_more'),
        ('integrations', '0003_remove_equipment_provider'),
        ('planning', '0002_remove_equipment_capacity_resource'),
        ('procurement', '0002_remove_maintenance_requisition_source'),
        ('production', '0003_remove_productionlaborentry_equipment_code_and_more'),
        ('qa', '0002_remove_qualityblock_equipment_reference_and_more'),
        ('quality', '0002_remove_qualityanalysis_equipment_code'),
        ('risks', '0002_remove_equipment_risk_links'),
        ('training', '0003_remove_criticalactivityrule_training_cr_equipme_c51040_idx_and_more'),
    ]

    operations = [
        migrations.DeleteModel(name='MaintenanceMetricReport'),
        migrations.DeleteModel(name='EquipmentUsageLog'),
        migrations.DeleteModel(name='EquipmentDowntime'),
        migrations.DeleteModel(name='MaintenanceOrder'),
        migrations.DeleteModel(name='MaintenancePlan'),
        migrations.DeleteModel(name='EquipmentAsset'),
        migrations.RunPython(delete_maintenance_metadata),
    ]
```

- [ ] **Step 4: Remove runtime code while retaining the migration tombstone**

Excluir `maintenance/models.py`, `admin.py`, `serializers.py`, `urls.py` e `views.py`. Manter `maintenance` em `INSTALLED_APPS`, junto com `apps.py`, `__init__.py` e o pacote de migrations.

Concluir as remoções já iniciadas de imports, campos, registros de UI, rotas, actions, admin, serializers, views, seeds e testes nos arquivos modificados do working tree. Não alterar hunks de campos automáticos, layout ou acessibilidade.

- [ ] **Step 5: Verify GREEN on a fresh test database**

Run:

```bash
pytest -q tests/test_equipment_removal.py tests/test_action_state_matrix.py tests/test_app_ui.py tests/test_changes.py tests/test_deviations.py tests/test_production.py tests/test_production_operations.py tests/test_qa.py tests/test_quality.py tests/test_training.py
python manage.py check
python manage.py makemigrations --check --dry-run
```

Expected: testes passam, system check sem issues e nenhuma migration pendente.

- [ ] **Step 6: Commit the Phase A retirement release**

Usar staging por hunk nos arquivos que também contêm alterações preexistentes:

```bash
git add maintenance tests/test_equipment_removal.py tests/test_maintenance.py
git add -p base changes deviations formulations production qa quality training governance core README.md mkdocs.yml
git diff --cached --check
git diff --cached
git commit -m "refactor: retire equipment maintenance module"
```

Não prosseguir se o diff staged contiver mudanças de identificadores automáticos, sticky footer ou acessibilidade.

---

### Task 3: Checkpoint obrigatório da Fase A

**Files:**
- No repository changes.

**Interfaces:**
- Consumes: release/commit da Fase A.
- Produces: confirmação auditável de que cada base persistente não possui tabelas nem metadados `maintenance`.

- [ ] **Step 1: Record the current database state before migration**

Run no ambiente-alvo:

```bash
python manage.py showmigrations maintenance training
python manage.py shell -c "from django.db import connection; print(sorted(t for t in connection.introspection.table_names() if t.startswith('maintenance_')))"
```

Expected: `maintenance.0002_delete_maintenance_schema` ainda não aplicada e as seis tabelas podem existir.

- [ ] **Step 2: Apply Phase A**

Run:

```bash
python manage.py migrate --noinput
```

Expected: migration `maintenance.0002_delete_maintenance_schema` aplicada sem erro.

- [ ] **Step 3: Prove destructive migration completion**

Run:

```bash
python manage.py shell -c "from django.contrib.auth.models import Permission; from django.contrib.contenttypes.models import ContentType; from django.db import connection; print({'tables': sorted(t for t in connection.introspection.table_names() if t.startswith('maintenance_')), 'content_types': ContentType.objects.filter(app_label='maintenance').count(), 'permissions': Permission.objects.filter(content_type__app_label='maintenance').count()})"
```

Expected exactly:

```text
{'tables': [], 'content_types': 0, 'permissions': 0}
```

- [ ] **Step 4: Stop until every persistent environment is confirmed**

Não iniciar Task 4 enquanto desenvolvimento persistente, homologação e produção aplicáveis não apresentarem o resultado vazio acima. Se somente a base local existir, registrar explicitamente essa condição antes de continuar.

---

### Task 4: Fase B — excluir fisicamente o app e reparar o histórico final

**Files:**
- Modify: `tests/test_equipment_removal.py`
- Create: `base/migrations/0002_prune_maintenance_history.py`
- Modify: `training/migrations/0001_initial.py`
- Delete: `training/migrations/0003_remove_criticalactivityrule_training_cr_equipme_c51040_idx_and_more.py`
- Delete: `maintenance/__init__.py`
- Delete: `maintenance/apps.py`
- Delete: `maintenance/migrations/__init__.py`
- Delete: `maintenance/migrations/0001_initial.py`
- Delete: `maintenance/migrations/0002_delete_maintenance_schema.py`
- Modify: `core/settings/base.py`
- Modify: `base/ui/urls.py`
- Delete: `base/ui/converters.py`
- Modify: `scripts/ci/quality-gate.sh`

**Interfaces:**
- Consumes: prova de que todas as bases aplicaram a Fase A.
- Produces: repositório sem pacote/app `maintenance`, grafo válido para banco novo e guard que rejeita banco que pulou a Fase A.

- [ ] **Step 1: Write the failing final-state contract**

Adicionar a `tests/test_equipment_removal.py`:

```python
from importlib.util import find_spec

from django.conf import settings


def test_maintenance_app_and_python_package_are_physically_absent():
    assert 'maintenance' not in settings.INSTALLED_APPS
    with pytest.raises(LookupError):
        apps.get_app_config('maintenance')
    assert find_spec('maintenance') is None
```

Adicionar também:

```python
from importlib import import_module


@pytest.mark.django_db(transaction=True)
def test_phase_b_guard_rejects_a_database_that_skipped_phase_a():
    migration = import_module('base.migrations.0002_prune_maintenance_history')
    table_name = 'maintenance_phase_guard'
    quoted_table = connection.ops.quote_name(table_name)
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE TABLE {quoted_table} (id integer primary key)')
    try:
        with connection.schema_editor() as schema_editor:
            with pytest.raises(RuntimeError, match='Fase A obrigatória não aplicada'):
                migration.prune_maintenance_history(apps, schema_editor)
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE {quoted_table}')
```

Isso prova que uma base que pulou a Fase A não é aceita.

Para `/app/maintenance/`, usar o client e exigir HTTP 404; para as duas APIs, manter `resolve()` levantando `Resolver404`. Isso permite remover o converter especial e toda referência de produção ao slug aposentado.

- [ ] **Step 2: Run and verify RED**

Run:

```bash
pytest -q tests/test_equipment_removal.py::test_maintenance_app_and_python_package_are_physically_absent
```

Expected: FAIL porque o tombstone ainda está instalado e importável.

- [ ] **Step 3: Create the defensive history-pruning migration**

Criar `base/migrations/0002_prune_maintenance_history.py`:

```python
from django.db import migrations
from django.db.migrations.recorder import MigrationRecorder


def prune_maintenance_history(apps, schema_editor):
    connection = schema_editor.connection
    remaining = sorted(
        table for table in connection.introspection.table_names()
        if table.startswith('maintenance_')
    )
    if remaining:
        raise RuntimeError(
            'Fase A obrigatória não aplicada; tabelas maintenance restantes: '
            + ', '.join(remaining)
        )

    alias = connection.alias
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    content_types = ContentType.objects.using(alias).filter(app_label='maintenance')
    Permission.objects.using(alias).filter(content_type__in=content_types).delete()
    content_types.delete()
    MigrationRecorder.Migration.objects.using(alias).filter(app='maintenance').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]
    operations = [migrations.RunPython(prune_maintenance_history)]
```

Sem função reversa, a limpeza continua irreversível.

- [ ] **Step 4: Repair the final migration graph for fresh installs**

Em `training/migrations/0001_initial.py`:

- remover `('maintenance', '0001_initial')` de `dependencies`;
- remover os dois campos FK chamados `equipment`;
- remover os índices `training_cr_equipme_c51040_idx` e `training_tr_equipme_c54e26_idx`.

Excluir `training/migrations/0003_remove_criticalactivityrule_training_cr_equipme_c51040_idx_and_more.py`, pois todas as bases existentes já a aplicaram antes do checkpoint e bancos novos não criam mais esses campos em `0001_initial`.

- [ ] **Step 5: Remove the app and tombstone code**

Remover `'maintenance'` de `LOCAL_APPS`, excluir o diretório `maintenance/`, retirar `maintenance` da lista em `scripts/ci/quality-gate.sh`, restaurar `<slug:module_slug>` em `base/ui/urls.py` e excluir `base/ui/converters.py`. Antes de testar `find_spec()`, remover também o diretório ignorado e já inspecionado `maintenance/__pycache__/`; não usar glob ou caminho amplo.

- [ ] **Step 6: Verify GREEN on the upgraded database**

Run:

```bash
python manage.py migrate --noinput
pytest -q tests/test_equipment_removal.py
python manage.py check
python manage.py makemigrations --check --dry-run
```

Expected: migration de prune aplicada, testes passam, system check limpo e nenhuma migration pendente.

- [ ] **Step 7: Verify a fresh database**

Run:

```bash
equipment_tmp_dir=$(mktemp -d)
TEST_DATABASE_URL="sqlite:///$equipment_tmp_dir/fresh.sqlite3" DJANGO_SETTINGS_MODULE=core.settings.test python manage.py migrate --noinput
TEST_DATABASE_URL="sqlite:///$equipment_tmp_dir/fresh.sqlite3" DJANGO_SETTINGS_MODULE=core.settings.test python manage.py shell -c "from django.db import connection; print(sorted(t for t in connection.introspection.table_names() if t.startswith('maintenance_')))"
```

Expected: migrations completas sem `NodeNotFoundError` e saída final `[]`. Remover apenas o diretório temporário explicitamente criado após a inspeção.

- [ ] **Step 8: Commit Phase B**

```bash
git add base/migrations/0002_prune_maintenance_history.py core/settings/base.py \
  training/migrations/0001_initial.py training/migrations/0003_remove_criticalactivityrule_training_cr_equipme_c51040_idx_and_more.py \
  maintenance base/ui/urls.py base/ui/converters.py scripts/ci/quality-gate.sh tests/test_equipment_removal.py
git diff --cached --check
git diff --cached
git commit -m "refactor: delete equipment maintenance app"
```

---

### Task 5: Alinhar documentação e executar a verificação integral

**Files:**
- Modify: `README.md`
- Modify: `PRD.md`
- Modify: `docs/architecture/production.md`
- Modify: `docs/pdf/especificacao_funcional.md`
- Modify: `docs/pdf/manual_usuario.md`
- Modify: `knowledge/step_by_step_manual.py`
- Modify: `auxiliary/cosmetics_seed.py`
- Modify/Delete: demais arquivos apontados pela busca final, somente quando representarem o módulo removido.

**Interfaces:**
- Consumes: estado final da Fase B.
- Produces: documentação coerente e evidência fresca de integridade, testes e ausência de resíduos.

- [ ] **Step 1: Remove functional documentation references**

Aplicar as substituições contextuais:

```text
PRD RF-04: retirar “equipamentos” da rastreabilidade de Produção.
docs/architecture/production.md: retirar campos e fluxos de equipamento removidos.
docs/pdf/especificacao_funcional.md: retirar equipamento dos registros de processo.
docs/pdf/manual_usuario.md: retirar equipamento dos cadastros/processos e preservar as instruções sobre impressora física.
knowledge/step_by_step_manual.py: retirar equipamento do passo operacional removido.
auxiliary/cosmetics_seed.py: trocar “Utilidades, equipamentos e manutenção.” por descrição sem o domínio excluído.
```

- [ ] **Step 2: Scan for residual active references**

Run:

```bash
rg -n -i --hidden --glob '!*.pyc' --glob '!.git/**' --glob '!design_system/refs/**' \
  'maintenance|EquipmentAsset|equipment_code|equipment_reference|\bequipment\b|equipamento' .
```

Expected: somente migrations históricas preservadas de outros apps, especificações/planos de decisão, testes negativos e menções legítimas a equipamento físico/regulatório. Nenhum import, model, choice, rota, menu, permissão, seed ou campo funcional ativo.

- [ ] **Step 3: Run targeted verification**

Run:

```bash
pytest -q tests/test_equipment_removal.py tests/test_equipment_removal_migrations.py tests/test_action_state_matrix.py tests/test_app_ui.py tests/test_changes.py tests/test_deviations.py tests/test_integrations.py tests/test_planning.py tests/test_procurement.py tests/test_production.py tests/test_production_operations.py tests/test_qa.py tests/test_quality.py tests/test_risks.py tests/test_training.py
python manage.py check
python manage.py makemigrations --check --dry-run
```

Expected: zero falhas, system check sem issues e `No changes detected`.

- [ ] **Step 4: Run the full quality gate**

Run:

```bash
pytest -q
bash scripts/ci/quality-gate.sh
```

Expected: suíte completa e quality gate com exit code `0`. Se o PostgreSQL isolado exigido pelo CI não estiver disponível, registrar separadamente a validação SQLite concluída e o gate PostgreSQL não executado; não declarar cobertura integral.

- [ ] **Step 5: Review requirements and staged diff**

Confirmar, um a um:

```text
[ ] diretório maintenance ausente
[ ] app ausente de INSTALLED_APPS
[ ] nenhuma tabela maintenance_* em banco atualizado ou novo
[ ] content types, permissões e histórico de migration removidos
[ ] choices e valores legados tratados conforme decisão aprovada
[ ] APIs ausentes e /app/maintenance/ retorna 404
[ ] documentação, menus, seeds e permissões revisados
[ ] migrations, checks e testes com evidência fresca
```

- [ ] **Step 6: Commit documentation and final regression tests**

```bash
git add README.md PRD.md docs/architecture/production.md docs/pdf/especificacao_funcional.md docs/pdf/manual_usuario.md knowledge/step_by_step_manual.py auxiliary/cosmetics_seed.py tests
git diff --cached --check
git diff --cached
git commit -m "docs: remove equipment maintenance references"
```

Antes do commit, retirar do índice qualquer hunk preexistente e não relacionado.
