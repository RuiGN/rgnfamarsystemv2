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


def _create_genealogy_fixture(apps, *, with_production_order=True):
    MasterFormula = apps.get_model('formulations', 'MasterFormula')
    ManufacturingRoute = apps.get_model('formulations', 'ManufacturingRoute')
    StockLot = apps.get_model('inventory', 'StockLot')
    StockLotGenealogy = apps.get_model('inventory', 'StockLotGenealogy')
    Product = apps.get_model('masters', 'Product')
    UnitOfMeasure = apps.get_model('masters', 'UnitOfMeasure')
    ProductionOrder = apps.get_model('production', 'ProductionOrder')

    unit = UnitOfMeasure.objects.create(
        code='KG-MIG-GENE',
        name='Quilograma migration genealogia',
        symbol='kg',
    )
    input_product = Product.objects.create(
        code='MP-MIG-GENE',
        description='Entrada migration genealogia',
        item_type='raw_material',
        unit=unit,
        status='approved',
    )
    output_product = Product.objects.create(
        code='PA-MIG-GENE',
        description='Saída migration genealogia',
        item_type='finished_product',
        unit=unit,
        status='approved',
    )
    formula = MasterFormula.objects.create(
        product=output_product,
        code='F-MIG-GENE',
        version=1,
        status='approved',
        batch_size=Decimal('100.0000'),
        batch_unit=unit,
        effective_from=timezone.localdate(),
    )
    route = ManufacturingRoute.objects.create(
        product=output_product,
        formula=formula,
        code='R-MIG-GENE',
        version=1,
        status='approved',
        effective_from=timezone.localdate(),
    )
    production_order = None
    if with_production_order:
        production_order = ProductionOrder.objects.create(
            order_number='OP-MIG-GENE',
            batch_number='LOT-MIG-GENE',
            product=output_product,
            formula=formula,
            route=route,
            planned_quantity=Decimal('100.0000'),
            unit=unit,
        )
    input_lot = StockLot.objects.create(product=input_product, lot_number='IN-MIG-GENE')
    output_lot = StockLot.objects.create(product=output_product, lot_number='OUT-MIG-GENE')
    values = {
        'input_lot': input_lot,
        'output_lot': output_lot,
        'production_order': production_order,
        'relation_type': 'consumed_in_production',
        'quantity': Decimal('1.0000'),
        'unit': unit,
    }
    first = StockLotGenealogy.objects.create(**values)
    second = StockLotGenealogy.objects.create(**values)
    return StockLotGenealogy, values, first, second


@pytest.mark.django_db(transaction=True)
def test_genealogy_unique_migration_preflights_duplicates_then_applies_and_unapplies(
    restore_latest_migrations,
):
    old_targets = [
        (
            'inventory',
            '0002_remove_stockbalance_unique_tenant_stock_balance_address_status_and_more',
        ),
        ('production', '0005_constrain_production_output_status'),
        ('masters', '0006_businesspartner_country_ref_site_country_ref'),
    ]
    new_target = ('inventory', '0003_unique_production_lot_genealogy')
    executor = MigrationExecutor(connection)
    executor.migrate(old_targets)
    old_apps = executor.loader.project_state(old_targets).apps
    StockLotGenealogy, values, first, second = _create_genealogy_fixture(old_apps)

    executor.loader.build_graph()
    with pytest.raises(RuntimeError) as error:
        executor.migrate([new_target])

    message = str(error.value)
    assert f'input_lot_id={values["input_lot"].pk}' in message
    assert f'output_lot_id={values["output_lot"].pk}' in message
    assert f'production_order_id={values["production_order"].pk}' in message
    assert f'IDs=[{first.pk}, {second.pk}]' in message
    assert 'saneamento explícito' in message
    assert StockLotGenealogy.objects.filter(pk__in=[first.pk, second.pk]).count() == 2
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'inventory_stocklotgenealogy'::regclass
                  AND conname = 'unique_production_lot_genealogy'
            )
            """
        )
        assert cursor.fetchone()[0] is False

    StockLotGenealogy.objects.filter(pk=second.pk).delete()
    executor = MigrationExecutor(connection)
    executor.migrate([new_target])
    migrated_apps = executor.loader.project_state([new_target]).apps
    MigratedGenealogy = migrated_apps.get_model('inventory', 'StockLotGenealogy')
    genealogy_values = {
        'input_lot_id': values['input_lot'].pk,
        'output_lot_id': values['output_lot'].pk,
        'production_order_id': values['production_order'].pk,
        'relation_type': values['relation_type'],
        'quantity': values['quantity'],
        'unit_id': values['unit'].pk,
    }

    with pytest.raises(IntegrityError), transaction.atomic():
        MigratedGenealogy.objects.create(**genealogy_values)

    executor.loader.build_graph()
    executor.migrate(old_targets)
    reversed_apps = executor.loader.project_state(old_targets).apps
    ReversedGenealogy = reversed_apps.get_model('inventory', 'StockLotGenealogy')
    duplicate_after_reverse = ReversedGenealogy.objects.create(**genealogy_values)
    assert (
        ReversedGenealogy.objects.filter(
            input_lot_id=values['input_lot'].pk,
            output_lot_id=values['output_lot'].pk,
            production_order_id=values['production_order'].pk,
            relation_type=values['relation_type'],
        ).count()
        == 2
    )
    duplicate_after_reverse.delete()


@pytest.mark.django_db(transaction=True)
def test_genealogy_unique_migration_treats_null_production_order_as_same_key(
    restore_latest_migrations,
):
    old_targets = [
        (
            'inventory',
            '0002_remove_stockbalance_unique_tenant_stock_balance_address_status_and_more',
        ),
        ('production', '0005_constrain_production_output_status'),
        ('masters', '0006_businesspartner_country_ref_site_country_ref'),
    ]
    new_target = ('inventory', '0003_unique_production_lot_genealogy')
    executor = MigrationExecutor(connection)
    executor.migrate(old_targets)
    old_apps = executor.loader.project_state(old_targets).apps
    StockLotGenealogy, values, first, second = _create_genealogy_fixture(
        old_apps,
        with_production_order=False,
    )

    executor.loader.build_graph()
    with pytest.raises(RuntimeError) as error:
        executor.migrate([new_target])

    message = str(error.value)
    assert 'production_order_id=None' in message
    assert f'IDs=[{first.pk}, {second.pk}]' in message
    assert StockLotGenealogy.objects.filter(pk__in=[first.pk, second.pk]).count() == 2
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'inventory_stocklotgenealogy'::regclass
                  AND conname = 'unique_production_lot_genealogy'
            )
            """
        )
        assert cursor.fetchone()[0] is False

    StockLotGenealogy.objects.filter(pk=second.pk).delete()
    executor = MigrationExecutor(connection)
    executor.migrate([new_target])
    migrated_apps = executor.loader.project_state([new_target]).apps
    MigratedGenealogy = migrated_apps.get_model('inventory', 'StockLotGenealogy')
    genealogy_values = {
        'input_lot_id': values['input_lot'].pk,
        'output_lot_id': values['output_lot'].pk,
        'production_order_id': None,
        'relation_type': values['relation_type'],
        'quantity': values['quantity'],
        'unit_id': values['unit'].pk,
    }

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'inventory_stocklotgenealogy'::regclass
              AND conname = 'unique_production_lot_genealogy'
            """
        )
        assert 'UNIQUE NULLS NOT DISTINCT' in cursor.fetchone()[0]

    with pytest.raises(IntegrityError), transaction.atomic():
        MigratedGenealogy.objects.create(**genealogy_values)

    executor.loader.build_graph()
    executor.migrate(old_targets)
    reversed_apps = executor.loader.project_state(old_targets).apps
    ReversedGenealogy = reversed_apps.get_model('inventory', 'StockLotGenealogy')
    duplicate_after_reverse = ReversedGenealogy.objects.create(**genealogy_values)
    assert (
        ReversedGenealogy.objects.filter(
            input_lot_id=values['input_lot'].pk,
            output_lot_id=values['output_lot'].pk,
            production_order_id=None,
            relation_type=values['relation_type'],
        ).count()
        == 2
    )
    duplicate_after_reverse.delete()


def test_stock_lot_genealogy_model_constraint_treats_nulls_as_not_distinct():
    from inventory.models import StockLotGenealogy

    constraint = next(
        constraint
        for constraint in StockLotGenealogy._meta.constraints
        if constraint.name == 'unique_production_lot_genealogy'
    )

    assert constraint.nulls_distinct is False
