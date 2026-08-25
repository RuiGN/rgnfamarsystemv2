import time

from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connections


class Command(BaseCommand):
    help = 'Aguarda o banco de dados padrão ficar disponível.'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=60)
        parser.add_argument('--interval', type=float, default=1.0)

    def handle(self, *args, **options):
        timeout = options['timeout']
        interval = options['interval']
        started_at = time.monotonic()

        self.stdout.write('Aguardando banco de dados...')
        while True:
            try:
                connections['default'].ensure_connection()
                self.stdout.write(self.style.SUCCESS('Banco de dados disponível.'))
                return
            except OperationalError as exc:
                if time.monotonic() - started_at >= timeout:
                    raise CommandError('Banco de dados indisponível no tempo limite.') from exc
                time.sleep(interval)
