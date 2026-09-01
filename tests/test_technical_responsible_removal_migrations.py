from datetime import date

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TechnicalResponsibleRemovalMigrationTests(TransactionTestCase):
    migrate_from = [('governance', '0002_alter_governanceauditlog_module_and_more')]
    migrate_to = [('governance', '0003_remove_technical_responsible')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        InstitutionSettings = old_apps.get_model('governance', 'InstitutionSettings')
        TechnicalResponsible = old_apps.get_model('governance', 'TechnicalResponsible')
        ContentType = old_apps.get_model('contenttypes', 'ContentType')
        Permission = old_apps.get_model('auth', 'Permission')

        institution = InstitutionSettings.objects.create(
            legal_name='Indústria de teste',
            document='12.345.678/0001-90',
        )
        TechnicalResponsible.objects.create(
            institution=institution,
            full_name='Registro legado',
            cpf='52998224725',
            council='CRF',
            council_registration_number='12345',
            start_date=date(2026, 1, 1),
        )
        content_type, _ = ContentType.objects.get_or_create(
            app_label='governance', model='technicalresponsible'
        )
        Permission.objects.get_or_create(
            content_type=content_type,
            codename='view_technicalresponsible',
            defaults={'name': 'Can view technical responsible'},
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_upgrade_removes_model_table_content_type_and_permissions(self):
        with pytest.raises(LookupError):
            self.apps.get_model('governance', 'TechnicalResponsible')

        tables = set(connection.introspection.table_names())
        ContentType = self.apps.get_model('contenttypes', 'ContentType')
        Permission = self.apps.get_model('auth', 'Permission')

        assert 'governance_technicalresponsible' not in tables
        assert not ContentType.objects.filter(
            app_label='governance', model='technicalresponsible'
        ).exists()
        assert not Permission.objects.filter(
            content_type__app_label='governance',
            content_type__model='technicalresponsible',
        ).exists()
