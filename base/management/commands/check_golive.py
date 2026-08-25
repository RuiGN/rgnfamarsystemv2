from django.core.management.base import BaseCommand, CommandError
from core.golive import evaluate_golive


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--format', choices=('text', 'json'), default='text')
        parser.add_argument('--fail-on-error', action='store_true')

    def handle(self, *args, **options):
        report = evaluate_golive()
        if options['format'] == 'json':
            self.stdout.write(report.to_json())
        else:
            self.stdout.write(f'golive: aprovado={report.passed}')
            for item in report.checks:
                self.stdout.write(f'- {item.code}: {item.passed} - {item.evidence}')
        if options['fail_on_error'] and not report.passed:
            raise CommandError('Checklist de go-live possui falhas.')
