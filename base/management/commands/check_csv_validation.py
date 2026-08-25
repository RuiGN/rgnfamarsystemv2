from django.core.management.base import BaseCommand, CommandError

from core.csv_validation import evaluate_csv_validation


class Command(BaseCommand):
    help = 'Valida a matriz de rastreabilidade CSV.'

    def add_arguments(self, parser):
        parser.add_argument('--format', choices=('text', 'json'), default='text')
        parser.add_argument('--fail-on-error', action='store_true')

    def handle(self, *args, **options):
        report = evaluate_csv_validation()
        if options['format'] == 'json':
            self.stdout.write(report.to_json())
        else:
            self.stdout.write(f'csv_validation: aprovado={report.passed}')
            for finding in report.findings:
                self.stdout.write(
                    f'- {finding.requirement_id}: {finding.status} - {finding.evidence}'
                )
        if options['fail_on_error'] and not report.passed:
            raise CommandError('Matriz CSV possui falhas.')
