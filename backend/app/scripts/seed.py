"""Идемпотентная инициализация: бакет MinIO + демо-товары (только если каталог пуст).

Запускается один раз как отдельная задача (init-контейнер / k8s Job), а не из реплик API.
"""

import asyncio
import logging
import struct
import time
import zlib
from uuid import uuid4

from sqlalchemy import func, insert, select

from app.config import get_settings
from app.infrastructure.db import create_engine
from app.infrastructure.storage import MinioImageStorage, create_storage
from app.infrastructure.tables import products

log = logging.getLogger("seed")

# (название, описание, цена в копейках, остаток, цвет картинки)
DEMO = [
    ("Кружка «Hello, World»", "Керамическая кружка, 350 мл.", 59_000, 50, (52, 120, 246)),
    ("Футболка «Python»", "Хлопок, унисекс, размеры S–XL.", 149_000, 30, (46, 160, 90)),
    ("Стикерпак «Dev»", "20 виниловых наклеек для ноутбука.", 25_000, 100, (230, 126, 34)),
    ("Блокнот «TODO»", "А5, 96 листов, точечная разметка.", 39_000, 80, (142, 68, 173)),
    ("Термос 500 мл", "Нержавеющая сталь, держит тепло 12 часов.", 199_000, 20, (192, 57, 43)),
    ("Рюкзак «Commit»", "Отделение для ноутбука 15\", водоотталкивающая ткань.", 349_000, 10, (44, 62, 80)),
]


def solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Минимальный PNG с вертикальным градиентом. Без Pillow и без временных файлов."""
    rows = []
    for y in range(height):
        k = 1 - 0.35 * y / height
        pixel = bytes(int(c * k) for c in rgb)
        rows.append(b"\x00" + pixel * width)  # \x00 — фильтр строки «None»

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8 бит, RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )


def wait_for_storage(storage: MinioImageStorage, attempts: int = 30) -> None:
    for attempt in range(1, attempts + 1):
        try:
            storage.ensure_bucket()
            return
        except Exception as exc:  # noqa: BLE001 — MinIO может ещё стартовать
            log.warning("MinIO не готов (%s), попытка %s/%s", exc, attempt, attempts)
            time.sleep(2)
    raise RuntimeError("MinIO недоступен")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    storage = create_storage(settings)
    await asyncio.to_thread(wait_for_storage, storage)

    engine = create_engine(settings.database_url, pool_size=1)
    async with engine.begin() as conn:
        count = (await conn.execute(select(func.count()).select_from(products))).scalar_one()
        if count:
            log.info("Каталог не пуст (%s товаров) — демо-данные не добавляю", count)
        else:
            for title, description, price, stock, rgb in DEMO:
                product_id = uuid4()
                key = f"products/{product_id}/main.png"
                await asyncio.to_thread(storage.put, key, solid_png(480, 320, rgb), "image/png")
                await conn.execute(
                    insert(products).values(
                        id=product_id,
                        title=title,
                        description=description,
                        price_cents=price,
                        stock=stock,
                        image_key=key,
                    )
                )
            log.info("Добавлено %s демо-товаров", len(DEMO))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
