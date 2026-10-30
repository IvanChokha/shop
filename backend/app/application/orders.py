from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.application.ports import UnitOfWorkFactory
from app.domain.entities import Order, OrderLine
from app.domain.errors import DuplicateOrder, EmptyCart, OrderNotFound, OutOfStock


class OrderService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow = uow_factory

    async def get_order(self, order_id: UUID) -> Order:
        async with self._uow() as uow:
            order = await uow.orders.get(order_id)
        if order is None:
            raise OrderNotFound(order_id)
        return order

    async def place_order(
        self,
        cart_key: str,
        *,
        name: str,
        phone: str,
        address: str = "",
        idempotency_key: str | None = None,
    ) -> Order:
        """Оформляет заказ из корзины одной транзакцией.

        Идемпотентность: повторный запрос с тем же ключом (двойной клик, ретрай,
        повторная доставка апдейта в боте) вернёт уже созданный заказ.
        """
        idempotency_key = idempotency_key or None  # пустая строка = ключа нет
        try:
            return await self._place(cart_key, name, phone, address, idempotency_key)
        except DuplicateOrder:
            # Параллельный запрос с тем же ключом на другой реплике успел закоммитить раньше.
            existing = await self._find(idempotency_key) if idempotency_key else None
            if existing is None:
                raise
            return existing

    async def _find(self, idempotency_key: str) -> Order | None:
        async with self._uow() as uow:
            return await uow.orders.get_by_idempotency_key(idempotency_key)

    async def _place(
        self, cart_key: str, name: str, phone: str, address: str, idempotency_key: str | None
    ) -> Order:
        async with self._uow() as uow:
            if idempotency_key:
                existing = await uow.orders.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    return existing

            cart = await uow.carts.get(cart_key)
            if not cart.lines:
                raise EmptyCart()

            lines: list[OrderLine] = []
            # Фиксированный порядок захвата строк products — иначе два заказа с
            # пересекающимися товарами на разных репликах могут взять дедлок.
            for line in sorted(cart.lines, key=lambda item: item.product.id):
                reserved = await uow.products.reserve(line.product.id, line.qty)
                if reserved is None:
                    raise OutOfStock(line.product.title)  # откат всей транзакции в __aexit__
                lines.append(
                    OrderLine(
                        product_id=reserved.id,
                        title=reserved.title,
                        unit_price_cents=reserved.price_cents,
                        qty=line.qty,
                    )
                )

            order = Order(
                id=uuid4(),
                customer_name=name,
                phone=phone,
                address=address,
                status="new",
                created_at=datetime.now(timezone.utc),
                lines=tuple(lines),
            )
            await uow.orders.add(order, idempotency_key)
            await uow.carts.clear(cart_key)
            await uow.commit()
            return order
