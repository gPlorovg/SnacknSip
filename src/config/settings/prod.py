"""Production settings."""

from decouple import config

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK

# Строго выключаем DEBUG
DEBUG = config("DEBUG", default=False, cast=bool)

# Настройки безопасности за прокси (Nginx)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 год
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Отключаем browsable API интерфейс в проде
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = ("rest_framework.renderers.JSONRenderer",)

# Логирование (пишем в stdout/stderr для сборки логов Docker)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "apps.api": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
