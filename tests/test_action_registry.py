from dataclasses import replace

import pytest
from django.core.exceptions import ImproperlyConfigured

from base.ui.actions.modules.production import PRODUCTION_ACTIONS
from base.ui.actions.registry import ActionRegistry
from base.ui.actions.types import ActionConfirmation, ActionField, FieldKind
from production.models import ProductionOrder


def test_registry_rejects_duplicate_missing_permission_and_unknown_resource():
    valid = PRODUCTION_ACTIONS[0]

    with pytest.raises(ImproperlyConfigured, match='duplicada'):
        ActionRegistry((valid, valid))
    with pytest.raises(ImproperlyConfigured, match='permissão'):
        ActionRegistry((replace(valid, permissions=()),))
    with pytest.raises(ImproperlyConfigured, match='recurso'):
        ActionRegistry((replace(valid, resource_slug='missing'),))


def test_registry_rejects_invalid_metadata_contracts():
    valid = PRODUCTION_ACTIONS[0]

    invalid_configs = (
        (replace(valid, model=type('WrongModel', (), {})), 'model'),
        (replace(valid, label=''), 'texto'),
        (replace(valid, route_name='missing:route'), 'rota'),
        (
            replace(valid, tone='danger', confirmation=None),
            'confirmação',
        ),
        (
            replace(
                valid,
                fields=(ActionField('reason', 'Motivo'), ActionField('reason', 'Motivo')),
            ),
            'campo',
        ),
        (replace(valid, allowed_states=('unknown',)), 'estado'),
    )

    for config, message in invalid_configs:
        with pytest.raises(ImproperlyConfigured, match=message):
            ActionRegistry((config,))


def test_registry_queries_configs_without_rebuilding_them():
    registry = ActionRegistry(PRODUCTION_ACTIONS)

    assert registry.all() == PRODUCTION_ACTIONS
    assert registry.get('production', 'orders', 'approve') is PRODUCTION_ACTIONS[0]
    assert registry.for_resource('production', 'orders') == PRODUCTION_ACTIONS


def test_production_cut_contains_the_eleven_real_actions_and_state_contracts():
    assert tuple(config.action_name for config in PRODUCTION_ACTIONS) == (
        'approve',
        'release',
        'start',
        'pause',
        'resume',
        'complete',
        'cancel',
        'reserve_materials',
        'issue_materials',
        'receive_outputs',
        'calculate_cost',
    )
    assert all(config.model is ProductionOrder for config in PRODUCTION_ACTIONS)
    assert all(
        config.permissions == ('production.change_productionorder',)
        for config in PRODUCTION_ACTIONS[:7]
    )
    assert PRODUCTION_ACTIONS[0].allowed_states == (ProductionOrder.Status.DRAFT,)
    assert PRODUCTION_ACTIONS[5].fields == (
        ActionField(
            'actual_yield_quantity',
            'Rendimento real',
            FieldKind.DECIMAL,
            required=True,
            min_value=0,
        ),
    )
    assert isinstance(PRODUCTION_ACTIONS[5].confirmation, ActionConfirmation)
    assert PRODUCTION_ACTIONS[6].tone == 'danger'
    assert PRODUCTION_ACTIONS[6].confirmation is not None


def test_production_operational_actions_use_api_routes_permissions_and_states():
    actions = {action.action_name: action for action in PRODUCTION_ACTIONS}

    assert {
        'reserve_materials',
        'issue_materials',
        'receive_outputs',
        'calculate_cost',
    } <= actions.keys()
    assert actions['reserve_materials'].permissions == (
        'production.change_productionorder',
        'production.change_materialconsumption',
        'inventory.add_stockmovement',
    )
    assert actions['issue_materials'].permissions == actions['reserve_materials'].permissions
    assert actions['receive_outputs'].permissions == (
        'production.receive_productionoutput',
        'inventory.add_stockmovement',
    )
    assert actions['calculate_cost'].permissions == (
        'production.change_productionorder',
        'costing.add_productioncostcapture',
    )
    assert actions['reserve_materials'].route_name == 'v1_production:order-reserve-materials'
    assert actions['issue_materials'].route_name == 'v1_production:order-issue-materials'
    assert actions['receive_outputs'].route_name == 'v1_production:order-receive-outputs'
    assert actions['calculate_cost'].route_name == 'v1_production:order-calculate-cost'
    assert actions['reserve_materials'].allowed_states == (
        ProductionOrder.Status.APPROVED,
        ProductionOrder.Status.RELEASED,
    )
    assert actions['issue_materials'].allowed_states == (ProductionOrder.Status.IN_PROGRESS,)
    assert actions['receive_outputs'].allowed_states == (ProductionOrder.Status.COMPLETED,)
    assert actions['calculate_cost'].allowed_states == (
        ProductionOrder.Status.COMPLETED,
        ProductionOrder.Status.CLOSED,
    )
    assert actions['reserve_materials'].confirmation.acknowledge_label
    assert actions['issue_materials'].confirmation.typed_phrase == 'CONFIRMAR'
    assert actions['receive_outputs'].confirmation.acknowledge_label
