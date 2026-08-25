from django.core.management.base import BaseCommand

from base.modules import OperationalModule
from compliance.services import evaluate_module_readiness


class Command(BaseCommand):
    help = 'Avalia criterios transversais RF-31 para um modulo.'

    def add_arguments(self, parser):
        parser.add_argument('--module', required=True, choices=OperationalModule.values)

    def handle(self, *args, **options):
        result = evaluate_module_readiness(module=options['module'])
        self.stdout.write(f'{result["module"]}: aprovado={result["passed"]}')
        for item in result['items']:
            self.stdout.write(f'- {item.check_type}: {item.status} - {item.evidence}')
