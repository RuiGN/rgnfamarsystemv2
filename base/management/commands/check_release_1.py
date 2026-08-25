from django.core.management.base import BaseCommand, CommandError
from core.release_1 import evaluate_release_1


class Command(BaseCommand):
    def add_arguments(self, p):
        p.add_argument('--release-version', dest='release_version', default='1.0.0')
        p.add_argument('--fail-on-error', action='store_true')

    def handle(self, *a, **o):
        r = evaluate_release_1(o['release_version'])
        self.stdout.write(r.to_json())
        if o['fail_on_error'] and not r.passed:
            raise CommandError('Release 1.0 possui falhas.')
