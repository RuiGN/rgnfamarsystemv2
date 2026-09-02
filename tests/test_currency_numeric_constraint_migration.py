import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CurrencyNumericConstraintMigrationTests(TransactionTestCase):
    migrate_from = [('auxiliary', '0004_currency_minor_unit_applicable')]
    migrate_to = [('auxiliary', '0005_currency_unique_numeric_code')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        Currency = old_apps.get_model('auxiliary', 'Currency')
        Currency.objects.create(code='LEG-A', name='Legado A', numeric_code='986')
        Currency.objects.create(code='LEG-B', name='Legado B', numeric_code='986')

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        old_apps.get_model('auxiliary', 'Currency').objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_migration_aborts_with_clear_message_instead_of_merging_legacy_duplicates(self):
        executor = MigrationExecutor(connection)

        with pytest.raises(RuntimeError, match='numeric_code.*986'):
            executor.migrate(self.migrate_to)

        old_apps = MigrationExecutor(connection).loader.project_state(self.migrate_from).apps
        Currency = old_apps.get_model('auxiliary', 'Currency')
        assert list(Currency.objects.order_by('code').values_list('code', 'numeric_code')) == [
            ('LEG-A', '986'),
            ('LEG-B', '986'),
        ]
