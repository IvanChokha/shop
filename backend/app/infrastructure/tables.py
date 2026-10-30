"""Описание таблиц (SQLAlchemy Core). Единственное место, где живёт схема БД."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Uuid,
    func,
    true,
)

metadata = MetaData()

products = Table(
    "products",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("title", String(200), nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("price_cents", Integer, nullable=False),
    Column("stock", Integer, nullable=False),
    Column("image_key", String(300)),
    Column("is_active", Boolean, nullable=False, server_default=true()),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("price_cents >= 0", name="ck_products_price"),
    CheckConstraint("stock >= 0", name="ck_products_stock"),
)

carts = Table(
    "carts",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("key", String(128), nullable=False, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

cart_items = Table(
    "cart_items",
    metadata,
    Column("cart_id", Uuid, ForeignKey("carts.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", Uuid, ForeignKey("products.id"), primary_key=True),
    Column("qty", Integer, nullable=False),
    CheckConstraint("qty > 0", name="ck_cart_items_qty"),
)

orders = Table(
    "orders",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("idempotency_key", String(128), unique=True),
    Column("customer_name", String(200), nullable=False),
    Column("phone", String(50), nullable=False),
    Column("address", Text, nullable=False, server_default=""),
    Column("status", String(20), nullable=False, server_default="new"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

order_items = Table(
    "order_items",
    metadata,
    Column("order_id", Uuid, ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", Uuid, ForeignKey("products.id"), primary_key=True),
    Column("title", String(200), nullable=False),
    Column("unit_price_cents", Integer, nullable=False),
    Column("qty", Integer, nullable=False),
)
