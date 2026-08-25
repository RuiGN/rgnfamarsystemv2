from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


@pytest.fixture
def restore_latest_migrations():
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_standard_cost_state_machine_trigger_applies_and_unapplies(restore_latest_migrations):
    old_target = ('costing', '0002_initial')
    new_target = ('costing', '0003_standard_cost_state_machine')
    executor = MigrationExecutor(connection)
    executor.migrate([old_target])
    old_apps = executor.loader.project_state([old_target]).apps
    StandardCost = old_apps.get_model('costing', 'StandardCost')
    Product = old_apps.get_model('masters', 'Product')
    UnitOfMeasure = old_apps.get_model('masters', 'UnitOfMeasure')

    unit = UnitOfMeasure.objects.create(
        code='KG-MIG-STATE',
        name='Quilograma migration state',
        symbol='kg',
    )
    product = Product.objects.create(
        code='MP-MIG-STATE',
        description='Material migration state',
        item_type='raw_material',
        unit=unit,
        status='approved',
    )
    standard = StandardCost.objects.create(
        product=product,
        version='STATE-MIGRATION',
        effective_from=timezone.localdate(),
        standard_quantity=Decimal('100.0000'),
        unit=unit,
    )

    executor.loader.build_graph()
    executor.migrate([new_target])

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_trigger
                WHERE tgname = 'costing_standardcost_state_transition_trigger'
                  AND NOT tgisinternal
            )
            """
        )
        assert cursor.fetchone()[0] is True

    with pytest.raises(IntegrityError), transaction.atomic():
        StandardCost.objects.filter(pk=standard.pk).update(status='obsolete')

    approved_at = timezone.now()
    StandardCost.objects.filter(pk=standard.pk).update(
        status='approved',
        approved_at=approved_at,
    )
    StandardCost.objects.filter(pk=standard.pk).update(
        status='obsolete',
    )
    migrated = StandardCost.objects.get(pk=standard.pk)
    assert migrated.status == 'obsolete'
    assert migrated.approved_at == approved_at

    executor.loader.build_graph()
    executor.migrate([old_target])

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                EXISTS (
                    SELECT 1 FROM pg_trigger
                    WHERE tgname = 'costing_standardcost_state_transition_trigger'
                      AND NOT tgisinternal
                ),
                EXISTS (
                    SELECT 1 FROM pg_proc
                    WHERE proname = 'costing_enforce_standard_cost_state_transition'
                )
            """
        )
        trigger_exists, function_exists = cursor.fetchone()

    assert trigger_exists is False
    assert function_exists is False
