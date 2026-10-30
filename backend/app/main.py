"""Composition root: единственное место, где слои соединяются друг с другом."""

import socket
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import text

from app.application.cart import CartService
from app.application.catalog import CatalogService
from app.application.orders import OrderService
from app.config import get_settings
from app.infrastructure.db import create_engine, create_session_factory
from app.infrastructure.storage import create_storage
from app.infrastructure.uow import SqlUnitOfWork
from app.presentation.api import admin_router, router
from app.presentation.deps import Services
from app.presentation.errors import install_error_handlers

INSTANCE = socket.gethostname()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = create_engine(settings.database_url, settings.db_pool_size)
    session_factory = create_session_factory(engine)
    storage = create_storage(settings)

    def uow_factory() -> SqlUnitOfWork:
        return SqlUnitOfWork(session_factory)

    app.state.engine = engine
    app.state.services = Services(
        catalog=CatalogService(uow_factory, storage),
        cart=CartService(uow_factory),
        orders=OrderService(uow_factory),
        storage=storage,
    )
    yield
    await engine.dispose()


app = FastAPI(title="Shop API", version="1.0.0", lifespan=lifespan)
install_error_handlers(app)
app.include_router(router)
app.include_router(admin_router)


@app.middleware("http")
async def add_instance_header(request: Request, call_next):
    # Чтобы при 2+ репликах было видно, какая из них ответила.
    response = await call_next(request)
    response.headers["X-Served-By"] = INSTANCE
    return response


@app.get("/healthz", tags=["ops"])
async def healthz():
    """Liveness: процесс жив."""
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def readyz(request: Request):
    """Readiness: есть связь с БД."""
    async with request.app.state.engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ready"}
