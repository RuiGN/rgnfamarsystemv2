from django.core.management.base import BaseCommand

from core.crypto import generate_aes256_key


class Command(BaseCommand):
    help = 'Gera uma chave AES-256 em base64 URL-safe para DATA_ENCRYPTION_KEYS.'

    def add_arguments(self, parser):
        parser.add_argument('--key-id', default='primary', help='Identificador lógico da chave.')

    def handle(self, *args, **options):
        key_id = options['key_id']
        if ':' in key_id or not key_id.strip():
            raise SystemExit('key-id não pode ser vazio nem conter dois-pontos.')
        self.stdout.write(f'{key_id}:{generate_aes256_key()}')
