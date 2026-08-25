# Auditoria de segurança

Execute `python manage.py check_security_audit --fail-on-error` para verificar
configuração explícita de DEBUG, chave, origens CSRF e cookies. O comando é um
gate de hardening e não substitui pentest autorizado.
