from django.core.management.base import BaseCommand

from auxiliary.reference_snapshots import apply_official_snapshot, load_official_snapshot


class Command(BaseCommand):
    help = 'Carrega países, UFs, municípios e moedas do snapshot oficial versionado local.'

    def handle(self, *args, **options):
        snapshot = load_official_snapshot()
        counts = apply_official_snapshot(snapshot)
        summary = ', '.join(f'{key}={value}' for key, value in counts.items())
        self.stdout.write(
            self.style.SUCCESS(
                f'Carga oficial versionada concluída: {summary}; '
                f'versão={snapshot.manifest.version}; sha256={snapshot.manifest.sha256}.'
            )
        )
