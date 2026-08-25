"""Cliente do Google Drive baseado em Service Account ou OAuth de usuario.

A classe ``GoogleDriveUploader`` encapsula a autenticacao via:

* Service Account JSON (ideal para Google Workspace/Shared Drives);
* OAuth 2.0 de usuario (ideal para contas pessoais @gmail.com, onde service
  accounts nao possuem quota de armazenamento).

Oferece interface enxuta para o servico de backup:

* ``upload_file`` faz upload resumable, recomendado para dumps PostgreSQL
  potencialmente grandes;
* ``find_file_by_name`` localiza um arquivo ja enviado para evitar duplicidade;
* ``delete_file`` remove artefatos antigos para implementar retencao na nuvem.

A biblioteca ``google-api-python-client`` e importada em tempo de execucao para
nao quebrar o Django quando o servico nao estiver instalado (devs que rodam
testes sem a dependencia).
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from django.conf import settings


logger = logging.getLogger(__name__)

PathLike = Union[str, os.PathLike]


class GoogleDriveError(Exception):
    """Erro generico nas operacoes contra o Google Drive."""


class GoogleDriveAuthError(GoogleDriveError):
    """Falha ao carregar credenciais de Service Account ou OAuth."""


class GoogleDriveUploadError(GoogleDriveError):
    """Falha durante o upload de um arquivo."""


@dataclass(frozen=True)
class GoogleDriveFile:
    file_id: str
    name: str
    mime_type: str
    size_bytes: int
    web_view_link: str
    md5_checksum: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'file_id': self.file_id,
            'name': self.name,
            'mime_type': self.mime_type,
            'size_bytes': self.size_bytes,
            'web_view_link': self.web_view_link,
            'md5_checksum': self.md5_checksum,
        }


def _import_google_clients():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
    except ImportError as error:  # pragma: no cover - dependencia opcional
        raise GoogleDriveError(
            'Dependencias do Google Drive ausentes. Instale google-api-python-client e google-auth.'
        ) from error
    return service_account, build, HttpError, MediaFileUpload, MediaIoBaseUpload


SCOPES = ('https://www.googleapis.com/auth/drive.file',)


def _resolve_service_account_credentials(
    *,
    credentials_path: Optional[str],
    credentials_base64: Optional[str],
):
    service_account_module, _, _, _, _ = _import_google_clients()

    json_text: Optional[str] = None
    if credentials_path:
        path = Path(credentials_path)
        if not path.exists():
            raise GoogleDriveAuthError(f'Arquivo de credenciais nao encontrado: {path}')
        try:
            json_text = path.read_text(encoding='utf-8')
        except OSError as error:
            raise GoogleDriveAuthError(f'Falha ao ler credenciais: {error}') from error
    elif credentials_base64:
        try:
            json_text = base64.b64decode(credentials_base64).decode('utf-8')
        except (ValueError, UnicodeDecodeError) as error:
            raise GoogleDriveAuthError('Conteudo base64 da service account invalido.') from error
    else:
        raise GoogleDriveAuthError(
            'Defina BACKUP_GDRIVE_CREDENTIALS_PATH ou BACKUP_GDRIVE_CREDENTIALS_BASE64.'
        )

    try:
        return service_account_module.Credentials.from_service_account_info(
            __import__('json').loads(json_text),
            scopes=SCOPES,
        )
    except ValueError as error:
        raise GoogleDriveAuthError(f'JSON da service account invalido: {error}') from error


def _resolve_oauth_credentials(
    refresh_token: Optional[str],
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
):
    if not refresh_token:
        raise GoogleDriveAuthError('BACKUP_GDRIVE_REFRESH_TOKEN nao configurado.')
    try:
        from integrations.services.google_drive_oauth import credentials_from_refresh_token
    except ImportError as error:
        raise GoogleDriveAuthError('Modulo google_drive_oauth nao disponivel.') from error
    return credentials_from_refresh_token(
        refresh_token,
        client_id=client_id,
        client_secret=client_secret,
    )


def _resolve_credentials(
    *,
    credentials_path: Optional[str],
    credentials_base64: Optional[str],
    refresh_token: Optional[str] = None,
    oauth_client_id: Optional[str] = None,
    oauth_client_secret: Optional[str] = None,
):
    """Resolve credenciais priorizando OAuth, depois Service Account."""
    if refresh_token:
        return _resolve_oauth_credentials(
            refresh_token,
            client_id=oauth_client_id,
            client_secret=oauth_client_secret,
        )
    return _resolve_service_account_credentials(
        credentials_path=credentials_path,
        credentials_base64=credentials_base64,
    )


def _build_service(credentials):
    _, build, _, _, _ = _import_google_clients()
    return build('drive', 'v3', credentials=credentials, cache_discovery=False)


class GoogleDriveUploader:
    """Wrapper de alto nivel para o servico ``drive.files``."""

    def __init__(
        self,
        *,
        folder_id: str,
        credentials_path: Optional[str] = None,
        credentials_base64: Optional[str] = None,
        refresh_token: Optional[str] = None,
        oauth_client_id: Optional[str] = None,
        oauth_client_secret: Optional[str] = None,
        service: Any = None,
    ) -> None:
        if not folder_id:
            raise GoogleDriveError('folder_id do Drive e obrigatorio.')
        self.folder_id = folder_id
        self._service = service or _build_service(
            _resolve_credentials(
                credentials_path=credentials_path,
                credentials_base64=credentials_base64,
                refresh_token=refresh_token,
                oauth_client_id=oauth_client_id,
                oauth_client_secret=oauth_client_secret,
            )
        )

    @classmethod
    def from_settings(cls) -> 'GoogleDriveUploader':
        folder_id = getattr(settings, 'BACKUP_GDRIVE_FOLDER_ID', '') or os.environ.get(
            'BACKUP_GDRIVE_FOLDER_ID', ''
        )
        credentials_path = os.environ.get('BACKUP_GDRIVE_CREDENTIALS_PATH', '') or None
        credentials_base64 = os.environ.get('BACKUP_GDRIVE_CREDENTIALS_BASE64', '') or None
        refresh_token = os.environ.get('BACKUP_GDRIVE_REFRESH_TOKEN', '') or None
        oauth_client_id = os.environ.get('BACKUP_GDRIVE_OAUTH_CLIENT_ID', '') or None
        oauth_client_secret = os.environ.get('BACKUP_GDRIVE_OAUTH_CLIENT_SECRET', '') or None

        if not credentials_path:
            credentials_file = '/run/secrets/GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON'
            if os.path.exists(credentials_file):
                credentials_path = credentials_file

        return cls(
            folder_id=folder_id,
            credentials_path=credentials_path,
            credentials_base64=credentials_base64,
            refresh_token=refresh_token,
            oauth_client_id=oauth_client_id,
            oauth_client_secret=oauth_client_secret,
        )

    def _files_api(self):
        return self._service.files()

    def ping(self) -> dict[str, Any]:
        """Verifica conectividade consultando ``about``."""
        _, _, HttpError, _, _ = _import_google_clients()
        try:
            about = self._files_api().get(fileId='about', fields='user').execute()
        except HttpError as error:  # pragma: no cover - depende de rede
            raise GoogleDriveError(f'Falha ao consultar Drive: {error}') from error
        return about or {}

    def find_file_by_name(self, name: str) -> Optional[GoogleDriveFile]:
        """Procura arquivo pelo nome dentro da pasta configurada."""
        _, _, HttpError, _, _ = _import_google_clients()
        query = (
            f"name = '{name.replace(chr(39), chr(39) + chr(39))}' "
            f"and '{self.folder_id}' in parents and trashed = false"
        )
        try:
            response = (
                self._files_api()
                .list(
                    q=query,
                    spaces='drive',
                    fields='files(id,name,mimeType,size,webViewLink,md5Checksum)',
                    pageSize=5,
                )
                .execute()
            )
        except HttpError as error:  # pragma: no cover
            raise GoogleDriveError(f'Falha ao listar arquivos: {error}') from error
        files = response.get('files', [])
        if not files:
            return None
        first = files[0]
        return GoogleDriveFile(
            file_id=first['id'],
            name=first.get('name', name),
            mime_type=first.get('mimeType', ''),
            size_bytes=int(first.get('size', 0) or 0),
            web_view_link=first.get('webViewLink', ''),
            md5_checksum=first.get('md5Checksum', ''),
        )

    def upload_file(
        self,
        source_path: PathLike,
        *,
        target_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        description: str = '',
    ) -> GoogleDriveFile:
        """Envia um arquivo local para a pasta do Drive.

        Utiliza ``MediaFileUpload(resumable=True)`` para suportar arquivos
        grandes sem carregar tudo em memoria.
        """
        path = Path(os.fspath(source_path))
        if not path.exists() or not path.is_file():
            raise GoogleDriveUploadError(f'Arquivo invalido para upload: {path}')

        name = target_name or path.name
        detected_mime, _ = mimetypes.guess_type(name)
        body: dict[str, Any] = {'name': name, 'parents': [self.folder_id]}
        if description:
            body['description'] = description

        _, _, HttpError, MediaFileUpload, _ = _import_google_clients()
        media = MediaFileUpload(
            str(path),
            mimetype=mime_type or detected_mime or 'application/octet-stream',
            resumable=True,
        )
        try:
            created = (
                self._files_api()
                .create(
                    body=body,
                    media_body=media,
                    fields='id,name,mimeType,size,webViewLink,md5Checksum',
                )
                .execute()
            )
        except HttpError as error:  # pragma: no cover - depende de rede
            raise GoogleDriveUploadError(f'Falha no upload para o Drive: {error}') from error
        except OSError as error:
            raise GoogleDriveUploadError(f'Falha de I/O no upload: {error}') from error

        logger.info(
            'Backup enviado para o Google Drive: %s (file_id=%s)',
            created.get('name'),
            created.get('id'),
        )
        return GoogleDriveFile(
            file_id=created['id'],
            name=created.get('name', name),
            mime_type=created.get('mimeType', ''),
            size_bytes=int(created.get('size', 0) or 0),
            web_view_link=created.get('webViewLink', ''),
            md5_checksum=created.get('md5Checksum', ''),
        )

    def delete_file(self, file_id: str) -> bool:
        _, _, HttpError, _, _ = _import_google_clients()
        try:
            self._files_api().delete(fileId=file_id).execute()
        except HttpError as error:  # pragma: no cover
            if (
                getattr(error, 'resp', None) is not None
                and getattr(error.resp, 'status', None) == 404
            ):
                return False
            raise GoogleDriveError(f'Falha ao remover arquivo {file_id}: {error}') from error
        return True


def build_uploader_from_mapping(payload: Mapping[str, str]) -> GoogleDriveUploader:
    return GoogleDriveUploader(
        folder_id=payload.get('folder_id', ''),
        credentials_path=payload.get('credentials_path') or None,
        credentials_base64=payload.get('credentials_base64') or None,
        refresh_token=payload.get('refresh_token') or None,
        oauth_client_id=payload.get('oauth_client_id') or None,
        oauth_client_secret=payload.get('oauth_client_secret') or None,
    )
