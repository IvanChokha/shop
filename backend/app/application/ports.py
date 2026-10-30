"""Порты: интерфейсы, которые application-слой требует от внешнего мира.

Реализации лежат в infrastructure; use case'ы про SQLAlchemy и MinIO ничего не знают.
"""

from collections.abc import Callable, Sequence
from typing import Protocol
from uuid import UUID

from app.domain.entities import Cart, Order, Product


class ProductRepository(Protocol):
    async def list_active(self, limit: int, offset: int) -> tuple[Sequence[Product], int]: ...
    async def get(self, product_id: UUID) -> Product | None: ...
    async def add(self, product: Product) -> None: ...
    async def set_image(self, product_id: UUID, image_key: str) -> None: ...

    async def reserve(self, product_id: UUID, qty: int) -> Product | None:
        """Атомарно списывает остаток. None — если товара нет/неактивен/не хватает."""
        ...


class CartRepository(Protocol):
    async def get(self, key: str) -> Cart:
        """Корзина по ключу сессии; если её ещё нет — пустая."""
        ...

    async def add_item(self, key: str, product_id: UUID, qty: int) -> None: ...
    async def remove_item(self, key: str, product_id: UUID) -> None: ...
    async def clear(self, key: str) -> None: ...


class OrderRepository(Protocol):
    async def add(self, order: Order, idempotency_key: str | None) -> None:
        """Бросает DuplicateOrder, если заказ с таким idempotency_key уже есть."""
        ...

    async def get(self, order_id: UUID) -> Order | None: ...
    async def get_by_idempotency_key(self, key: str) -> Order | None: ...


class UnitOfWork(Protocol):
    """Одна бизнес-транзакция. Создаётся на каждый запрос, между запросами ничего не хранит."""

    products: ProductRepository
    carts: CartRepository
    orders: OrderRepository

    async def __aenter__(self) -> "UnitOfWork": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...
    async def commit(self) -> None: ...


UnitOfWorkFactory = Callable[[], UnitOfWork]


class ImageStorage(Protocol):
    def public_url(self, key: str) -> str: ...

    def presign_upload(self, key: str) -> str:
        """Подписанный PUT-URL: файл уходит из клиента прямо в хранилище, мимо API и диска."""
        ...
