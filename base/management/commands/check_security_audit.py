from django.core.management.base import BaseCommand, CommandError
from core.security_audit import evaluate_security_audit


class Command(BaseCommand):
    def add_arguments(self, p):
        p.add_argument('--format', choices=('text', 'json'), default='text')
        p.add_argument('--fail-on-error', action='store_true')

    def handle(self, *a, **o):
        r = evaluate_security_audit()
        self.stdout.write(
            r.to_json() if o['format'] == 'json' else f'security_audit: aprovado={r.passed}'
        )
        if o['fail_on_error'] and not r.passed:
            raise CommandError('Auditoria de segurança possui falhas.')
