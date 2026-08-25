from decimal import Decimal

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.test.client import RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient

from formulations.models import FormulaComponent, ManufacturingRoute, MasterFormula, RouteStep
from masters.models import Product, UnitOfMeasure


User = get_user_model()


def create_released_manufacturing_set(suffix='001'):
    today = timezone.localdate()
    unit = UnitOfMeasure.objects.create(
        code=f'KG-{suffix}',
        name='Quilograma',
        symbol='kg',
    )
    product = Product.objects.create(
        code=f'PA-{suffix}',
        description='Comprimido 500mg',
        item_type=Product.ItemType.FINISHED_PRODUCT,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    material = Product.objects.create(
        code=f'MP-{suffix}',
        description='Celulose microcristalina',
        item_type=Product.ItemType.EXCIPIENT,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    formula = MasterFormula.objects.create(
        product=product,
        code=f'F-PA-{suffix}',
        version=1,
        status=MasterFormula.Status.APPROVED,
        batch_size=Decimal('100.0000'),
        batch_unit=unit,
        effective_from=today,
    )
    component = FormulaComponent.objects.create(
        formula=formula,
        line_number=10,
        material=material,
        quantity=Decimal('10.0000'),
        unit=unit,
    )
    route = ManufacturingRoute.objects.create(
        product=product,
        formula=formula,
        code=f'R-PA-{suffix}',
        version=1,
        status=ManufacturingRoute.Status.APPROVED,
        effective_from=today,
    )
    RouteStep.objects.create(
        route=route,
        sequence=10,
        operation='Pesagem',
        work_center='Sala de pesagem',
        standard_time_minutes=Decimal('30.00'),
    )
    return unit, product, material, formula, component, route


def create_production_order(suffix='001'):
    from production.models import ProductionOrder

    unit, product, _material, formula, _component, route = create_released_manufacturing_set(
        suffix=suffix
    )
    return ProductionOrder.objects.create(
        order_number=f'OP-{suffix}',
        product=product,
        formula=formula,
        route=route,
        planned_quantity=Decimal('100.0000'),
        unit=unit,
    )


class CostingModelTests(TestCase):
    def _draft_standard_cost(self, suffix='STATE'):
        from costing.models import StandardCost

        unit, product, _material, _formula, _component, _route = create_released_manufacturing_set(
            suffix=suffix
        )
        return StandardCost.objects.create(
            product=product,
            version=f'VER-{suffix}',
            effective_from=timezone.localdate(),
            standard_quantity=Decimal('100.0000'),
            unit=unit,
            material_cost=Decimal('10.0000'),
        )

    def _approval_user(self, suffix='STATE'):
        return User.objects.create_user(
            username=f'controller-{suffix}@example.com',
            email=f'controller-{suffix}@example.com',
            password='S3curePass!123',
        )

    def test_standard_cost_full_clean_requires_approval_timestamp(self):
        from costing.models import StandardCost

        unit, product, _material, _formula, _component, _route = create_released_manufacturing_set()
        standard = StandardCost(
            product=product,
            version='SEM-DATA-APROVACAO',
            status=StandardCost.Status.APPROVED,
            effective_from=timezone.localdate(),
            standard_quantity=Decimal('100.0000'),
            unit=unit,
        )

        with pytest.raises(ValidationError) as error:
            standard.full_clean()

        assert 'approved_at' in error.value.message_dict

    def test_standard_cost_database_rejects_approved_status_without_timestamp(self):
        from costing.models import StandardCost

        unit, product, _material, _formula, _component, _route = create_released_manufacturing_set()

        with pytest.raises(IntegrityError), transaction.atomic():
            StandardCost.objects.create(
                product=product,
                version='SEM-DATA-NO-BANCO',
                status=StandardCost.Status.APPROVED,
                approved_at=timezone.now(),
                effective_from=timezone.localdate(),
                standard_quantity=Decimal('100.0000'),
                unit=unit,
            )

    def test_standard_cost_rejects_reapproval_and_preserves_approval_evidence(self):
        standard = self._draft_standard_cost()
        approver = self._approval_user()
        replacement_approver = self._approval_user(suffix='REPLACEMENT')
        standard.approve(user=approver)
        standard.refresh_from_db()
        original_approved_at = standard.approved_at

        with pytest.raises(ValidationError) as error:
            standard.approve(user=replacement_approver)

        standard.refresh_from_db()
        assert 'status' in error.value.message_dict
        assert standard.approved_by == approver
        assert standard.approved_at == original_approved_at

    def test_standard_cost_rejects_draft_to_obsolete(self):
        standard = self._draft_standard_cost()

        with pytest.raises(ValidationError) as error:
            standard.obsolete()

        standard.refresh_from_db()
        assert 'status' in error.value.message_dict
        assert standard.status == standard.Status.DRAFT
        assert standard.approved_by is None
        assert standard.approved_at is None

    def test_standard_cost_obsolete_preserves_evidence_and_cannot_be_reapproved(self):
        standard = self._draft_standard_cost()
        approver = self._approval_user()
        standard.approve(user=approver)
        standard.refresh_from_db()
        original_approved_at = standard.approved_at

        standard.obsolete()

        standard.refresh_from_db()
        assert standard.status == standard.Status.OBSOLETE
        assert standard.approved_by == approver
        assert standard.approved_at == original_approved_at

        with pytest.raises(ValidationError) as error:
            standard.approve(user=approver)

        assert 'status' in error.value.message_dict

    def test_standard_cost_clean_rejects_invalid_persisted_transition(self):
        standard = self._draft_standard_cost()
        standard.status = standard.Status.OBSOLETE

        with pytest.raises(ValidationError) as error:
            standard.full_clean()

        assert 'status' in error.value.message_dict

    def test_standard_cost_queryset_update_cannot_bypass_state_machine(self):
        standard = self._draft_standard_cost()

        with pytest.raises(IntegrityError), transaction.atomic():
            type(standard).objects.filter(pk=standard.pk).update(status=standard.Status.OBSOLETE)

        standard.refresh_from_db()
        assert standard.status == standard.Status.DRAFT

    def test_standard_cost_save_cannot_bypass_state_machine(self):
        standard = self._draft_standard_cost()
        standard.status = standard.Status.OBSOLETE

        with pytest.raises(IntegrityError), transaction.atomic():
            standard.save(update_fields=['status', 'updated_at'])

        standard.refresh_from_db()
        assert standard.status == standard.Status.DRAFT

    def test_standard_cost_bulk_update_cannot_bypass_state_machine(self):
        standard = self._draft_standard_cost()
        standard.status = standard.Status.OBSOLETE

        with pytest.raises(IntegrityError), transaction.atomic():
            type(standard).objects.bulk_update([standard], ['status'])

        standard.refresh_from_db()
        assert standard.status == standard.Status.DRAFT

    def test_standard_cost_raw_sql_cannot_bypass_state_machine(self):
        standard = self._draft_standard_cost()

        with pytest.raises(IntegrityError), transaction.atomic():
            with transaction.get_connection().cursor() as cursor:
                cursor.execute(
                    'UPDATE costing_standardcost SET status = %s WHERE id = %s',
                    [standard.Status.OBSOLETE, standard.pk],
                )

        standard.refresh_from_db()
        assert standard.status == standard.Status.DRAFT

    def test_standard_cost_status_neutral_update_preserves_approval_evidence(self):
        standard = self._draft_standard_cost()
        approver = self._approval_user()
        standard.approve(user=approver)
        standard.refresh_from_db()
        original_approved_at = standard.approved_at

        type(standard).objects.filter(pk=standard.pk).update(notes='Nota permitida.')

        with pytest.raises(IntegrityError), transaction.atomic():
            type(standard).objects.filter(pk=standard.pk).update(
                approved_at=timezone.now(),
            )

        standard.refresh_from_db()
        assert standard.notes == 'Nota permitida.'
        assert standard.approved_by == approver
        assert standard.approved_at == original_approved_at

    def test_standard_cost_recalculates_components_and_approval_audit(self):
        from costing.models import StandardCost

        unit, product, _material, _formula, _component, _route = create_released_manufacturing_set()
        standard = StandardCost.objects.create(
            product=product,
            version='2026.01',
            effective_from=timezone.localdate(),
            standard_quantity=Decimal('100.0000'),
            unit=unit,
            material_cost=Decimal('100.0000'),
            loss_cost=Decimal('5.0000'),
            labor_cost=Decimal('20.0000'),
            machine_cost=Decimal('10.0000'),
            third_party_cost=Decimal('8.0000'),
            analysis_cost=Decimal('3.0000'),
            overhead_cost=Decimal('7.0000'),
            indirect_cost=Decimal('2.0000'),
            tax_cost=Decimal('9.0000'),
        )
        user = User.objects.create_user(
            username='custos@example.com', email='custos@example.com', password='S3curePass!123'
        )

        standard.recalculate()
        standard.approve(user=user)
        standard.refresh_from_db()

        assert standard.total_standard_cost == Decimal('164.0000')
        assert standard.status == StandardCost.Status.APPROVED
        assert standard.approved_by == user
        assert standard.approved_at is not None

    def test_cost_simulation_calculates_total_unit_cost_from_yield_rates_and_capacity(self):
        from costing.models import CostSimulation

        _unit, product, _material, formula, _component, _route = create_released_manufacturing_set()
        simulation = CostSimulation.objects.create(
            product=product,
            formula=formula,
            name='Simulação lote comercial',
            batch_size=Decimal('100.0000'),
            expected_yield_percent=Decimal('90.0000'),
            material_cost=Decimal('1000.0000'),
            loss_percent=Decimal('10.0000'),
            labor_hours=Decimal('5.0000'),
            labor_rate=Decimal('20.0000'),
            machine_hours=Decimal('2.0000'),
            machine_rate=Decimal('50.0000'),
            third_party_cost=Decimal('80.0000'),
            analysis_cost=Decimal('20.0000'),
            overhead_rate_percent=Decimal('10.0000'),
            indirect_cost=Decimal('50.0000'),
            tax_rate_percent=Decimal('5.0000'),
            capacity_factor_percent=Decimal('100.0000'),
        )

        simulation.calculate()

        assert simulation.simulated_total_cost == Decimal('1674.7500')
        assert simulation.simulated_unit_cost == Decimal('18.6083')

    def test_production_cost_capture_calculates_actual_variance_and_non_quality_costs(self):
        from costing.models import ProductionCostCapture

        order = create_production_order()
        capture = ProductionCostCapture.objects.create(
            production_order=order,
            period_start=timezone.localdate().replace(day=1),
            period_end=timezone.localdate().replace(day=28),
            planned_cost=Decimal('500.0000'),
            actual_material_cost=Decimal('200.0000'),
            actual_loss_cost=Decimal('25.0000'),
            actual_labor_cost=Decimal('100.0000'),
            actual_machine_cost=Decimal('80.0000'),
            actual_third_party_cost=Decimal('40.0000'),
            actual_analysis_cost=Decimal('10.0000'),
            actual_overhead_cost=Decimal('50.0000'),
            actual_indirect_cost=Decimal('20.0000'),
            non_quality_cost=Decimal('30.0000'),
            rework_cost=Decimal('20.0000'),
        )

        capture.calculate_actuals()

        assert capture.total_actual_cost == Decimal('575.0000')
        assert capture.variance_amount == Decimal('75.0000')

    def test_monthly_cost_closing_requires_validation_before_closing_and_records_audit(self):
        from costing.models import MonthlyCostClosing

        user = User.objects.create_user(
            username='controller@example.com',
            email='controller@example.com',
            password='S3curePass!123',
        )
        closing = MonthlyCostClosing.objects.create(period_year=2026, period_month=7)

        with pytest.raises(ValidationError) as error:
            closing.close(user=user)

        assert 'status' in error.value.message_dict

        closing.validate_period(notes='Capturas de custo conciliadas.')
        closing.close(user=user)

        assert closing.status == MonthlyCostClosing.Status.CLOSED
        assert closing.closed_by == user
        assert closing.closed_at is not None
        assert closing.validation_notes == 'Capturas de custo conciliadas.'

    def test_cost_report_snapshot_calculates_margin_and_percent(self):
        from costing.models import CostReportSnapshot

        _unit, product, _material, _formula, _component, _route = (
            create_released_manufacturing_set()
        )
        snapshot = CostReportSnapshot.objects.create(
            report_type=CostReportSnapshot.ReportType.MARGIN,
            product=product,
            period_start=timezone.localdate().replace(day=1),
            period_end=timezone.localdate().replace(day=28),
            revenue_amount=Decimal('1000.0000'),
            cost_amount=Decimal('700.0000'),
        )

        snapshot.calculate_margin()

        assert snapshot.margin_amount == Decimal('300.0000')
        assert snapshot.margin_percent == Decimal('30.0000')


def test_standard_cost_admin_form_does_not_expose_approval_fields():
    from costing.admin import StandardCostAdmin
    from costing.models import StandardCost

    model_admin = StandardCostAdmin(StandardCost, admin.site)
    request = RequestFactory().get('/admin/costing/standardcost/add/')
    request.user = AnonymousUser()
    form_class = model_admin.get_form(request)

    assert {'status', 'approved_by', 'approved_at'}.isdisjoint(form_class.base_fields)
    assert 'approved_by' not in model_admin.autocomplete_fields


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestCostingApi:
    def test_standard_cost_api_approves_and_validates_related_objects(self):
        from costing.models import StandardCost

        unit, product, _material, _formula, _component, _route = create_released_manufacturing_set()
        standard = StandardCost.objects.create(
            product=product,
            version='2026.01',
            effective_from=timezone.localdate(),
            standard_quantity=Decimal('100.0000'),
            unit=unit,
            material_cost=Decimal('100.0000'),
            labor_cost=Decimal('20.0000'),
        )
        user = User.objects.create_user(
            username='controller@example.com',
            email='controller@example.com',
            password='S3curePass!123',
        )
        client = APIClient()
        client.force_authenticate(user)
        direct_approval_timestamp = timezone.now()

        invalid_response = client.post(
            '/api/costing/standard-costs/',
            {
                'product': product.id,
                'version': '2026.02',
                'effective_from': str(timezone.localdate()),
                'standard_quantity': '100.0000',
                'unit': unit.id,
                'status': StandardCost.Status.APPROVED,
                'approved_by': user.id,
                'approved_at': direct_approval_timestamp.isoformat(),
            },
        )
        directly_created = StandardCost.objects.get(version='2026.02')
        direct_update_response = client.patch(
            f'/api/costing/standard-costs/{standard.id}/',
            {
                'status': StandardCost.Status.APPROVED,
                'approved_by': user.id,
                'approved_at': direct_approval_timestamp.isoformat(),
            },
        )
        standard.refresh_from_db()
        approve_response = client.post(
            f'/api/costing/standard-costs/{standard.id}/approve/',
        )
        repeated_approve_response = client.post(
            f'/api/costing/standard-costs/{standard.id}/approve/',
        )
        obsolete_response = client.post(
            f'/api/costing/standard-costs/{standard.id}/obsolete/',
        )
        repeated_obsolete_response = client.post(
            f'/api/costing/standard-costs/{standard.id}/obsolete/',
        )
        obsolete_approve_response = client.post(
            f'/api/costing/standard-costs/{standard.id}/approve/',
        )

        assert invalid_response.status_code == 201
        assert directly_created.status == StandardCost.Status.DRAFT
        assert directly_created.approved_by is None
        assert directly_created.approved_at is None
        assert direct_update_response.status_code == 400
        assert standard.status == StandardCost.Status.DRAFT
        assert standard.approved_by is None
        assert standard.approved_at is None
        assert approve_response.status_code == 200
        assert approve_response.json()['status'] == StandardCost.Status.APPROVED
        assert approve_response.json()['total_standard_cost'] == '120.0000'
        assert repeated_approve_response.status_code == 400
        assert obsolete_response.status_code == 200
        assert obsolete_response.json()['status'] == StandardCost.Status.OBSOLETE
        assert repeated_obsolete_response.status_code == 400
        assert obsolete_approve_response.status_code == 400
