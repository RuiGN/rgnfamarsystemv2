from django.db import models


class OperationalRole(models.TextChoices):
    OWNER = 'owner', 'Proprietário'
    ADMIN = 'admin', 'Administrador'
    QUALITY = 'quality', 'Qualidade'
    PRODUCTION = 'production', 'Produção'
    REGULATORY = 'regulatory', 'Regulatório'
    FINANCE = 'finance', 'Financeiro'
    VIEWER = 'viewer', 'Leitura'


def user_has_operational_role(user, role):
    if not role:
        return True
    if not user or not getattr(user, 'is_authenticated', False) or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__iexact=str(role)).exists()
