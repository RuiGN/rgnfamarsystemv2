import json
from io import StringIO
from pathlib import Path

from django.core.management import call_command
import yaml

from core.csv_validation import evaluate_csv_validation, evidence_sha256


ROOT = Path(__file__).resolve().parents[1]


def test_csv_matrix_is_traceable_and_serializable():
    report = evaluate_csv_validation()
    assert report.passed is True
    payload = json.loads(report.to_json())
    expected_ids = {
        item['id']
        for item in yaml.safe_load(
            (ROOT / 'docs/validation/requirements-matrix.yml').read_text(encoding='utf-8')
        )['requirements']
    }
    actual_ids = {item['requirement_id'] for item in payload['findings']}
    assert actual_ids == expected_ids
    assert {
        'CSV-001',
        'CSV-002',
        'CSV-003',
        'SI-001',
        'SI-002',
        'SI-003',
    }.issubset(actual_ids)


def test_csv_command_outputs_passing_json():
    stdout = StringIO()
    call_command('check_csv_validation', format='json', fail_on_error=True, stdout=stdout)
    assert json.loads(stdout.getvalue())['passed'] is True


def test_csv_matrix_rejects_missing_evidence_file(tmp_path):
    matrix = tmp_path / 'requirements-matrix.yml'
    matrix.write_text(
        """
version: '1.0'
requirements:
  - id: CSV-MISSING
    title: Evidencia ausente
    framework: ALCOA+
    control: Evidencia deve existir
    evidence: tests/does_not_exist.py
""",
        encoding='utf-8',
    )

    report = evaluate_csv_validation(matrix)

    assert report.passed is False
    assert report.findings[0].status == 'fail'
    assert 'não encontrada' in report.findings[0].evidence


def test_evidence_hash_is_sha256(tmp_path):
    evidence = tmp_path / 'evidence.txt'
    evidence.write_text('ALCOA+', encoding='utf-8')
    assert len(evidence_sha256(evidence)) == 64
