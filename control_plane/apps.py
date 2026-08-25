from django.apps import AppConfig


class ControlPlaneConfig(AppConfig):
    """
    DEPRECATED: Module maintained temporarily to preserve migration history
    during the single-instance architecture transition.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'control_plane'
    verbose_name = 'Histórico do Control Plane'
