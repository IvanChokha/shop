"""Сущности предметной области. Не зависят ни от FastAPI, ни от SQLAlchemy, ни от MinIO."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Product:
    id: UUID
    title: str
    description: str
    price_cents: int  # деньги храним в минорных единицах (копейки), без float
    stock: int
    image_key: str | None = None  # ключ объекта в MinIO
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class CartLine:
    product: Product
    qty: int

    @property
    def subtotal_cents(self) -> int:
        return self.product.price_cents * self.qty


@dataclass(frozen=True, slots=True)
class Cart:
    # Непрозрачный ключ анонимной сессии: cookie у веба, HMAC от telegram id у бота.
    key: str
    lines: tuple[CartLine, ...] = ()

    @property
    def total_cents(self) -> int:
        return sum(line.subtotal_cents for line in self.lines)

    def qty_of(self, product_id: UUID) -> int:
        return next((line.qty for line in self.lines if line.product.id == product_id), 0)


@dataclass(frozen=True, slots=True)
class OrderLine:
    product_id: UUID
    title: str  # снимок названия и цены на момент заказа
    unit_price_cents: int
    qty: int


@dataclass(frozen=True, slots=True)
class Order:
    id: UUID
    customer_name: str
    phone: str
    address: str
    status: str
    created_at: datetime
    lines: tuple[OrderLine, ...]

    @property
    def total_cents(self) -> int:
        return sum(line.unit_price_cents * line.qty for line in self.lines)
