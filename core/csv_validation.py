import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ValidationFinding:
    requirement_id: str
    status: str
    evidence: str


@dataclass(frozen=True)
class CsvValidationReport:
    findings: tuple[ValidationFinding, ...]

    @property
    def passed(self):
        return all(item.status == 'pass' for item in self.findings)

    def to_dict(self):
        return {'passed': self.passed, 'findings': [item.__dict__ for item in self.findings]}

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def evaluate_csv_validation(matrix_path=None):
    path = Path(
        matrix_path
        or Path(__file__).resolve().parents[1] / 'docs/validation/requirements-matrix.yml'
    )
    root = Path(__file__).resolve().parents[1]
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    findings = []
    for item in data.get('requirements', []):
        required = ('id', 'title', 'framework', 'control', 'evidence')
        missing = [key for key in required if not item.get(key)]
        evidence = item.get('evidence', '')
        evidence_path = root / evidence
        if missing:
            findings.append(
                ValidationFinding(
                    item.get('id', 'unknown'), 'fail', f'Campos ausentes: {", ".join(missing)}'
                )
            )
        elif Path(evidence).is_absolute() or '..' in Path(evidence).parts:
            findings.append(
                ValidationFinding(
                    item['id'], 'fail', 'Referência de evidência fora da raiz permitida.'
                )
            )
        elif not evidence_path.is_file():
            findings.append(ValidationFinding(item['id'], 'fail', 'Evidência não encontrada.'))
        else:
            findings.append(ValidationFinding(item['id'], 'pass', evidence))
    return CsvValidationReport(tuple(findings))


def evidence_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
