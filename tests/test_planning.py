from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from masters.models import Product, UnitOfMeasure


User = get_user_model()


def create_planning_product(suffix='001', item_type=Product.ItemType.FINISHED_PRODUCT):
    unit = UnitOfMeasure.objects.create(
        code=f'UN-{suffix}',
        name='Unidade',
        symbol='un',
    )
    product = Product.objects.create(
        code=f'PA-{suffix}',
        description='Produto planejável',
        item_type=item_type,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    return unit, product


class PlanningModelTests(TestCase):
    def test_planning_policy_rounds_requirement_to_minimum_and_multiple(self):
        from planning.models import PlanningPolicy

        _unit, product = create_planning_product()
        policy = PlanningPolicy.objects.create(
            product=product,
            preferred_source=PlanningPolicy.Source.PRODUCE,
            safety_stock_quantity=Decimal('10.0000'),
            minimum_order_quantity=Decimal('50.0000'),
            order_multiple=Decimal('25.0000'),
            lead_time_days=7,
        )

        assert policy.round_requirement(Decimal('30.0000')) == Decimal('50.0000')
        assert policy.round_requirement(Decimal('60.0000')) == Decimal('75.0000')

    def test_mps_line_requires_due_date_inside_schedule(self):
        from planning.models import MPSLine, MasterProductionSchedule

        today = timezone.localdate()
        unit, product = create_planning_product()
        other_unit, _other_product = create_planning_product(suffix='999')
        schedule = MasterProductionSchedule.objects.create(
            code='MPS-2026-07',
            name='Plano julho',
            period_start=today,
            period_end=today + timedelta(days=30),
        )

        out_of_period = MPSLine(
            schedule=schedule,
            product=product,
            due_date=today + timedelta(days=31),
            demand_quantity=Decimal('10.0000'),
            unit=unit,
            source=MPSLine.Source.FORECAST,
        )
        with pytest.raises(ValidationError) as date_error:
            out_of_period.full_clean()
        assert 'due_date' in date_error.value.message_dict

        alternate_unit = MPSLine(
            schedule=schedule,
            product=product,
            due_date=today + timedelta(days=10),
            demand_quantity=Decimal('10.0000'),
            unit=other_unit,
            source=MPSLine.Source.FORECAST,
        )
        alternate_unit.full_clean()

    def test_mrp_run_calculates_net_requirement_and_suggestion(self):
        from planning.models import (
            InventoryPosition,
            MPSLine,
            MRPRun,
            MRPSuggestion,
            MasterProductionSchedule,
            PlanningPolicy,
        )

        today = timezone.localdate()
        unit, product = create_planning_product()
        schedule = MasterProductionSchedule.objects.create(
            code='MPS-2026-07',
            name='Plano julho',
            period_start=today,
            period_end=today + timedelta(days=30),
        )
        due_date = today + timedelta(days=10)
        MPSLine.objects.create(
            schedule=schedule,
            product=product,
            due_date=due_date,
            demand_quantity=Decimal('120.0000'),
            unit=unit,
            source=MPSLine.Source.FORECAST,
        )
        PlanningPolicy.objects.create(
            product=product,
            preferred_source=PlanningPolicy.Source.PRODUCE,
            safety_stock_quantity=Decimal('10.0000'),
            minimum_order_quantity=Decimal('50.0000'),
            order_multiple=Decimal('25.0000'),
            lead_time_days=7,
        )
        InventoryPosition.objects.create(
            product=product,
            unit=unit,
            on_hand_quantity=Decimal('40.0000'),
            quarantine_quantity=Decimal('10.0000'),
            reserved_quantity=Decimal('5.0000'),
            incoming_purchase_quantity=Decimal('20.0000'),
            incoming_production_quantity=Decimal('0.0000'),
        )
        run = MRPRun.objects.create(schedule=schedule)

        run.calculate()
        run.refresh_from_db()
        suggestion = run.suggestions.get()

        assert run.status == MRPRun.Status.CALCULATED
        assert suggestion.suggestion_type == MRPSuggestion.SuggestionType.PRODUCE
        assert suggestion.required_quantity == Decimal('120.0000')
        assert suggestion.available_quantity == Decimal('45.0000')
        assert suggestion.net_requirement == Decimal('85.0000')
        assert suggestion.suggested_quantity == Decimal('100.0000')
        assert suggestion.release_date == due_date - timedelta(days=7)
        assert suggestion.alert_level == MRPSuggestion.AlertLevel.SHORTAGE

    def test_mrp_run_flags_stock_expiring_before_demand(self):
        from planning.models import (
            InventoryPosition,
            MPSLine,
            MRPRun,
            MRPSuggestion,
            MasterProductionSchedule,
        )

        today = timezone.localdate()
        unit, product = create_planning_product()
        schedule = MasterProductionSchedule.objects.create(
            code='MPS-2026-08',
            name='Plano agosto',
            period_start=today,
            period_end=today + timedelta(days=30),
        )
        MPSLine.objects.create(
            schedule=schedule,
            product=product,
            due_date=today + timedelta(days=20),
            demand_quantity=Decimal('50.0000'),
            unit=unit,
            source=MPSLine.Source.FORECAST,
        )
        InventoryPosition.objects.create(
            product=product,
            unit=unit,
            on_hand_quantity=Decimal('200.0000'),
            quarantine_quantity=Decimal('0.0000'),
            reserved_quantity=Decimal('0.0000'),
            expiry_date=today + timedelta(days=3),
        )
        run = MRPRun.objects.create(schedule=schedule)

        run.calculate()

        suggestion = run.suggestions.get()
        assert suggestion.net_requirement == Decimal('0.0000')
        assert suggestion.suggested_quantity == Decimal('0.0000')
        assert suggestion.alert_level == MRPSuggestion.AlertLevel.EXPIRING

    def test_capacity_load_identifies_bottleneck(self):
        from planning.models import CapacityLoad, CapacityResource

        resource = CapacityResource.objects.create(
            code='LIN-001',
            name='Linha sólidos 1',
            resource_type=CapacityResource.ResourceType.LINE,
            work_center='Compressao',
            daily_capacity_minutes=Decimal('480.00'),
        )
        load = CapacityLoad.objects.create(
            resource=resource,
            period_date=timezone.localdate(),
            required_minutes=Decimal('600.00'),
            available_minutes=Decimal('480.00'),
        )

        assert load.is_overloaded is True
        assert load.overload_minutes == Decimal('120.00')


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestPlanningApi:
    def test_mrp_run_api_calculates_suggestions_in_global_scope(self):
        from planning.models import (
            InventoryPosition,
            MPSLine,
            MRPRun,
            MasterProductionSchedule,
            PlanningPolicy,
        )

        today = timezone.localdate()
        unit, product = create_planning_product()
        schedule = MasterProductionSchedule.objects.create(
            code='MPS-2026-07',
            name='Plano julho',
            period_start=today,
            period_end=today + timedelta(days=30),
        )
        MPSLine.objects.create(
            schedule=schedule,
            product=product,
            due_date=today + timedelta(days=10),
            demand_quantity=Decimal('120.0000'),
            unit=unit,
            source=MPSLine.Source.FORECAST,
        )
        PlanningPolicy.objects.create(
            product=product,
            preferred_source=PlanningPolicy.Source.BUY,
            safety_stock_quantity=Decimal('10.0000'),
            minimum_order_quantity=Decimal('50.0000'),
            order_multiple=Decimal('25.0000'),
            lead_time_days=7,
        )
        InventoryPosition.objects.create(
            product=product,
            unit=unit,
            on_hand_quantity=Decimal('40.0000'),
            quarantine_quantity=Decimal('10.0000'),
            reserved_quantity=Decimal('5.0000'),
            incoming_purchase_quantity=Decimal('20.0000'),
        )
        user = User.objects.create_user(
            username='pcp@example.com', email='pcp@example.com', password='S3curePass!123'
        )
        client = APIClient()
        client.force_authenticate(user)

        create_response = client.post(
            '/api/planning/mrp-runs/',
            {'schedule': schedule.id, 'notes': 'Simulacao RF-05'},
        )
        assert create_response.status_code == 201
        assert create_response.json()['status'] == MRPRun.Status.DRAFT

        calculate_response = client.post(
            f'/api/planning/mrp-runs/{create_response.json()["id"]}/calculate/',
            {},
        )
        assert calculate_response.status_code == 200
        assert calculate_response.json()['status'] == MRPRun.Status.CALCULATED

        suggestions_response = client.get('/api/planning/suggestions/')
        assert suggestions_response.status_code == 200
        suggestion = suggestions_response.json()['results'][0]
        assert suggestion['product'] == product.id
        assert suggestion['suggestion_type'] == PlanningPolicy.Source.BUY
        assert suggestion['suggested_quantity'] == '100.0000'

    @pytest.mark.permission_strict
    def test_planning_api_requires_view_permission(self):
        from planning.models import MasterProductionSchedule

        today = timezone.localdate()
        MasterProductionSchedule.objects.create(
            code='MPS-2026-07',
            name='Plano julho',
            period_start=today,
            period_end=today + timedelta(days=30),
        )
        user = User.objects.create_user(
            username='pcp@example.com', email='pcp@example.com', password='S3curePass!123'
        )
        client = APIClient()
        client.login(username=user.username, password='S3curePass!123')

        response = client.get('/api/planning/schedules/')

        assert response.status_code == 403
