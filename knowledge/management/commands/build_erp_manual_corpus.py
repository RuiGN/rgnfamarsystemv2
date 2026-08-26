from django.core.management.base import BaseCommand, CommandError

from knowledge.manual_catalog import manual_entries
from knowledge.services import ingest_source


class Command(BaseCommand):
    help = 'Gera e ingere o manual funcional dos módulos do ERP.'

    def add_arguments(self, parser):
        parser.add_argument('--module', action='append', default=[])
        parser.add_argument('--rebuild-index', action='store_true')

    def handle(self, *args, **options):
        entries = manual_entries()
        selected = set(options['module'] or [])
        if selected:
            entries = [entry for entry in entries if entry['metadata']['module_slug'] in selected]
            found = {entry['metadata']['module_slug'] for entry in entries}
            missing = selected - found
            if missing:
                raise CommandError('Módulos não encontrados: ' + ', '.join(sorted(missing)))

        total_chunks = 0
        for entry in entries:
            result = ingest_source(entry)
            total_chunks += result['chunks_created']
            self.stdout.write(
                self.style.SUCCESS(
                    f'{entry["metadata"]["module_slug"]}: {result["chunks_created"]} chunks'
                )
            )
        self.stdout.write(self.style.SUCCESS(f'Manual ERP ingerido: {total_chunks} chunks.'))
        if options['rebuild_index']:
            from knowledge.indexing import build_index_generation
            from knowledge.models import KnowledgeIndexGeneration

            generation = build_index_generation()
            if generation.status != KnowledgeIndexGeneration.Status.ACTIVE:
                raise CommandError('A geração do índice do manual não foi ativada.')
            self.stdout.write(self.style.SUCCESS('Índice do manual ERP ativado.'))
