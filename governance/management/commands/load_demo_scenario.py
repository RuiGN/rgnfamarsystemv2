from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from governance.models import DemoScenarioLoad


class Command(BaseCommand):
    help = 'Carrega dados fake/demonstracao de governanca para a instancia local.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scenario', nargs='+', choices=DemoScenarioLoad.Scenario.values, required=True
        )
        parser.add_argument('--user-email', default='', dest='user_email')

    def handle(self, *args, **options):
        user = None
        user_email = options.get('user_email') or ''
        if user_email:
            user = get_user_model().objects.filter(email=user_email).first()
            if user is None:
                raise CommandError(f'Usuario "{user_email}" nao encontrado.')
            if not user.is_active:
                raise CommandError('Usuario informado esta inativo.')

        scenarios = options.get('scenario') or []
        for scenario in scenarios:
            load = DemoScenarioLoad.objects.create(scenario=scenario, requested_by=user)
            load.run(user=user)
            self.stdout.write(
                self.style.SUCCESS(
                    f'{scenario}: {load.status} '
                    f'parametros={load.records_created.get("parameters", 0)} '
                    f'catalogos={load.records_created.get("catalog_items", 0)}'
                )
            )
