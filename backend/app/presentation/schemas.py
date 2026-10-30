from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductOut(BaseModel):
    id: UUID
    title: str
    description: str
    price_cents: int
    stock: int
    image_url: str | None


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
    limit: int
    offset: int


class CartItemOut(BaseModel):
    product: ProductOut
    qty: int
    subtotal_cents: int


class CartOut(BaseModel):
    items: list[CartItemOut]
    total_cents: int


class AddToCartIn(BaseModel):
    product_id: UUID
    qty: int = Field(1, ge=1, le=99)


class OrderIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    customer_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=3, max_length=50)
    address: str = Field("", max_length=1000)


class OrderItemOut(BaseModel):
    product_id: UUID
    title: str
    unit_price_cents: int
    qty: int


class OrderOut(BaseModel):
    id: UUID
    status: str
    customer_name: str
    phone: str
    address: str
    total_cents: int
    created_at: datetime
    items: list[OrderItemOut]


class ProductCreateIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=5000)
    price_cents: int = Field(ge=0)
    stock: int = Field(ge=0)


class ImageUploadIn(BaseModel):
    content_type: Literal["image/png", "image/jpeg", "image/webp"]


class ImageUploadOut(BaseModel):
    method: Literal["PUT"] = "PUT"
    upload_url: str
    image_url: str
