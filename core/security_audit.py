import json
from dataclasses import dataclass
from django.conf import settings


@dataclass(frozen=True)
class SecurityCheck:
    code: str
    passed: bool
    evidence: str


@dataclass(frozen=True)
class SecurityReport:
    checks: tuple[SecurityCheck, ...]

    @property
    def passed(self):
        return all(x.passed for x in self.checks)

    def to_json(self):
        return json.dumps(
            {'passed': self.passed, 'checks': [x.__dict__ for x in self.checks]},
            ensure_ascii=False,
            indent=2,
        )


def evaluate_security_audit():
    return SecurityReport(
        (
            SecurityCheck('debug_explicit', isinstance(settings.DEBUG, bool), 'DEBUG definido.'),
            SecurityCheck('secret_key', bool(settings.SECRET_KEY), 'SECRET_KEY configurada.'),
            SecurityCheck(
                'csrf_origins',
                bool(getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])),
                'Origens CSRF configuradas.',
            ),
            SecurityCheck(
                'session_cookie',
                isinstance(getattr(settings, 'SESSION_COOKIE_SECURE', False), bool),
                'Cookie de sessão explicitamente configurado.',
            ),
        )
    )
