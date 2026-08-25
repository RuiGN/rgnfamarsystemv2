import unicodedata

import pytest
from django.core.exceptions import ImproperlyConfigured

from base.ui.actions.copy import ACTION_LABELS
from base.ui.actions.factory import action_config
from base.ui.actions.registry import action_registry


def test_copy_covers_every_registered_action_with_normalized_pt_br():
    for config in action_registry.all():
        assert config.action_name in ACTION_LABELS
        for value in (config.label, config.description, config.success_message):
            assert value
            assert unicodedata.normalize('NFC', value) == value


def test_factory_rejects_action_without_approved_copy():
    with pytest.raises(ImproperlyConfigured, match='vocabulário'):
        action_config('production', 'orders', 'missing_action')
