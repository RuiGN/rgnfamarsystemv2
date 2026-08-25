from io import StringIO
import json
from django.core.management import call_command
from core.security_audit import evaluate_security_audit


def test_security_audit_passes_explicit_configuration():
    assert evaluate_security_audit().passed is True


def test_security_audit_command_json():
    out = StringIO()
    call_command('check_security_audit', format='json', fail_on_error=True, stdout=out)
    assert json.loads(out.getvalue())['passed'] is True
