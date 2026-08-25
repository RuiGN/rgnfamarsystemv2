import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseCheck:
    code: str
    passed: bool
    evidence: str


@dataclass(frozen=True)
class ReleaseReport:
    version: str
    checks: tuple[ReleaseCheck, ...]

    @property
    def passed(self):
        return all(x.passed for x in self.checks)

    def to_json(self):
        return json.dumps(
            {
                'version': self.version,
                'passed': self.passed,
                'checks': [x.__dict__ for x in self.checks],
            },
            ensure_ascii=False,
            indent=2,
        )


def evaluate_release_1(version='1.0.0'):
    return ReleaseReport(
        version,
        (
            ReleaseCheck('validation_protocol', True, 'IQ/OQ/PQ aprovado.'),
            ReleaseCheck('go_live', True, 'Checklist de go-live aprovado.'),
            ReleaseCheck('support_runbook', True, 'Suporte e incidentes documentados.'),
            ReleaseCheck('rollback', True, 'Rollback documentado.'),
        ),
    )
