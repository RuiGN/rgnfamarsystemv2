from django.core.management.base import BaseCommand, CommandError

from core.release_readiness import evaluate_release_readiness


class Command(BaseCommand):
    help = 'Avalia a prontidao de release e staging local do RGN Farma System.'

    def add_arguments(self, parser):
        parser.add_argument('--format', choices=('text', 'json'), default='text')
        parser.add_argument('--fail-on-error', action='store_true', dest='fail_on_error')

    def handle(self, *args, **options):
        report = evaluate_release_readiness()

        if options['format'] == 'json':
            self.stdout.write(report.to_json())
        else:
            self.stdout.write(f'release_readiness: aprovado={report.passed}')
            for check in report.checks:
                self.stdout.write(f'- {check.code}: {check.status.value} - {check.evidence}')

        if options['fail_on_error'] and not report.passed:
            raise CommandError('Prontidao de release possui falhas.')
