import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.api import ShopApi
from app.config import Settings
from app.handlers import router

log = logging.getLogger("bot")


def build(settings: Settings) -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Dispatcher без FSM-хранилища в деле: диалоговое состояние в процессе не держим.
    dp = Dispatcher()
    dp.include_router(router)
    dp["settings"] = settings
    dp["api"] = ShopApi(
        httpx.AsyncClient(base_url=settings.api_url, timeout=10),
        cart_secret=settings.cart_secret,
        s3_public_url=settings.s3_public_url,
        s3_internal_url=settings.s3_internal_url,
    )
    dp.shutdown.register(close_api)
    return bot, dp


async def close_api(api: ShopApi) -> None:
    await api.aclose()


async def set_webhook(bot: Bot, settings: Settings) -> None:
    # Идемпотентно: все реплики регистрируют один и тот же URL.
    await bot.set_webhook(
        f"{settings.webhook_base_url.rstrip('/')}{settings.webhook_path}",
        secret_token=settings.webhook_secret,
        allowed_updates=["message", "callback_query"],
    )


async def healthz(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    await bot.delete_webhook()
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    bot, dp = build(settings)

    if settings.bot_mode == "polling":
        log.warning("Режим polling: запускайте строго одну реплику")
        asyncio.run(run_polling(bot, dp))
        return

    if not settings.webhook_base_url or not settings.webhook_secret:
        raise SystemExit("Для BOT_MODE=webhook нужны WEBHOOK_BASE_URL и WEBHOOK_SECRET")

    dp.startup.register(set_webhook)
    app = web.Application()
    app.router.add_get("/healthz", healthz)
    # handle_in_background=False: отвечаем Telegram после обработки; при сбое он повторит
    # доставку — дубль безопасен благодаря идемпотентному оформлению заказа.
    SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=settings.webhook_secret, handle_in_background=False
    ).register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
