from django.db import migrations


# Funcao/trigger PL/pgSQL especificos do PostgreSQL para impor a maquina de
# estados de StandardCost. Em SQLite (backend de desenvolvimento local) nao ha
# equivalente direto; a operacao e um no-op e a aplicacao deve impor as
# transicoes em nivel de modelo/servico.
FORWARD_SQL = """
CREATE OR REPLACE FUNCTION costing_enforce_standard_cost_state_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'draft' THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                CONSTRAINT = 'costing_standardcost_state_machine',
                MESSAGE = 'Custos padrão novos devem ser inseridos como rascunho.';
        END IF;
        IF NEW.approved_by_id IS NOT NULL OR NEW.approved_at IS NOT NULL THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                CONSTRAINT = 'costing_standardcost_state_machine',
                MESSAGE = 'Rascunhos novos não podem conter evidência de aprovação.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
        IF NEW.approved_by_id IS DISTINCT FROM OLD.approved_by_id
           OR NEW.approved_at IS DISTINCT FROM OLD.approved_at THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                CONSTRAINT = 'costing_standardcost_state_machine',
                MESSAGE = 'Atualizações sem mudança de status devem preservar a evidência de aprovação.';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'approved' THEN
        IF NEW.approved_at IS NULL THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                CONSTRAINT = 'costing_standardcost_state_machine',
                MESSAGE = 'A aprovação exige data de aprovação.';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status = 'approved' AND NEW.status = 'obsolete' THEN
        IF NEW.approved_by_id IS DISTINCT FROM OLD.approved_by_id
           OR NEW.approved_at IS DISTINCT FROM OLD.approved_at THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                CONSTRAINT = 'costing_standardcost_state_machine',
                MESSAGE = 'A obsolescência deve preservar a evidência de aprovação.';
        END IF;
        RETURN NEW;
    END IF;

    RAISE EXCEPTION USING
        ERRCODE = '23514',
        CONSTRAINT = 'costing_standardcost_state_machine',
        MESSAGE = format(
            'Transição de custo padrão não permitida: %s -> %s.',
            OLD.status,
            NEW.status
        );
END;
$$;

CREATE TRIGGER costing_standardcost_state_transition_trigger
BEFORE INSERT OR UPDATE ON costing_standardcost
FOR EACH ROW
EXECUTE FUNCTION costing_enforce_standard_cost_state_transition();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS costing_standardcost_state_transition_trigger
ON costing_standardcost;
DROP FUNCTION IF EXISTS costing_enforce_standard_cost_state_transition();
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
        ('costing', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(code=_run_forward, reverse_code=_run_reverse),
    ]
