from django.db import migrations


OLD_CONSTRAINT = 'compliance_transversalrequirement_require_tenant_scope_not_null'
NEW_CONSTRAINT = 'compliance_policy_single_instance_scope_not_null'

# SQL especifico do PostgreSQL: renomeia uma constraint CHECK nomeada usando
# informacoes de pg_catalog. SQLite nao possui constraints CHECK nomeadas da
# mesma forma e a migration anterior (0006) ja removeu a constraint legada,
# portanto esta operacao e um no-op em qualquer backend nao-PostgreSQL.
FORWARD_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'compliance_transversalrequirementpolicy'::regclass
          AND conname = 'compliance_transversalrequirement_require_tenant_scope_not_null'
    ) THEN
        ALTER TABLE compliance_transversalrequirementpolicy
        RENAME CONSTRAINT compliance_transversalrequirement_require_tenant_scope_not_null
        TO compliance_policy_single_instance_scope_not_null;
    END IF;
END
$$;
"""

REVERSE_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'compliance_transversalrequirementpolicy'::regclass
          AND conname = 'compliance_policy_single_instance_scope_not_null'
    ) THEN
        ALTER TABLE compliance_transversalrequirementpolicy
        RENAME CONSTRAINT compliance_policy_single_instance_scope_not_null
        TO compliance_transversalrequirement_require_tenant_scope_not_null;
    END IF;
END
$$;
"""


def _run_forward(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(FORWARD_SQL)


def _run_reverse(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ('compliance', '0006_remove_transversalrequirementpolicy_require_tenant_scope_and_more'),
    ]

    operations = [
        migrations.RunPython(code=_run_forward, reverse_code=_run_reverse),
    ]
