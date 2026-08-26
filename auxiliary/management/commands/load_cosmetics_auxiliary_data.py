from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from auxiliary.cosmetics_seed import seed_cosmetics_auxiliary_data


class Command(BaseCommand):
    help = 'Carrega referências auxiliares pt-BR para uma indústria cosmética.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-official-references',
            action='store_true',
            help='Carrega primeiro países, UFs, municípios e moedas oficiais.',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=60,
            help='Tempo limite das requisições oficiais, entre 1 e 300 segundos.',
        )

    def handle(self, *args, **options):
        timeout = options['timeout']
        if timeout < 1 or timeout > 300:
            raise CommandError('--timeout deve estar entre 1 e 300 segundos.')

        if options['with_official_references']:
            call_command('load_official_reference_data', timeout=timeout)

        counts = seed_cosmetics_auxiliary_data()
        summary = ', '.join(f'{key}={value}' for key, value in counts.items())
        self.stdout.write(
            self.style.SUCCESS(f'Carga auxiliar cosmética concluída: {summary}.')
        )
