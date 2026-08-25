import time

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, OperationalError, connections
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = 'Aguarda todas as migrations do banco padrão estarem aplicadas.'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=300)
        parser.add_argument('--interval', type=float, default=2.0)

    def handle(self, *args, **options):
        timeout = options['timeout']
        interval = options['interval']
        started_at = time.monotonic()
        last_error = None
        pending_labels = ''

        self.stdout.write('Aguardando migrations aplicadas...')
        while True:
            try:
                connection = connections['default']
                connection.ensure_connection()
                executor = MigrationExecutor(connection)
                targets = executor.loader.graph.leaf_nodes()
                pending = executor.migration_plan(targets)
                if not pending:
                    self.stdout.write(self.style.SUCCESS('Migrations aplicadas.'))
                    return
                pending_labels = ', '.join(
                    f'{migration.app_label}.{migration.name}'
                    for migration, _backwards in pending[:5]
                )
                last_error = None
            except (OperationalError, DatabaseError) as exc:
                last_error = exc

            if time.monotonic() - started_at >= timeout:
                detail = f' Pendentes: {pending_labels}.' if pending_labels else ''
                if last_error is not None:
                    detail = f' Último erro: {last_error}.'
                raise CommandError(f'Migrations não aplicadas no tempo limite.{detail}')

            time.sleep(interval)
