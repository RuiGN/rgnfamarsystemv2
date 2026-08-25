import json
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.core.management import call_command
from django.test import SimpleTestCase
from django.urls import resolve


class ProductAcceptanceTests(SimpleTestCase):
    def test_product_acceptance_report_covers_routes_commands_docs_and_prd(self):
        from core.product_acceptance import (
            ProductAcceptanceCheckStatus,
            evaluate_product_acceptance,
        )

        report = evaluate_product_acceptance(project_root=settings.BASE_DIR)
        checks = {check.code: check for check in report.checks}

        expected_codes = {
            'routes.core_entrypoints',
            'auth.single_login',
            'routes.api_v1_modules',
            'ui.admin_menus',
            'commands.operational_gates',
            'docs.product_acceptance',
            'prd.sprint_35_recorded',
            'security.no_real_secrets',
        }

        assert report.passed is True
        assert expected_codes.issubset(checks)
        assert all(check.status == ProductAcceptanceCheckStatus.PASS for check in checks.values())
        assert '/api/v1/' in checks['routes.api_v1_modules'].evidence
        assert '/admin/' in checks['ui.admin_menus'].evidence
        assert 'check_product_acceptance' in checks['docs.product_acceptance'].evidence

    def test_product_acceptance_report_serializes_to_json(self):
        from core.product_acceptance import evaluate_product_acceptance

        payload = json.loads(evaluate_product_acceptance(project_root=settings.BASE_DIR).to_json())

        assert payload['passed'] is True
        assert 'checks' in payload
        assert 'routes.core_entrypoints' in {item['code'] for item in payload['checks']}

    def test_product_acceptance_can_report_documentation_failure(self):
        from core.product_acceptance import evaluate_product_acceptance

        temporary_root = (
            Path(settings.BASE_DIR) / 'tests' / 'fixtures' / 'missing-product-acceptance-docs'
        )

        report = evaluate_product_acceptance(project_root=temporary_root)
        checks = {check.code: check for check in report.checks}

        assert report.passed is False
        assert checks['docs.product_acceptance'].status.value == 'fail'

    def test_product_acceptance_rejects_parallel_admin_login_view(self):
        from core.product_acceptance import evaluate_product_acceptance

        runtime_resolve = resolve

        def resolve_with_parallel_admin_login(path):
            if path == '/admin/login/':
                return SimpleNamespace(func=admin.site.login)
            return runtime_resolve(path)

        with patch(
            'core.product_acceptance.resolve',
            side_effect=resolve_with_parallel_admin_login,
        ):
            report = evaluate_product_acceptance(project_root=settings.BASE_DIR)

        checks = {check.code: check for check in report.checks}
        assert checks['auth.single_login'].status.value == 'fail'

    def test_product_acceptance_command_outputs_json_report(self):
        stdout = StringIO()

        call_command('check_product_acceptance', format='json', stdout=stdout)

        payload = json.loads(stdout.getvalue())
        assert payload['passed'] is True
        assert {item['status'] for item in payload['checks']} == {'pass'}
        assert 'commands.operational_gates' in {item['code'] for item in payload['checks']}

    def test_product_acceptance_command_can_fail_on_errors(self):
        stdout = StringIO()

        call_command('check_product_acceptance', fail_on_error=True, stdout=stdout)

        assert 'product_acceptance: aprovado=True' in stdout.getvalue()
