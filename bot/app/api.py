import hashlib
import hmac
from typing import Any
from uuid import UUID

import httpx


class ApiError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class ShopApi:
    """Тонкий клиент к backend. Своего состояния нет."""

    def __init__(
        self, http: httpx.AsyncClient, *, cart_secret: str, s3_public_url: str, s3_internal_url: str
    ) -> None:
        self._http = http
        self._secret = cart_secret.encode()
        self._public = s3_public_url.rstrip("/")
        self._internal = s3_internal_url.rstrip("/")

    def cart_key(self, user_id: int) -> str:
        # Детерминированный и непредсказуемый без секрета: чужую корзину не подобрать.
        digest = hmac.new(self._secret, f"tg:{user_id}".encode(), hashlib.sha256).hexdigest()
        return f"tg_{digest[:48]}"

    async def _call(
        self,
        method: str,
        path: str,
        *,
        user_id: int | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Any:
        headers = dict(headers or {})
        if user_id is not None:
            headers["X-Cart-Key"] = self.cart_key(user_id)
        resp = await self._http.request(method, f"/api/v1{path}", headers=headers, **kwargs)
        if resp.is_error:
            detail = None
            try:
                body = resp.json()
                detail = body.get("detail") if isinstance(body, dict) else None
            except ValueError:
                pass
            raise ApiError(resp.status_code, detail if isinstance(detail, str) else "Ошибка сервиса")
        return resp.json()

    async def products(self, page: int, size: int) -> dict:
        return await self._call("GET", "/products", params={"limit": size, "offset": page * size})

    async def product(self, product_id: UUID | str) -> dict:
        return await self._call("GET", f"/products/{product_id}")

    async def cart(self, user_id: int) -> dict:
        return await self._call("GET", "/cart", user_id=user_id)

    async def add_to_cart(self, user_id: int, product_id: UUID | str) -> dict:
        return await self._call(
            "POST", "/cart/items", user_id=user_id, json={"product_id": str(product_id), "qty": 1}
        )

    async def remove_from_cart(self, user_id: int, product_id: UUID | str) -> dict:
        return await self._call("DELETE", f"/cart/items/{product_id}", user_id=user_id)

    async def place_order(
        self, user_id: int, *, name: str, phone: str, idempotency_key: str
    ) -> dict:
        return await self._call(
            "POST",
            "/orders",
            user_id=user_id,
            headers={"Idempotency-Key": idempotency_key},
            json={"customer_name": name, "phone": phone, "address": ""},
        )

    async def fetch_image(self, public_url: str) -> bytes:
        """Картинка берётся в память и уходит в Telegram как байты — на диск не пишем."""
        url = public_url.replace(self._public, self._internal, 1)
        resp = await self._http.get(url)
        resp.raise_for_status()
        return resp.content

    async def aclose(self) -> None:
        await self._http.aclose()
