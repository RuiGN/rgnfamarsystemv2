from django.core.management import call_command
from django.core.management.base import BaseCommand

from auxiliary.cosmetics_seed import seed_cosmetics_auxiliary_data


class Command(BaseCommand):
    help = 'Carrega referências auxiliares pt-BR para uma indústria cosmética.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-official-references',
            action='store_true',
            help='Carrega primeiro países, UFs, municípios e moedas oficiais.',
        )

    def handle(self, *args, **options):
        if options['with_official_references']:
            call_command('load_official_reference_data')

        counts = seed_cosmetics_auxiliary_data()
        summary = ', '.join(f'{key}={value}' for key, value in counts.items())
        self.stdout.write(self.style.SUCCESS(f'Carga auxiliar cosmética concluída: {summary}.'))
