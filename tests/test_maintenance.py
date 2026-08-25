from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from inventory.models import StockLot, StockQualityStatus
from masters.models import Product, UnitOfMeasure


User = get_user_model()


def create_maintenance_context(suffix='001'):
    unit = UnitOfMeasure.objects.create(code=f'UN-MAN-{suffix}', name='Unidade', symbol='un')
    product = Product.objects.create(
        code=f'MAN-PROD-{suffix}',
        description=f'Produto Manutencao {suffix}',
        item_type=Product.ItemType.FINISHED_PRODUCT,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    lot = StockLot.objects.create(
        product=product,
        lot_number=f'MAN-LOTE-{suffix}',
        quality_status=StockQualityStatus.APPROVED,
        expiry_date=timezone.localdate() + timedelta(days=365),
    )
    return product, lot


class MaintenanceModelTests(TestCase):
    def test_rf23_blocks_unavailable_assets_and_controls_calibration_order_lifecycle(self):
        from maintenance.models import EquipmentAsset, MaintenanceOrder, MaintenancePlan

        owner = User.objects.create_user(
            username='man.owner@example.com',
            email='man.owner@example.com',
            password='S3curePass!123',
        )
        _product, lot = create_maintenance_context()
        asset = EquipmentAsset.objects.create(
            asset_code='EQP-HPLC-001',
            name='HPLC laboratorio CQ',
            asset_type=EquipmentAsset.AssetType.INSTRUMENT,
            area='Controle de Qualidade',
            location='Laboratorio FQ',
            status=EquipmentAsset.Status.AVAILABLE,
            qualification_status=EquipmentAsset.QualificationStatus.QUALIFIED,
            qualification_valid_until=timezone.localdate() + timedelta(days=120),
            calibration_required=True,
            calibration_status=EquipmentAsset.CalibrationStatus.EXPIRED,
            calibration_valid_until=timezone.localdate() - timedelta(days=1),
            responsible=owner,
        )

        with pytest.raises(ValidationError) as unavailable:
            asset.release(user=owner)

        plan = MaintenancePlan.objects.create(
            asset=asset,
            plan_type=MaintenancePlan.PlanType.CALIBRATION,
            trigger_type=MaintenancePlan.TriggerType.TIME,
            interval_days=180,
            next_due_date=timezone.localdate(),
            description='Calibracao semestral do HPLC.',
            responsible=owner,
        )
        order = plan.generate_order(triggered_by=owner)

        order.start(user=owner)
        asset.refresh_from_db()

        with pytest.raises(ValidationError) as incomplete_completion:
            order.complete(
                summary='Calibracao executada.', evidence_reference='', content_hash='', user=owner
            )

        order.complete(
            summary='Calibracao executada conforme POP vigente.',
            evidence_reference='maintenance/hplc/calibracao-2026.pdf',
            content_hash='sha256:calibracao-hplc-2026',
            user=owner,
        )
        asset.refresh_from_db()
        order.refresh_from_db()

        lot_plan = MaintenancePlan.objects.create(
            asset=asset,
            plan_type=MaintenancePlan.PlanType.PREVENTIVE_MAINTENANCE,
            trigger_type=MaintenancePlan.TriggerType.LOT,
            description='Inspecao preventiva por lote critico.',
            responsible=owner,
        )
        lot_order = lot_plan.generate_order(triggered_by=owner, source_lot=lot)

        assert 'calibration_status' in unavailable.value.message_dict
        assert 'evidence_reference' in incomplete_completion.value.message_dict
        assert order.status == MaintenanceOrder.Status.COMPLETED
        assert asset.status == EquipmentAsset.Status.AVAILABLE
        assert asset.calibration_status == EquipmentAsset.CalibrationStatus.VALID
        assert asset.calibration_valid_until == timezone.localdate() + timedelta(days=180)
        assert asset.is_available_for_use is True
        assert lot_order.source_lot == lot
        assert lot_order.trigger_type == MaintenancePlan.TriggerType.LOT

    def test_rf23_supports_required_asset_types_triggers_and_metric_indicators(self):
        from maintenance.models import (
            EquipmentAsset,
            EquipmentDowntime,
            MaintenanceMetricReport,
            MaintenanceOrder,
            MaintenancePlan,
        )

        owner = User.objects.create_user(
            username='man.metrics@example.com',
            email='man.metrics@example.com',
            password='S3curePass!123',
        )
        asset = EquipmentAsset.objects.create(
            asset_code='LIN-SOL-001',
            name='Linha solidos 1',
            asset_type=EquipmentAsset.AssetType.PRODUCTION_LINE,
            area='Producao',
            location='Sala de compressao',
            status=EquipmentAsset.Status.AVAILABLE,
            qualification_status=EquipmentAsset.QualificationStatus.QUALIFIED,
            qualification_valid_until=timezone.localdate() + timedelta(days=365),
            calibration_required=False,
            responsible=owner,
        )
        started_at = timezone.now() - timedelta(hours=4)
        ended_at = timezone.now() - timedelta(hours=2)
        EquipmentDowntime.objects.create(
            asset=asset,
            downtime_type=EquipmentDowntime.DowntimeType.UNPLANNED,
            started_at=started_at,
            ended_at=ended_at,
            reason='Parada por falha mecanica.',
        )
        MaintenanceOrder.objects.create(
            asset=asset,
            order_type=MaintenanceOrder.OrderType.PREVENTIVE_MAINTENANCE,
            trigger_type=MaintenancePlan.TriggerType.TIME,
            due_date=timezone.localdate() - timedelta(days=1),
            description='Ordem preventiva vencida.',
            responsible=owner,
        )
        report = MaintenanceMetricReport.objects.create(
            asset=asset,
            report_type=MaintenanceMetricReport.ReportType.AVAILABILITY,
            title='Indicadores linha solidos',
            period_start=timezone.now() - timedelta(days=1),
            period_end=timezone.now(),
        )
        report.generate(user=owner, content_reference='maintenance/reports/linha-solidos.pdf')

        assert {
            EquipmentAsset.AssetType.EQUIPMENT,
            EquipmentAsset.AssetType.INSTRUMENT,
            EquipmentAsset.AssetType.PRODUCTION_LINE,
            EquipmentAsset.AssetType.ROOM,
            EquipmentAsset.AssetType.UTILITY,
            EquipmentAsset.AssetType.CRITICAL_COMPONENT,
        }.issubset(set(EquipmentAsset.AssetType.values))
        assert {
            MaintenancePlan.TriggerType.TIME,
            MaintenancePlan.TriggerType.USAGE,
            MaintenancePlan.TriggerType.EVENT,
            MaintenancePlan.TriggerType.LOT,
            MaintenancePlan.TriggerType.RULE,
        }.issubset(set(MaintenancePlan.TriggerType.values))
        assert report.status == MaintenanceMetricReport.Status.GENERATED
        assert report.downtime_hours == Decimal('2.00')
        assert report.mttr_hours == Decimal('2.00')
        assert report.mtbf_hours > Decimal('0.00')
        assert report.availability_rate < Decimal('100.00')
        assert report.overdue_orders == 1
        assert report.content_reference == 'maintenance/reports/linha-solidos.pdf'


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestMaintenanceApi:
    def test_maintenance_api_uses_global_scope_and_executes_required_workflow(self):
        from maintenance.models import (
            EquipmentAsset,
            EquipmentDowntime,
            MaintenanceMetricReport,
            MaintenanceOrder,
            MaintenancePlan,
        )

        owner = User.objects.create_user(
            username='api.man.owner@example.com',
            email='api.man.owner@example.com',
            password='S3curePass!123',
        )
        other_owner = User.objects.create_user(
            username='api.man.other@example.com',
            email='api.man.other@example.com',
            password='S3curePass!123',
        )
        _product, lot = create_maintenance_context()
        other_asset = EquipmentAsset.objects.create(
            asset_code='EQP-OUTRO-001',
            name='Equipamento secundario',
            asset_type=EquipmentAsset.AssetType.EQUIPMENT,
            status=EquipmentAsset.Status.AVAILABLE,
            qualification_status=EquipmentAsset.QualificationStatus.QUALIFIED,
            qualification_valid_until=timezone.localdate() + timedelta(days=365),
            responsible=other_owner,
        )
        client = APIClient()
        client.force_authenticate(owner)

        asset_response = client.post(
            '/api/maintenance/assets/',
            {
                'asset_code': 'BAL-API-001',
                'name': 'Balanca analitica API',
                'asset_type': EquipmentAsset.AssetType.INSTRUMENT,
                'area': 'Controle de Qualidade',
                'location': 'Sala de pesagem',
                'status': EquipmentAsset.Status.AVAILABLE,
                'qualification_status': EquipmentAsset.QualificationStatus.QUALIFIED,
                'qualification_valid_until': str(timezone.localdate() + timedelta(days=365)),
                'calibration_required': True,
                'calibration_status': EquipmentAsset.CalibrationStatus.EXPIRED,
                'calibration_valid_until': str(timezone.localdate() - timedelta(days=1)),
                'responsible': owner.id,
            },
        )
        asset_id = asset_response.json()['id']
        invalid_plan_response = client.post(
            '/api/maintenance/plans/',
            {
                'asset': other_asset.id,
                'plan_type': MaintenancePlan.PlanType.CALIBRATION,
                'trigger_type': MaintenancePlan.TriggerType.TIME,
                'interval_days': 180,
                'next_due_date': str(timezone.localdate()),
                'description': 'Plano de equipamento secundario.',
                'responsible': owner.id,
            },
        )
        plan_response = client.post(
            '/api/maintenance/plans/',
            {
                'asset': asset_id,
                'plan_type': MaintenancePlan.PlanType.CALIBRATION,
                'trigger_type': MaintenancePlan.TriggerType.TIME,
                'interval_days': 180,
                'next_due_date': str(timezone.localdate()),
                'description': 'Calibracao semestral por API.',
                'responsible': owner.id,
            },
        )
        plan_id = plan_response.json()['id']
        order_response = client.post(
            f'/api/maintenance/plans/{plan_id}/generate_order/',
            {'source_lot': lot.id},
        )
        order_id = order_response.json()['id']
        start_response = client.post(f'/api/maintenance/orders/{order_id}/start/')
        complete_response = client.post(
            f'/api/maintenance/orders/{order_id}/complete/',
            {
                'summary': 'Calibracao API concluida.',
                'evidence_reference': 'maintenance/api/balanca.pdf',
                'content_hash': 'sha256:api-balanca',
            },
        )
        downtime_response = client.post(
            '/api/maintenance/downtimes/',
            {
                'asset': asset_id,
                'order': order_id,
                'downtime_type': EquipmentDowntime.DowntimeType.CALIBRATION,
                'started_at': (timezone.now() - timedelta(hours=1)).isoformat(),
                'reason': 'Parada para calibracao.',
            },
        )
        downtime_id = downtime_response.json()['id']
        close_downtime_response = client.post(
            f'/api/maintenance/downtimes/{downtime_id}/close/',
            {'ended_at': timezone.now().isoformat()},
        )
        usage_response = client.post(
            '/api/maintenance/usage-logs/',
            {
                'asset': asset_id,
                'source_lot': lot.id,
                'used_at': timezone.now().isoformat(),
                'usage_quantity': '1.0000',
                'usage_unit': 'lote',
                'event_reference': 'OP-API-001',
            },
        )
        report_response = client.post(
            '/api/maintenance/reports/',
            {
                'asset': asset_id,
                'report_type': MaintenanceMetricReport.ReportType.AVAILABILITY,
                'title': 'Indicadores de manutencao API',
                'period_start': (timezone.now() - timedelta(days=1)).isoformat(),
                'period_end': timezone.now().isoformat(),
            },
        )
        report_id = report_response.json()['id']
        generate_report_response = client.post(
            f'/api/maintenance/reports/{report_id}/generate/',
            {'content_reference': 'maintenance/api/indicadores.pdf'},
        )
        list_response = client.get('/api/maintenance/assets/')

        assert asset_response.status_code == 201
        assert invalid_plan_response.status_code == 201
        assert plan_response.status_code == 201
        assert order_response.status_code == 200
        assert start_response.status_code == 200
        assert complete_response.status_code == 200
        assert downtime_response.status_code == 201
        assert close_downtime_response.status_code == 200
        assert usage_response.status_code == 201
        assert report_response.status_code == 201
        assert generate_report_response.status_code == 200
        assert list_response.status_code == 200
        assert list_response.json()['count'] == 2
        assert MaintenanceOrder.objects.get(id=order_id).status == MaintenanceOrder.Status.COMPLETED
        assert (
            EquipmentAsset.objects.get(id=asset_id).calibration_status
            == EquipmentAsset.CalibrationStatus.VALID
        )
