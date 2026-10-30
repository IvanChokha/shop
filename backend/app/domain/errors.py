"""Доменные ошибки. HTTP-коды к ним привязывает только слой presentation."""

from uuid import UUID


class DomainError(Exception):
    """Базовая ошибка предметной области."""


class ProductNotFound(DomainError):
    def __init__(self, product_id: UUID) -> None:
        super().__init__(f"Товар {product_id} не найден")


class OrderNotFound(DomainError):
    def __init__(self, order_id: UUID) -> None:
        super().__init__(f"Заказ {order_id} не найден")


class OutOfStock(DomainError):
    def __init__(self, title: str) -> None:
        super().__init__(f"Недостаточно товара на складе: {title}")


class EmptyCart(DomainError):
    def __init__(self) -> None:
        super().__init__("Корзина пуста")


class InvalidQuantity(DomainError):
    def __init__(self, qty: int, maximum: int) -> None:
        super().__init__(f"Количество должно быть от 1 до {maximum}, получено {qty}")


class UnsupportedImageType(DomainError):
    def __init__(self, content_type: str) -> None:
        super().__init__(f"Неподдерживаемый тип изображения: {content_type}")


class DuplicateOrder(DomainError):
    """Заказ с таким Idempotency-Key уже создан (гонка между репликами)."""
