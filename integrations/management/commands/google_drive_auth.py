"""Gera o refresh token OAuth para backup no Google Drive.

Uso:

    python manage.py google_drive_auth \
        --client-id SEU_CLIENT_ID \
        --client-secret SEU_CLIENT_SECRET

O comando abre o navegador padrao, solicita permissao ao usuario e imprime o
refresh_token que deve ser guardado em BACKUP_GDRIVE_REFRESH_TOKEN.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integrations.services.google_drive_oauth import (
    exchange_code_for_token,
    request_authorization_code,
)


class Command(BaseCommand):
    help = 'Gera refresh token OAuth para envio de backups ao Google Drive.'

    def add_arguments(self, parser):
        parser.add_argument('--client-id', required=True, help='Client ID OAuth 2.0')
        parser.add_argument('--client-secret', required=True, help='Client Secret OAuth 2.0')
        parser.add_argument(
            '--port',
            type=int,
            default=0,
            help='Porta local para o callback (0 = automatico).',
        )
        parser.add_argument(
            '--no-browser',
            action='store_true',
            help='Nao abre o navegador automaticamente; apenas imprime a URL de autorizacao.',
        )

    def handle(self, *args, **options):
        client_id = options['client_id']
        client_secret = options['client_secret']
        open_browser = not options['no_browser']

        self.stdout.write('Iniciando fluxo OAuth de usuario...')
        if open_browser:
            self.stdout.write('Um navegador sera aberto. Autorize o acesso ao Google Drive.')
        else:
            self.stdout.write('Abra a URL abaixo no navegador e autorize o acesso ao Google Drive.')

        try:
            code, verifier, redirect_uri = request_authorization_code(
                client_id, open_browser=open_browser
            )
            result = exchange_code_for_token(client_id, client_secret, code, redirect_uri, verifier)
        except Exception as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS('Refresh token gerado com sucesso!'))
        self.stdout.write('')
        self.stdout.write('Adicione a seguinte linha no seu .env:')
        self.stdout.write(self.style.WARNING(f'BACKUP_GDRIVE_REFRESH_TOKEN={result.refresh_token}'))
        self.stdout.write('')
        self.stdout.write('E mantenha tambem:')
        self.stdout.write(self.style.WARNING(f'BACKUP_GDRIVE_OAUTH_CLIENT_ID={client_id}'))
        self.stdout.write(self.style.WARNING(f'BACKUP_GDRIVE_OAUTH_CLIENT_SECRET={client_secret}'))
