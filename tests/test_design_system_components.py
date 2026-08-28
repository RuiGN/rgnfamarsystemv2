from dataclasses import FrozenInstanceError

import pytest

from base.ui.presentation import ProgressMetric


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
