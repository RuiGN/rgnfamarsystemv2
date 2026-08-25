from django.core.management.base import BaseCommand, CommandError

from core.operational_readiness import evaluate_operational_readiness


class Command(BaseCommand):
    help = 'Avalia requisitos não funcionais de operação, deploy e runtime.'

    def add_arguments(self, parser):
        parser.add_argument('--format', choices=('text', 'json'), default='text')
        parser.add_argument('--fail-on-error', action='store_true', dest='fail_on_error')

    def handle(self, *args, **options):
        report = evaluate_operational_readiness()

        if options['format'] == 'json':
            self.stdout.write(report.to_json())
        else:
            self.stdout.write(f'operational_readiness: aprovado={report.passed}')
            for check in report.checks:
                self.stdout.write(f'- {check.code}: {check.status.value} - {check.evidence}')

        if options['fail_on_error'] and not report.passed:
            raise CommandError('Requisitos não funcionais possuem falhas.')
