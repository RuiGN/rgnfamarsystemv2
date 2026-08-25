"""Autenticacao OAuth de usuario para o Google Drive.

Quando a conta do Google e pessoal (@gmail.com), service accounts nao tem
quota de armazenamento. A solucao e usar OAuth 2.0 de usuario: o dono da
conta autoriza o aplicativo uma unica vez e o refresh token e armazenado de
forma segura (Docker secret ou variavel de ambiente cifrada).

Este modulo fornece:

* ``request_authorization_code``: inicia o fluxo local server e retorna o
  codigo de autorizacao;
* ``exchange_code_for_token``: troca o codigo por access/refresh tokens;
* ``credentials_from_refresh_token``: cria ``Credentials`` a partir do
  refresh token salvo, para uso no upload.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import socket
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

from django.conf import settings


SCOPES = ['https://www.googleapis.com/auth/drive.file']
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_OAUTH_ENDPOINT = 'https://oauth2.googleapis.com/token'


@dataclass(frozen=True)
class OAuthTokenResult:
    """Resultado do fluxo de troca do codigo por tokens."""

    refresh_token: str
    access_token: str
    expires_in: int
    token_type: str
    scope: str


def _generate_pkce_pair() -> tuple[str, str]:
    """Gera um par code_verifier/code_challenge para PKCE."""
    verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8').rstrip('=')
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('utf-8')).digest())
        .decode('utf-8')
        .rstrip('=')
    )
    return verifier, challenge


def _find_free_port(start: int = 8080, end: int = 8100) -> int:
    """Encontra uma porta livre no localhost para o callback OAuth."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(('localhost', port)) != 0:
                return port
    raise RuntimeError('Nenhuma porta livre encontrada para o callback OAuth')


def request_authorization_code(
    client_id: str,
    redirect_uri: str = 'http://127.0.0.1:8080/oauth2callback',
    timeout: int = 120,
    open_browser: bool = True,
) -> tuple[str, str, str]:
    """Inicia o fluxo OAuth e devolve (codigo, code_verifier, redirect_uri).

    Abre o navegador padrao do sistema e sobe um servidor HTTP temporario no
    localhost para capturar o codigo retornado pelo Google. Utiliza PKCE para
    seguranca adicional.
    """
    port = _find_free_port()
    redirect_uri = f'http://localhost:{port}/oauth2callback'
    verifier, challenge = _generate_pkce_pair()
    state = secrets.token_urlsafe(16)

    auth_request_url = (
        f'{AUTH_URL}?'
        f'client_id={client_id}&'
        f'redirect_uri={redirect_uri}&'
        f'response_type=code&'
        f'scope={"+".join(SCOPES)}&'
        f'state={state}&'
        f'code_challenge={challenge}&'
        f'code_challenge_method=S256&'
        f'access_type=offline&'
        f'prompt=consent'
    )

    authorization_code: Optional[str] = None
    received_state: Optional[str] = None

    class _CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal authorization_code, received_state
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            authorization_code = query.get('code', [None])[0]
            received_state = query.get('state', [None])[0]
            error = query.get('error', [None])[0]

            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            if error:
                self.wfile.write(
                    f'<h1>Erro OAuth: {error}</h1><p>Pode fechar esta aba.</p>'.encode('utf-8')
                )
            else:
                self.wfile.write(b'<h1>Autorizacao recebida</h1><p>Pode fechar esta aba.</p>')

        def log_message(self, format, *args):
            pass

    server = HTTPServer(('localhost', port), _CallbackHandler)
    server.timeout = timeout

    print(f'Callback: {redirect_uri}')
    if open_browser:
        print('Abrindo navegador para autorizacao...')
        webbrowser.open(auth_request_url)
    else:
        print(f'URL de autorizacao:\n{auth_request_url}')

    server.handle_request()
    server.server_close()

    if received_state != state:
        raise RuntimeError('Parametro state do OAuth nao confere. Possivel ataque CSRF.')
    if not authorization_code:
        raise RuntimeError('Codigo de autorizacao nao recebido.')

    return authorization_code, verifier, redirect_uri


def exchange_code_for_token(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str = 'http://localhost:8080/oauth2callback',
    code_verifier: str = '',
) -> OAuthTokenResult:
    """Troca o codigo de autorizacao por access/refresh tokens."""
    import urllib.request

    data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }
    if code_verifier:
        data['code_verifier'] = code_verifier
    req = urllib.request.Request(
        GOOGLE_OAUTH_ENDPOINT,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    # req sempre usa GOOGLE_OAUTH_ENDPOINT, constante HTTPS definida neste módulo.
    with urllib.request.urlopen(req, timeout=30) as response:  # nosec B310
        payload = json.loads(response.read().decode('utf-8'))

    refresh_token = payload.get('refresh_token')
    if not refresh_token:
        raise RuntimeError(
            'Google nao retornou refresh_token. '
            'Tente revogar o acesso do app em myaccount.google.com/permissions e repetir.'
        )

    return OAuthTokenResult(
        refresh_token=refresh_token,
        access_token=payload['access_token'],
        expires_in=payload.get('expires_in', 3600),
        token_type=payload.get('token_type', 'Bearer'),
        scope=payload.get('scope', ''),
    )


def credentials_from_refresh_token(
    refresh_token: str,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
):
    """Cria Credentials do Google a partir de um refresh token salvo."""
    from google.oauth2.credentials import Credentials

    client_id = client_id or os.environ.get('BACKUP_GDRIVE_OAUTH_CLIENT_ID', '')
    client_secret = client_secret or os.environ.get('BACKUP_GDRIVE_OAUTH_CLIENT_SECRET', '')
    if not client_id or not client_secret:
        raise RuntimeError(
            'BACKUP_GDRIVE_OAUTH_CLIENT_ID e BACKUP_GDRIVE_OAUTH_CLIENT_SECRET sao obrigatorios.'
        )

    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=GOOGLE_OAUTH_ENDPOINT,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )


def load_oauth_credentials_from_settings():
    """Carrega Credentials OAuth a partir das configuracoes do projeto."""
    refresh_token = getattr(settings, 'BACKUP_GDRIVE_REFRESH_TOKEN', '') or os.environ.get(
        'BACKUP_GDRIVE_REFRESH_TOKEN', ''
    )
    if not refresh_token:
        raise RuntimeError('BACKUP_GDRIVE_REFRESH_TOKEN nao configurado.')
    return credentials_from_refresh_token(refresh_token)
