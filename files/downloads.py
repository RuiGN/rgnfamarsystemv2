import os
import re

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers
from django.utils.http import content_disposition_header

from core.crypto import EncryptionKeyConfigurationError
from files.models import ProtectedFileAuditTrail


_MIME_TYPE_PATTERN = re.compile(
    r'^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+(?:;[ \t]*charset=[A-Za-z0-9_-]+)?$'
)


def protected_file_client_metadata(request):
    return {
        'ip_address': request.META.get('REMOTE_ADDR') or None,
        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
    }


def _safe_download_name(file_name):
    basename = os.path.basename(str(file_name or '').replace('\\', '/'))
    basename = ''.join(character for character in basename if 31 < ord(character) != 127)
    return basename[:180] or 'arquivo-protegido'


def _safe_mime_type(mime_type):
    candidate = str(mime_type or '').strip()
    return candidate if _MIME_TYPE_PATTERN.fullmatch(candidate) else 'application/octet-stream'


def protected_file_download_response(
    protected_file,
    *,
    user,
    ip_address='',
    user_agent='',
):
    try:
        content = protected_file.read_encrypted_content(
            user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except (
        OSError,
        UnicodeError,
        ValueError,
        EncryptionKeyConfigurationError,
    ) as error:
        protected_file.record_audit(
            ProtectedFileAuditTrail.Action.ACCESS_DENIED,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            details={'reason': 'content_unavailable'},
        )
        raise ValidationError({'file': 'Arquivo protegido indisponível.'}) from error
    protected_file.record_access(
        user,
        ProtectedFileAuditTrail.Action.DOWNLOAD,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    response = HttpResponse(content, content_type=_safe_mime_type(protected_file.mime_type))
    response['Content-Disposition'] = content_disposition_header(
        True,
        _safe_download_name(protected_file.file_name),
    )
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    patch_vary_headers(response, ('Authorization', 'Cookie'))
    return response
