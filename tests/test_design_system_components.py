from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest
from django.utils import timezone

from base.ui.deadlines import DeadlineItem
from base.ui.presentation import ProgressMetric
from base.ui.workspaces import WorkspaceMetric


class PermissionUser:
    def __init__(self, permissions=()):
        self.permissions = set(permissions)

    def has_perm(self, permission):
        return permission in self.permissions


def test_progress_metric_normalizes_percent_and_handles_zero_target():
    metric = ProgressMetric('Concluídas', 12, 'feather-check', 'success', 'Produção', '/app/', 20)
    overflow = ProgressMetric('Concluídas', 30, 'feather-check', 'success', 'Produção', '/app/', 20)
    no_target = ProgressMetric('Pendentes', 4, 'feather-clock', 'warning', 'Qualidade', '/app/')

    assert metric.has_progress is True
    assert metric.percent == 60
    assert overflow.percent == 100
    assert no_target.has_progress is False
    assert no_target.percent == 0


def test_progress_metric_is_immutable():
    metric = ProgressMetric('Concluídas', 12, 'feather-check', 'success', 'Produção', '/app/', 20)

    with pytest.raises(FrozenInstanceError):
        metric.target = 30


def test_workspace_metric_keeps_legacy_seventh_positional_permission():
    metric = WorkspaceMetric(
        'Concluídas',
        12,
        'feather-check',
        'success',
        'Produção',
        '/app/',
        'production.view_productionorder',
    )

    assert metric.has_progress is False
    assert metric.target is None
    assert metric.required_permission == 'production.view_productionorder'
    assert metric.can_view(PermissionUser()) is False
    assert metric.can_view(PermissionUser({'production.view_productionorder'})) is True


def test_deadline_item_uses_ptbr_temporal_labels():
    overdue = DeadlineItem(
        'OP-001',
        '',
        timezone.now() - timedelta(days=1),
        'danger',
        'feather-alert-triangle',
        '/app/',
    )
    today = DeadlineItem(
        'OP-002',
        '',
        timezone.now(),
        'warning',
        'feather-clock',
        '/app/',
    )

    assert overdue.temporal_label == 'Vencido'
    assert today.temporal_label == 'Vence hoje'
