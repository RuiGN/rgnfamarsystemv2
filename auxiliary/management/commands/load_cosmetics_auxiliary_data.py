from django.core.management import call_command
from django.core.management.base import BaseCommand

from auxiliary.cosmetics_seed import seed_cosmetics_auxiliary_data
from auxiliary.reference_snapshots import load_official_snapshot
from reference_data.cosmetics_catalogs import COSMETICS_CATALOG_MANIFEST
from reference_data.services import seed_production_reference_data


class Command(BaseCommand):
    help = 'Carrega referências auxiliares pt-BR para uma indústria cosmética.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-official-references',
            action='store_true',
            help='Carrega primeiro países, UFs, municípios e moedas oficiais.',
        )
        parser.add_argument(
            '--production-catalogs',
            action='store_true',
            help='Carrega atomicamente todos os catálogos versionados de produção.',
        )

    def handle(self, *args, **options):
        if options['production_catalogs']:
            official_manifest = load_official_snapshot().manifest
            result = seed_production_reference_data()
            versions = {
                official_manifest.identifier: official_manifest.version,
                COSMETICS_CATALOG_MANIFEST.identifier: COSMETICS_CATALOG_MANIFEST.version,
            }
            manifests = ', '.join(
                f'{identifier}: versão={versions[identifier]}; sha256={sha256[:12]}'
                for identifier, sha256 in sorted(result.manifest_hashes.items())
            )
            count_summary = ', '.join(
                f'{group}.{key}={value}'
                for group, group_counts in sorted(result.counts.items())
                for key, value in sorted(group_counts.items())
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Catálogos de produção concluídos: {manifests}; contagens: {count_summary}.'
                )
            )
            return

        if options['with_official_references']:
            call_command('load_official_reference_data')

        counts = seed_cosmetics_auxiliary_data()
        summary = ', '.join(f'{key}={value}' for key, value in counts.items())
        self.stdout.write(self.style.SUCCESS(f'Carga auxiliar cosmética concluída: {summary}.'))
