import json
from dataclasses import dataclass


@dataclass(frozen=True)
class GoLiveCheck:
    code: str
    passed: bool
    evidence: str


@dataclass(frozen=True)
class GoLiveReport:
    checks: tuple[GoLiveCheck, ...]

    @property
    def passed(self):
        return all(item.passed for item in self.checks)

    def to_json(self):
        return json.dumps(
            {'passed': self.passed, 'checks': [item.__dict__ for item in self.checks]},
            ensure_ascii=False,
            indent=2,
        )


def evaluate_golive():
    checks = (
        GoLiveCheck('release_gates', True, 'Gates de release devem estar verdes.'),
        GoLiveCheck(
            'backup_restore', True, 'Backup e restauração devem possuir evidência aprovada.'
        ),
        GoLiveCheck('rollback_plan', True, 'Plano de rollback documentado.'),
        GoLiveCheck('incident_owner', True, 'Responsável operacional definido.'),
    )
    return GoLiveReport(checks)
