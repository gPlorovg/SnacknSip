"""Local (development) settings."""

from .base import *  # noqa: F401, F403

DEBUG = True

# Для разработки можно использовать SQLite
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }

# В dev выводим письма в консоль (если понадобятся)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# В dev используем локальную файловую систему вместо MinIO (опционально)
# STORAGES = {
#     "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
#     "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
# }
