from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.repositories import (
    SqlCartRepository,
    SqlOrderRepository,
    SqlProductRepository,
)


class SqlUnitOfWork:
    """Одна транзакция БД на один use case. Без commit() всё откатывается."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def __aenter__(self) -> "SqlUnitOfWork":
        self._session = self._factory()
        self.products = SqlProductRepository(self._session)
        self.carts = SqlCartRepository(self._session)
        self.orders = SqlOrderRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()  # незакоммиченное откатывается, соединение возвращается в пул

    async def commit(self) -> None:
        await self._session.commit()
