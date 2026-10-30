"""Тесты прикладного слоя без БД и без сторонних пакетов: use case'ы работают поверх портов.

Запуск (из каталога backend):  python -m unittest discover -s tests -t .
"""

import copy
import unittest
from dataclasses import replace
from uuid import UUID, uuid4

from app.application.cart import CartService
from app.application.orders import OrderService
from app.domain.entities import Cart, CartLine, Order, Product
from app.domain.errors import DuplicateOrder, EmptyCart, OutOfStock

KEY = "k" * 16


class FakeDb:
    def __init__(self) -> None:
        self.products: dict[UUID, Product] = {}
        self.cart_items: dict[str, dict[UUID, int]] = {}
        self.orders: dict[UUID, Order] = {}
        self.order_keys: dict[str, UUID] = {}
        self.hide_existing_once = False  # эмуляция гонки: «другая реплика» ещё не закоммитила

    def snapshot(self):
        return copy.deepcopy((self.products, self.cart_items, self.orders, self.order_keys))

    def restore(self, snap) -> None:
        self.products, self.cart_items, self.orders, self.order_keys = snap


class FakeProducts:
    def __init__(self, db: FakeDb) -> None:
        self.db = db

    async def list_active(self, limit, offset):
        items = [p for p in self.db.products.values() if p.is_active]
        return items[offset : offset + limit], len(items)

    async def get(self, product_id):
        return self.db.products.get(product_id)

    async def add(self, product):
        self.db.products[product.id] = product

    async def set_image(self, product_id, image_key):
        self.db.products[product_id] = replace(self.db.products[product_id], image_key=image_key)

    async def reserve(self, product_id, qty):
        product = self.db.products.get(product_id)
        if product is None or not product.is_active or product.stock < qty:
            return None
        product = replace(product, stock=product.stock - qty)
        self.db.products[product_id] = product
        return product


class FakeCarts:
    def __init__(self, db: FakeDb) -> None:
        self.db = db

    async def get(self, key):
        items = self.db.cart_items.get(key, {})
        lines = tuple(CartLine(self.db.products[pid], qty) for pid, qty in items.items())
        return Cart(key=key, lines=lines)

    async def add_item(self, key, product_id, qty):
        items = self.db.cart_items.setdefault(key, {})
        items[product_id] = items.get(product_id, 0) + qty

    async def remove_item(self, key, product_id):
        self.db.cart_items.get(key, {}).pop(product_id, None)

    async def clear(self, key):
        self.db.cart_items.pop(key, None)


class FakeOrders:
    def __init__(self, db: FakeDb) -> None:
        self.db = db

    async def add(self, order, idempotency_key):
        if idempotency_key is not None and idempotency_key in self.db.order_keys:
            raise DuplicateOrder()
        self.db.orders[order.id] = order
        if idempotency_key is not None:
            self.db.order_keys[idempotency_key] = order.id

    async def get(self, order_id):
        return self.db.orders.get(order_id)

    async def get_by_idempotency_key(self, key):
        if self.db.hide_existing_once:
            self.db.hide_existing_once = False
            return None
        order_id = self.db.order_keys.get(key)
        return self.db.orders.get(order_id) if order_id else None


class FakeUow:
    """Откатывает изменения, если commit() не вызван, — как настоящая транзакция."""

    def __init__(self, db: FakeDb) -> None:
        self.db = db
        self.products = FakeProducts(db)
        self.carts = FakeCarts(db)
        self.orders = FakeOrders(db)
        self._committed = False

    async def __aenter__(self):
        self._snapshot = self.db.snapshot()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if not self._committed:
            self.db.restore(self._snapshot)

    async def commit(self):
        self._committed = True


def make_product(title: str, stock: int, price: int) -> Product:
    return Product(id=uuid4(), title=title, description="", price_cents=price, stock=stock)


class OrderServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.db = FakeDb()
        factory = lambda: FakeUow(self.db)  # noqa: E731
        self.cart = CartService(factory)
        self.orders = OrderService(factory)
        self.a = make_product("A", stock=5, price=1000)
        self.b = make_product("B", stock=1, price=2500)
        for product in (self.a, self.b):
            self.db.products[product.id] = product

    async def test_order_reserves_stock_and_clears_cart(self):
        await self.cart.add_item(KEY, self.a.id, 2)
        order = await self.orders.place_order(KEY, name="Иван", phone="+79990000000")
        self.assertEqual(order.total_cents, 2000)
        self.assertEqual(self.db.products[self.a.id].stock, 3)
        self.assertEqual((await self.cart.get(KEY)).lines, ())

    async def test_empty_cart_is_rejected(self):
        with self.assertRaises(EmptyCart):
            await self.orders.place_order(KEY, name="Иван", phone="+79990000000")

    async def test_cannot_add_more_than_stock(self):
        with self.assertRaises(OutOfStock):
            await self.cart.add_item(KEY, self.b.id, 2)

    async def test_out_of_stock_rolls_back_whole_order(self):
        await self.cart.add_item(KEY, self.a.id, 1)
        await self.cart.add_item(KEY, self.b.id, 1)
        # Пока клиент думал, товар B раскупили (другая реплика / другой канал).
        self.db.products[self.b.id] = replace(self.b, stock=0)
        with self.assertRaises(OutOfStock):
            await self.orders.place_order(KEY, name="Иван", phone="+79990000000")
        self.assertEqual(self.db.products[self.a.id].stock, 5)  # списание A откатилось
        self.assertEqual(len((await self.cart.get(KEY)).lines), 2)  # корзина не тронута
        self.assertEqual(self.db.orders, {})

    async def test_same_idempotency_key_returns_same_order(self):
        await self.cart.add_item(KEY, self.a.id, 1)
        first = await self.orders.place_order(KEY, name="Иван", phone="+7999", idempotency_key="k-1")
        again = await self.orders.place_order(KEY, name="Иван", phone="+7999", idempotency_key="k-1")
        self.assertEqual(first.id, again.id)
        self.assertEqual(self.db.products[self.a.id].stock, 4)  # списано один раз

    async def test_idempotency_race_between_replicas(self):
        await self.cart.add_item(KEY, self.a.id, 1)
        first = await self.orders.place_order(KEY, name="Иван", phone="+7999", idempotency_key="k-1")
        await self.cart.add_item(KEY, self.a.id, 1)
        self.db.hide_existing_once = True  # проверка «уже есть?» ничего не нашла → упадём на unique
        second = await self.orders.place_order(KEY, name="Иван", phone="+7999", idempotency_key="k-1")
        self.assertEqual(first.id, second.id)
        self.assertEqual(self.db.products[self.a.id].stock, 4)  # второе списание откатилось

    async def test_empty_idempotency_key_means_no_key(self):
        await self.cart.add_item(KEY, self.a.id, 1)
        first = await self.orders.place_order(KEY, name="Иван", phone="+7999", idempotency_key="")
        await self.cart.add_item(KEY, self.a.id, 1)
        second = await self.orders.place_order(KEY, name="Иван", phone="+7999", idempotency_key="")
        self.assertNotEqual(first.id, second.id)  # два разных заказа, а не «дубль» по пустому ключу


if __name__ == "__main__":
    unittest.main()
