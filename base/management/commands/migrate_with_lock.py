from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


LOCK_KEY = 883019730


class Command(BaseCommand):
    help = 'Executa migrations usando advisory lock no PostgreSQL.'

    def add_arguments(self, parser):
        parser.add_argument('--noinput', '--no-input', action='store_false', dest='interactive')

    def handle(self, *args, **options):
        interactive = options.get('interactive', True)
        if connection.vendor != 'postgresql':
            self.stdout.write('Banco não PostgreSQL; executando migrate sem advisory lock.')
            call_command('migrate', interactive=interactive)
            return

        with connection.cursor() as cursor:
            self.stdout.write('Obtendo advisory lock para migrations...')
            cursor.execute('SELECT pg_advisory_lock(%s);', [LOCK_KEY])
            try:
                call_command('migrate', interactive=interactive)
            finally:
                cursor.execute('SELECT pg_advisory_unlock(%s);', [LOCK_KEY])
                self.stdout.write(self.style.SUCCESS('Advisory lock liberado.'))
