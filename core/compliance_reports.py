import hashlib
import json
from datetime import datetime, timezone

from .csv_validation import evaluate_csv_validation
from .evidence_audit import evaluate_evidence_catalog


def generate_compliance_report(framework=None, status=None):
    csv_report = evaluate_csv_validation()
    evidence_report = evaluate_evidence_catalog()
    findings = []
    for item in csv_report.findings:
        findings.append(
            {
                'id': item.requirement_id,
                'framework': framework or 'all',
                'status': item.status,
                'evidence': item.evidence,
            }
        )
    for item in evidence_report.findings:
        findings.append(
            {
                'id': item.evidence_id,
                'framework': framework or 'all',
                'status': item.status,
                'evidence': item.message,
            }
        )
    if status:
        findings = [item for item in findings if item['status'] == status]
    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'single-instance',
        'findings': findings,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    payload['sha256'] = hashlib.sha256(canonical).hexdigest()
    return payload


def report_markdown(payload):
    lines = [
        f'# Relatório de conformidade\n\nGerado em: `{payload["generated_at"]}`  \nHash: `{payload["sha256"]}`\n',
        '| ID | Framework | Status | Evidência |',
        '|---|---|---|---|',
    ]
    lines.extend(
        f'| {item["id"]} | {item["framework"]} | {item["status"]} | {item["evidence"]} |'
        for item in payload['findings']
    )
    return '\n'.join(lines) + '\n'
