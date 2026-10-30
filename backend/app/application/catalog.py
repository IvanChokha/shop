from uuid import UUID, uuid4

from app.application.ports import ImageStorage, UnitOfWorkFactory
from app.domain.entities import Product
from app.domain.errors import ProductNotFound, UnsupportedImageType

IMAGE_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


class CatalogService:
    def __init__(self, uow_factory: UnitOfWorkFactory, storage: ImageStorage) -> None:
        self._uow = uow_factory
        self._storage = storage

    async def list_products(self, limit: int, offset: int) -> tuple[list[Product], int]:
        async with self._uow() as uow:
            items, total = await uow.products.list_active(limit, offset)
        return list(items), total

    async def get_product(self, product_id: UUID) -> Product:
        async with self._uow() as uow:
            product = await uow.products.get(product_id)
        if product is None or not product.is_active:
            raise ProductNotFound(product_id)
        return product

    async def create_product(
        self, *, title: str, description: str, price_cents: int, stock: int
    ) -> Product:
        product = Product(
            id=uuid4(), title=title, description=description, price_cents=price_cents, stock=stock
        )
        async with self._uow() as uow:
            await uow.products.add(product)
            await uow.commit()
        return product

    async def prepare_image_upload(self, product_id: UUID, content_type: str) -> tuple[str, str]:
        """Возвращает (presigned PUT URL, публичный URL картинки).

        Ключ объекта привязывается к товару сразу; сам файл клиент зальёт напрямую в MinIO.
        """
        extension = IMAGE_EXTENSIONS.get(content_type)
        if extension is None:
            raise UnsupportedImageType(content_type)
        key = f"products/{product_id}/{uuid4().hex}.{extension}"
        async with self._uow() as uow:
            if await uow.products.get(product_id) is None:
                raise ProductNotFound(product_id)
            await uow.products.set_image(product_id, key)
            await uow.commit()
        return self._storage.presign_upload(key), self._storage.public_url(key)
