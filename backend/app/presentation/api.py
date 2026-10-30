from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query

from app.application.ports import ImageStorage
from app.domain.entities import Cart, Order, Product
from app.presentation import schemas
from app.presentation.deps import CartKeyDep, ServicesDep, require_admin

router = APIRouter(prefix="/api/v1")
admin_router = APIRouter(
    prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


# --- domain → schema ---------------------------------------------------------------------
def _product(p: Product, storage: ImageStorage) -> schemas.ProductOut:
    return schemas.ProductOut(
        id=p.id,
        title=p.title,
        description=p.description,
        price_cents=p.price_cents,
        stock=p.stock,
        image_url=storage.public_url(p.image_key) if p.image_key else None,
    )


def _cart(cart: Cart, storage: ImageStorage) -> schemas.CartOut:
    return schemas.CartOut(
        items=[
            schemas.CartItemOut(
                product=_product(line.product, storage),
                qty=line.qty,
                subtotal_cents=line.subtotal_cents,
            )
            for line in cart.lines
        ],
        total_cents=cart.total_cents,
    )


def _order(order: Order) -> schemas.OrderOut:
    return schemas.OrderOut(
        id=order.id,
        status=order.status,
        customer_name=order.customer_name,
        phone=order.phone,
        address=order.address,
        total_cents=order.total_cents,
        created_at=order.created_at,
        items=[
            schemas.OrderItemOut(
                product_id=line.product_id,
                title=line.title,
                unit_price_cents=line.unit_price_cents,
                qty=line.qty,
            )
            for line in order.lines
        ],
    )


# --- каталог -----------------------------------------------------------------------------
@router.get("/products", response_model=schemas.ProductPage, tags=["catalog"])
async def list_products(
    svc: ServicesDep,
    limit: int = Query(12, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    items, total = await svc.catalog.list_products(limit, offset)
    return schemas.ProductPage(
        items=[_product(p, svc.storage) for p in items], total=total, limit=limit, offset=offset
    )


@router.get("/products/{product_id}", response_model=schemas.ProductOut, tags=["catalog"])
async def get_product(product_id: UUID, svc: ServicesDep):
    return _product(await svc.catalog.get_product(product_id), svc.storage)


# --- корзина (ключ сессии — заголовок X-Cart-Key) ----------------------------------------
@router.get("/cart", response_model=schemas.CartOut, tags=["cart"])
async def get_cart(svc: ServicesDep, cart_key: CartKeyDep):
    return _cart(await svc.cart.get(cart_key), svc.storage)


@router.post("/cart/items", response_model=schemas.CartOut, tags=["cart"])
async def add_to_cart(body: schemas.AddToCartIn, svc: ServicesDep, cart_key: CartKeyDep):
    cart = await svc.cart.add_item(cart_key, body.product_id, body.qty)
    return _cart(cart, svc.storage)


@router.delete("/cart/items/{product_id}", response_model=schemas.CartOut, tags=["cart"])
async def remove_from_cart(product_id: UUID, svc: ServicesDep, cart_key: CartKeyDep):
    return _cart(await svc.cart.remove_item(cart_key, product_id), svc.storage)


# --- заказы ------------------------------------------------------------------------------
@router.post("/orders", response_model=schemas.OrderOut, status_code=201, tags=["orders"])
async def create_order(
    body: schemas.OrderIn,
    svc: ServicesDep,
    cart_key: CartKeyDep,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
):
    order = await svc.orders.place_order(
        cart_key,
        name=body.customer_name,
        phone=body.phone,
        address=body.address,
        idempotency_key=idempotency_key,
    )
    return _order(order)


@router.get("/orders/{order_id}", response_model=schemas.OrderOut, tags=["orders"])
async def get_order(order_id: UUID, svc: ServicesDep):
    return _order(await svc.orders.get_order(order_id))


# --- админка (X-Admin-Token) -------------------------------------------------------------
@admin_router.post("/products", response_model=schemas.ProductOut, status_code=201)
async def create_product(body: schemas.ProductCreateIn, svc: ServicesDep):
    product = await svc.catalog.create_product(
        title=body.title,
        description=body.description,
        price_cents=body.price_cents,
        stock=body.stock,
    )
    return _product(product, svc.storage)


@admin_router.post("/products/{product_id}/image", response_model=schemas.ImageUploadOut)
async def request_image_upload(product_id: UUID, body: schemas.ImageUploadIn, svc: ServicesDep):
    upload_url, image_url = await svc.catalog.prepare_image_upload(product_id, body.content_type)
    return schemas.ImageUploadOut(upload_url=upload_url, image_url=image_url)
