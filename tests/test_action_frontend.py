from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
    unit = UnitOfMeasure.objects.create(code='KG-FRONT', name='Quilograma', symbol='kg')
    product = Product.objects.create(
        code='PA-FRONT',
        description='Produto do frontend',
        item_type=Product.ItemType.FINISHED_PRODUCT,
        unit=unit,
        status=Product.Status.APPROVED,
    )
    formula = MasterFormula.objects.create(
        product=product,
        code='F-FRONT',
        version=1,
        status=MasterFormula.Status.APPROVED,
        batch_size=Decimal('100'),
        batch_unit=unit,
        effective_from=timezone.localdate(),
    )
    route = ManufacturingRoute.objects.create(
        product=product,
        formula=formula,
        code='R-FRONT',
        version=1,
        status=ManufacturingRoute.Status.APPROVED,
        effective_from=timezone.localdate(),
    )
    return ProductionOrder.objects.create(
        order_number='OP-FRONT',
        product=product,
        formula=formula,
        route=route,
        planned_quantity=Decimal('100'),
        unit=unit,
    )


class ActionFrontendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('front-user', 'front@example.com', 'Secret123!')
        grant(self.user, 'view')
        grant(self.user, 'change')
        self.order = create_order()
        self.detail_url = reverse(
            'app:resource_detail',
            kwargs={
                'module_slug': 'production',
                'resource_slug': 'orders',
                'pk': self.order.pk,
            },
        )
        self.action_url = reverse(
            'app:resource_action',
            kwargs={
                'module_slug': 'production',
                'resource_slug': 'orders',
                'pk': self.order.pk,
                'action_name': 'approve',
            },
        )

    def test_detail_renders_only_authorized_state_compatible_actions(self):
        self.client.force_login(self.user)

        response = self.client.get(self.detail_url)

        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="resource-actions-title"' in content
        assert f'href="{self.action_url}"' in content
        assert 'data-domain-action' in content
        assert 'Aprovar' in content

        self.order.status = ProductionOrder.Status.COMPLETED
        self.order.save(update_fields=['status'])
        incompatible = self.client.get(self.detail_url).content.decode()
        assert 'data-domain-action' not in incompatible

    def test_user_without_change_permission_does_not_see_action_buttons(self):
        readonly = User.objects.create_user('readonly', 'readonly@example.com', 'Secret123!')
        grant(readonly, 'view')
        self.client.force_login(readonly)

        response = self.client.get(self.detail_url)

        assert response.status_code == 200
        assert 'data-domain-action' not in response.content.decode()

    def test_action_page_is_accessible_without_javascript(self):
        self.client.force_login(self.user)

        response = self.client.get(self.action_url)

        assert response.status_code == 200
        content = response.content.decode()
        assert 'data-action-form' in content
        assert 'csrfmiddlewaretoken' in content
        assert 'aria-describedby="action-description"' in content
        assert 'Confirmar ação' in content
        assert 'Cancelar' in content

    def test_action_form_errors_are_announced_accessibly(self):
        self.client.force_login(self.user)

        response = self.client.post(self.action_url, {})

        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="id_confirmation_acknowledged_errors"' in content
        assert 'role="alert"' in content
        assert 'aria-invalid="true"' in content
        assert 'aria-describedby="id_confirmation_acknowledged_errors"' in content

    def test_progressive_script_uses_safe_dom_apis_and_is_loaded_with_defer(self):
        script = (Path(settings.BASE_DIR) / 'static/js/resource-actions.js').read_text(
            encoding='utf-8'
        )
        base = (Path(settings.BASE_DIR) / 'templates/base.html').read_text(encoding='utf-8')

        assert 'innerHTML' not in script
        assert 'DOMParser' in script
        assert 'textContent' in script
        assert "credentials: 'same-origin'" in script
        assert "js/resource-actions.js' %}" in base
        assert 'resource-actions.js\' %}" defer' in base

    def test_new_visible_copy_preserves_pt_br_accents(self):
        sources = '\n'.join(
            (Path(settings.BASE_DIR) / path).read_text(encoding='utf-8')
            for path in (
                'base/ui/actions/modules/production.py',
                'templates/app/includes/resource_actions.html',
                'templates/app/resource_action_form.html',
            )
        ).casefold()

        for invalid in (
            'aprovacao',
            'producao',
            'execucao',
            'nao ',
            'confirmacao',
            'exclusao',
        ):
            assert invalid not in sources
