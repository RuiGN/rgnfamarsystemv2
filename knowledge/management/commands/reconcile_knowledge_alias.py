from django.core.management.base import BaseCommand

from knowledge.indexing import reconcile_active_alias


class Command(BaseCommand):
    help = 'Reconcilia idempotentemente o alias Redis com a geração ativa no banco.'

    def handle(self, *args, **options):
        del args, options
        generation = reconcile_active_alias()
        value = generation.generation_id if generation else 'none'
        self.stdout.write(f'knowledge_alias_active_generation={value}')
