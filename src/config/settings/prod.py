"""Production settings."""

from decouple import config

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK

# Строго выключаем DEBUG
DEBUG = config("DEBUG", default=False, cast=bool)

# Toggle for deployments behind real HTTPS termination.
# If site is served only via http://, set USE_HTTPS=false in .env.prod.
USE_HTTPS = config("USE_HTTPS", default=False, cast=bool)

# Разрешаем домен для CSRF
CSRF_TRUSTED_ORIGINS = [
    "https://snacknsip.ru",
    "https://www.snacknsip.ru",
]
if not USE_HTTPS:
    CSRF_TRUSTED_ORIGINS += [
        "http://snacknsip.ru",
        "http://www.snacknsip.ru",
    ]
CSRF_COOKIE_SAMESITE = "Lax"

# Настройки безопасности за прокси (Nginx)
if USE_HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 год
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
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
