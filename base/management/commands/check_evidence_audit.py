from django.core.management.base import BaseCommand, CommandError

from core.evidence_audit import evaluate_evidence_catalog


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--format', choices=('text', 'json'), default='text')
        parser.add_argument('--fail-on-error', action='store_true')

    def handle(self, *args, **options):
        report = evaluate_evidence_catalog()
        if options['format'] == 'json':
            self.stdout.write(report.to_json())
        else:
            self.stdout.write(f'evidence_audit: aprovado={report.passed}')
            for item in report.findings:
                self.stdout.write(f'- {item.evidence_id}: {item.status} - {item.message}')
        if options['fail_on_error'] and not report.passed:
            raise CommandError('Catálogo de evidências possui falhas.')
