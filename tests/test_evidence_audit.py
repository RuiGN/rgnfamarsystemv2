from io import StringIO
import json

from django.core.management import call_command

from core.evidence_audit import evaluate_evidence_catalog


def test_evidence_catalog_passes_hash_and_approval():
    report = evaluate_evidence_catalog()
    assert report.passed is True
    assert report.findings[0].status == 'pass'


def test_evidence_audit_command_outputs_json():
    stdout = StringIO()
    call_command('check_evidence_audit', format='json', fail_on_error=True, stdout=stdout)
    assert json.loads(stdout.getvalue())['passed'] is True
