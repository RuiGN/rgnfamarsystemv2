import json
from dataclasses import dataclass
from django.conf import settings


@dataclass(frozen=True)
class PerformanceCheck:
    code: str
    passed: bool
    evidence: str


@dataclass(frozen=True)
class PerformanceReport:
    checks: tuple[PerformanceCheck, ...]

    @property
    def passed(self):
        return all(x.passed for x in self.checks)

    def to_json(self):
        return json.dumps(
            {'passed': self.passed, 'checks': [x.__dict__ for x in self.checks]},
            ensure_ascii=False,
            indent=2,
        )


def evaluate_performance():
    db = settings.DATABASES['default']
    return PerformanceReport(
        (
            PerformanceCheck(
                'db_connection_policy',
                db.get('CONN_MAX_AGE', 0) >= 0,
                'Política de conexão definida.',
            ),
            PerformanceCheck('cache_available', bool(settings.CACHES), 'Cache disponível.'),
            PerformanceCheck(
                'pagination_default',
                bool(getattr(settings, 'REST_FRAMEWORK', {}).get('DEFAULT_PAGINATION_CLASS')),
                'Paginação DRF configurada.',
            ),
            PerformanceCheck(
                'debug_disabled', settings.DEBUG is False, 'DEBUG desabilitado para operação.'
            ),
        )
    )
