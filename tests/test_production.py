from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
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


class ProductionOrderModelTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username='production-model-actor',
            email='production-model-actor@example.com',
        )

    def test_order_generates_order_and_batch_numbers_and_releases_with_approved_formula_route(self):
        from production.models import ProductionOrder

        unit, product, _material, formula, _component, route = create_released_manufacturing_set()
        order = ProductionOrder.objects.create(
            product=product,
            formula=formula,
            route=route,
            planned_quantity=Decimal('100.0000'),
            unit=unit,
        )

        assert order.order_number.startswith(f'OP-{timezone.localdate():%Y%m%d}-')
        assert order.batch_number.startswith(f'LOT-{timezone.localdate():%Y%m%d}-')
        assert order.status == ProductionOrder.Status.DRAFT

        order.approve(user=self.actor)
        order.release(user=self.actor)

        assert order.status == ProductionOrder.Status.RELEASED
        assert order.released_at is not None

    def test_release_blocks_unreleased_formula_or_route(self):
        from production.models import ProductionOrder

        today = timezone.localdate()
        unit, product, _material, formula, _component, route = create_released_manufacturing_set()
        formula.status = MasterFormula.Status.DRAFT
        formula.save(update_fields=['status'])
        route.status = ManufacturingRoute.Status.DRAFT
        route.save(update_fields=['status'])
        order = ProductionOrder.objects.create(
            order_number='OP-0001',
            product=product,
            formula=formula,
            route=route,
            planned_quantity=Decimal('100.0000'),
            unit=unit,
            scheduled_start=today,
        )

        order.approve(user=self.actor)

        with pytest.raises(ValidationError) as error:
            order.release(user=self.actor)

        assert 'formula' in error.value.message_dict
        assert 'route' in error.value.message_dict

    def test_order_execution_lifecycle_requires_valid_transitions(self):
        from production.models import ProductionOrder

        unit, product, _material, formula, _component, route = create_released_manufacturing_set()
        order = ProductionOrder.objects.create(
            order_number='OP-0001',
            product=product,
            formula=formula,
            route=route,
            planned_quantity=Decimal('100.0000'),
            unit=unit,
        )

        with pytest.raises(ValidationError):
            order.start(user=self.actor)

        order.approve(user=self.actor)
        order.release(user=self.actor)
        order.start(user=self.actor)
        order.pause(user=self.actor)
        order.resume(user=self.actor)
        order.complete(actual_yield_quantity=Decimal('96.0000'), user=self.actor)

        assert order.status == ProductionOrder.Status.COMPLETED
        assert order.actual_yield_quantity == Decimal('96.0000')
        assert order.actual_end is not None

    def test_material_issue_blocks_non_approved_quality_and_expired_material(self):
        from production.models import MaterialConsumption, ProductionOrder

        unit, product, material, formula, component, route = create_released_manufacturing_set()
        order = ProductionOrder.objects.create(
            order_number='OP-0001',
            product=product,
            formula=formula,
            route=route,
            planned_quantity=Decimal('100.0000'),
            unit=unit,
        )
        order.approve(user=self.actor)
        order.release(user=self.actor)
        order.start(user=self.actor)

        valid_issue = MaterialConsumption.objects.create(
            order=order,
            component=component,
            material=material,
            planned_quantity=component.quantity,
            actual_quantity=Decimal('9.5000'),
            unit=unit,
            quality_status=MaterialConsumption.QualityStatus.APPROVED,
            expiry_date=timezone.localdate().replace(year=timezone.localdate().year + 1),
        )

        assert valid_issue.variance_quantity == Decimal('-0.5000')

        invalid_issue = MaterialConsumption(
            order=order,
            component=component,
            material=material,
            planned_quantity=component.quantity,
            actual_quantity=Decimal('1.0000'),
            unit=unit,
            quality_status=MaterialConsumption.QualityStatus.QUARANTINE,
            expiry_date=timezone.localdate().replace(year=timezone.localdate().year - 1),
        )

        with pytest.raises(ValidationError) as error:
            invalid_issue.full_clean()

        assert 'quality_status' in error.value.message_dict
        assert 'expiry_date' in error.value.message_dict


@pytest.mark.django_db
@pytest.mark.legacy_api_permissions
class TestProductionApi:
    def test_order_api_uses_single_instance_global_scope(self):
        from production.models import ProductionOrder

        unit, product, _material, formula, _component, route = create_released_manufacturing_set()
        other_unit, other_product, _other_material, other_formula, _other_component, other_route = (
            create_released_manufacturing_set(suffix='999')
        )
        ProductionOrder.objects.create(
            order_number='OP-9999',
            product=other_product,
            formula=other_formula,
            route=other_route,
            planned_quantity=Decimal('50.0000'),
            unit=other_unit,
        )
        user = User.objects.create_user(
            username='pcp@example.com', email='pcp@example.com', password='S3curePass!123'
        )
        client = APIClient()
        client.force_authenticate(user)

        create_response = client.post(
            '/api/production/orders/',
            {
                'product': product.id,
                'formula': formula.id,
                'route': route.id,
                'planned_quantity': '100.0000',
                'unit': unit.id,
            },
        )

        assert create_response.status_code == 201
        assert 'tenant' not in create_response.json()
        assert create_response.json()['status'] == ProductionOrder.Status.DRAFT

        list_response = client.get('/api/production/orders/')

        assert list_response.status_code == 200
        created_order_number = create_response.json()['order_number']
        assert created_order_number.startswith(f'OP-{timezone.localdate():%Y%m%d}-')
        assert {item['order_number'] for item in list_response.json()['results']} == {
            created_order_number,
            'OP-9999',
        }

    def test_order_api_release_action_enforces_formula_route_release(self):
        from production.models import ProductionOrder

        unit, product, _material, formula, _component, route = create_released_manufacturing_set()
        user = User.objects.create_user(
            username='pcp@example.com', email='pcp@example.com', password='S3curePass!123'
        )
        client = APIClient()
        client.force_authenticate(user)
        order = ProductionOrder.objects.create(
            order_number='OP-0001',
            product=product,
            formula=formula,
            route=route,
            planned_quantity=Decimal('100.0000'),
            unit=unit,
        )

        release_before_approval = client.post(
            f'/api/production/orders/{order.id}/release/',
            {},
        )
        assert release_before_approval.status_code == 400

        approve_response = client.post(
            f'/api/production/orders/{order.id}/approve/',
            {},
        )
        release_response = client.post(
            f'/api/production/orders/{order.id}/release/',
            {},
        )

        assert approve_response.status_code == 200
        assert release_response.status_code == 200
        assert release_response.json()['status'] == ProductionOrder.Status.RELEASED

    @pytest.mark.permission_strict
    def test_material_consumption_api_requires_model_permission(self):
        from production.models import ProductionOrder

        unit, product, _material, formula, _component, route = create_released_manufacturing_set()
        ProductionOrder.objects.create(
            order_number='OP-0001',
            product=product,
            formula=formula,
            route=route,
            planned_quantity=Decimal('100.0000'),
            unit=unit,
        )
        user = User.objects.create_user(
            username='pcp@example.com', email='pcp@example.com', password='S3curePass!123'
        )
        client = APIClient()
        client.login(username=user.username, password='S3curePass!123')

        response = client.get('/api/production/consumptions/')

        assert response.status_code == 403
