from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Вся конфигурация — из переменных окружения (12-factor). Локального состояния нет."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+asyncpg://shop:shop@db:5432/shop"
    db_pool_size: int = 5

    s3_endpoint: str = "minio:9000"  # адрес MinIO внутри сети кластера
    s3_public_url: str = "http://localhost:9000"  # адрес MinIO, каким его видит браузер
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "shop"
    s3_region: str = "us-east-1"
    s3_secure: bool = False
    presign_ttl_seconds: int = 600

    admin_token: str = "change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
