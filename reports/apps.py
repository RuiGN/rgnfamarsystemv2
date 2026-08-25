from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reports'
    verbose_name = 'relatórios e BI'

    def ready(self) -> None:
        from reports import executors  # noqa: F401
