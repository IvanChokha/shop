from collections.abc import Sequence
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Cart, CartLine, Order, OrderLine, Product
from app.domain.errors import DuplicateOrder
from app.infrastructure.tables import cart_items, carts, order_items, orders, products


def _product(row) -> Product:
    return Product(
        id=row.id,
        title=row.title,
        description=row.description,
        price_cents=row.price_cents,
        stock=row.stock,
        image_key=row.image_key,
        is_active=row.is_active,
    )


class SqlProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_active(self, limit: int, offset: int) -> tuple[Sequence[Product], int]:
        stmt = (
            select(products)
            .where(products.c.is_active)
            .order_by(products.c.title, products.c.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).all()
        total = (
            await self._s.execute(
                select(func.count()).select_from(products).where(products.c.is_active)
            )
        ).scalar_one()
        return [_product(row) for row in rows], total

    async def get(self, product_id: UUID) -> Product | None:
        row = (await self._s.execute(select(products).where(products.c.id == product_id))).first()
        return _product(row) if row else None

    async def add(self, product: Product) -> None:
        await self._s.execute(
            insert(products).values(
                id=product.id,
                title=product.title,
                description=product.description,
                price_cents=product.price_cents,
                stock=product.stock,
                image_key=product.image_key,
                is_active=product.is_active,
            )
        )

    async def set_image(self, product_id: UUID, image_key: str) -> None:
        await self._s.execute(
            update(products).where(products.c.id == product_id).values(image_key=image_key)
        )

    async def reserve(self, product_id: UUID, qty: int) -> Product | None:
        # Одно атомарное условное UPDATE: гонки между репликами решает сама БД
        # (строка блокируется, условие stock >= qty перепроверяется после ожидания).
        stmt = (
            update(products)
            .where(products.c.id == product_id, products.c.is_active, products.c.stock >= qty)
            .values(stock=products.c.stock - qty)
            .returning(*products.c)
        )
        row = (await self._s.execute(stmt)).first()
        return _product(row) if row else None


class SqlCartRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, key: str) -> Cart:
        stmt = (
            select(cart_items.c.qty, *products.c)
            .select_from(
                carts.join(cart_items, cart_items.c.cart_id == carts.c.id).join(
                    products, products.c.id == cart_items.c.product_id
                )
            )
            .where(carts.c.key == key)
            .order_by(products.c.title)
        )
        rows = (await self._s.execute(stmt)).all()
        return Cart(key=key, lines=tuple(CartLine(product=_product(r), qty=r.qty) for r in rows))

    async def _get_or_create_id(self, key: str) -> UUID:
        stmt = (
            pg_insert(carts)
            .values(id=uuid4(), key=key)
            .on_conflict_do_nothing(index_elements=[carts.c.key])
            .returning(carts.c.id)
        )
        cart_id = (await self._s.execute(stmt)).scalar_one_or_none()
        if cart_id is not None:
            return cart_id
        # Корзину уже создал параллельный запрос (возможно, с другой реплики).
        return (await self._s.execute(select(carts.c.id).where(carts.c.key == key))).scalar_one()

    async def add_item(self, key: str, product_id: UUID, qty: int) -> None:
        cart_id = await self._get_or_create_id(key)
        stmt = pg_insert(cart_items).values(cart_id=cart_id, product_id=product_id, qty=qty)
        stmt = stmt.on_conflict_do_update(
            index_elements=[cart_items.c.cart_id, cart_items.c.product_id],
            set_={"qty": cart_items.c.qty + stmt.excluded.qty},
        )
        await self._s.execute(stmt)

    async def remove_item(self, key: str, product_id: UUID) -> None:
        cart_id = select(carts.c.id).where(carts.c.key == key).scalar_subquery()
        await self._s.execute(
            delete(cart_items).where(
                cart_items.c.cart_id == cart_id, cart_items.c.product_id == product_id
            )
        )

    async def clear(self, key: str) -> None:
        cart_id = select(carts.c.id).where(carts.c.key == key).scalar_subquery()
        await self._s.execute(delete(cart_items).where(cart_items.c.cart_id == cart_id))


class SqlOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, order: Order, idempotency_key: str | None) -> None:
        try:
            await self._s.execute(
                insert(orders).values(
                    id=order.id,
                    idempotency_key=idempotency_key,
                    customer_name=order.customer_name,
                    phone=order.phone,
                    address=order.address,
                    status=order.status,
                    created_at=order.created_at,
                )
            )
        except IntegrityError as exc:
            if idempotency_key is None:
                raise
            raise DuplicateOrder() from exc
        await self._s.execute(
            insert(order_items),
            [
                {
                    "order_id": order.id,
                    "product_id": line.product_id,
                    "title": line.title,
                    "unit_price_cents": line.unit_price_cents,
                    "qty": line.qty,
                }
                for line in order.lines
            ],
        )

    async def get(self, order_id: UUID) -> Order | None:
        return await self._load(orders.c.id == order_id)

    async def get_by_idempotency_key(self, key: str) -> Order | None:
        return await self._load(orders.c.idempotency_key == key)

    async def _load(self, where) -> Order | None:
        row = (await self._s.execute(select(orders).where(where))).first()
        if row is None:
            return None
        items = (
            await self._s.execute(
                select(order_items)
                .where(order_items.c.order_id == row.id)
                .order_by(order_items.c.title)
            )
        ).all()
        return Order(
            id=row.id,
            customer_name=row.customer_name,
            phone=row.phone,
            address=row.address,
            status=row.status,
            created_at=row.created_at,
            lines=tuple(
                OrderLine(
                    product_id=i.product_id,
                    title=i.title,
                    unit_price_cents=i.unit_price_cents,
                    qty=i.qty,
                )
                for i in items
            ),
        )
