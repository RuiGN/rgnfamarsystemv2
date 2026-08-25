"""Backends de e-mail customizados do projeto."""

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend


class ErrorEmailBackend(EmailBackend):
    """
    Backend SMTP exclusivo para envio de notificacoes de erro.

    Le as configuracoes das variaveis ERROR_EMAIL_* do settings, permitindo
    usar um servidor de e-mail diferente do configurado para envio de nota
    fiscal e outras comunicacoes do sistema.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('host', settings.ERROR_EMAIL_HOST)
        kwargs.setdefault('port', settings.ERROR_EMAIL_PORT)
        kwargs.setdefault('username', settings.ERROR_EMAIL_HOST_USER)
        kwargs.setdefault('password', settings.ERROR_EMAIL_HOST_PASSWORD)
        kwargs.setdefault('use_tls', settings.ERROR_EMAIL_USE_TLS)
        kwargs.setdefault('use_ssl', settings.ERROR_EMAIL_USE_SSL)
        kwargs.setdefault('fail_silently', True)
        super().__init__(**kwargs)
