from django.core.management.base import BaseCommand, CommandError
from core.sre_health import evaluate_sre_health


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--format', choices=('text', 'json'), default='text')
        parser.add_argument('--fail-on-error', action='store_true')

    def handle(self, *args, **options):
        report = evaluate_sre_health()
        if options['format'] == 'json':
            self.stdout.write(report.to_json())
        else:
            self.stdout.write(f'sre_health: aprovado={report.passed}')
            for x in report.checks:
                self.stdout.write(f'- {x.code}: {x.passed} - {x.evidence}')
        if options['fail_on_error'] and not report.passed:
            raise CommandError('SRE health possui falhas.')
