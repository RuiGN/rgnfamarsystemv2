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


def test_stock_lot_genealogy_model_constraint_treats_nulls_as_not_distinct():
    from inventory.models import StockLotGenealogy

    constraint = next(
        constraint
        for constraint in StockLotGenealogy._meta.constraints
        if constraint.name == 'unique_production_lot_genealogy'
    )

    assert constraint.nulls_distinct is False
