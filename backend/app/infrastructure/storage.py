import io
import json
from datetime import timedelta
from urllib.parse import urlparse

from minio import Minio

from app.config import Settings


class MinioImageStorage:
    """Картинки живут только в MinIO. На диск сервиса ничего не пишется.

    Загрузка — через presigned PUT: байты идут от клиента прямо в MinIO, минуя API.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        public_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
        secure: bool,
        presign_ttl_seconds: int,
    ) -> None:
        self._bucket = bucket
        self._public = public_url.rstrip("/")
        self._ttl = timedelta(seconds=presign_ttl_seconds)
        self._client = Minio(endpoint, access_key, secret_key, secure=secure, region=region)
        # Подпись включает host, поэтому подписываем тем адресом, который увидит браузер.
        # region задан явно → presign считается локально, без сетевых запросов.
        public = urlparse(self._public)
        self._signer = Minio(
            public.netloc,
            access_key,
            secret_key,
            secure=public.scheme == "https",
            region=region,
        )

    # --- порт ImageStorage (используется на горячем пути, I/O нет) -----------------------
    def public_url(self, key: str) -> str:
        return f"{self._public}/{self._bucket}/{key}"

    def presign_upload(self, key: str) -> str:
        return self._signer.presigned_put_object(self._bucket, key, expires=self._ttl)

    # --- только для init-скрипта (синхронные, в запросах не вызываются) ------------------
    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self._bucket}/*"],
                }
            ],
        }
        self._client.set_bucket_policy(self._bucket, json.dumps(policy))

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            self._bucket, key, io.BytesIO(data), len(data), content_type=content_type
        )


def create_storage(settings: Settings) -> MinioImageStorage:
    return MinioImageStorage(
        endpoint=settings.s3_endpoint,
        public_url=settings.s3_public_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
        secure=settings.s3_secure,
        presign_ttl_seconds=settings.presign_ttl_seconds,
    )
