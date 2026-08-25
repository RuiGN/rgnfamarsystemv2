import json
from io import StringIO

from django.core.management import call_command

from core.compliance_reports import generate_compliance_report, report_markdown


def test_report_has_hash_timestamp_and_findings():
    report = generate_compliance_report()
    assert report['scope'] == 'single-instance'
    assert len(report['sha256']) == 64
    assert report['findings']
    assert 'CSV-001' in {item['id'] for item in report['findings']}


def test_status_filter_and_markdown_output():
    report = generate_compliance_report(status='pass')
    assert all(item['status'] == 'pass' for item in report['findings'])
    assert '| ID | Framework | Status | Evidência |' in report_markdown(report)


def test_management_command_outputs_json():
    stdout = StringIO()
    call_command('generate_compliance_report', format='json', stdout=stdout)
    assert json.loads(stdout.getvalue())['scope'] == 'single-instance'
