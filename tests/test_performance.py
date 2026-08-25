from io import StringIO
import json
from django.core.management import call_command
from core.performance import evaluate_performance


def test_performance_report_passes_operational_configuration():
    report = evaluate_performance()
    assert report.passed is True
    assert len(report.checks) == 4


def test_performance_command_json():
    output = StringIO()
    call_command('check_performance', format='json', fail_on_error=True, stdout=output)
    assert json.loads(output.getvalue())['passed'] is True
