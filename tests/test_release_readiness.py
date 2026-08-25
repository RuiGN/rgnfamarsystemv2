import json
from pathlib import Path
from io import StringIO
import tempfile

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase


class ReleaseReadinessTests(SimpleTestCase):
    def test_release_readiness_report_covers_gates_smoke_openapi_demo_docs_navigation_and_prd(self):
        from core.release_readiness import ReleaseReadinessCheckStatus, evaluate_release_readiness

        report = evaluate_release_readiness(project_root=settings.BASE_DIR)
        checks = {check.code: check for check in report.checks}

        expected_codes = {
            'release.required_gates',
            'release.smoke_routes',
            'release.openapi_schema',
            'release.demo_data',
            'release.evidence_runbook',
            'docs.release_navigation',
            'prd.sprint_36_recorded',
            'security.no_real_secrets',
        }

        assert report.passed is True
        assert expected_codes.issubset(checks)
        assert all(check.status == ReleaseReadinessCheckStatus.PASS for check in checks.values())
        assert 'prontidão de release' in checks['docs.release_navigation'].evidence.lower()
        assert 'check_release_readiness' in checks['docs.release_navigation'].evidence
        assert 'check_release_readiness' in checks['release.required_gates'].evidence
        assert 'openapi-schema.yml' in checks['release.openapi_schema'].evidence

    def test_release_readiness_report_serializes_to_json(self):
        from core.release_readiness import evaluate_release_readiness

        payload = json.loads(evaluate_release_readiness(project_root=settings.BASE_DIR).to_json())

        assert payload['passed'] is True
        assert 'checks' in payload
        assert 'release.evidence_runbook' in {item['code'] for item in payload['checks']}

    def test_release_readiness_can_report_documentation_failure(self):
        from core.release_readiness import evaluate_release_readiness

        temporary_root = (
            Path(settings.BASE_DIR) / 'tests' / 'fixtures' / 'missing-release-readiness-docs'
        )

        report = evaluate_release_readiness(project_root=temporary_root)
        checks = {check.code: check for check in report.checks}

        assert report.passed is False
        assert checks['release.evidence_runbook'].status.value == 'fail'

    def test_release_readiness_can_report_missing_navigation_docs_failure(self):
        from core.release_readiness import evaluate_release_readiness

        with tempfile.TemporaryDirectory() as tmpdir:
            temporary_root = Path(tmpdir)
            (temporary_root / 'docs' / 'architecture').mkdir(parents=True)
            (temporary_root / 'docs' / 'architecture' / 'release-readiness.md').write_text(
                '# Prontidão de Release\n\nO comando `check_release_readiness` valida a documentação.',
                encoding='utf-8',
            )

            report = evaluate_release_readiness(project_root=temporary_root)

        checks = {check.code: check for check in report.checks}

        assert report.passed is False
        assert checks['docs.release_navigation'].status.value == 'fail'

    def test_release_readiness_command_outputs_json_report(self):
        stdout = StringIO()

        call_command('check_release_readiness', format='json', stdout=stdout)

        payload = json.loads(stdout.getvalue())
        assert payload['passed'] is True
        assert {item['status'] for item in payload['checks']} == {'pass'}
        assert 'release.required_gates' in {item['code'] for item in payload['checks']}

    def test_release_readiness_command_can_fail_on_errors(self):
        stdout = StringIO()

        call_command('check_release_readiness', fail_on_error=True, stdout=stdout)

        assert 'release_readiness: aprovado=True' in stdout.getvalue()
