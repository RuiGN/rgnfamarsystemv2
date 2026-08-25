import json
from io import StringIO
from django.core.management import call_command
from core.golive import evaluate_golive


def test_golive_report_contains_operational_checks():
    report = evaluate_golive()
    assert report.passed is True
    assert {'release_gates', 'backup_restore', 'rollback_plan', 'incident_owner'} == {
        x.code for x in report.checks
    }


def test_golive_command_json():
    output = StringIO()
    call_command('check_golive', format='json', fail_on_error=True, stdout=output)
    assert json.loads(output.getvalue())['passed'] is True
