from io import StringIO
import json
from django.core.management import call_command
from core.sre_health import evaluate_sre_health


def test_sre_health_report_passes_configured_services():
    report = evaluate_sre_health()
    assert report.passed is True
    assert {
        'cache_configured',
        'celery_broker_configured',
        'result_backend_configured',
        'security_logging',
    } == {x.code for x in report.checks}


def test_sre_health_command_json():
    output = StringIO()
    call_command('check_sre_health', format='json', fail_on_error=True, stdout=output)
    assert json.loads(output.getvalue())['passed'] is True
