from django.core.management.base import BaseCommand, CommandError

from knowledge.source_catalog import SEED_SOURCES
from knowledge.services import ingest_source


class Command(BaseCommand):
    help = 'Ingere fontes oficiais iniciais no banco de conhecimento RAG.'

    def add_arguments(self, parser):
        parser.add_argument('--source-code', action='append', default=[])
        parser.add_argument('--max-chunks-per-source', type=int, default=None)
        parser.add_argument('--timeout', type=int, default=30)

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
            self.stdout.write(
                self.style.WARNING(
                    f'Corpus RAG atualizado com {failures} falha(s). Chunks criados: {total_chunks}'
                )
            )
            return
        self.stdout.write(
            self.style.SUCCESS(f'Corpus RAG atualizado. Chunks criados: {total_chunks}')
        )
