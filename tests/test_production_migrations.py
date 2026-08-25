from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


@pytest.fixture
def restore_latest_migrations():
    yield
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE production_productionoperationexecution
            SET status = 'pending',
                started_at = NULL,
                ended_at = NULL,
                actual_minutes = 0,
                recorded_by_id = NULL,
                notes = ''
            """
        )
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def _create_operation_migration_fixture(apps):
    ManufacturingRoute = apps.get_model('formulations', 'ManufacturingRoute')
    MasterFormula = apps.get_model('formulations', 'MasterFormula')
    Product = apps.get_model('masters', 'Product')
    UnitOfMeasure = apps.get_model('masters', 'UnitOfMeasure')
    ProductionOperationExecution = apps.get_model(
        'production',
        'ProductionOperationExecution',
    )
    ProductionOrder = apps.get_model('production', 'ProductionOrder')
    User = apps.get_model('accounts', 'User')

    unit = UnitOfMeasure.objects.create(
        code='KG-MIG-OP',
        name='Quilograma migration operação',
        symbol='kg',
    )
    product = Product.objects.create(
        code='PA-MIG-OP',
        description='Produto migration operação',
        item_type='finished_product',
        unit=unit,
        status='approved',
    )
    formula = MasterFormula.objects.create(
        product=product,
        code='F-MIG-OP',
        version=1,
        status='approved',
        batch_size=Decimal('100.0000'),
        batch_unit=unit,
        effective_from=timezone.localdate(),
    )
    route = ManufacturingRoute.objects.create(
        product=product,
        formula=formula,
        code='R-MIG-OP',
        version=1,
        status='approved',
        effective_from=timezone.localdate(),
    )
    order = ProductionOrder.objects.create(
        order_number='OP-MIG-EVIDENCIA',
        batch_number='LOT-MIG-EVIDENCIA',
        product=product,
        formula=formula,
        route=route,
        planned_quantity=Decimal('100.0000'),
        unit=unit,
    )
    actor = User.objects.create(
        username='ator-migracao-operacao',
        email='ator-migracao-operacao@example.com',
    )
    now = timezone.now()
    invalid = {
        'pending': ProductionOperationExecution.objects.create(
            order=order,
            sequence=10,
            operation='Pendente incompatível',
            status='pending',
            started_at=now,
        ),
        'in_progress': ProductionOperationExecution.objects.create(
            order=order,
            sequence=20,
            operation='Em execução incompatível',
            status='in_progress',
        ),
        'completed': ProductionOperationExecution.objects.create(
            order=order,
            sequence=30,
            operation='Concluída incompatível',
            status='completed',
            started_at=now,
        ),
        'skipped': ProductionOperationExecution.objects.create(
            order=order,
            sequence=40,
            operation='Não executada incompatível',
            status='skipped',
            recorded_by=actor,
            notes='   ',
        ),
    }
    return ProductionOperationExecution, order, actor, invalid, now


@pytest.mark.django_db(transaction=True)
def test_operation_evidence_migration_preflights_then_applies_and_unapplies(
    restore_latest_migrations,
):
    old_target = ('production', '0005_constrain_production_output_status')
    old_targets = [
        old_target,
        ('accounts', '0013_user_avatar'),
    ]
    new_target = ('production', '0006_constrain_operation_status_evidence')
    executor = MigrationExecutor(connection)
    executor.migrate(old_targets)
    old_apps = executor.loader.project_state(old_targets).apps
    Operation, order, actor, invalid, now = _create_operation_migration_fixture(old_apps)

    executor.loader.build_graph()
    with pytest.raises(RuntimeError) as error:
        executor.migrate([new_target, old_targets[1]])

    message = str(error.value)
    expected_categories = {
        'pending_evidence': invalid['pending'].pk,
        'in_progress_evidence': invalid['in_progress'].pk,
        'completed_evidence': invalid['completed'].pk,
        'skipped_reason_blank_or_whitespace': invalid['skipped'].pk,
    }
    for category, record_id in expected_categories.items():
        assert category in message
        assert f'IDs=[{record_id}]' in message
    assert 'saneamento explícito' in message
    assert 'migrate production 0006' in message
    assert Operation.objects.filter(pk__in=[item.pk for item in invalid.values()]).count() == 4
    assert Operation.objects.get(pk=invalid['skipped'].pk).notes == '   '
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'production_productionoperationexecution'::regclass
                  AND conname IN (
                      'production_operation_status_evidence',
                      'production_operation_skipped_reason'
                  )
            )
            """
        )
        assert cursor.fetchone()[0] is False

    Operation.objects.filter(pk=invalid['pending'].pk).update(started_at=None)
    Operation.objects.filter(pk=invalid['in_progress'].pk).update(
        started_at=now,
        recorded_by_id=actor.pk,
    )
    Operation.objects.filter(pk=invalid['completed'].pk).update(
        ended_at=now,
        recorded_by_id=actor.pk,
    )
    Operation.objects.filter(pk=invalid['skipped'].pk).update(
        notes='Desvio documentado antes da migração.',
    )

    executor = MigrationExecutor(connection)
    executor.migrate([new_target, old_targets[1]])
    migrated_apps = executor.loader.project_state([new_target, old_targets[1]]).apps
    MigratedOperation = migrated_apps.get_model(
        'production',
        'ProductionOperationExecution',
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        MigratedOperation.objects.create(
            order_id=order.pk,
            sequence=50,
            operation='Novo pendente incompatível',
            status='pending',
            started_at=now,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        MigratedOperation.objects.create(
            order_id=order.pk,
            sequence=60,
            operation='Novo skipped sem justificativa',
            status='skipped',
            recorded_by_id=actor.pk,
            notes='   ',
        )

    executor.loader.build_graph()
    executor.migrate(old_targets)
    reversed_apps = executor.loader.project_state(old_targets).apps
    ReversedOperation = reversed_apps.get_model(
        'production',
        'ProductionOperationExecution',
    )
    legacy = ReversedOperation.objects.create(
        order_id=order.pk,
        sequence=70,
        operation='Legado permitido após reversão',
        status='skipped',
        recorded_by_id=actor.pk,
        notes='   ',
    )
    assert ReversedOperation.objects.filter(pk=legacy.pk).exists()
