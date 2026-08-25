import json
from io import StringIO
from django.core.management import call_command
from core.release_1 import evaluate_release_1


def test_release_1_report_passes():
    report = evaluate_release_1()
    assert report.passed is True
    assert report.version == '1.0.0'


def test_release_1_command():
    out = StringIO()
    call_command('check_release_1', release_version='1.0.0', fail_on_error=True, stdout=out)
    assert json.loads(out.getvalue())['passed'] is True
