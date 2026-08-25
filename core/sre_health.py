import json
from dataclasses import dataclass
from django.conf import settings


@dataclass(frozen=True)
class SreCheck:
    code: str
    passed: bool
    evidence: str


@dataclass(frozen=True)
class SreReport:
    checks: tuple[SreCheck, ...]

    @property
    def passed(self):
        return all(x.passed for x in self.checks)

    def to_json(self):
        return json.dumps(
            {'passed': self.passed, 'checks': [x.__dict__ for x in self.checks]},
            ensure_ascii=False,
            indent=2,
        )


def evaluate_sre_health():
    return SreReport(
        (
            SreCheck('cache_configured', bool(settings.CACHES), 'Cache Django configurado.'),
            SreCheck(
                'celery_broker_configured',
                bool(getattr(settings, 'CELERY_BROKER_URL', '')),
                'Broker Celery configurado.',
            ),
            SreCheck(
                'result_backend_configured',
                bool(getattr(settings, 'CELERY_RESULT_BACKEND', '')),
                'Backend de resultados configurado.',
            ),
            SreCheck(
                'security_logging',
                bool(getattr(settings, 'LOGGING', {})),
                'Logging estruturado carregado.',
            ),
        )
    )
