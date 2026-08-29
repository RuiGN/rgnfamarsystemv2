from datetime import date

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from integrations.models import IntegrationConnector
from planning.models import CapacityResource
from procurement.models import PurchaseRequisition
from risks.models import RiskLink


def test_active_choices_no_longer_offer_equipment_or_maintenance():
    assert 'equipment' not in IntegrationConnector.ProviderType.values
    assert 'equipment' not in CapacityResource.ResourceType.values
    assert 'equipment' not in RiskLink.LinkType.values
    assert 'maintenance' not in PurchaseRequisition.Source.values


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
        # These migrations only alter TextChoices at schema level. Mark them
        # unapplied for test setup without reversing their intentionally
        # irreversible data cleanup, then exercise the real forward migration.
        executor.migrate(self.migrate_from, fake=True)
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
            code='LEGACY-EQP',
            name='Legacy',
            resource_type='equipment',
            daily_capacity_minutes='480.00',
        )
        Load.objects.create(
            resource=resource,
            period_date=date(2026, 8, 29),
            required_minutes='60.00',
            available_minutes='480.00',
        )

        Requisition = old_apps.get_model('procurement', 'PurchaseRequisition')
        self.requisition_pk = Requisition.objects.create(
            requisition_number='REQ-LEGACY',
            source='maintenance',
            justification='Registro transacional preservado.',
        ).pk

        Risk = old_apps.get_model('risks', 'RiskRecord')
        Link = old_apps.get_model('risks', 'RiskLink')
        risk = Risk.objects.create(
            risk_number='RISK-LEGACY',
            risk_category='operations',
            title='Legacy',
            description='Legacy',
            process_area='Operações',
            owner=owner,
            due_date=date(2026, 12, 1),
            next_review_date=date(2026, 12, 1),
        )
        self.risk_pk = risk.pk
        Link.objects.create(
            risk=risk,
            link_type='equipment',
            reference_code='EQP-01',
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
