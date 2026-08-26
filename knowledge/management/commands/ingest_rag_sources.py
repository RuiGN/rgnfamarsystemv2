from django.core.management.base import BaseCommand, CommandError

from knowledge.source_catalog import SEED_SOURCES
from knowledge.services import ingest_source


class Command(BaseCommand):
    help = 'Ingere fontes oficiais iniciais no banco de conhecimento RAG.'

    def add_arguments(self, parser):
        parser.add_argument('--source-code', action='append', default=[])
        parser.add_argument('--max-chunks-per-source', type=int, default=None)
        parser.add_argument('--timeout', type=int, default=30)
        parser.add_argument(
            '--rebuild-index',
            action='store_true',
            help='Constrói e ativa a geração do índice Redis após a ingestão.',
        )
        parser.add_argument('--generation-id', type=str, default='')

    def handle(self, *args, **options):
        selected_codes = set(options['source_code'] or [])
        sources = [
            source
            for source in SEED_SOURCES
            if not selected_codes or source['code'] in selected_codes
        ]
        if selected_codes and len(sources) != len(selected_codes):
            found = {source['code'] for source in sources}
            missing = ', '.join(sorted(selected_codes - found))
            raise CommandError(f'Fontes não encontradas no catálogo: {missing}')

        total_chunks = 0
        failures = 0
        for source in sources:
            self.stdout.write(f'Ingerindo {source["code"]}...')
            try:
                result = ingest_source(
                    source,
                    max_chunks=options['max_chunks_per_source'],
                    timeout=options['timeout'],
                )
            except Exception as error:
                failures += 1
                self.stderr.write(self.style.ERROR(f'{source["code"]}: falhou - {error}'))
                continue
            total_chunks += result['chunks_created']
            self.stdout.write(
                self.style.SUCCESS(
                    f'{source["code"]}: {result["status"]} ({result["chunks_created"]} chunks)'
                )
            )
        if failures:
            raise CommandError(
                f'Ingestão RAG incompleta: {failures} fonte(s) falharam; '
                f'chunks criados: {total_chunks}.'
            )
        self.stdout.write(
            self.style.SUCCESS(f'Corpus RAG atualizado. Chunks criados: {total_chunks}')
        )
        if options['rebuild_index']:
            self._rebuild_index(options)

    def _rebuild_index(self, options):
        from knowledge.indexing import build_index_generation
        from knowledge.models import KnowledgeIndexGeneration

        self.stdout.write('Construindo geração do índice Redis...')
        generation = build_index_generation(generation_id=options['generation_id'] or None)
        if generation.status != KnowledgeIndexGeneration.Status.ACTIVE:
            raise CommandError(
                f'Geração {generation.generation_id} não foi ativada (status={generation.status}).'
            )
        self.stdout.write(
            self.style.SUCCESS(
                f'Índice publicado. generation_id={generation.generation_id} '
                f'chunks={generation.chunk_count} embedding_model={generation.embedding_model}'
            )
        )
