from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from base.ui.actions.context import available_actions
from base.ui.registry import get_resource
from formulations.models import ManufacturingRoute, MasterFormula
from masters.models import Product, UnitOfMeasure
from production.models import ProductionOrder


User = get_user_model()


def grant(user, action):
    permission = Permission.objects.get(
        content_type__app_label='production',
        content_type__model='productionorder',
        codename=f'{action}_productionorder',
    )
    user.user_permissions.add(permission)


def create_order():
    unit = UnitOfMeasure.objects.create(code='KG-ACTION', name='Quilograma', symbol='kg')
    product = Product.objects.create(
        code='PA-ACTION',
        description='Produto para ação',
        item_type=Product.ItemType.FINISHED_PRODUCT,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    formula = MasterFormula.objects.create(
        product=product,
        code='F-ACTION',
        version=1,
        status=MasterFormula.Status.APPROVED,
        batch_size=Decimal('100'),
        batch_unit=unit,
        effective_from=timezone.localdate(),
    )
    route = ManufacturingRoute.objects.create(
        product=product,
        formula=formula,
        code='R-ACTION',
        version=1,
        status=ManufacturingRoute.Status.APPROVED,
        effective_from=timezone.localdate(),
    )
    return ProductionOrder.objects.create(
        order_number='OP-ACTION',
        product=product,
        formula=formula,
        route=route,
        planned_quantity=Decimal('100'),
        unit=unit,
    )


class ActionDispatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'action-user',
            'action@example.com',
            'Secret123!',
        )
        grant(self.user, 'view')
        grant(self.user, 'change')
        self.order = create_order()
        self.url = reverse(
            'app:resource_action',
            kwargs={
                'module_slug': 'production',
                'resource_slug': 'orders',
                'pk': self.order.pk,
                'action_name': 'approve',
            },
        )

    def csrf_client(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.get(self.url)
        assert response.status_code == 200
        return client, client.cookies['csrftoken'].value

    def test_context_filters_by_permission_detail_and_state_without_queries(self):
        resource = get_resource('production', 'orders')
        request = type('Request', (), {'user': self.user})()
        self.user.get_all_permissions()
        with CaptureQueriesContext(connection) as queries:
            actions = available_actions(request, resource, self.order)

        assert len(queries) == 0
        assert tuple(action.action_name for action in actions) == ('approve', 'cancel')
        assert available_actions(request, resource) == ()
        assert actions[0] is available_actions(request, resource, self.order)[0]

    def test_get_renders_registered_action_form(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert response.context['action'].action_name == 'approve'
        assert 'csrfmiddlewaretoken' in response.content.decode()

    def test_post_requires_csrf_permission_existing_object_and_allowed_state(self):
        self.client.force_login(self.user)
        protected_client = Client(enforce_csrf_checks=True)
        protected_client.force_login(self.user)
        assert (
            protected_client.post(self.url, {'confirmation_acknowledged': 'on'}).status_code == 403
        )

        denied = User.objects.create_user('denied', 'denied@example.com', 'Secret123!')
        denied_client = Client()
        denied_client.force_login(denied)
        assert denied_client.post(self.url, {'confirmation_acknowledged': 'on'}).status_code == 403

        missing_url = self.url.replace(f'/{self.order.pk}/', '/999999/')
        assert self.client.post(missing_url, {'confirmation_acknowledged': 'on'}).status_code == 404

        self.order.status = ProductionOrder.Status.COMPLETED
        self.order.save(update_fields=['status'])
        assert self.client.post(self.url, {'confirmation_acknowledged': 'on'}).status_code == 409

    def test_fallback_dispatches_to_registered_drf_callback(self):
        client, csrf_token = self.csrf_client()

        response = client.post(
            self.url,
            {'confirmation_acknowledged': 'on'},
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_X_REQUEST_ID='ui-123',
        )

        assert response.status_code == 302
        assert response['Location'] == reverse(
            'app:resource_detail',
            kwargs={
                'module_slug': 'production',
                'resource_slug': 'orders',
                'pk': self.order.pk,
            },
        )
        self.order.refresh_from_db()
        assert self.order.status == ProductionOrder.Status.APPROVED

    def test_invalid_form_is_rendered_without_dispatch(self):
        self.order.approve(self.user)
        self.order.release(self.user)
        self.order.start(self.user)
        complete_url = self.url.replace('/approve/', '/complete/')
        client = Client()
        client.force_login(self.user)

        response = client.post(
            complete_url,
            {'actual_yield_quantity': '', 'confirmation_phrase': 'INCORRETO'},
        )

        assert response.status_code == 200
        assert 'actual_yield_quantity' in response.context['form'].errors
        self.order.refresh_from_db()
        assert self.order.status == ProductionOrder.Status.IN_PROGRESS
