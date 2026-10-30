import re
import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from app.application.cart import CartService
from app.application.catalog import CatalogService
from app.application.orders import OrderService
from app.application.ports import ImageStorage
from app.config import get_settings

CART_KEY_RE = re.compile(r"[A-Za-z0-9_-]{16,128}")


@dataclass(frozen=True)
class Services:
    """Контейнер зависимостей. Собирается один раз в main.py (composition root)."""

    catalog: CatalogService
    cart: CartService
    orders: OrderService
    storage: ImageStorage


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_cart_key(x_cart_key: Annotated[str | None, Header()] = None) -> str:
    """Ключ анонимной сессии. Хранит его клиент (cookie / HMAC в боте), сервер — нет."""
    if not x_cart_key or not CART_KEY_RE.fullmatch(x_cart_key):
        raise HTTPException(
            status_code=400,
            detail="Нужен заголовок X-Cart-Key (16–128 символов: A-Z a-z 0-9 _ -)",
        )
    return x_cart_key


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().admin_token.encode()
    if not x_admin_token or not secrets.compare_digest(x_admin_token.encode(), expected):
        raise HTTPException(status_code=401, detail="Неверный X-Admin-Token")


ServicesDep = Annotated[Services, Depends(get_services)]
CartKeyDep = Annotated[str, Depends(get_cart_key)]
