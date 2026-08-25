import json
from django.core.management.base import BaseCommand, CommandError
from core.validation_protocol import evaluate_validation_protocol


class Command(BaseCommand):
    def add_arguments(self, p):
        p.add_argument('--fail-on-error', action='store_true')

    def handle(self, *a, **o):
        r = evaluate_validation_protocol()
        self.stdout.write(json.dumps(r, ensure_ascii=False, indent=2))
        if o['fail_on_error'] and not r['passed']:
            raise CommandError('Protocolo IQ/OQ/PQ possui falhas.')
