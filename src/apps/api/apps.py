"""SnacknSip API application configuration."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api"
    verbose_name = "SnacknSip API"

    def ready(self) -> None:
        # Register schema extensions (e.g., custom auth) for drf-spectacular.
        from apps.api import schema  # noqa: F401
