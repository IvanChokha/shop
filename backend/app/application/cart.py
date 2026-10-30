from uuid import UUID

from app.application.ports import UnitOfWorkFactory
from app.domain.entities import Cart
from app.domain.errors import InvalidQuantity, OutOfStock, ProductNotFound

MAX_QTY = 99


class CartService:
    """Корзина живёт в БД под ключом сессии — любая реплика обслужит любой запрос."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow = uow_factory

    async def get(self, key: str) -> Cart:
        async with self._uow() as uow:
            return await uow.carts.get(key)

    async def add_item(self, key: str, product_id: UUID, qty: int = 1) -> Cart:
        if not 1 <= qty <= MAX_QTY:
            raise InvalidQuantity(qty, MAX_QTY)
        async with self._uow() as uow:
            product = await uow.products.get(product_id)
            if product is None or not product.is_active:
                raise ProductNotFound(product_id)
            cart = await uow.carts.get(key)
            # Мягкая проверка для UX; жёсткая (атомарная) — при оформлении заказа.
            if cart.qty_of(product_id) + qty > product.stock:
                raise OutOfStock(product.title)
            await uow.carts.add_item(key, product_id, qty)
            await uow.commit()
            return await uow.carts.get(key)

    async def remove_item(self, key: str, product_id: UUID) -> Cart:
        async with self._uow() as uow:
            await uow.carts.remove_item(key, product_id)
            await uow.commit()
            return await uow.carts.get(key)
