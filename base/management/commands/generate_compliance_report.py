import json

from django.core.management.base import BaseCommand

from core.compliance_reports import generate_compliance_report, report_markdown


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--format', choices=('json', 'markdown'), default='json')
        parser.add_argument('--framework')
        parser.add_argument('--status')
        parser.add_argument('--output')

    def handle(self, *args, **options):
        payload = generate_compliance_report(options['framework'], options['status'])
        content = (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if options['format'] == 'json'
            else report_markdown(payload)
        )
        if options['output']:
            with open(options['output'], 'w', encoding='utf-8') as stream:
                stream.write(content)
        else:
            self.stdout.write(content)
