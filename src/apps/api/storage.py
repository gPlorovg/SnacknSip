from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings

class PublicMinioStorage(S3Boto3Storage):
    """
    Хранилище, которое использует внутренний URL для операций (upload/delete),
    но генерирует публичные ссылки на основе внешнего домена.
    """
    def url(self, name, parameters=None, expire=None, http_method=None):
        url = super().url(name, parameters, expire, http_method)

        # Если задан внешний домен, подменяем внутренний адрес (minio:9000) на внешний
        internal_url = (settings.AWS_S3_ENDPOINT_URL or "").rstrip("/")
        public_url = (getattr(settings, "MINIO_PUBLIC_URL", None) or "").rstrip("/")

        if public_url and internal_url:
            for candidate in (internal_url, internal_url.replace("http://", "https://")):
                if candidate in url:
                    return url.replace(candidate, public_url, 1)

        return url
