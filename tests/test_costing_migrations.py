from datetime import datetime
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
def test_standard_cost_approval_timestamp_migration_backfills_created_at_and_reverses_schema(
    restore_latest_migrations,
):
    old_target = ('costing', '0002_remove_costcenter_unique_tenant_cost_center_code_and_more')
    new_target = ('costing', '0003_standard_cost_approved_at_required')
    executor = MigrationExecutor(connection)
    executor.migrate([old_target])
    old_apps = executor.loader.project_state([old_target]).apps
    CostCenter = old_apps.get_model('costing', 'CostCenter')
    StandardCost = old_apps.get_model('costing', 'StandardCost')
    Product = old_apps.get_model('masters', 'Product')
    UnitOfMeasure = old_apps.get_model('masters', 'UnitOfMeasure')

    unit = UnitOfMeasure.objects.create(
        code='KG-MIG-CUSTO',
        name='Quilograma migration custo',
        symbol='kg',
    )
    product = Product.objects.create(
        code='MP-MIG-CUSTO',
        description='Material migration custo',
        item_type='raw_material',
        unit=unit,
        status='approved',
    )
    cost_center = CostCenter.objects.create(
        code='CC-MIG-CUSTO',
        name='Centro migration custo',
        center_type='production',
    )
    standard = StandardCost.objects.create(
        product=product,
        cost_center=cost_center,
        version='LEGADO-SEM-DATA',
        status='approved',
        effective_from=timezone.localdate(),
        standard_quantity=Decimal('100.0000'),
        unit=unit,
    )
    deterministic_created_at = timezone.make_aware(datetime(2026, 7, 1, 9, 30))
    StandardCost.objects.filter(pk=standard.pk).update(created_at=deterministic_created_at)

    executor.loader.build_graph()
    executor.migrate([new_target])
    new_apps = executor.loader.project_state([new_target]).apps
    MigratedStandardCost = new_apps.get_model('costing', 'StandardCost')

    migrated = MigratedStandardCost.objects.get(pk=standard.pk)
    assert migrated.approved_at == deterministic_created_at

    executor.loader.build_graph()
    executor.migrate([old_target])
    reversed_apps = executor.loader.project_state([old_target]).apps
    ReversedStandardCost = reversed_apps.get_model('costing', 'StandardCost')

    assert ReversedStandardCost.objects.get(pk=standard.pk).approved_at == deterministic_created_at


@pytest.mark.django_db(transaction=True)
def test_standard_cost_state_machine_trigger_applies_and_unapplies(restore_latest_migrations):
    old_target = ('costing', '0003_standard_cost_approved_at_required')
    new_target = ('costing', '0004_standard_cost_state_machine')
    executor = MigrationExecutor(connection)
    executor.migrate([old_target])
    old_apps = executor.loader.project_state([old_target]).apps
    CostCenter = old_apps.get_model('costing', 'CostCenter')
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
    cost_center = CostCenter.objects.create(
        code='CC-MIG-STATE',
        name='Centro migration state',
        center_type='production',
    )
    standard = StandardCost.objects.create(
        product=product,
        cost_center=cost_center,
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
        assert cursor.fetchone() == (False, False)

    StandardCost.objects.filter(pk=standard.pk).update(status='draft')
    assert StandardCost.objects.get(pk=standard.pk).status == 'draft'
