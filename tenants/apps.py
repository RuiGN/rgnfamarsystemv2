from django.apps import AppConfig


class HistoricalTenancyConfig(AppConfig):
    """
    DEPRECATED: Module maintained temporarily to preserve migration history
    during the single-instance architecture transition.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tenants'
    verbose_name = 'Historical scope migrations'
