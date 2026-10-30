from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    bot_token: str
    # polling — только для разработки и строго 1 реплика (иначе Telegram отвечает 409 Conflict).
    # webhook — для 2+ реплик за балансировщиком.
    bot_mode: Literal["polling", "webhook"] = "polling"
    webhook_base_url: str = ""  # публичный https-адрес, напр. https://shop.example.com
    webhook_path: str = "/telegram/webhook"
    webhook_secret: str = ""  # проверяется на каждом входящем апдейте
    port: int = 8080

    api_url: str = "http://backend:8000"
    # Секрет, из которого выводится ключ корзины пользователя. Состояния в боте нет:
    # любая реплика получит тот же ключ для того же telegram id.
    cart_secret: str = "change-me-too"

    s3_public_url: str = "http://localhost:9000"  # как backend отдаёт image_url
    s3_internal_url: str = "http://minio:9000"  # как бот сам ходит за картинками
