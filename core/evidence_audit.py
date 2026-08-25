import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class EvidenceFinding:
    evidence_id: str
    status: str
    message: str


@dataclass(frozen=True)
class EvidenceAuditReport:
    findings: tuple[EvidenceFinding, ...]

    @property
    def passed(self):
        return all(item.status == 'pass' for item in self.findings)

    def to_json(self):
        return json.dumps(
            {'passed': self.passed, 'findings': [item.__dict__ for item in self.findings]},
            ensure_ascii=False,
            indent=2,
        )


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate_evidence_catalog(path=None, root=None):
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    catalog = Path(path or root / 'docs/validation/evidence-catalog.yml')
    data = yaml.safe_load(catalog.read_text(encoding='utf-8'))
    findings = []
    required = (
        'id',
        'requirement',
        'owner',
        'reviewed_by',
        'captured_at',
        'status',
        'sha256',
        'artifact',
    )
    for item in data.get('evidence', []):
        missing = [key for key in required if not item.get(key)]
        artifact = (root / item.get('artifact', '')).resolve()
        valid_path = artifact.is_relative_to(root) and artifact.is_file()
        valid_hash = valid_path and _sha256(artifact) == item.get('sha256')
        status = (
            'pass'
            if not missing and valid_path and valid_hash and item.get('status') == 'approved'
            else 'fail'
        )
        message = (
            'Evidência íntegra e aprovada.'
            if status == 'pass'
            else 'Metadados, caminho, estado ou SHA-256 inválidos.'
        )
        findings.append(EvidenceFinding(item.get('id', 'unknown'), status, message))
    return EvidenceAuditReport(tuple(findings))
