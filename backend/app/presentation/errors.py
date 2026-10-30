from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain import errors as e

_STATUS: dict[type[e.DomainError], int] = {
    e.ProductNotFound: 404,
    e.OrderNotFound: 404,
    e.OutOfStock: 409,
    e.EmptyCart: 409,
    e.DuplicateOrder: 409,
    e.InvalidQuantity: 422,
    e.UnsupportedImageType: 422,
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(e.DomainError)
    async def handle_domain_error(_: Request, exc: e.DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=_STATUS.get(type(exc), 400), content={"detail": str(exc)}
        )
